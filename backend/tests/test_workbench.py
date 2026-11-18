import json
import subprocess
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app import llm_service, python_graph, repo_analyzer
from conftest import create_project, login


@pytest.fixture
def rich_repo(tmp_path):
    repo = tmp_path / "rich_app"
    repo.mkdir()

    def run(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

    run("init", "-q")
    run("config", "user.email", "dev@example.invalid")
    run("config", "user.name", "Dev")

    (repo / "storages").mkdir()
    (repo / "table").mkdir()
    (repo / "database").mkdir()
    (repo / "tests").mkdir()

    (repo / "storages" / "store.py").write_text(
        "class RecordEntity:\n"
        "    id: int\n"
        "    title: str\n\n"
        "def write_disk(payload):\n"
        "    if not payload:\n"
        "        return False\n"
        "    return True\n",
        encoding="utf-8",
    )
    (repo / "table" / "core.py").write_text(
        "from storages.store import write_disk\n\n"
        "class Table:\n"
        "    def update(self, doc_ids):\n"
        "        for doc_id in doc_ids:\n"
        "            write_disk(doc_id)\n"
        "        return doc_ids\n\n"
        "    def upsert(self, doc_ids):\n"
        "        try:\n"
        "            return self.update(doc_ids)\n"
        "        except ValueError:\n"
        "            return []\n"
        "        finally:\n"
        "            pass\n",
        encoding="utf-8",
    )
    (repo / "database" / "entry.py").write_text(
        "from table.core import Table\n\n"
        "def sync_account(ids):\n"
        "    tbl = Table()\n"
        "    return tbl.upsert(ids)\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_core.py").write_text(
        "from table.core import Table\n\n"
        "def test_update_flow():\n"
        "    assert Table().update([1]) == [1]\n",
        encoding="utf-8",
    )
    run("add", ".")
    run("commit", "-qm", "Initial structured version")
    base = run("rev-parse", "HEAD")

    (repo / "table" / "core.py").write_text(
        "from storages.store import write_disk\n\n"
        "class Table:\n"
        "    def update(self, doc_ids):\n"
        "        valid = [d for d in doc_ids if d > 0]\n"
        "        if not valid:\n"
        "            return []\n"
        "        for doc_id in valid:\n"
        "            write_disk(doc_id)\n"
        "        return valid\n\n"
        "    def upsert(self, doc_ids):\n"
        "        try:\n"
        "            return self.update(doc_ids)\n"
        "        except ValueError:\n"
        "            return []\n"
        "        finally:\n"
        "            pass\n",
        encoding="utf-8",
    )
    (repo / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    run("add", ".")
    run("commit", "-qm", "Filter missing ids before update")
    head = run("rev-parse", "HEAD")

    # Add an uncommitted worktree edit for WORKTREE verification
    (repo / "database" / "entry.py").write_text(
        "from table.core import Table\n\n"
        "def sync_account(ids):\n"
        "    if not ids:\n"
        "        return []\n"
        "    tbl = Table()\n"
        "    return tbl.upsert(ids)\n",
        encoding="utf-8",
    )
    return repo, base, head


def _mock_http_response(status_code: int, payload: dict | str):
    resp = MagicMock()
    resp.status_code = status_code
    if isinstance(payload, dict):
        resp.json.return_value = payload
        resp.text = json.dumps(payload)
    else:
        resp.json.side_effect = ValueError("not json")
        resp.text = payload
    return resp


def test_llm_settings_and_multi_provider_transport(client):
    login(client, "dev")
    initial = client.get("/api/settings/llm").json()
    assert initial["configured"] is False
    assert initial["presets"]

    # Validation errors
    assert client.put("/api/settings/llm", json={
        "provider": "bad", "base_url": "https://api.deepseek.com/v1", "model": "m",
    }).status_code == 422
    assert client.put("/api/settings/llm", json={
        "provider": "openai_compatible", "base_url": "ftp://bad", "model": "m",
    }).status_code == 422

    # Save OpenAI-compatible key and verify masking + key preservation
    saved = client.put("/api/settings/llm", json={
        "provider": "openai_compatible",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key": "sk-1234567890abcdef",
    }).json()
    assert saved["configured"] is True
    assert saved["masked_key"] == "sk-1••••cdef"
    assert "1234567890" not in json.dumps(saved)

    kept = client.put("/api/settings/llm", json={
        "provider": "openai_compatible",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-reasoner",
        "api_key": "",
    }).json()
    assert kept["configured"] is True and kept["model"] == "deepseek-reasoner"

    # Reviewer can read configured flag, cannot mutate or test
    login(client, "review")
    assert client.get("/api/settings/llm").json()["configured"] is True
    assert client.put("/api/settings/llm", json={
        "provider": "openai_compatible", "base_url": "https://api.deepseek.com/v1", "model": "m",
    }).status_code == 403
    assert client.post("/api/settings/llm/test", json={
        "provider": "openai_compatible", "base_url": "https://api.deepseek.com/v1", "model": "m",
    }).status_code == 403

    # Test connection across OpenAI-compatible, Gemini, Anthropic, and error paths
    login(client, "dev")
    with patch("app.llm_service.httpx.post", return_value=_mock_http_response(200, {
        "choices": [{"message": {"content": "OK"}}],
    })):
        probe = client.post("/api/settings/llm/test", json={
            "provider": "openai_compatible", "base_url": "https://api.deepseek.com", "model": "deepseek-chat",
        })
        assert probe.status_code == 200 and probe.json()["ok"] is True

    with patch("app.llm_service.httpx.post", return_value=_mock_http_response(200, {
        "candidates": [{"content": {"parts": [{"text": "OK"}]}}],
    })):
        assert llm_service.call_llm(
            {"provider": "gemini", "base_url": "https://generativelanguage.googleapis.com", "model": "gemini-2.5-flash", "api_key": "shortkey"},
            "sys", "usr",
        ) == "OK"
    assert llm_service.mask_key("short") == "••••••••"

    with patch("app.llm_service.httpx.post", return_value=_mock_http_response(200, {
        "content": [{"type": "text", "text": "OK"}],
    })):
        assert llm_service.call_llm(
            {"provider": "anthropic", "base_url": "https://api.anthropic.com", "model": "claude", "api_key": "sk-ant-123456789"},
            "sys", "usr",
        ) == "OK"

    for status, match in ((401, "认证失败"), (429, "限流"), (502, "HTTP 502")):
        with patch("app.llm_service.httpx.post", return_value=_mock_http_response(status, "err")):
            with pytest.raises(llm_service.LLMError, match=match):
                llm_service.call_llm({"provider": "openai_compatible", "base_url": "https://x.test/v1", "model": "m", "api_key": "k"}, "s", "u")

    for err, match in ((httpx.TimeoutException("slow"), "超时"), (httpx.ConnectError("down"), "无法连接")):
        with patch("app.llm_service.httpx.post", side_effect=err):
            with pytest.raises(llm_service.LLMError, match=match):
                llm_service.call_llm({"provider": "openai_compatible", "base_url": "https://x.test/v1", "model": "m", "api_key": "k"}, "s", "u")

    cleared = client.put("/api/settings/llm", json={
        "provider": "openai_compatible", "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat", "clear_key": True,
    }).json()
    assert cleared["configured"] is False


def test_overview_generation_caching_and_anchor_sanitization(client, rich_repo):
    project = create_project(client, rich_repo)
    pid = project["id"]

    # Edit project metadata (F2)
    updated = client.patch(f"/api/projects/{pid}", json={
        "name": "数据同步引擎", "description": "带缓存与存储分层的样例仓库", "reviewer_id": 2,
    })
    assert updated.status_code == 200 and updated.json()["name"] == "数据同步引擎"
    assert client.patch(f"/api/projects/{pid}", json={"name": "  ", "reviewer_id": 2}).status_code == 422
    assert client.patch(f"/api/projects/{pid}", json={"name": "OK", "reviewer_id": 999}).status_code == 422

    # Heuristic overview + DB cache hit on second call
    ov = client.get(f"/api/projects/{pid}/overview?revision={rich_repo[1]}").json()
    assert ov["sourceMode"] == "heuristic"
    assert ov["roles"] and ov["roleFlows"] and ov["storylines"] and ov["dataCards"]
    cached_ov = client.get(f"/api/projects/{pid}/overview?revision={rich_repo[1]}").json()
    assert cached_ov["headline"] == ov["headline"]

    # Upgrade overview via LLM and verify hallucinated paths are stripped
    client.put("/api/settings/llm", json={
        "provider": "openai_compatible", "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat", "api_key": "sk-valid-key-1234",
    })
    fake_llm_overview = "```json\n" + json.dumps({
        "headline": "这是一个把外部数据校验后安全写入磁盘的数据管理小系统。",
        "narrative": "入口接收待更新编号，交由数据表模块逐条核验并写盘。",
        "roles": [{
            "id": "table",
            "title": "数据核验与更新中心",
            "subtitle": "负责过滤无效编号并协调落盘",
            "plainHow": "通过内部方法逐步筛选并调用底层存储",
            "anchors": [
                {"path": "table/core.py", "line": 3, "end": 10, "label": "核心更新实现"},
                {"path": "hallucinated/nonexistent.py", "line": 99, "label": "幻觉文件"},
            ],
        }],
        "roleFlows": [{"from": "database", "to": "table", "action": "转交待同步编号", "detail": "入口转发请求"}],
        "storylines": [{
            "id": "s1", "title": "账号数据同步主线", "when": "触发同步时", "outcome": "完成落盘",
            "steps": [{"stepNo": 1, "what": "过滤有效编号并写盘", "why": "防止空数据写入", "howPlain": "逐项遍历写入", "moduleId": "table",
                       "anchors": [{"path": "table/core.py", "line": 4, "end": 8, "label": "更新步骤"}]}],
        }],
        "hotspots": [{
            "id": "h1", "title": "异常处理与重试逻辑集中", "whyHard": "多分支耦合", "splitIdea": "拆分独立校验步骤",
            "severity": "medium", "metrics": "15 行", "moduleId": "table",
            "anchors": [{"path": "table/core.py", "line": 10, "end": 18, "label": "异常分支"}],
        }],
    }, ensure_ascii=False) + "\n```"

    with patch("app.llm_service.call_llm", return_value=fake_llm_overview):
        upgraded = client.post(f"/api/projects/{pid}/overview/generate", json={
            "revision": rich_repo[1], "use_llm": True,
        }).json()
    assert upgraded["sourceMode"] == "llm"
    assert upgraded["roles"][0]["title"] == "数据核验与更新中心"
    role_paths = [a["path"] for a in upgraded["roles"][0]["anchors"]]
    assert "table/core.py" in role_paths
    assert "hallucinated/nonexistent.py" not in role_paths


def test_change_review_impact_radius_and_role_workflow(client, rich_repo):
    project = create_project(client, rich_repo)
    pid = project["id"]
    base, head = rich_repo[1], rich_repo[2]

    # AI change requires user_prompt
    assert client.post(f"/api/projects/{pid}/analyses", json={
        "task_type": "ai_change", "title": "AI 修复", "base_ref": base, "head_ref": head,
    }).status_code == 422

    # Create analysis (base -> head): broken.py causes partial status; update impacts upsert & sync_account!
    created = client.post(f"/api/projects/{pid}/analyses", json={
        "task_type": "ai_change",
        "title": "过滤不存在的记录编号",
        "user_prompt": "更新前先过滤掉无效编号，避免写入空项",
        "raw_log": "Step 1: inspect core.py",
        "base_ref": base,
        "head_ref": head,
        "use_llm": True,  # Not configured yet -> graceful fallback!
    })
    assert created.status_code == 201
    detail = created.json()
    tid = detail["id"]
    assert detail["status"] == "partial"
    assert detail["llm_status"] == "not_configured"
    assert detail["result"]["flowComparisons"]
    impact_symbols = {item["symbolName"] for item in detail["result"]["impactRadius"]}
    assert "Table.upsert" in impact_symbols
    assert "sync_account" in impact_symbols

    # Also verify WORKTREE comparison and WORKTREE file/source endpoints
    wt_files = client.get(f"/api/projects/{pid}/files?revision=WORKTREE").json()
    assert any(f["path"] == "database/entry.py" for f in wt_files["files"])
    wt_src = client.get(f"/api/projects/{pid}/source", params={"revision": "WORKTREE", "file": "database/entry.py"}).json()
    assert "if not ids:" in wt_src["content"]
    wt_task = client.post(f"/api/projects/{pid}/analyses", json={
        "title": "检查未提交改动", "base_ref": head, "head_ref": "WORKTREE",
    }).json()
    assert wt_task["head_sha"] == "WORKTREE"
    assert wt_task["result"]["diagnostics"]["changedFileCount"] >= 1

    # Same-version comparison produces clean zero-change summary
    same_task = client.post(f"/api/projects/{pid}/analyses", json={
        "title": "同版本对照", "base_ref": base, "head_ref": base,
    }).json()
    assert same_task["result"]["diagnostics"]["changedFileCount"] == 0

    # Configure LLM and upgrade explanation on existing task
    client.put("/api/settings/llm", json={
        "provider": "openai_compatible", "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat", "api_key": "sk-test-12345678",
    })
    llm_change_reply = json.dumps({
        "headline": "更新逻辑增加了前置正数编号筛选，上游同步入口随之受影响。",
        "beforeVsAfter": "修改前直接遍历全部输入编号写盘；修改后先筛掉非正数编号并在为空时提前返回。",
        "riskPoints": [{"title": "空列表返回值处理", "detail": "确认上游调用方允许接收空列表",
                        "anchors": [{"path": "table/core.py", "line": 4, "end": 9, "label": "筛选分支"}]}],
        "testSuggestions": ["补充全无效编号输入测试"],
    }, ensure_ascii=False)
    with patch("app.llm_service.call_llm", return_value=llm_change_reply):
        explained = client.post(f"/api/projects/{pid}/analyses/{tid}/explain")
        assert explained.status_code == 200
        assert explained.json()["llm_status"] == "generated"
        assert "前置正数编号筛选" in explained.json()["result"]["plainSummary"]["headline"]

    # Developer cannot submit review; Reviewer cannot create analysis
    assert client.post(f"/api/projects/{pid}/analyses/{tid}/reviews", json={
        "verdict": "approved", "comment": "自审",
    }).status_code == 403

    login(client, "review")
    assert client.post(f"/api/projects/{pid}/analyses", json={
        "title": "越权发起", "base_ref": base, "head_ref": head,
    }).status_code == 403
    assert client.post(f"/api/projects/{pid}/analyses/{tid}/reviews", json={
        "verdict": "approved", "comment": "缺少测试说明", "test_status": "passed", "test_notes": "",
    }).status_code == 422

    rev = client.post(f"/api/projects/{pid}/analyses/{tid}/reviews", json={
        "verdict": "attention",
        "comment": "已核对筛选分支，需补充空编号用例。",
        "test_status": "passed",
        "test_notes": "运行 pytest tests/test_core.py 通过",
    })
    assert rev.status_code == 201
    assert rev.json()["author_username"] == "review"

    listed = client.get(f"/api/projects/{pid}/analyses").json()
    matched = next(x for x in listed if x["id"] == tid)
    assert matched["review_count"] == 1 and matched["latest_verdict"] == "attention"
    reopened = client.get(f"/api/projects/{pid}/analyses/{tid}").json()
    assert len(reopened["reviews"]) == 1


def test_maintenance_notes_contextual_ask_and_auto_kotlin_detection(client, rich_repo, tmp_path):
    project = create_project(client, rich_repo)
    pid = project["id"]

    # Create, resolve, list, and delete maintenance notes
    created = client.post(f"/api/projects/{pid}/notes", json={
        "target_type": "module",
        "target_key": "table",
        "target_label": "数据表读写与缓存核心",
        "kind": "pitfall",
        "title": "写盘失败未回滚内存状态",
        "content": "修改 update 时注意保持异常分支与缓存一致。",
    })
    assert created.status_code == 201
    nid = created.json()["id"]
    assert len(client.get(f"/api/projects/{pid}/notes").json()) == 1

    # Ask without API key -> heuristic answer includes callers + active maintenance note!
    heuristic_ans = client.post(f"/api/projects/{pid}/ask", json={
        "question": "update 这个步骤是谁调用的？改的时候要注意什么？",
        "revision": rich_repo[2],
        "target_path": "table/core.py",
        "target_line": 5,
        "target_label": "Table.update",
    }).json()
    assert heuristic_ans["mode"] == "heuristic"
    assert any("upsert" in p for p in heuristic_ans["keyPoints"])
    assert any("写盘失败未回滚" in p for p in heuristic_ans["keyPoints"])

    # Ask with configured API key -> LLM answer + fallback on error
    client.put("/api/settings/llm", json={
        "provider": "openai_compatible", "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat", "api_key": "sk-ask-key-123456",
    })
    with patch("app.llm_service.call_llm", return_value=json.dumps({
        "answer": "该步骤由同模块的更新或插入流程直接调用，修改时需留意空编号过滤。",
        "keyPoints": ["上游入口会传入编号列表"],
        "anchors": [{"path": "table/core.py", "line": 4, "end": 10, "label": "过滤与写盘"}],
    }, ensure_ascii=False)):
        llm_ans = client.post(f"/api/projects/{pid}/ask", json={
            "question": "这里怎么工作的？", "revision": rich_repo[2],
        }).json()
        assert llm_ans["mode"] == "llm"
        assert llm_ans["anchors"][0]["path"] == "table/core.py"

    with patch("app.llm_service.call_llm", side_effect=llm_service.LLMError("模拟网络超时")):
        degraded = client.post(f"/api/projects/{pid}/ask", json={
            "question": "这里怎么工作的？", "revision": rich_repo[2],
        }).json()
        assert degraded["mode"] == "heuristic"
        assert any("模拟网络超时" in p for p in degraded["keyPoints"])

    toggled = client.patch(f"/api/projects/{pid}/notes/{nid}", json={"resolved": True})
    assert toggled.status_code == 200 and toggled.json()["resolved"] is True
    assert client.delete(f"/api/projects/{pid}/notes/{nid}").status_code == 204
    assert client.get(f"/api/projects/{pid}/notes").json() == []

    # Auto-detect zero-config Gradle Kotlin repo
    kt_repo = tmp_path / "auto_kt"
    (kt_repo / "core" / "src" / "main" / "kotlin").mkdir(parents=True)
    (kt_repo / "core" / "build.gradle.kts").write_text("// gradle\n", encoding="utf-8")
    (kt_repo / "core" / "src" / "main" / "kotlin" / "Flow.kt").write_text(
        "package demo\nfun startTask(flag: Boolean) {\n  if (flag) stepOne()\n}\nfun stepOne() {}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(kt_repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(kt_repo), "config", "user.email", "t@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(kt_repo), "config", "user.name", "T"], check=True)
    subprocess.run(["git", "-C", str(kt_repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(kt_repo), "commit", "-qm", "init kt"], check=True)

    lang, pf, snap = repo_analyzer.load_snapshot(kt_repo, "HEAD")
    assert lang == "kotlin" and snap["metrics"]["functions"] == 2


def test_local_git_repository_workflow(client, rich_repo):
    project = create_project(client, rich_repo)
    pid = project["id"]
    repo_dir = rich_repo[0]
    (repo_dir / "notes.md").write_text("# New Untracked File\nhello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_dir), "tag", "v0.1.0"], check=True)

    refs = client.get(f"/api/projects/{pid}/refs").json()
    assert refs["branches"] and refs["tags"][0]["name"] == "v0.1.0"

    status = client.get(f"/api/projects/{pid}/git/status").json()
    assert status["clean"] is False
    assert any(x["path"] == "database/entry.py" for x in status["unstaged"])
    assert any(x["path"] == "notes.md" for x in status["untracked"])

    # Diff for unstaged modified file and untracked file
    diff_mod = client.get(f"/api/projects/{pid}/git/diff", params={"file": "database/entry.py"}).json()
    assert "+    if not ids:" in diff_mod["diff"]
    diff_new = client.get(f"/api/projects/{pid}/git/diff", params={"file": "notes.md"}).json()
    assert "+# New Untracked File" in diff_new["diff"]
    assert client.get(f"/api/projects/{pid}/git/diff", params={"file": "../bad"}).status_code == 422

    # Reviewer cannot stage or commit
    login(client, "review")
    assert client.post(f"/api/projects/{pid}/git/stage", json={"all": True}).status_code == 403
    assert client.post(f"/api/projects/{pid}/git/commit", json={"message": "x"}).status_code == 403

    # Developer stages, unstages, commits, and inspects commit detail
    login(client, "dev")
    assert client.post(f"/api/projects/{pid}/git/commit", json={"message": "empty stage"}).status_code == 422
    assert client.post(f"/api/projects/{pid}/git/stage", json={"files": []}).status_code == 422

    staged = client.post(f"/api/projects/{pid}/git/stage", json={"files": ["notes.md"]}).json()
    assert any(x["path"] == "notes.md" for x in staged["staged"])
    diff_staged = client.get(f"/api/projects/{pid}/git/diff", params={"file": "notes.md", "staged": True}).json()
    assert "+hello" in diff_staged["diff"]

    unstaged = client.post(f"/api/projects/{pid}/git/unstage", json={"files": ["notes.md"]}).json()
    assert not any(x["path"] == "notes.md" for x in unstaged["staged"])

    client.post(f"/api/projects/{pid}/git/stage", json={"all": True})
    committed = client.post(f"/api/projects/{pid}/git/commit", json={"message": "feat: add local git commit"})
    assert committed.status_code == 201
    new_sha = committed.json()["sha"]
    assert committed.json()["stats"]["files"] >= 2

    detail = client.get(f"/api/projects/{pid}/commits/{new_sha}").json()
    assert detail["subject"] == "feat: add local git commit"
    assert any(f["path"] == "notes.md" for f in detail["files"])
