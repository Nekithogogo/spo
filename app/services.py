"""Бизнес-операции над проектами и задачами: валидация входных данных и работа с БД."""
from datetime import date

from .db import execute, query
from .errors import NotFound, ValidationError

PROJECT_STATUSES = ("new", "preproduction", "shooting", "postproduction", "review", "done", "cancelled")
PROJECT_TYPES = ("commercial", "music_video", "corporate", "event", "documentary", "other")
TASK_STAGES = ("preproduction", "shooting", "postproduction", "review")
TASK_STATUSES = ("todo", "in_progress", "done")

PROJECT_LIST_SQL = """
    SELECT p.id, p.title, p.project_type, p.status, p.budget, p.start_date, p.deadline, p.description,
           c.id AS client_id, c.name AS client_name,
           u.id AS producer_id, u.full_name AS producer_name,
           count(t.id) AS tasks_total,
           count(t.id) FILTER (WHERE t.status = 'done') AS tasks_done
    FROM projects p
    JOIN clients c ON c.id = p.client_id
    LEFT JOIN users u ON u.id = p.producer_id
    LEFT JOIN tasks t ON t.project_id = p.id
"""


def _parse_date(value, field, errors):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        errors[field] = "Дата в формате ГГГГ-ММ-ДД"
        return None


def _parse_int(value, field, errors):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        errors[field] = "Ожидается целое число"
        return None


def _serialize_project(row):
    row = dict(row)
    row["budget"] = float(row["budget"])
    for key in ("start_date", "deadline"):
        if row.get(key):
            row[key] = row[key].isoformat()
    return row


def _serialize_task(row):
    row = dict(row)
    if row.get("due_date"):
        row["due_date"] = row["due_date"].isoformat()
    row.pop("created_at", None)
    return row


def list_projects(status=None):
    if status and status not in PROJECT_STATUSES:
        raise ValidationError({"status": "Неизвестный статус"})
    sql = PROJECT_LIST_SQL
    params = []
    if status:
        sql += " WHERE p.status = %s"
        params.append(status)
    sql += " GROUP BY p.id, c.id, u.id ORDER BY p.deadline NULLS LAST, p.id"
    return [_serialize_project(r) for r in query(sql, params)]


def get_project(project_id):
    row = query(PROJECT_LIST_SQL + " WHERE p.id = %s GROUP BY p.id, c.id, u.id", (project_id,), one=True)
    if row is None:
        raise NotFound("Проект не найден")
    project = _serialize_project(row)
    project["tasks"] = list_tasks(project_id)
    project["members"] = query(
        """SELECT u.id, u.full_name, m.role_in_project
           FROM project_members m JOIN users u ON u.id = m.user_id
           WHERE m.project_id = %s ORDER BY u.full_name""",
        (project_id,),
    )
    return project


def validate_project(data):
    errors = {}
    title = (data.get("title") or "").strip()
    if not title:
        errors["title"] = "Укажите название проекта"
    elif len(title) > 200:
        errors["title"] = "Не более 200 символов"

    client_id = _parse_int(data.get("client_id"), "client_id", errors)
    if client_id is None and "client_id" not in errors:
        errors["client_id"] = "Выберите заказчика"
    producer_id = _parse_int(data.get("producer_id"), "producer_id", errors)

    project_type = data.get("project_type") or "commercial"
    if project_type not in PROJECT_TYPES:
        errors["project_type"] = "Недопустимый тип проекта"

    budget = data.get("budget", 0) or 0
    try:
        budget = float(budget)
        if budget < 0:
            errors["budget"] = "Бюджет не может быть отрицательным"
    except (TypeError, ValueError):
        errors["budget"] = "Ожидается число"

    start_date = _parse_date(data.get("start_date"), "start_date", errors)
    deadline = _parse_date(data.get("deadline"), "deadline", errors)
    if start_date and deadline and deadline < start_date:
        errors["deadline"] = "Дедлайн не может быть раньше даты начала"

    if client_id and "client_id" not in errors and not query("SELECT 1 FROM clients WHERE id = %s", (client_id,)):
        errors["client_id"] = "Заказчик не найден"
    if producer_id and "producer_id" not in errors and not query(
        "SELECT 1 FROM users WHERE id = %s AND role IN ('producer', 'admin') AND is_active", (producer_id,)
    ):
        errors["producer_id"] = "Продюсер не найден"

    if errors:
        raise ValidationError(errors)
    return {
        "title": title,
        "client_id": client_id,
        "producer_id": producer_id,
        "project_type": project_type,
        "budget": budget,
        "start_date": start_date,
        "deadline": deadline,
        "description": (data.get("description") or "").strip() or None,
    }


def create_project(data):
    p = validate_project(data)
    row = execute(
        """INSERT INTO projects (title, client_id, producer_id, project_type, budget, start_date, deadline, description)
           VALUES (%(title)s, %(client_id)s, %(producer_id)s, %(project_type)s, %(budget)s,
                   %(start_date)s, %(deadline)s, %(description)s)
           RETURNING id""",
        p,
    )
    return get_project(row["id"])


def list_tasks(project_id):
    rows = query(
        """SELECT t.id, t.project_id, t.title, t.stage, t.status, t.due_date,
                  t.assignee_id, u.full_name AS assignee_name, t.created_at
           FROM tasks t LEFT JOIN users u ON u.id = t.assignee_id
           WHERE t.project_id = %s
           ORDER BY array_position(ARRAY['preproduction','shooting','postproduction','review']::varchar[], t.stage),
                    t.due_date NULLS LAST, t.id""",
        (project_id,),
    )
    return [_serialize_task(r) for r in rows]


def create_task(project_id, data):
    if not query("SELECT 1 FROM projects WHERE id = %s", (project_id,)):
        raise NotFound("Проект не найден")
    errors = {}
    title = (data.get("title") or "").strip()
    if not title:
        errors["title"] = "Укажите название задачи"
    elif len(title) > 200:
        errors["title"] = "Не более 200 символов"
    stage = data.get("stage") or "preproduction"
    if stage not in TASK_STAGES:
        errors["stage"] = "Недопустимый этап"
    assignee_id = _parse_int(data.get("assignee_id"), "assignee_id", errors)
    due_date = _parse_date(data.get("due_date"), "due_date", errors)
    if assignee_id and "assignee_id" not in errors and not query(
        "SELECT 1 FROM users WHERE id = %s AND is_active", (assignee_id,)
    ):
        errors["assignee_id"] = "Исполнитель не найден"
    if errors:
        raise ValidationError(errors)

    row = execute(
        """INSERT INTO tasks (project_id, title, stage, assignee_id, due_date)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (project_id, title, stage, assignee_id, due_date),
    )
    return get_task(row["id"])


def get_task(task_id):
    row = query(
        """SELECT t.id, t.project_id, t.title, t.stage, t.status, t.due_date,
                  t.assignee_id, u.full_name AS assignee_name
           FROM tasks t LEFT JOIN users u ON u.id = t.assignee_id WHERE t.id = %s""",
        (task_id,),
        one=True,
    )
    if row is None:
        raise NotFound("Задача не найдена")
    return _serialize_task(row)


def update_task_status(task_id, data):
    status = data.get("status")
    if status not in TASK_STATUSES:
        raise ValidationError({"status": "Допустимые значения: " + ", ".join(TASK_STATUSES)})
    row = execute("UPDATE tasks SET status = %s WHERE id = %s RETURNING id", (status, task_id))
    if row is None:
        raise NotFound("Задача не найдена")
    return get_task(task_id)


def list_clients():
    return query("SELECT id, name, contact_person FROM clients ORDER BY name")


def list_users(role=None):
    sql = "SELECT id, full_name, role FROM users WHERE is_active"
    params = []
    if role:
        sql += " AND role = %s"
        params.append(role)
    return query(sql + " ORDER BY full_name", params)


def list_equipment():
    return query("SELECT id, name, category, inventory_number, is_available FROM equipment ORDER BY inventory_number")
