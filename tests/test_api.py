def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok", "db": "ok"}


def test_list_projects(client):
    r = client.get("/api/projects")
    assert r.status_code == 200
    titles = [p["title"] for p in r.get_json()]
    assert "Клип «Ветер перемен»" in titles
    assert len(titles) == 4


def test_filter_projects_by_status(client):
    r = client.get("/api/projects?status=shooting")
    assert [p["id"] for p in r.get_json()] == [1]


def test_filter_unknown_status(client):
    r = client.get("/api/projects?status=archived")
    assert r.status_code == 400
    assert "status" in r.get_json()["details"]


def test_get_project_with_tasks(client):
    r = client.get("/api/projects/1")
    body = r.get_json()
    assert r.status_code == 200
    assert body["tasks_total"] == 4 and body["tasks_done"] == 2
    assert len(body["tasks"]) == 4
    assert {m["role_in_project"] for m in body["members"]} >= {"Продюсер", "Режиссёр"}


def test_get_missing_project(client):
    r = client.get("/api/projects/999")
    assert r.status_code == 404
    assert r.get_json()["error"] == "Проект не найден"


def test_create_project(client):
    payload = {
        "title": "Свадебный фильм Ивановых",
        "client_id": 1,
        "producer_id": 2,
        "project_type": "event",
        "budget": "120000",
        "start_date": "2026-11-01",
        "deadline": "2026-11-30",
    }
    r = client.post("/api/projects", json=payload)
    assert r.status_code == 201
    body = r.get_json()
    assert body["status"] == "new"
    assert body["budget"] == 120000
    assert r.headers["Location"] == f"/api/projects/{body['id']}"
    assert client.get(f"/api/projects/{body['id']}").status_code == 200


def test_create_project_validation(client):
    r = client.post("/api/projects", json={"title": "", "client_id": 999, "budget": -5,
                                           "start_date": "2026-12-01", "deadline": "2026-11-01"})
    assert r.status_code == 400
    details = r.get_json()["details"]
    assert set(details) == {"title", "client_id", "budget", "deadline"}


def test_create_project_producer_must_be_producer(client):
    r = client.post("/api/projects", json={"title": "X", "client_id": 1, "producer_id": 5})
    assert r.status_code == 400
    assert "producer_id" in r.get_json()["details"]


def test_create_project_bad_body(client):
    r = client.post("/api/projects", data="not json", content_type="application/json")
    assert r.status_code == 400


def test_create_and_update_task(client):
    r = client.post("/api/projects/2/tasks", json={"title": "Аренда локации", "stage": "shooting", "assignee_id": 4})
    assert r.status_code == 201
    task = r.get_json()
    assert task["status"] == "todo" and task["assignee_name"] == "Смирнов Павел Олегович"

    r = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert r.status_code == 200 and r.get_json()["status"] == "done"
    assert client.get("/api/projects/2").get_json()["tasks_done"] == 1


def test_task_errors(client):
    assert client.post("/api/projects/999/tasks", json={"title": "x"}).status_code == 404
    assert client.post("/api/projects/1/tasks", json={"title": "x", "stage": "party"}).status_code == 400
    assert client.patch("/api/tasks/1", json={"status": "finished"}).status_code == 400
    assert client.patch("/api/tasks/999", json={"status": "done"}).status_code == 404


def test_unknown_api_route_returns_json(client):
    r = client.get("/api/nothing")
    assert r.status_code == 404 and r.is_json


def test_pages_render(client):
    assert client.get("/").status_code == 200
    assert "Новая задача" in client.get("/projects/1").get_data(as_text=True)
