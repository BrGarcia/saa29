import multiprocessing
import os

# Bind - Railway uses the PORT environment variable
port = os.getenv("PORT", "8000")
bind = f"0.0.0.0:{port}"

# Workers
workers = multiprocessing.cpu_count() * 2 + 1
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
