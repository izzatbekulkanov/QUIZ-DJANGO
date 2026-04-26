import multiprocessing
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
TMP_DIR = Path("/dev/shm")


def env_int(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


cpu_count = multiprocessing.cpu_count() or 2
default_workers = max(4, cpu_count * 2 + 1)

bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
workers = env_int("GUNICORN_WORKERS", default_workers)
threads = env_int("GUNICORN_THREADS", 8)
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
timeout = env_int("GUNICORN_TIMEOUT", 120)
graceful_timeout = env_int("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = env_int("GUNICORN_KEEPALIVE", 5)
max_requests = env_int("GUNICORN_MAX_REQUESTS", 2000)
max_requests_jitter = env_int("GUNICORN_MAX_REQUESTS_JITTER", 200)
worker_tmp_dir = str(TMP_DIR) if TMP_DIR.exists() else str(BASE_DIR / ".gunicorn-tmp")
accesslog = "-"
errorlog = "-"
capture_output = True
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
proc_name = os.getenv("GUNICORN_PROC_NAME", "quiz-django")
umask = 0o002
preload_app = False
sendfile = True

