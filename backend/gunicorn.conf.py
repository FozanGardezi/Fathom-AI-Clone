"""Gunicorn configuration. Values come from the environment so the same image
runs unchanged in every deployment."""

import multiprocessing
import os

bind = "0.0.0.0:%s" % os.environ.get("PORT", "8000")

# 2n+1 is the usual starting point for sync workers; capped so a big host does
# not open hundreds of database connections.
workers = int(os.environ.get("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 8)))
threads = int(os.environ.get("WEB_THREADS", 2))
worker_class = "gthread"

timeout = int(os.environ.get("WEB_TIMEOUT", 60))
graceful_timeout = 30
keepalive = 5

# Recycle workers to bound the damage from any slow memory leak.
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
forwarded_allow_ips = "*"
