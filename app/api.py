"""REST-маршруты MVP. Логика и валидация вынесены в services."""
from flask import Blueprint, jsonify, request

from . import services
from .db import query
from .errors import ValidationError

api = Blueprint("api", __name__)


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError({"body": "Ожидается JSON-объект"})
    return data


@api.get("/health")
def health():
    query("SELECT 1")
    return jsonify({"status": "ok", "db": "ok"})


@api.get("/projects")
def projects_list():
    return jsonify(services.list_projects(request.args.get("status")))


@api.post("/projects")
def projects_create():
    project = services.create_project(_json_body())
    return jsonify(project), 201, {"Location": f"/api/projects/{project['id']}"}


@api.get("/projects/<int:project_id>")
def projects_get(project_id):
    return jsonify(services.get_project(project_id))


@api.get("/projects/<int:project_id>/tasks")
def tasks_list(project_id):
    services.get_project(project_id)
    return jsonify(services.list_tasks(project_id))


@api.post("/projects/<int:project_id>/tasks")
def tasks_create(project_id):
    return jsonify(services.create_task(project_id, _json_body())), 201


@api.patch("/tasks/<int:task_id>")
def tasks_update(task_id):
    return jsonify(services.update_task_status(task_id, _json_body()))


@api.get("/clients")
def clients_list():
    return jsonify(services.list_clients())


@api.get("/users")
def users_list():
    return jsonify(services.list_users(request.args.get("role")))


@api.get("/equipment")
def equipment_list():
    return jsonify(services.list_equipment())
