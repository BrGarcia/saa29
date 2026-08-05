import os

# Bind - PORT is overridable by the host; defaults to 8000
port = os.getenv("PORT", "8000")
bind = f"0.0.0.0:{port}"

# Workers - kept low for SQLite stability and small-VPS memory limits.
# The workload is I/O-bound, so 2 is adequate even on a single vCPU; raising it
# there only creates contention. Override via GUNICORN_WORKERS on larger hosts.
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
worker_class = "uvicorn.workers.UvicornWorker"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Security
keepalive = 5
timeout = 30
max_requests = 1000
max_requests_jitter = 50
