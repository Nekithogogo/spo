"""Наблюдаемость (ПР №14): идентификатор запроса, журнал, метрики, health при отказе БД."""
import json
import logging

from app import create_app
from app.observability import JsonFormatter


def test_request_id_generated_and_propagated(anon):
    assert len(anon.get("/api/health").headers["X-Request-ID"]) == 16
    r = anon.get("/api/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"
    r = anon.get("/api/health", headers={"X-Request-ID": "<script>"})   # мусор не попадает в журнал
    assert r.headers["X-Request-ID"] != "<script>"


def test_metrics_exposed(client, anon):
    client.get("/api/projects")
    client.get("/api/projects/999")
    text = anon.get("/api/metrics").get_data(as_text=True)
    assert 'studio_http_requests_total{method="GET",route="/api/projects/<int:project_id>",status="404"}' in text
    assert "studio_http_request_duration_seconds_bucket" in text
    assert 'studio_projects{status="shooting"} 1.0' in text
    assert "studio_db_up 1.0" in text
    assert 'studio_app_info{schema="0004",version="2.0.0"} 1.0' in text


def test_metrics_token(app, anon):
    app.config["METRICS_TOKEN"] = "m-secret"
    assert anon.get("/api/metrics").status_code == 403
    assert anon.get("/api/metrics", headers={"Authorization": "Bearer m-secret"}).status_code == 200


def test_health_reports_database_failure():
    app = create_app({"TESTING": True, "DATABASE_URL": "postgresql://nobody@127.0.0.1:1/none"})
    r = app.test_client().get("/api/health")
    assert r.status_code == 503
    body = r.get_json()
    assert body["status"] == "fail" and body["db"] == "unavailable" and body["version"] == "2.0.0"
    assert app.test_client().get("/api/metrics").status_code == 200   # метрики доступны и без БД


def test_json_log_line(app):
    record = logging.LogRecord("studio.access", logging.INFO, __file__, 1, "request", None, None)
    record.fields = {"method": "GET", "status": 200, "ms": 3.2, "user_id": None}
    with app.test_request_context():
        line = json.loads(JsonFormatter().format(record))
    assert line["level"] == "INFO" and line["status"] == 200 and "user_id" not in line
