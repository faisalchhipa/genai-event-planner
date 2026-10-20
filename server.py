"""
Standard library HTTP server for Event Planning Assistant.
- Endpoint: POST /api/plan
- Whitelisted static file serving (GET /, /index.html, /static/*)
- Security:
  * Strict Content-Length body size limits (max 64KB)
  * Sliding-window rate limiting per client IP (reads X-Forwarded-For for Cloud Run)
  * Hardened security headers (CSP, HSTS, X-Content-Type-Options, X-Frame-Options)
  * Whitelisted static routes (prevent directory traversal)
  * Zero stack trace leakage (clean JSON error responses)
"""

from collections import defaultdict, deque
from datetime import date
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

from planner.ai import generate_personalized_ideas
from planner.logic import generate_plan, validate_input

# Limits and Configuration
MAX_BODY_SIZE = 64 * 1024  # 64 KB
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30  # 30 requests per minute per IP

# Directory setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Whitelisted static files: mapping from URL path to (relative file path, MIME type)
WHITELISTED_STATIC_FILES: Dict[str, Tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/static/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/static/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/favicon.ico": ("favicon.ico", "image/x-icon"),
}

# In-memory rate limiter: client_ip -> deque of request timestamps
_RATE_LIMITER_RECORDS: Dict[str, deque] = defaultdict(deque)
_LAST_CLEANUP_TIME = 0.0


def is_rate_limited(client_ip: str, now: Optional[float] = None) -> bool:
    """
    Sliding window rate limiter per client IP.
    Returns True if request should be blocked.
    """
    global _LAST_CLEANUP_TIME
    current_time = now if now is not None else time.time()

    # Periodic cleanup of expired records every 5 minutes
    if current_time - _LAST_CLEANUP_TIME > 300:
        stale_threshold = current_time - RATE_LIMIT_WINDOW_SECONDS
        expired_ips = [ip for ip, timestamps in _RATE_LIMITER_RECORDS.items() if not timestamps or timestamps[-1] < stale_threshold]
        for ip in expired_ips:
            del _RATE_LIMITER_RECORDS[ip]
        _LAST_CLEANUP_TIME = current_time

    history = _RATE_LIMITER_RECORDS[client_ip]
    cutoff = current_time - RATE_LIMIT_WINDOW_SECONDS

    # Remove timestamps older than current window
    while history and history[0] < cutoff:
        history.popleft()

    if len(history) >= RATE_LIMIT_MAX_REQUESTS:
        return True

    history.append(current_time)
    return False


def clear_rate_limits() -> None:
    """Reset rate limiting store (useful for testing)."""
    _RATE_LIMITER_RECORDS.clear()


class EventPlannerRequestHandler(BaseHTTPRequestHandler):
    """
    Hardened HTTP request handler for the Event Planner Assistant.
    """
    server_version = "EventPlannerServer/1.0"
    sys_version = ""  # Hide Python version in Server header

    def send_security_headers(self, content_type: str = "text/html; charset=utf-8") -> None:
        """Apply strict security and privacy headers to all responses."""
        self.send_header("Content-Type", content_type)
        # Content Security Policy: strict, textContent only, no eval or external scripts
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        self.send_header("Content-Security-Policy", csp)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        self.send_header("X-XSS-Protection", "1; mode=block")

    def get_client_ip(self) -> str:
        """
        Extract client IP for rate limiting.
        Reads X-Forwarded-For header if running behind reverse proxy (e.g., Google Cloud Run).
        Falls back to direct socket client address.
        """
        x_forwarded_for = self.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            # First IP in comma-separated chain is the client IP
            first_ip = x_forwarded_for.split(",")[0].strip()
            if first_ip:
                return first_ip
        if self.client_address and len(self.client_address) > 0:
            return str(self.client_address[0])
        return "127.0.0.1"

    def respond_json(self, status_code: int, data: Dict[str, Any]) -> None:
        """Send a JSON response without leaking internals."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_security_headers(content_type="application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_error(self, status_code: int, message: str) -> None:
        """Send a clean, safe JSON error response."""
        self.respond_json(status_code, {"success": False, "error": message})

    def do_HEAD(self) -> None:
        """Handle HEAD requests."""
        if self.path in WHITELISTED_STATIC_FILES:
            rel_path, mime_type = WHITELISTED_STATIC_FILES[self.path]
            abs_path = os.path.join(STATIC_DIR, rel_path)
            if os.path.isfile(abs_path):
                self.send_response(HTTPStatus.OK)
                self.send_security_headers(content_type=mime_type)
                self.send_header("Content-Length", str(os.path.getsize(abs_path)))
                self.end_headers()
                return
        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_GET(self) -> None:
        """
        Handle GET requests with whitelisted static routing.
        Any unknown path or directory traversal is safely rejected with 404.
        """
        # Normalize and remove query string
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path == "":
            clean_path = "/"

        # Whitelist verification
        if clean_path not in WHITELISTED_STATIC_FILES:
            self.respond_error(HTTPStatus.NOT_FOUND, "The requested resource was not found.")
            return

        rel_path, mime_type = WHITELISTED_STATIC_FILES[clean_path]
        abs_path = os.path.realpath(os.path.join(STATIC_DIR, rel_path))

        # Secondary path traversal defense: ensure file is inside STATIC_DIR
        real_static_dir = os.path.realpath(STATIC_DIR)
        if not abs_path.startswith(real_static_dir):
            self.respond_error(HTTPStatus.FORBIDDEN, "Access denied.")
            return

        if not os.path.isfile(abs_path):
            self.respond_error(HTTPStatus.NOT_FOUND, "Resource not found.")
            return

        try:
            with open(abs_path, "rb") as f:
                content = f.read()
            self.send_response(HTTPStatus.OK)
            self.send_security_headers(content_type=mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self.respond_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Failed to read requested resource.")

    def do_POST(self) -> None:
        """
        Handle POST requests.
        Currently handles /api/plan with body size limits, rate limits, and safe error handling.
        """
        clean_path = self.path.split("?")[0]
        if clean_path != "/api/plan":
            self.respond_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")
            return

        # 1. Rate limiting
        client_ip = self.get_client_ip()
        if is_rate_limited(client_ip):
            self.send_response(HTTPStatus.TOO_MANY_REQUESTS)
            self.send_security_headers(content_type="application/json; charset=utf-8")
            self.send_header("Retry-After", str(RATE_LIMIT_WINDOW_SECONDS))
            body = json.dumps({
                "success": False,
                "error": "Rate limit exceeded. Please wait a moment before trying again."
            }).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # 2. Body size check
        content_length_header = self.headers.get("Content-Length")
        if not content_length_header:
            self.respond_error(HTTPStatus.LENGTH_REQUIRED, "Missing Content-Length header.")
            return

        try:
            content_length = int(content_length_header)
        except ValueError:
            self.respond_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length header.")
            return

        if content_length > MAX_BODY_SIZE:
            # Drain residual input to prevent socket RST on client
            try:
                _ = self.rfile.read(min(content_length, 128 * 1024))
            except Exception:
                pass
            self.close_connection = True
            self.send_response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            self.send_security_headers(content_type="application/json; charset=utf-8")
            self.send_header("Connection", "close")
            body = json.dumps({
                "success": False,
                "error": f"Payload too large. Maximum allowed size is {MAX_BODY_SIZE // 1024} KB.",
            }).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # 3. Read payload
        try:
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.respond_error(HTTPStatus.BAD_REQUEST, "Invalid JSON payload.")
            return
        except Exception:
            self.respond_error(HTTPStatus.BAD_REQUEST, "Error reading request body.")
            return

        if not isinstance(payload, dict):
            self.respond_error(HTTPStatus.BAD_REQUEST, "Request body must be a JSON object.")
            return

        # 4. Process plan and AI ideas safely
        try:
            event_type = payload.get("event_type", "")
            guests = payload.get("guests")
            budget = payload.get("budget")
            event_date = payload.get("event_date", "")
            preferences = payload.get("preferences", "")
            location_hint = payload.get("location_hint", "India")

            # Deterministic plan generation
            plan_data = generate_plan(
                event_type=event_type,
                guests=guests,
                budget=budget,
                event_date=event_date,
                preferences=preferences,
                location_hint=location_hint,
            )

            # Generate personalized ideas (Gemini or rule-based fallback)
            ai_result = generate_personalized_ideas(
                event_type=plan_data["inputs"]["event_type"],
                tier=plan_data["budget_plan"]["tier"],
                guests=plan_data["inputs"]["guests"],
                budget_inr=plan_data["budget_plan"]["total_budget_inr"],
                preferences=plan_data["inputs"]["preferences"],
            )

            response_data = {
                "success": True,
                "plan": plan_data,
                "ideas": ai_result.get("ideas", []),
                "ideas_meta": {
                    "source": ai_result.get("source"),
                    "cached": ai_result.get("cached", False),
                    "reason": ai_result.get("reason"),
                },
            }

            self.respond_json(HTTPStatus.OK, response_data)

        except ValueError as val_err:
            # Client validation error - safe to return message
            self.respond_error(HTTPStatus.BAD_REQUEST, str(val_err))
        except Exception:
            # Unexpected error - generic message, NO stack trace leaked
            self.respond_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "An unexpected error occurred while generating your plan. Please verify your inputs.",
            )


def run_server(host: str = "0.0.0.0", port: Optional[int] = None) -> None:
    """Run the HTTP server."""
    if port is None:
        port = int(os.environ.get("PORT", "8080"))

    server_address = (host, port)
    httpd = HTTPServer(server_address, EventPlannerRequestHandler)
    print(f"Event Planner Assistant running on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
