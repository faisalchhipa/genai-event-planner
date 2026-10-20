# Use lightweight official Python slim image
FROM python:3.10-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Create a non-root system user for least privilege execution
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -M appuser

WORKDIR /app

# Copy application source code (stdlib only - no external dependencies to pip install)
COPY --chown=appuser:appgroup planner/ ./planner/
COPY --chown=appuser:appgroup static/ ./static/
COPY --chown=appuser:appgroup server.py ./

# Drop root privileges
USER appuser

# Cloud Run defaults to port 8080
EXPOSE 8080

# Launch server
CMD ["python", "server.py"]
