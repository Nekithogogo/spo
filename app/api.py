"""REST API версии 2.0. Маршруты только разбирают запрос; логика и валидация — в services.

Все ресурсы, кроме перечисленных в PUBLIC_ENDPOINTS, требуют заголовок Authorization: Bearer <токен>.
Спецификация: /api/openapi.json, интерактивная документация: /api/docs.
"""
from flask import Blueprint, jsonify, request

from . import auth, observability, openapi, services
from .auth import MANAGERS, require_roles
from .errors import ApiError, ValidationError

api = Blueprint("api", __name__)

PUBLIC_ENDPOINTS = {"api.health", "api.login", "api.openapi_json", "api.openapi_yaml", "api.docs", "api.metrics"}


@api.before_request
def authenticate():
    if request.endpoint in PUBLIC_ENDPOINTS or request.method == "OPTIONS":
        return
    auth.load_current_user()


def _json_body():
    if not request.is_json:
        raise ApiError(415, "Ожидается Content-Type: application/json")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError({"body": "Ожидается JSON-объект"})
    return data


# ---------- служебные ----------

@api.get("/health")
def health():
    return observability.health()


@api.get("/metrics")
def metrics():
    return observability.metrics_response()


@api.get("/openapi.json")
def openapi_json():
    return jsonify(openapi.spec())


@api.get("/openapi.yaml")
def openapi_yaml():
    return openapi.spec_yaml(), 200, {"Content-Type": "application/yaml; charset=utf-8"}


@api.get("/docs")
def docs():
    return openapi.swagger_page()


# ---------- аутентификация ----------

@api.post("/auth/login")
def login():
    return jsonify(auth.login(_json_body()))


@api.post("/auth/logout")
def logout():
    auth.logout(auth.current_user())
    return "", 204


@api.get("/auth/me")
def me():
    return jsonify(auth.public_user(auth.current_user()))


# ---------- проекты ----------

@api.get("/projects")
def projects_list():
    items, total = services.list_projects(request.args)
    return jsonify(items), 200, {"X-Total-Count": str(total)}


@api.post("/projects")
@require_roles(*MANAGERS)
def projects_create():
    project = services.create_project(_json_body())
    return jsonify(project), 201, {"Location": f"/api/projects/{project['id']}",
                                   "ETag": services.project_etag(project)}


@api.get("/projects/<int:project_id>")
def projects_get(project_id):
    project = services.get_project(project_id)
    return jsonify(project), 200, {"ETag": services.project_etag(project)}


@api.patch("/projects/<int:project_id>")
@require_roles(*MANAGERS)
def projects_update(project_id):
    project = services.update_project(project_id, _json_body(), request.headers.get("If-Match"))
    return jsonify(project), 200, {"ETag": services.project_etag(project)}


@api.delete("/projects/<int:project_id>")
@require_roles("admin")
def projects_delete(project_id):
    services.delete_project(project_id)
    return "", 204


@api.get("/projects/<int:project_id>/history")
def projects_history(project_id):
    return jsonify(services.project_history(project_id))


# ---------- съёмочная группа ----------

@api.get("/projects/<int:project_id>/members")
def members_list(project_id):
    services.get_project(project_id)
    return jsonify(services.list_members(project_id))


@api.put("/projects/<int:project_id>/members/<int:user_id>")
@require_roles(*MANAGERS)
def members_put(project_id, user_id):
    member, created = services.put_member(project_id, user_id, _json_body())
    return jsonify(member), 201 if created else 200


@api.delete("/projects/<int:project_id>/members/<int:user_id>")
@require_roles(*MANAGERS)
def members_delete(project_id, user_id):
    services.delete_member(project_id, user_id)
    return "", 204


# ---------- задачи ----------

@api.get("/projects/<int:project_id>/tasks")
def tasks_list(project_id):
    services.get_project(project_id)
    return jsonify(services.list_tasks(project_id))


@api.post("/projects/<int:project_id>/tasks")
def tasks_create(project_id):
    task = services.create_task(project_id, _json_body())
    return jsonify(task), 201, {"Location": f"/api/tasks/{task['id']}"}


@api.get("/tasks/<int:task_id>")
def tasks_get(task_id):
    return jsonify(services.get_task(task_id))


@api.patch("/tasks/<int:task_id>")
def tasks_update(task_id):
    return jsonify(services.update_task(task_id, _json_body()))


@api.delete("/tasks/<int:task_id>")
def tasks_delete(task_id):
    services.delete_task(task_id)
    return "", 204


# ---------- бронирование оборудования ----------

@api.get("/projects/<int:project_id>/bookings")
def bookings_list(project_id):
    return jsonify(services.list_project_bookings(project_id))


@api.post("/projects/<int:project_id>/bookings")
@require_roles(*MANAGERS)
def bookings_create(project_id):
    booking = services.create_booking(project_id, _json_body())
    return jsonify(booking), 201


@api.delete("/bookings/<int:booking_id>")
@require_roles(*MANAGERS)
def bookings_delete(booking_id):
    services.delete_booking(booking_id)
    return "", 204


@api.get("/equipment/<int:equipment_id>/bookings")
def equipment_bookings(equipment_id):
    return jsonify(services.list_equipment_bookings(equipment_id, request.args))


# ---------- справочники и отчёты ----------

@api.get("/clients")
def clients_list():
    return jsonify(services.list_clients())


@api.get("/users")
def users_list():
    return jsonify(services.list_users(request.args.get("role")))


@api.post("/users")
@require_roles("admin")
def users_create():
    user = services.create_user(_json_body())
    return jsonify(user), 201


@api.get("/equipment")
def equipment_list():
    return jsonify(services.list_equipment())


@api.get("/reports/workload")
@require_roles(*MANAGERS)
def reports_workload():
    return jsonify(services.workload_report())
