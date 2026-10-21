"""
Integration tests for the HTTP server (server.py).
Tests static file serving, security headers, POST /api/plan endpoint,
rate limiting per client IP (including X-Forwarded-For), body size limits,
and error handling without stack trace leakage.
"""

from datetime import date, timedelta
from http import HTTPStatus
import json
import os
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request

from server import (
    clear_rate_limits,
    is_rate_limited,
    EventPlannerRequestHandler,
    HTTPServer,
    MAX_BODY_SIZE,
    RATE_LIMIT_MAX_REQUESTS,
)


class TestServerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Bind to ephemeral port on localhost
        cls.server = HTTPServer(("127.0.0.1", 0), EventPlannerRequestHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        # Start server in daemon thread
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        clear_rate_limits()

    def test_get_root_serves_html_with_security_headers(self):
        req = urllib.request.Request(f"{self.base_url}/")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.getcode(), 200)
            headers = dict(resp.headers)
            self.assertIn("text/html", headers.get("Content-Type", ""))
            self.assertIn("Content-Security-Policy", headers)
            self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(headers.get("X-Frame-Options"), "DENY")
            body = resp.read().decode("utf-8")
            self.assertIn("Event Planning Assistant", body)
            self.assertIn("skip-link", body)

    def test_get_static_assets(self):
        # CSS
        with urllib.request.urlopen(f"{self.base_url}/static/style.css") as resp:
            self.assertEqual(resp.getcode(), 200)
            self.assertIn("text/css", resp.headers.get("Content-Type", ""))

        # JS
        with urllib.request.urlopen(f"{self.base_url}/static/app.js") as resp:
            self.assertEqual(resp.getcode(), 200)
            self.assertIn("javascript", resp.headers.get("Content-Type", ""))

    def test_path_traversal_blocked(self):
        # Attempt to access planner/ai.py via traversal
        traversal_urls = [
            f"{self.base_url}/../planner/ai.py",
            f"{self.base_url}/static/../planner/logic.py",
            f"{self.base_url}/unknown_route",
        ]
        for url in traversal_urls:
            try:
                urllib.request.urlopen(url)
                self.fail(f"Should have raised HTTPError for {url}")
            except urllib.error.HTTPError as e:
                self.assertIn(e.code, (404, 403, 400))

    def test_post_plan_valid(self):
        future_date = (date.today() + timedelta(days=90)).isoformat()
        payload = {
            "event_type": "weddings",
            "guests": 250,
            "budget": 750000,
            "event_date": future_date,
            "preferences": "Royal theme with jasmine florals.",
        }

        req = urllib.request.Request(
            f"{self.base_url}/api/plan",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Forwarded-For": "198.51.100.1"},
            method="POST",
        )

        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.getcode(), 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["success"])
            self.assertIn("plan", data)
            self.assertIn("budget_plan", data["plan"])
            self.assertIn("timeline", data["plan"])
            self.assertIn("vendor_checklist", data["plan"])
            self.assertEqual(len(data["ideas"]), 5)

            # 250 guests must trigger mandatory security & parking
            vendors = [v["category"] for v in data["plan"]["vendor_checklist"]]
            self.assertIn("Dedicated Security & Bouncers", vendors)
            self.assertIn("Valet & Parking Marshals", vendors)

    def test_post_plan_validation_error_no_stack_trace(self):
        # Invalid guest count (> 5000)
        payload = {
            "event_type": "weddings",
            "guests": 9999,
            "budget": 500000,
            "event_date": "2027-01-01",
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/plan",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Forwarded-For": "198.51.100.2"},
            method="POST",
        )

        try:
            urllib.request.urlopen(req)
            self.fail("Expected 400 Bad Request")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            err_data = json.loads(e.read().decode("utf-8"))
            self.assertFalse(err_data["success"])
            self.assertIn("error", err_data)
            # Ensure no traceback / file path leakage
            self.assertNotIn("Traceback", err_data["error"])
            self.assertNotIn(".py", err_data["error"])

    def test_body_size_limit_rejected(self):
        # Generate payload larger than 64KB
        huge_payload = {
            "event_type": "weddings",
            "guests": 100,
            "budget": 50000,
            "event_date": "2027-01-01",
            "preferences": "A" * (MAX_BODY_SIZE + 500),
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/plan",
            data=json.dumps(huge_payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Forwarded-For": "198.51.100.3"},
            method="POST",
        )

        try:
            urllib.request.urlopen(req)
            self.fail("Expected 413 Payload Too Large")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 413)

    def test_rate_limiting_per_client_ip(self):
        client_ip = "203.0.113.42"
        future_date = (date.today() + timedelta(days=60)).isoformat()
        payload = json.dumps({
            "event_type": "birthdays",
            "guests": 20,
            "budget": 20000,
            "event_date": future_date,
        }).encode("utf-8")

        # Exceed rate limit
        hit_429 = False
        for i in range(RATE_LIMIT_MAX_REQUESTS + 5):
            req = urllib.request.Request(
                f"{self.base_url}/api/plan",
                data=payload,
                headers={"Content-Type": "application/json", "X-Forwarded-For": f"{client_ip}, 10.0.0.1"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    pass
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    hit_429 = True
                    self.assertIn("Retry-After", e.headers)
                    break

        self.assertTrue(hit_429, "Expected client to be rate limited with HTTP 429")

    def test_forged_first_x_forwarded_for_entry_does_not_change_rate_limit_key(self):
        """
        Verify that get_client_ip uses the rightmost X-Forwarded-For entry added by Cloud Run,
        so forging the first (leftmost) entry cannot bypass rate limiting.
        """
        trusted_client_ip = "198.51.100.88"
        future_date = (date.today() + timedelta(days=60)).isoformat()
        payload = json.dumps({
            "event_type": "birthdays",
            "guests": 15,
            "budget": 15000,
            "event_date": future_date,
        }).encode("utf-8")

        hit_429 = False
        # Each request has a different spoofed leftmost IP, but identical rightmost IP
        for i in range(RATE_LIMIT_MAX_REQUESTS + 5):
            spoofed_first_ip = f"10.0.{i // 256}.{i % 256}"
            req = urllib.request.Request(
                f"{self.base_url}/api/plan",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Forwarded-For": f"{spoofed_first_ip}, {trusted_client_ip}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    pass
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    hit_429 = True
                    break

        self.assertTrue(
            hit_429,
            "Rate limit must be enforced against rightmost IP; forged first entry should not bypass rate limiting."
        )

    def test_frontend_does_not_use_inner_html(self):
        """Verify strict textContent only security constraint in app.js."""
        app_js_path = os.path.join(os.path.dirname(__file__), "..", "static", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertNotIn(".innerHTML", code, "app.js must not use .innerHTML")
        self.assertNotIn(".outerHTML", code, "app.js must not use .outerHTML")
        self.assertNotIn(".insertAdjacentHTML(", code, "app.js must not use .insertAdjacentHTML")


if __name__ == "__main__":
    unittest.main()
