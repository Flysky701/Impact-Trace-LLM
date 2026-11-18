import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import User
from app.security import PASSWORDS


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / "sample repo"
    repo.mkdir()
    def run(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()
    run("init", "-q")
    run("config", "user.email", "test@example.invalid")
    run("config", "user.name", "Test")
    (repo / "sample.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    (repo / "中文.py").write_text("message = '你好'\n", encoding="utf-8")
    (repo / "blob.bin").write_bytes(b"a\0b")
    (repo / "large.txt").write_bytes(b"x" * (1024 * 1024 + 1))
    run("add", ".")
    run("commit", "-qm", "First version")
    base = run("rev-parse", "HEAD")
    (repo / "sample.py").write_text("def hello():\n    return 2\n", encoding="utf-8")
    run("add", ".")
    run("commit", "-qm", "Second version")
    return repo, base, run("rev-parse", "HEAD")


@pytest.fixture
def app(tmp_path, repository):
    instance = create_app(Settings("sqlite://", (tmp_path,), frontend_dist=tmp_path / "no-build"))
    with instance.state.sessions() as db:
        for name, role in (("dev", "developer"), ("review", "reviewer"), ("other", "developer")):
            db.add(User(username=name, password_hash=PASSWORDS.hash("testing-password"), role=role))
        db.commit()
    return instance


@pytest.fixture
def client(app):
    with TestClient(app, headers={"X-Requested-With": "ImpactTrace"}) as test_client:
        yield test_client


def login(client, username="dev"):
    result = client.post("/api/auth/login", json={"username": username, "password": "testing-password"})
    assert result.status_code == 200
    return result


def create_project(client, repository, reviewer_id=2):
    login(client)
    result = client.post("/api/projects", json={"name": "Demo", "repository_path": str(repository[0]),
                                                "reviewer_id": reviewer_id})
    assert result.status_code == 201
    return result.json()
