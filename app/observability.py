"""Наблюдаемость (ПР №14): журнал запросов в JSON, метрики Prometheus, расширенный health-check.

Каждый запрос получает X-Request-ID (берётся из заголовка прокси или генерируется), который
попадает в ответ и во все строки журнала. Метрики при запуске под gunicorn собираются со всех
рабочих процессов через каталог PROMETHEUS_MULTIPROC_DIR.
"""
import json
import logging
import os
import re
import time
import uuid

import psycopg2
from flask import current_app, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client import REGISTRY, multiprocess
from prometheus_client.core import GaugeMetricFamily

from .db import query

access_log = logging.getLogger("studio.access")
STARTED_AT = time.time()

REQUESTS = Counter("studio_http_requests_total", "HTTP-запросы", ["method", "route", "status"])
LATENCY = Histogram(
    "studio_http_request_duration_seconds", "Время обработки запроса", ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
LOGINS = Counter("studio_login_total", "Попытки входа", ["result"])

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class JsonFormatter(logging.Formatter):
    """Одна строка JSON на событие: удобно искать и разбирать (docker logs | jq)."""

    def format(self, record):
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)) + f".{int(record.msecs):03d}",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        try:
            entry.setdefault("request_id", g.get("request_id"))
        except RuntimeError:  # вне контекста запроса
            pass
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps({k: v for k, v in entry.items() if v is not None}, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Читаемый формат для разработки: поля запроса дописываются как ключ=значение."""

    def format(self, record):
        line = super().format(record)
        fields = getattr(record, "fields", None)
        return line + (" " + " ".join(f"{k}={v}" for k, v in fields.items() if v is not None) if fields else "")


def configure_logging(level, fmt):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if fmt == "json" else
                         TextFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def _before():
    g.started = time.perf_counter()
    rid = request.headers.get("X-Request-ID", "")
    g.request_id = rid if _REQUEST_ID_RE.match(rid) else uuid.uuid4().hex[:16]


def _after(response):
    elapsed = time.perf_counter() - g.get("started", time.perf_counter())
    route = request.url_rule.rule if request.url_rule else "unmatched"
    if not route.startswith("/static"):
        REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        LATENCY.labels(request.method, route).observe(elapsed)
        if request.endpoint == "api.login" and request.method == "POST":
            LOGINS.labels("success" if response.status_code == 200 else "fail").inc()
    response.headers["X-Request-ID"] = g.get("request_id", "")
    ms = round(elapsed * 1000, 1)
    user = g.get("user")
    fields = {
        "method": request.method, "path": request.path, "status": response.status_code, "ms": ms,
        "ip": request.remote_addr, "user_id": user["id"] if user else None,
    }
    slow = ms > current_app.config["SLOW_REQUEST_MS"]
    # health и metrics опрашиваются каждые 15 с: в журнал попадают только их сбои
    if request.path not in ("/api/health", "/api/metrics") or response.status_code != 200 or slow:
        access_log.log(logging.WARNING if slow or response.status_code >= 500 else logging.INFO,
                       "slow request" if slow else "request", extra={"fields": fields})
    return response


def init_app(app):
    app.before_request(_before)
    app.after_request(_after)


def health():
    """200 — приложение и БД работают; 503 — БД недоступна (балансировщик/мониторинг выведут экземпляр)."""
    body = {
        "status": "ok",
        "version": current_app.config["VERSION"],
        "uptime_s": int(time.time() - STARTED_AT),
    }
    started = time.perf_counter()
    try:
        row = query("SELECT max(version) AS schema FROM schema_migrations", one=True)
        body.update(db="ok", schema=row["schema"], db_ms=round((time.perf_counter() - started) * 1000, 1))
        return jsonify(body)
    except psycopg2.Error as e:
        logging.getLogger("studio.health").error("health: database unavailable: %s", str(e).strip())
        body.update(status="fail", db="unavailable")
        return jsonify(body), 503


class BusinessCollector:
    """Показатели предметной области считаются из БД в момент опроса Prometheus."""

    def describe(self):  # без описания реестр вызвал бы collect() (и запросы к БД) уже при регистрации
        return []

    def collect(self):
        up = GaugeMetricFamily("studio_db_up", "БД доступна (1) или нет (0)")
        info = GaugeMetricFamily("studio_app_info", "Версия приложения", labels=["version", "schema"])
        projects = GaugeMetricFamily("studio_projects", "Проекты по статусам", labels=["status"])
        overdue = GaugeMetricFamily("studio_tasks_overdue", "Просроченные незакрытые задачи")
        uptime = GaugeMetricFamily("studio_process_uptime_seconds", "Время работы процесса")
        uptime.add_metric([], time.time() - STARTED_AT)
        try:
            for r in query("SELECT status, count(*) AS n FROM projects GROUP BY status"):
                projects.add_metric([r["status"]], r["n"])
            overdue.add_metric([], query(
                "SELECT count(*) AS n FROM tasks WHERE status <> 'done' AND due_date < current_date", one=True)["n"])
            schema = query("SELECT max(version) AS v FROM schema_migrations", one=True)["v"]
            up.add_metric([], 1)
        except psycopg2.Error:
            schema = "unknown"
            up.add_metric([], 0)
        info.add_metric([current_app.config["VERSION"], schema or "none"], 1)
        yield from (up, info, projects, overdue, uptime)


def metrics_response():
    token = current_app.config.get("METRICS_TOKEN")
    if token and request.headers.get("Authorization") != f"Bearer {token}":
        return jsonify({"error": "Доступ к метрикам запрещён"}), 403
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = REGISTRY
    business = CollectorRegistry()
    business.register(BusinessCollector())
    payload = generate_latest(registry) + generate_latest(business)
    return payload, 200, {"Content-Type": CONTENT_TYPE_LATEST}
