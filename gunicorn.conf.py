# Настройки gunicorn для тестового и рабочего окружения.
import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", 2))
threads = 2
timeout = 30
graceful_timeout = 20       # при перезапуске текущие запросы успевают завершиться
max_requests = 2000         # плановый перезапуск рабочих процессов против утечек памяти
max_requests_jitter = 200
forwarded_allow_ips = "*"   # приложение доступно только из сети compose, перед ним nginx
accesslog = None            # журнал запросов пишет само приложение (JSON, с request_id)
errorlog = "-"
loglevel = "info"


def on_starting(server):
    # каталог метрик общий для всех рабочих процессов; очищается при старте мастера
    path = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if path:
        os.makedirs(path, exist_ok=True)
        for name in os.listdir(path):
            os.remove(os.path.join(path, name))


def child_exit(server, worker):
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess
        multiprocess.mark_process_dead(worker.pid)
