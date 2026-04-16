import multiprocessing
import os

# Bind - Railway uses the PORT environment variable
port = os.getenv("PORT", "8000")
bind = f"0.0.0.0:{port}"

# Workers - Limited for Railway memory constraints and SQLite stability
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
