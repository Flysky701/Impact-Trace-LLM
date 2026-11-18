from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.bootstrap import bootstrap
from app.config import ROOT, Settings
from app.main import create_app
from app.models import LoginSession, database
from app.security import token_digest
from conftest import create_project, login


def test_health_and_auth_lifecycle(client, app):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/projects").status_code == 401
    for name, password in (("unknown", "bad"), ("dev", "bad")):
        assert client.post("/api/auth/login", json={"username": name, "password": password}).status_code == 401
    result = login(client)
    assert "httponly" in result.headers["set-cookie"].lower()
    assert "samesite=strict" in result.headers["set-cookie"].lower()
    first = client.cookies.get("impact_session")
    assert "password" not in str(result.json())
    assert client.get("/api/auth/me").json()["role"] == "developer"
    login(client)
    with app.state.sessions() as db:
        assert db.get(LoginSession, token_digest(first)) is None
        rows = list(db.scalars(select(LoginSession)))
        assert len(rows) == 1
        assert rows[0].token_hash != client.cookies.get("impact_session")
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/logout").status_code == 204


def test_expired_session(client, app):
    login(client)
    with app.state.sessions() as db:
        row = db.scalar(select(LoginSession))
        row.expires_at = 0
        db.commit()
    assert client.get("/api/auth/me").status_code == 401
    with app.state.sessions() as db:
        assert db.scalar(select(LoginSession)) is None


def test_csrf_and_host(app):
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={}).status_code == 403
        assert client.post("/api/auth/logout", headers={"X-Requested-With": "ImpactTrace", "Origin": "https://elsewhere.invalid"}).status_code == 403
        assert client.get("/api/health", headers={"Host": "attacker.invalid"}).status_code == 400
        assert client.post("/api/auth/logout", headers={"X-Requested-With": "ImpactTrace", "Origin": "http://testserver"}).status_code == 204


def test_project_acl_and_repository_browsing(client, repository):
    project = create_project(client, repository)
    project_id = project["id"]
    assert client.get("/api/config").json()["repository_roots"]
    assert len(client.get("/api/reviewers").json()) == 1
    assert client.get("/api/projects").json()[0]["id"] == project_id
    route = f"/api/projects/{project_id}"
    result = client.get(route + "/commits?limit=1").json()
    assert result["total"] == 2 and result["commits"][0]["sha"] == repository[2]
    assert client.get(route + "/commits?limit=1&offset=1").json()["commits"][0]["sha"] == repository[1]
    assert client.get(route + "/commits?limit=99").status_code == 422
    assert client.get(route + "/commits?revision=missing").status_code == 422
    files = client.get(route + "/files", params={"revision": repository[1]}).json()
    assert "中文.py" in [f["path"] for f in files["files"]]
    for sha, content in ((repository[1], "return 1"), (repository[2], "return 2")):
        response = client.get(route + "/source", params={"revision": sha, "file": "sample.py"})
        assert content in response.json()["content"]
        assert response.json()["revision"] == sha
    for path in ("../secret", "blob.bin", "large.txt"):
        assert client.get(route + "/source", params={"revision": "HEAD", "file": path}).status_code == 422
    login(client, "review")
    assert client.get(route).status_code == 200
    assert client.get(route + "/commits").status_code == 200
    assert client.get("/api/projects").json()[0]["id"] == project_id
    assert client.post("/api/projects", json={"name": "X", "repository_path": str(repository[0])}).status_code == 403
    assert client.get("/api/config").status_code == 403
    login(client, "other")
    assert client.get("/api/projects").json() == []
    for suffix in ("", "/commits", "/files?revision=HEAD", "/source?revision=HEAD&file=sample.py"):
        assert client.get(route + suffix).status_code == 404


def test_project_validation(client, repository, tmp_path):
    login(client)
    payload = {"name": "X", "repository_path": str(repository[0])}
    for replacement in ({"name": " "}, {"reviewer_id": 1}, {"reviewer_id": 999},
                        {"repository_path": str(tmp_path.parent)}, {"repository_path": str(tmp_path / "missing")}):
        assert client.post("/api/projects", json=payload | replacement).status_code == 422
    assert client.post("/api/projects", json=payload).status_code == 201


def test_bootstrap_is_idempotent_and_config(tmp_path, monkeypatch):
    settings = Settings(f"sqlite:///{tmp_path / 'demo.db'}", (tmp_path,))
    output = tmp_path / "credentials.txt"
    assert bootstrap(settings, output)[0] == 2
    credentials = output.read_text()
    assert bootstrap(settings, output)[0] == 0
    assert output.read_text() == credentials
    app = create_app(settings)
    with TestClient(app, headers={"X-Requested-With": "ImpactTrace"}) as client:
        name, password = credentials.splitlines()[0].split(": ")
        assert client.post("/api/auth/login", json={"username": name, "password": password}).status_code == 200
    monkeypatch.setenv("IMPACT_REPOSITORY_ROOTS", str(tmp_path))
    monkeypatch.setenv("IMPACT_SECURE_COOKIES", "1")
    monkeypatch.setenv("IMPACT_DATABASE_URL", "sqlite://")
    actual = Settings.from_env()
    assert actual.repository_roots == (tmp_path,)
    assert actual.secure_cookies
    assert ROOT.name == "Impact-Trace-LLM"


def test_static_frontend(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<h1>ImpactTrace</h1>")
    app = create_app(Settings("sqlite://", (tmp_path,), frontend_dist=tmp_path))
    with TestClient(app) as client:
        assert "ImpactTrace" in client.get("/").text
        assert client.get("/api/not-a-route").status_code == 404
