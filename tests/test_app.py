def register(client, username="alice", email="alice@example.com", password="StrongPass123"):
    return client.post("/api/register", json={"username": username, "email": email, "password": password})

def login(client, username="alice", password="StrongPass123"):
    return client.post("/api/login", json={"username": username, "password": password})

def task_payload(**overrides):
    data = {"title":"Write project report","description":"Finish the first draft","status":"Pending","priority":"High","tags":"study,project","due_date":"2026-12-31"}
    data.update(overrides)
    return data

def test_register_login_and_invalid_login(client):
    assert register(client).status_code == 201
    assert login(client).status_code == 200
    client.post("/api/logout")
    assert login(client, password="wrong-password").status_code == 401

def test_task_crud(client):
    register(client); login(client)
    created = client.post("/api/tasks", json=task_payload())
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert client.get("/api/tasks").json()[0]["title"] == "Write project report"
    edited = client.patch(f"/api/tasks/{task_id}", json=task_payload(title="Updated report"))
    assert edited.status_code == 200 and edited.json()["title"] == "Updated report"
    assert client.delete(f"/api/tasks/{task_id}").status_code == 204
    assert client.get("/api/tasks").json() == []

def test_user_cannot_access_another_users_task(client):
    register(client); login(client)
    task_id = client.post("/api/tasks", json=task_payload()).json()["id"]
    client.post("/api/logout")
    register(client, "bob", "bob@example.com", "AnotherPass123")
    assert client.get(f"/api/tasks").json() == []
    assert client.patch(f"/api/tasks/{task_id}", json=task_payload()).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}").status_code == 404

def test_filters(client):
    register(client); login(client)
    client.post("/api/tasks", json=task_payload(title="Read Python book", priority="High"))
    client.post("/api/tasks", json=task_payload(title="Buy groceries", priority="Low"))
    assert len(client.get("/api/tasks?priority=High").json()) == 1
    assert len(client.get("/api/tasks?q=Python").json()) == 1
    assert client.get("/api/tasks?status_filter=Completed").json() == []

def test_status_transition_rules(client):
    register(client); login(client)
    task_id = client.post("/api/tasks", json=task_payload()).json()["id"]
    assert client.post(f"/api/tasks/{task_id}/transition?new_status=Completed").status_code == 409
    assert client.post(f"/api/tasks/{task_id}/transition?new_status=In%20Progress").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/transition?new_status=Pending").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/transition?new_status=In%20Progress").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/transition?new_status=Completed").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/transition?new_status=Pending").status_code == 409

def test_api_requires_login(client):
    assert client.get("/api/tasks").status_code == 401
