"""Бизнес-операции над проектами, задачами, группой и бронями: валидация и работа с БД."""
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import psycopg2
from flask import current_app

from .auth import MANAGERS, current_user, ensure_can_manage
from .db import execute, query, transaction
from .errors import ApiError, NotFound, ValidationError

PROJECT_STATUSES = ("new", "preproduction", "shooting", "postproduction", "review", "done", "cancelled")
PROJECT_TYPES = ("commercial", "music_video", "corporate", "event", "documentary", "other")
TASK_STAGES = ("preproduction", "shooting", "postproduction", "review")
TASK_STATUSES = ("todo", "in_progress", "done")
USER_ROLES = ("admin", "producer", "director", "operator", "editor")
CLOSED_STATUSES = ("done", "cancelled")

# Допустимые переходы проекта по этапам производства (FR-08). Возврат на шаг назад разрешён
# для доработок; «Сдан» — конечный статус, отменённый проект можно вернуть в «Новый».
TRANSITIONS = {
    "new": ("preproduction", "cancelled"),
    "preproduction": ("shooting", "cancelled"),
    "shooting": ("postproduction", "preproduction", "cancelled"),
    "postproduction": ("review", "shooting", "cancelled"),
    "review": ("done", "postproduction", "cancelled"),
    "done": (),
    "cancelled": ("new",),
}

PROJECT_EDITABLE = ("title", "client_id", "producer_id", "project_type", "budget", "start_date", "deadline", "description")

PROJECT_LIST_SQL = """
    SELECT p.id, p.title, p.project_type, p.status, p.budget, p.start_date, p.deadline, p.description,
           p.updated_at,
           c.id AS client_id, c.name AS client_name,
           u.id AS producer_id, u.full_name AS producer_name,
           count(t.id) AS tasks_total,
           count(t.id) FILTER (WHERE t.status = 'done') AS tasks_done
    FROM projects p
    JOIN clients c ON c.id = p.client_id
    LEFT JOIN users u ON u.id = p.producer_id
    LEFT JOIN tasks t ON t.project_id = p.id
"""


def _tz():
    return ZoneInfo(os.environ.get("TZ") or "Europe/Moscow")


def _parse_date(value, field, errors):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        errors[field] = "Дата в формате ГГГГ-ММ-ДД"
        return None


def _parse_datetime(value, field, errors):
    """ISO 8601; время без часового пояса (из поля datetime-local) считается местным временем студии."""
    if value in (None, ""):
        errors[field] = "Укажите дату и время"
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        errors[field] = "Дата и время в формате ГГГГ-ММ-ДДTЧЧ:ММ"
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=_tz())


def _parse_int(value, field, errors):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        errors[field] = "Ожидается целое число"
        return None


def _parse_limit(value, default, maximum, field, errors):
    n = _parse_int(value, field, errors)
    if n is None:
        return default
    if not 0 <= n <= maximum:
        errors[field] = f"Допустимо от 0 до {maximum}"
    return n


def _serialize_project(row):
    row = dict(row)
    row["budget"] = float(row["budget"])
    for key in ("start_date", "deadline"):
        if row.get(key):
            row[key] = row[key].isoformat()
    row["updated_at"] = row["updated_at"].isoformat()
    return row


def _serialize_task(row):
    row = dict(row)
    if row.get("due_date"):
        row["due_date"] = row["due_date"].isoformat()
    row.pop("created_at", None)
    row.pop("updated_at", None)
    return row


def project_etag(project):
    """Версия проекта для оптимистической блокировки (ETag / If-Match)."""
    return '"' + str(int(datetime.fromisoformat(project["updated_at"]).timestamp() * 1_000_000)) + '"'


# ---------- проекты ----------

def list_projects(args):
    errors = {}
    status = args.get("status") or None
    if status and status not in PROJECT_STATUSES:
        errors["status"] = "Неизвестный статус"
    limit = _parse_limit(args.get("limit"), 50, 100, "limit", errors)
    offset = _parse_limit(args.get("offset"), 0, 1_000_000, "offset", errors)
    q = (args.get("q") or "").strip()
    if len(q) > 100:
        errors["q"] = "Не более 100 символов"
    if errors:
        raise ValidationError(errors)

    where, params = [], []
    if status:
        where.append("p.status = %s")
        params.append(status)
    if q:
        where.append("p.title ILIKE %s")
        params.append("%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = query("SELECT count(*) AS n FROM projects p" + where_sql, params, one=True)["n"]
    sql = PROJECT_LIST_SQL + where_sql + " GROUP BY p.id, c.id, u.id ORDER BY p.deadline NULLS LAST, p.id LIMIT %s OFFSET %s"
    items = [_serialize_project(r) for r in query(sql, params + [limit, offset])]
    return items, total


def _project_row(project_id):
    row = query("SELECT id, status, producer_id FROM projects WHERE id = %s", (project_id,), one=True)
    if row is None:
        raise NotFound("Проект не найден")
    return row


def get_project(project_id):
    row = query(PROJECT_LIST_SQL + " WHERE p.id = %s GROUP BY p.id, c.id, u.id", (project_id,), one=True)
    if row is None:
        raise NotFound("Проект не найден")
    project = _serialize_project(row)
    project["tasks"] = list_tasks(project_id)
    project["members"] = list_members(project_id)
    project["allowed_transitions"] = list(TRANSITIONS[project["status"]])
    user = current_user()
    project["can_manage"] = bool(user) and (
        user["role"] == "admin" or (user["role"] == "producer" and project["producer_id"] == user["id"]))
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
        elif budget >= 10_000_000_000:
            errors["budget"] = "Слишком большой бюджет"
    except (TypeError, ValueError):
        errors["budget"] = "Ожидается число"

    start_date = _parse_date(data.get("start_date"), "start_date", errors)
    deadline = _parse_date(data.get("deadline"), "deadline", errors)
    if start_date and deadline and deadline < start_date:
        errors["deadline"] = "Дедлайн не может быть раньше даты начала"

    description = (data.get("description") or "").strip() or None
    if description and len(description) > 5000:
        errors["description"] = "Не более 5000 символов"

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
        "description": description,
    }


def create_project(data):
    user = current_user()
    if user["role"] == "producer" and data.get("producer_id") in (None, ""):
        data = {**data, "producer_id": user["id"]}  # продюсер по умолчанию ведёт свой проект сам
    p = validate_project(data)
    with transaction() as cur:
        cur.execute(
            """INSERT INTO projects (title, client_id, producer_id, project_type, budget, start_date, deadline, description)
               VALUES (%(title)s, %(client_id)s, %(producer_id)s, %(project_type)s, %(budget)s,
                       %(start_date)s, %(deadline)s, %(description)s)
               RETURNING id""",
            p,
        )
        project_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO project_status_history (project_id, old_status, new_status, changed_by) VALUES (%s, NULL, 'new', %s)",
            (project_id, user["id"]),
        )
    return get_project(project_id)


def update_project(project_id, data, if_match=None):
    current = get_project(project_id)
    ensure_can_manage(current)
    if if_match and if_match != project_etag(current):
        raise ApiError(412, "Проект уже изменён другим пользователем. Обновите страницу и повторите")

    unknown = set(data) - set(PROJECT_EDITABLE) - {"status", "status_comment"}
    if unknown:
        raise ValidationError({k: "Поле нельзя изменять" for k in sorted(unknown)})

    merged = {k: current[k] for k in PROJECT_EDITABLE}
    merged.update({k: data[k] for k in PROJECT_EDITABLE if k in data})
    p = validate_project(merged)

    new_status = data.get("status", current["status"])
    comment = (data.get("status_comment") or "").strip()[:500] or None
    if new_status != current["status"]:
        if new_status not in PROJECT_STATUSES:
            raise ValidationError({"status": "Неизвестный статус"})
        if new_status not in TRANSITIONS[current["status"]]:
            raise ApiError(409, "Недопустимый переход статуса", {
                "status": f"Из «{current['status']}» можно перейти только в: "
                          + (", ".join(TRANSITIONS[current["status"]]) or "— (конечный статус)")})
        if new_status == "done" and current["tasks_done"] < current["tasks_total"]:
            open_tasks = current["tasks_total"] - current["tasks_done"]
            raise ApiError(409, "Нельзя сдать проект с незакрытыми задачами",
                           {"status": f"Незакрытых задач: {open_tasks}"})

    with transaction() as cur:
        cur.execute(
            """UPDATE projects SET title = %(title)s, client_id = %(client_id)s, producer_id = %(producer_id)s,
                   project_type = %(project_type)s, budget = %(budget)s, start_date = %(start_date)s,
                   deadline = %(deadline)s, description = %(description)s, status = %(status)s
               WHERE id = %(id)s""",
            {**p, "status": new_status, "id": project_id},
        )
        if new_status != current["status"]:
            cur.execute(
                """INSERT INTO project_status_history (project_id, old_status, new_status, changed_by, comment)
                   VALUES (%s, %s, %s, %s, %s)""",
                (project_id, current["status"], new_status, current_user()["id"], comment),
            )
    return get_project(project_id)


def delete_project(project_id):
    row = execute("DELETE FROM projects WHERE id = %s RETURNING id", (project_id,))
    if row is None:
        raise NotFound("Проект не найден")


def project_history(project_id):
    _project_row(project_id)
    rows = query(
        """SELECT h.id, h.old_status, h.new_status, h.changed_at, h.comment,
                  h.changed_by, u.full_name AS changed_by_name
           FROM project_status_history h LEFT JOIN users u ON u.id = h.changed_by
           WHERE h.project_id = %s ORDER BY h.changed_at DESC, h.id DESC""",
        (project_id,),
    )
    return [{**r, "changed_at": r["changed_at"].isoformat()} for r in rows]


# ---------- съёмочная группа (FR-10) ----------

def list_members(project_id):
    return query(
        """SELECT u.id, u.full_name, u.role, m.role_in_project
           FROM project_members m JOIN users u ON u.id = m.user_id
           WHERE m.project_id = %s ORDER BY u.full_name""",
        (project_id,),
    )


def put_member(project_id, user_id, data):
    ensure_can_manage(_project_row(project_id))
    role_in_project = (data.get("role_in_project") or "").strip()
    errors = {}
    if not role_in_project:
        errors["role_in_project"] = "Укажите роль в проекте"
    elif len(role_in_project) > 50:
        errors["role_in_project"] = "Не более 50 символов"
    if not query("SELECT 1 FROM users WHERE id = %s AND is_active", (user_id,)):
        errors["user_id"] = "Сотрудник не найден"
    if errors:
        raise ValidationError(errors)
    row = execute(
        """INSERT INTO project_members (project_id, user_id, role_in_project) VALUES (%s, %s, %s)
           ON CONFLICT (project_id, user_id) DO UPDATE SET role_in_project = EXCLUDED.role_in_project
           RETURNING (xmax = 0) AS created""",
        (project_id, user_id, role_in_project),
    )
    member = next(m for m in list_members(project_id) if m["id"] == user_id)
    return member, row["created"]


def delete_member(project_id, user_id):
    ensure_can_manage(_project_row(project_id))
    row = execute("DELETE FROM project_members WHERE project_id = %s AND user_id = %s RETURNING user_id",
                  (project_id, user_id))
    if row is None:
        raise NotFound("Сотрудник не входит в группу проекта")


# ---------- бронирование оборудования (FR-09) ----------

BOOKING_SQL = """
    SELECT b.id, b.equipment_id, e.name AS equipment_name, e.inventory_number,
           b.project_id, p.title AS project_title, b.starts_at, b.ends_at
    FROM equipment_bookings b
    JOIN equipment e ON e.id = b.equipment_id
    JOIN projects p ON p.id = b.project_id
"""


def _serialize_booking(row):
    row = dict(row)
    for key in ("starts_at", "ends_at"):
        row[key] = row[key].astimezone(_tz()).isoformat()
    return row


def list_project_bookings(project_id):
    _project_row(project_id)
    rows = query(BOOKING_SQL + " WHERE b.project_id = %s ORDER BY b.starts_at", (project_id,))
    return [_serialize_booking(r) for r in rows]


def list_equipment_bookings(equipment_id, args):
    if not query("SELECT 1 FROM equipment WHERE id = %s", (equipment_id,)):
        raise NotFound("Оборудование не найдено")
    errors = {}
    sql, params = BOOKING_SQL + " WHERE b.equipment_id = %s", [equipment_id]
    if args.get("from"):
        sql += " AND b.ends_at > %s"
        params.append(_parse_datetime(args["from"], "from", errors))
    if args.get("to"):
        sql += " AND b.starts_at < %s"
        params.append(_parse_datetime(args["to"], "to", errors))
    if errors:
        raise ValidationError(errors)
    return [_serialize_booking(r) for r in query(sql + " ORDER BY b.starts_at", params)]


def create_booking(project_id, data):
    project = _project_row(project_id)
    ensure_can_manage(project)
    if project["status"] in CLOSED_STATUSES:
        raise ApiError(409, "Проект закрыт: бронировать оборудование нельзя")
    errors = {}
    equipment_id = _parse_int(data.get("equipment_id"), "equipment_id", errors)
    if equipment_id is None and "equipment_id" not in errors:
        errors["equipment_id"] = "Выберите оборудование"
    starts_at = _parse_datetime(data.get("starts_at"), "starts_at", errors)
    ends_at = _parse_datetime(data.get("ends_at"), "ends_at", errors)
    if starts_at and ends_at and ends_at <= starts_at:
        errors["ends_at"] = "Окончание должно быть позже начала"
    if equipment_id and "equipment_id" not in errors:
        eq = query("SELECT is_available FROM equipment WHERE id = %s", (equipment_id,), one=True)
        if eq is None:
            errors["equipment_id"] = "Оборудование не найдено"
        elif not eq["is_available"]:
            errors["equipment_id"] = "Оборудование выведено из работы"
    if errors:
        raise ValidationError(errors)
    try:
        row = execute(
            "INSERT INTO equipment_bookings (equipment_id, project_id, starts_at, ends_at) VALUES (%s, %s, %s, %s) RETURNING id",
            (equipment_id, project_id, starts_at, ends_at),
        )
    except psycopg2.errors.ExclusionViolation:
        # ограничение EXCLUDE в БД гарантирует отсутствие пересечений даже при одновременных запросах
        conflict = query(
            BOOKING_SQL + " WHERE b.equipment_id = %s AND tstzrange(b.starts_at, b.ends_at) && tstzrange(%s, %s) LIMIT 1",
            (equipment_id, starts_at, ends_at), one=True)
        details = {"equipment_id": "Оборудование уже забронировано на это время"}
        if conflict:
            c = _serialize_booking(conflict)
            details["conflict"] = f"{c['project_title']}: {c['starts_at']} — {c['ends_at']}"
        raise ApiError(409, "Оборудование уже занято в это время", details)
    return _serialize_booking(query(BOOKING_SQL + " WHERE b.id = %s", (row["id"],), one=True))


def delete_booking(booking_id):
    row = query("SELECT project_id FROM equipment_bookings WHERE id = %s", (booking_id,), one=True)
    if row is None:
        raise NotFound("Бронь не найдена")
    ensure_can_manage(_project_row(row["project_id"]))
    execute("DELETE FROM equipment_bookings WHERE id = %s", (booking_id,), returning=False)


# ---------- задачи ----------

TASK_SQL = """
    SELECT t.id, t.project_id, t.title, t.description, t.stage, t.status, t.due_date,
           t.assignee_id, u.full_name AS assignee_name
    FROM tasks t LEFT JOIN users u ON u.id = t.assignee_id
"""


def list_tasks(project_id):
    rows = query(
        TASK_SQL + """ WHERE t.project_id = %s
           ORDER BY array_position(ARRAY['preproduction','shooting','postproduction','review']::varchar[], t.stage),
                    t.due_date NULLS LAST, t.id""",
        (project_id,),
    )
    return [_serialize_task(r) for r in rows]


def _validate_task_fields(data, errors, partial):
    result = {}
    if not partial or "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            errors["title"] = "Укажите название задачи"
        elif len(title) > 200:
            errors["title"] = "Не более 200 символов"
        result["title"] = title
    if not partial or "stage" in data:
        stage = data.get("stage") or "preproduction"
        if stage not in TASK_STAGES:
            errors["stage"] = "Недопустимый этап"
        result["stage"] = stage
    if not partial or "assignee_id" in data:
        assignee_id = _parse_int(data.get("assignee_id"), "assignee_id", errors)
        if assignee_id and "assignee_id" not in errors and not query(
            "SELECT 1 FROM users WHERE id = %s AND is_active", (assignee_id,)
        ):
            errors["assignee_id"] = "Исполнитель не найден"
        result["assignee_id"] = assignee_id
    if not partial or "due_date" in data:
        result["due_date"] = _parse_date(data.get("due_date"), "due_date", errors)
    if not partial or "description" in data:
        description = (data.get("description") or "").strip() or None
        if description and len(description) > 5000:
            errors["description"] = "Не более 5000 символов"
        result["description"] = description
    if partial and "status" in data:
        if data["status"] not in TASK_STATUSES:
            errors["status"] = "Допустимые значения: " + ", ".join(TASK_STATUSES)
        result["status"] = data["status"]
    return result


def create_task(project_id, data):
    project = _project_row(project_id)
    user = current_user()
    if user["role"] not in MANAGERS + ("director",):
        raise ApiError(403, "Задачи ставят продюсер, режиссёр или администратор")
    if project["status"] in CLOSED_STATUSES:
        raise ApiError(409, "Проект закрыт: новые задачи добавлять нельзя")
    errors = {}
    t = _validate_task_fields(data, errors, partial=False)
    if errors:
        raise ValidationError(errors)
    row = execute(
        """INSERT INTO tasks (project_id, title, stage, assignee_id, due_date, description)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (project_id, t["title"], t["stage"], t["assignee_id"], t["due_date"], t["description"]),
    )
    return get_task(row["id"])


def get_task(task_id):
    row = query(TASK_SQL + " WHERE t.id = %s", (task_id,), one=True)
    if row is None:
        raise NotFound("Задача не найдена")
    return _serialize_task(row)


def _can_edit_task(task, project):
    """Полностью задачу меняет администратор или продюсер проекта; исполнитель — только статус."""
    user = current_user()
    if user["role"] == "admin" or (user["role"] == "producer" and project["producer_id"] == user["id"]):
        return "full"
    if task["assignee_id"] == user["id"]:
        return "status"
    if user["role"] in ("producer", "director"):
        return "full" if query("SELECT 1 FROM project_members WHERE project_id = %s AND user_id = %s",
                               (project["id"], user["id"])) else None
    return None


def update_task(task_id, data):
    task = get_task(task_id)
    project = _project_row(task["project_id"])
    if not data:
        raise ValidationError({"body": "Нет полей для изменения"})
    unknown = set(data) - {"title", "stage", "assignee_id", "due_date", "description", "status"}
    if unknown:
        raise ValidationError({k: "Поле нельзя изменять" for k in sorted(unknown)})
    access = _can_edit_task(task, project)
    if access is None or (access == "status" and set(data) != {"status"}):
        raise ApiError(403, "Недостаточно прав для изменения задачи")
    errors = {}
    fields = _validate_task_fields(data, errors, partial=True)
    if errors:
        raise ValidationError(errors)
    sets = ", ".join(f"{k} = %({k})s" for k in fields)
    execute(f"UPDATE tasks SET {sets} WHERE id = %(id)s", {**fields, "id": task_id}, returning=False)
    return get_task(task_id)


def delete_task(task_id):
    task = get_task(task_id)
    project = _project_row(task["project_id"])
    if _can_edit_task(task, project) != "full":
        raise ApiError(403, "Удалять задачи может продюсер проекта или администратор")
    execute("DELETE FROM tasks WHERE id = %s", (task_id,), returning=False)


# ---------- справочники и отчёты ----------

def list_clients():
    return query("SELECT id, name, contact_person FROM clients ORDER BY name")


def list_users(role=None):
    if role and role not in USER_ROLES:
        raise ValidationError({"role": "Неизвестная роль"})
    sql = "SELECT id, full_name, role FROM users WHERE is_active"
    params = []
    if role:
        sql += " AND role = %s"
        params.append(role)
    return query(sql + " ORDER BY full_name", params)


def create_user(data):
    from werkzeug.security import generate_password_hash

    errors = {}
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = data.get("role") or "editor"
    password = data.get("password") or ""
    if not full_name or len(full_name) > 150:
        errors["full_name"] = "Укажите ФИО (до 150 символов)"
    if "@" not in email or len(email) > 150:
        errors["email"] = "Некорректный e-mail"
    elif query("SELECT 1 FROM users WHERE lower(email) = %s", (email,)):
        errors["email"] = "Сотрудник с таким e-mail уже есть"
    if role not in USER_ROLES:
        errors["role"] = "Неизвестная роль"
    if len(password) < 8:
        errors["password"] = "Пароль не короче 8 символов"
    if errors:
        raise ValidationError(errors)
    return execute(
        """INSERT INTO users (full_name, email, role, password_hash) VALUES (%s, %s, %s, %s)
           RETURNING id, full_name, email, role""",
        (full_name, email, role, generate_password_hash(password)),
    )


def list_equipment():
    return query("SELECT id, name, category, inventory_number, is_available FROM equipment ORDER BY inventory_number")


def workload_report():
    return query(
        """SELECT user_id, full_name, role, open_tasks, in_progress, overdue, projects
           FROM v_user_workload ORDER BY open_tasks DESC, overdue DESC, full_name"""
    )


def schema_version():
    row = query("SELECT max(version) AS v FROM schema_migrations", one=True)
    return row["v"] if row else None


def app_version():
    return current_app.config["VERSION"]
