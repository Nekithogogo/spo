"""Новые ресурсы API версии 2.0: этапы проекта, группа, брони, задачи, отчёты (ПР №11–12)."""


def test_pagination_and_search(client):
    r = client.get("/api/projects?limit=2&offset=1")
    assert r.status_code == 200 and len(r.get_json()) == 2
    assert r.headers["X-Total-Count"] == "4"
    r = client.get("/api/projects", query_string={"q": "клип"})
    assert [p["id"] for p in r.get_json()] == [2]
    assert client.get("/api/projects?limit=1000").status_code == 400


def test_project_card_has_transitions(client):
    p = client.get("/api/projects/1").get_json()
    assert p["status"] == "shooting"
    assert set(p["allowed_transitions"]) == {"postproduction", "preproduction", "cancelled"}
    assert p["can_manage"] is True


def test_status_transition_and_history(producer):
    r = producer.patch("/api/projects/1", json={"status": "postproduction", "status_comment": "Съёмки завершены"})
    assert r.status_code == 200 and r.get_json()["status"] == "postproduction"
    history = producer.get("/api/projects/1/history").get_json()
    assert history[0]["old_status"] == "shooting" and history[0]["new_status"] == "postproduction"
    assert history[0]["changed_by_name"] == "Кузнецов Дмитрий Игоревич"
    assert history[0]["comment"] == "Съёмки завершены"


def test_invalid_transition(producer):
    r = producer.patch("/api/projects/1", json={"status": "done"})
    assert r.status_code == 409 and "status" in r.get_json()["details"]


def test_cannot_finish_project_with_open_tasks(client):
    client.patch("/api/projects/3", json={"status": "review"})
    r = client.patch("/api/projects/3", json={"status": "done"})
    assert r.status_code == 409
    assert r.get_json()["error"] == "Нельзя сдать проект с незакрытыми задачами"
    for task in client.get("/api/projects/3/tasks").get_json():
        client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    r = client.patch("/api/projects/3", json={"status": "done"})
    assert r.status_code == 200 and r.get_json()["allowed_transitions"] == []
    assert client.post("/api/projects/3/tasks", json={"title": "Ещё"}).status_code == 409


def test_patch_validation_and_unknown_fields(client):
    r = client.patch("/api/projects/1", json={"deadline": "2026-01-01"})
    assert r.status_code == 400 and "deadline" in r.get_json()["details"]
    r = client.patch("/api/projects/1", json={"id": 5, "created_at": "x"})
    assert r.status_code == 400 and set(r.get_json()["details"]) == {"created_at", "id"}


def test_optimistic_locking(client):
    etag = client.get("/api/projects/2").headers["ETag"]
    assert client.patch("/api/projects/2", json={"budget": 230000}, headers={"If-Match": etag}).status_code == 200
    r = client.patch("/api/projects/2", json={"budget": 240000}, headers={"If-Match": etag})
    assert r.status_code == 412


def test_members_put_is_idempotent(producer):
    r = producer.put("/api/projects/1/members/6", json={"role_in_project": "Второй продюсер"})
    assert r.status_code == 201 and r.get_json()["role_in_project"] == "Второй продюсер"
    r = producer.put("/api/projects/1/members/6", json={"role_in_project": "Консультант"})
    assert r.status_code == 200 and r.get_json()["role_in_project"] == "Консультант"
    assert len(producer.get("/api/projects/1/members").get_json()) == 5
    assert producer.delete("/api/projects/1/members/6").status_code == 204
    assert producer.delete("/api/projects/1/members/6").status_code == 404


def test_member_validation(producer):
    r = producer.put("/api/projects/1/members/999", json={"role_in_project": " "})
    assert r.status_code == 400 and set(r.get_json()["details"]) == {"role_in_project", "user_id"}


def test_booking_and_overlap_conflict(producer):
    r = producer.post("/api/projects/1/bookings",
                      json={"equipment_id": 2, "starts_at": "2026-11-20T09:00", "ends_at": "2026-11-20T18:00"})
    assert r.status_code == 201
    b = r.get_json()
    assert b["starts_at"] == "2026-11-20T09:00:00+03:00" and b["inventory_number"] == "CAM-002"
    # камера CAM-001 занята проектом 1 25.10 с 08:00 до 20:00
    r = producer.post("/api/projects/3/bookings",
                      json={"equipment_id": 1, "starts_at": "2026-10-25T19:00", "ends_at": "2026-10-25T23:00"})
    assert r.status_code == 409
    assert "Рекламный ролик" in r.get_json()["details"]["conflict"]
    # стык интервалов допустим: [08:00, 20:00) и [20:00, 23:00) не пересекаются
    r = producer.post("/api/projects/3/bookings",
                      json={"equipment_id": 1, "starts_at": "2026-10-25T20:00", "ends_at": "2026-10-25T23:00"})
    assert r.status_code == 201
    assert producer.delete(f"/api/bookings/{b['id']}").status_code == 204


def test_booking_validation(producer):
    r = producer.post("/api/projects/1/bookings",
                      json={"equipment_id": 99, "starts_at": "2026-11-20T18:00", "ends_at": "2026-11-20T09:00"})
    assert r.status_code == 400 and set(r.get_json()["details"]) == {"equipment_id", "ends_at"}
    r = producer.post("/api/projects/1/bookings", json={"starts_at": "завтра"})
    assert set(r.get_json()["details"]) == {"equipment_id", "starts_at", "ends_at"}


def test_equipment_schedule(client):
    r = client.get("/api/equipment/1/bookings?from=2026-10-25T00:00&to=2026-10-26T00:00")
    assert r.status_code == 200 and len(r.get_json()) == 1
    assert client.get("/api/equipment/1/bookings?from=2026-11-01T00:00").get_json() == []
    assert client.get("/api/equipment/99/bookings").status_code == 404


def test_task_full_update_and_delete(producer):
    r = producer.patch("/api/tasks/4", json={"title": "Монтаж 1-й версии", "due_date": "2026-11-07",
                                             "stage": "postproduction", "description": "Хронометраж 30 с"})
    assert r.status_code == 200
    t = r.get_json()
    assert t["title"] == "Монтаж 1-й версии" and t["due_date"] == "2026-11-07" and t["description"] == "Хронометраж 30 с"
    assert producer.delete("/api/tasks/4").status_code == 204
    assert producer.get("/api/tasks/4").status_code == 404


def test_assignee_changes_only_status(editor):
    assert editor.patch("/api/tasks/4", json={"status": "in_progress"}).status_code == 200   # своя задача
    assert editor.patch("/api/tasks/4", json={"title": "Другое"}).status_code == 403
    assert editor.patch("/api/tasks/1", json={"status": "todo"}).status_code == 403          # чужая
    assert editor.delete("/api/tasks/4").status_code == 403
    assert editor.post("/api/projects/1/tasks", json={"title": "x"}).status_code == 403


def test_workload_report(producer, editor):
    rows = {r["full_name"]: r for r in producer.get("/api/reports/workload").get_json()}
    volkov = rows["Волков Артём Денисович"]
    assert volkov["open_tasks"] == 3 and volkov["in_progress"] == 1 and volkov["projects"] == 2
    assert editor.get("/api/reports/workload").status_code == 403
