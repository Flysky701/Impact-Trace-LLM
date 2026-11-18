import json
import secrets
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import git_service as git, llm_service, repo_analyzer
from .config import Settings
from .models import (
    AnalysisTask, LoginSession, MaintenanceNote, Project,
    RepoOverview, ReviewRecord, User, database,
)
from .security import authenticate, timestamp, token_digest

COOKIE = "impact_session"


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    repository_path: str = Field(min_length=1, max_length=1000)
    reviewer_id: int | None = None


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    reviewer_id: int | None = None


class LlmSettingsInput(BaseModel):
    provider: str = Field(default="openai_compatible", max_length=40)
    base_url: str = Field(min_length=1, max_length=300)
    model: str = Field(min_length=1, max_length=120)
    api_key: str = Field(default="", max_length=400)
    clear_key: bool = False


class OverviewGenerateInput(BaseModel):
    revision: str = Field(default="HEAD", min_length=1, max_length=200)
    use_llm: bool = True


class AnalysisInput(BaseModel):
    task_type: Literal["commit_compare", "ai_change"] = "commit_compare"
    title: str = Field(min_length=1, max_length=200)
    user_prompt: str = Field(default="", max_length=4000)
    raw_log: str = Field(default="", max_length=12000)
    base_ref: str = Field(default="HEAD~1", min_length=1, max_length=200)
    head_ref: str = Field(default="HEAD", min_length=1, max_length=200)
    use_llm: bool = False


class ReviewInput(BaseModel):
    verdict: Literal["approved", "attention", "needs_work"]
    comment: str = Field(min_length=1, max_length=4000)
    test_status: Literal["not_run", "passed", "failed", "blocked"] = "not_run"
    test_notes: str = Field(default="", max_length=4000)


class NoteInput(BaseModel):
    target_type: Literal["module", "flow", "file", "symbol"] = "module"
    target_key: str = Field(min_length=1, max_length=300)
    target_label: str = Field(min_length=1, max_length=200)
    kind: Literal["pitfall", "refactor", "note"] = "pitfall"
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=4000)


class NoteUpdate(BaseModel):
    resolved: bool


class AskInput(BaseModel):
    question: str = Field(min_length=1, max_length=1500)
    revision: str = Field(default="HEAD", min_length=1, max_length=200)
    target_path: str = Field(default="", max_length=500)
    target_line: int = Field(default=0, ge=0, le=200000)
    target_label: str = Field(default="", max_length=200)


class GitStageInput(BaseModel):
    files: list[str] = Field(default_factory=list)
    all: bool = False


class GitCommitInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def user_json(user):
    return {"id": user.id, "username": user.username, "role": user.role}


def project_json(project):
    return {key: getattr(project, key) for key in (
        "id", "name", "description", "repository_path", "owner_id", "reviewer_id", "created_at"
    )}


def review_json(row: ReviewRecord, users_by_id: dict[int, User]):
    author = users_by_id.get(row.author_id)
    return {
        "id": row.id,
        "task_id": row.task_id,
        "author_id": row.author_id,
        "author_username": author.username if author else f"user-{row.author_id}",
        "verdict": row.verdict,
        "comment": row.comment,
        "test_status": row.test_status,
        "test_notes": row.test_notes,
        "created_at": row.created_at,
    }


def note_json(row: MaintenanceNote, users_by_id: dict[int, User]):
    author = users_by_id.get(row.author_id)
    return {
        "id": row.id,
        "project_id": row.project_id,
        "author_id": row.author_id,
        "author_username": author.username if author else f"user-{row.author_id}",
        "target_type": row.target_type,
        "target_key": row.target_key,
        "target_label": row.target_label,
        "kind": row.kind,
        "title": row.title,
        "content": row.content,
        "resolved": bool(row.resolved),
        "created_at": row.created_at,
    }


def task_summary_json(task: AnalysisTask, review_count: int = 0, latest_verdict: str | None = None):
    data = json.loads(task.result_json)
    return {
        "id": task.id,
        "project_id": task.project_id,
        "created_by": task.created_by,
        "task_type": task.task_type,
        "title": task.title,
        "user_prompt": task.user_prompt,
        "base_ref": task.base_ref,
        "head_ref": task.head_ref,
        "base_sha": task.base_sha,
        "head_sha": task.head_sha,
        "status": task.status,
        "llm_status": task.llm_status,
        "headline": data.get("plainSummary", {}).get("headline", ""),
        "diagnostics": data.get("diagnostics", {}),
        "review_count": review_count,
        "latest_verdict": latest_verdict,
        "created_at": task.created_at,
    }


def task_detail_json(task: AnalysisTask, reviews: list[dict]):
    return {
        **task_summary_json(task, len(reviews), reviews[0]["verdict"] if reviews else None),
        "raw_log": task.raw_log,
        "result": json.loads(task.result_json),
        "reviews": reviews,
    }


def create_app(settings=None):
    settings = settings or Settings.from_env()
    engine, sessions = database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_):
        yield
        engine.dispose()

    app = FastAPI(title="ImpactTrace", lifespan=lifespan)
    app.state.sessions = sessions
    app.state.settings = settings
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.middleware("http")
    async def protect_mutations(request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("x-requested-with") != "ImpactTrace":
                return JSONResponse({"detail": "请求缺少同源操作标识。"}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "不允许跨站修改数据。"}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(git.RepositoryError)
    async def repository_error(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(llm_service.LLMError)
    async def llm_error(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    def db_session():
        with sessions() as db:
            yield db

    def current_user(request: Request, db=Depends(db_session)):
        token = request.cookies.get(COOKIE, "")
        session = db.get(LoginSession, token_digest(token)) if token else None
        if not session or session.expires_at <= timestamp():
            if session:
                db.delete(session)
                db.commit()
            raise HTTPException(401, "请登录，或会话已过期。")
        user = db.get(User, session.user_id)
        if not user:
            raise HTTPException(401, "账号不可用。")
        return user

    def developer(user=Depends(current_user)):
        if user.role != "developer":
            raise HTTPException(403, "只有开发者可以执行此操作。")
        return user

    def reviewer_role(user=Depends(current_user)):
        if user.role != "reviewer":
            raise HTTPException(403, "只有审核者可以提交风险审核结论。")
        return user

    def project_access(project_id: int, user=Depends(current_user), db=Depends(db_session)):
        project = db.get(Project, project_id)
        if not project or user.id not in (project.owner_id, project.reviewer_id):
            raise HTTPException(404, "项目不存在或无权访问。")
        return project

    def project_repository(project=Depends(project_access)):
        return git.repository_path(project.repository_path, settings.repository_roots)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "stage": "comprehension-workbench"}

    @app.post("/api/auth/login")
    def login(data: Credentials, request: Request, response: Response, db=Depends(db_session)):
        user = authenticate(db, data.username, data.password)
        if not user:
            raise HTTPException(401, "用户名或密码错误。")
        old = request.cookies.get(COOKIE)
        previous = db.get(LoginSession, token_digest(old)) if old else None
        if previous:
            db.delete(previous)
        token = secrets.token_urlsafe(32)
        db.add(LoginSession(token_hash=token_digest(token), user_id=user.id,
                            expires_at=timestamp() + settings.session_seconds))
        db.commit()
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict",
                            secure=settings.secure_cookies, max_age=settings.session_seconds)
        return user_json(user)

    @app.get("/api/auth/me")
    def me(user=Depends(current_user)):
        return user_json(user)

    @app.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response, db=Depends(db_session)):
        token = request.cookies.get(COOKIE)
        row = db.get(LoginSession, token_digest(token)) if token else None
        if row:
            db.delete(row)
            db.commit()
        response.delete_cookie(COOKIE)

    @app.get("/api/reviewers")
    def reviewers(_=Depends(developer), db=Depends(db_session)):
        return [user_json(u) for u in db.scalars(select(User).where(User.role == "reviewer"))]

    @app.get("/api/config")
    def config(_=Depends(developer)):
        return {"repository_roots": [str(p) for p in settings.repository_roots]}

    @app.get("/api/settings/llm")
    def read_llm_settings(_=Depends(current_user), db=Depends(db_session)):
        return llm_service.public_llm_config(llm_service.get_llm_config(db, settings))

    @app.put("/api/settings/llm")
    def update_llm_settings(data: LlmSettingsInput, _=Depends(developer), db=Depends(db_session)):
        cfg = llm_service.save_llm_config(
            db, settings, data.provider, data.base_url, data.model,
            api_key=data.api_key, clear_key=data.clear_key,
        )
        return llm_service.public_llm_config(cfg)

    @app.post("/api/settings/llm/test")
    def test_llm_settings(data: LlmSettingsInput, _=Depends(developer), db=Depends(db_session)):
        saved = llm_service.get_llm_config(db, settings)
        probe_cfg = {
            "provider": data.provider,
            "base_url": data.base_url.strip(),
            "model": data.model.strip(),
            "api_key": "" if data.clear_key else (data.api_key.strip() or saved["api_key"]),
        }
        return llm_service.test_connection(probe_cfg)

    @app.get("/api/projects")
    def projects(user=Depends(current_user), db=Depends(db_session)):
        rows = db.scalars(select(Project).where(or_(Project.owner_id == user.id,
                                                    Project.reviewer_id == user.id)).order_by(Project.id.desc()))
        return [project_json(p) for p in rows]

    @app.post("/api/projects", status_code=201)
    def create_project(data: ProjectInput, user=Depends(developer), db=Depends(db_session)):
        if not data.name.strip():
            raise HTTPException(422, "项目名称不能为空。")
        if data.reviewer_id is not None:
            reviewer = db.get(User, data.reviewer_id)
            if not reviewer or reviewer.role != "reviewer":
                raise HTTPException(422, "请选择有效的审核者。")
        path = git.repository_path(data.repository_path, settings.repository_roots)
        project = Project(name=data.name.strip(), description=data.description.strip(),
                          repository_path=str(path), owner_id=user.id, reviewer_id=data.reviewer_id,
                          created_at=timestamp())
        db.add(project)
        db.commit()
        return project_json(project)

    @app.get("/api/projects/{project_id}")
    def get_project(project=Depends(project_access)):
        return project_json(project)

    @app.patch("/api/projects/{project_id}")
    def update_project(data: ProjectUpdate, project=Depends(project_access),
                       user=Depends(developer), db=Depends(db_session)):
        if project.owner_id != user.id:
            raise HTTPException(403, "只有项目创建者可以修改项目信息。")
        if not data.name.strip():
            raise HTTPException(422, "项目名称不能为空。")
        if data.reviewer_id is not None:
            reviewer = db.get(User, data.reviewer_id)
            if not reviewer or reviewer.role != "reviewer":
                raise HTTPException(422, "请选择有效的审核者。")
        project.name = data.name.strip()
        project.description = data.description.strip()
        project.reviewer_id = data.reviewer_id
        db.commit()
        return project_json(project)

    @app.get("/api/projects/{project_id}/refs")
    def list_refs(path=Depends(project_repository)):
        return git.refs(path)

    @app.get("/api/projects/{project_id}/commits")
    def commits(revision: str = "HEAD", offset: int = Query(0, ge=0, le=100000),
                limit: int = Query(20, ge=1, le=50), path=Depends(project_repository)):
        return git.history(path, revision, offset, limit)

    @app.get("/api/projects/{project_id}/commits/{revision}")
    def get_commit_detail(revision: str, path=Depends(project_repository)):
        return git.commit_detail(path, revision)

    @app.get("/api/projects/{project_id}/git/status")
    def get_git_status(path=Depends(project_repository)):
        return git.worktree_status(path)

    @app.get("/api/projects/{project_id}/git/diff")
    def get_git_diff(file: str, staged: bool = False, path=Depends(project_repository)):
        return git.worktree_diff(path, file, staged=staged)

    @app.post("/api/projects/{project_id}/git/stage")
    def stage_git_files(data: GitStageInput, _=Depends(developer), path=Depends(project_repository)):
        return git.stage_files(path, data.files, all_changes=data.all)

    @app.post("/api/projects/{project_id}/git/unstage")
    def unstage_git_files(data: GitStageInput, _=Depends(developer), path=Depends(project_repository)):
        return git.unstage_files(path, data.files, all_changes=data.all)

    @app.post("/api/projects/{project_id}/git/commit", status_code=201)
    def commit_git_changes(data: GitCommitInput, _=Depends(developer), path=Depends(project_repository)):
        return git.create_commit(path, data.message)

    @app.get("/api/projects/{project_id}/files")
    def files(revision: str, limit: int = Query(1000, ge=1, le=5000), path=Depends(project_repository)):
        return git.tree(path, revision, limit=limit)

    @app.get("/api/projects/{project_id}/source")
    def read_source(revision: str, file: str, path=Depends(project_repository)):
        return git.source(path, revision, file)

    @app.get("/api/projects/{project_id}/overview")
    def get_overview(revision: str = "HEAD", project=Depends(project_access),
                     path=Depends(project_repository), db=Depends(db_session)):
        resolved = "WORKTREE" if revision == "WORKTREE" else git.resolve_revision(path, revision)
        if resolved != "WORKTREE":
            cached = db.scalar(
                select(RepoOverview)
                .where(RepoOverview.project_id == project.id, RepoOverview.revision == resolved)
                .order_by(RepoOverview.id.desc())
            )
            if cached:
                return json.loads(cached.overview_json)

        lang, profile, snap = repo_analyzer.load_snapshot(path, resolved)
        overview, _, _ = repo_analyzer.build_plain_overview(project.name, lang, profile, snap)
        if resolved != "WORKTREE":
            db.add(RepoOverview(
                project_id=project.id, revision=resolved, language=lang,
                source_mode="heuristic", model_name="",
                overview_json=json.dumps(overview, ensure_ascii=False),
                created_at=timestamp(),
            ))
            db.commit()
        return overview

    @app.post("/api/projects/{project_id}/overview/generate")
    def generate_overview(data: OverviewGenerateInput, project=Depends(project_access),
                          path=Depends(project_repository), db=Depends(db_session)):
        resolved = "WORKTREE" if data.revision == "WORKTREE" else git.resolve_revision(path, data.revision)
        lang, profile, snap = repo_analyzer.load_snapshot(path, resolved)
        overview, valid_paths, llm_pack = repo_analyzer.build_plain_overview(project.name, lang, profile, snap)
        source_mode, model_name = "heuristic", ""
        if data.use_llm:
            cfg = llm_service.get_llm_config(db, settings)
            overview = llm_service.generate_overview_with_llm(cfg, llm_pack, valid_paths, overview)
            source_mode, model_name = "llm", cfg["model"]

        if resolved != "WORKTREE":
            existing = db.scalar(
                select(RepoOverview)
                .where(RepoOverview.project_id == project.id, RepoOverview.revision == resolved)
                .order_by(RepoOverview.id.desc())
            )
            if existing:
                existing.source_mode = source_mode
                existing.model_name = model_name
                existing.overview_json = json.dumps(overview, ensure_ascii=False)
                existing.created_at = timestamp()
            else:
                db.add(RepoOverview(
                    project_id=project.id, revision=resolved, language=lang,
                    source_mode=source_mode, model_name=model_name,
                    overview_json=json.dumps(overview, ensure_ascii=False),
                    created_at=timestamp(),
                ))
            db.commit()
        return overview

    @app.get("/api/projects/{project_id}/analyses")
    def list_analyses(project=Depends(project_access), db=Depends(db_session)):
        tasks = list(db.scalars(
            select(AnalysisTask).where(AnalysisTask.project_id == project.id).order_by(AnalysisTask.id.desc())
        ))
        if not tasks:
            return []
        task_ids = [t.id for t in tasks]
        counts = dict(db.execute(
            select(ReviewRecord.task_id, func.count(ReviewRecord.id))
            .where(ReviewRecord.task_id.in_(task_ids))
            .group_by(ReviewRecord.task_id)
        ).all())
        latest_verdict = {}
        for rev in db.scalars(
            select(ReviewRecord).where(ReviewRecord.task_id.in_(task_ids)).order_by(ReviewRecord.id.desc())
        ):
            latest_verdict.setdefault(rev.task_id, rev.verdict)
        return [task_summary_json(t, counts.get(t.id, 0), latest_verdict.get(t.id)) for t in tasks]

    @app.post("/api/projects/{project_id}/analyses", status_code=201)
    def create_analysis(data: AnalysisInput, project=Depends(project_access),
                        path=Depends(project_repository), user=Depends(developer), db=Depends(db_session)):
        if not data.title.strip():
            raise HTTPException(422, "请填写变更说明或任务标题。")
        if data.task_type == "ai_change" and not data.user_prompt.strip():
            raise HTTPException(422, "记录 AI 修改任务时，请填写当时提出的修改要求。")
        cfg = llm_service.get_llm_config(db, settings)
        result = repo_analyzer.analyze_change(
            path, project.name, data.base_ref.strip(), data.head_ref.strip(),
            user_prompt=data.user_prompt.strip(), llm_cfg=cfg, use_llm=data.use_llm,
        )
        task = AnalysisTask(
            project_id=project.id,
            created_by=user.id,
            task_type=data.task_type,
            title=data.title.strip(),
            user_prompt=data.user_prompt.strip(),
            raw_log=data.raw_log.strip(),
            base_ref=data.base_ref.strip(),
            head_ref=data.head_ref.strip(),
            base_sha=result["baseSha"],
            head_sha=result["headSha"],
            status=result["status"],
            llm_status=result["llmStatus"],
            result_json=json.dumps(result, ensure_ascii=False),
            created_at=timestamp(),
        )
        db.add(task)
        db.commit()
        return task_detail_json(task, [])

    @app.get("/api/projects/{project_id}/analyses/{task_id}")
    def get_analysis(task_id: int, project=Depends(project_access), db=Depends(db_session)):
        task = db.get(AnalysisTask, task_id)
        if not task or task.project_id != project.id:
            raise HTTPException(404, "审阅记录不存在。")
        rows = list(db.scalars(
            select(ReviewRecord).where(ReviewRecord.task_id == task.id).order_by(ReviewRecord.id.desc())
        ))
        users_map = {u.id: u for u in db.scalars(select(User))} if rows else {}
        return task_detail_json(task, [review_json(r, users_map) for r in rows])

    @app.post("/api/projects/{project_id}/analyses/{task_id}/explain")
    def explain_analysis(task_id: int, project=Depends(project_access),
                         path=Depends(project_repository), db=Depends(db_session)):
        task = db.get(AnalysisTask, task_id)
        if not task or task.project_id != project.id:
            raise HTTPException(404, "审阅记录不存在。")
        cfg = llm_service.get_llm_config(db, settings)
        updated = repo_analyzer.analyze_change(
            path, project.name, task.base_sha, task.head_sha,
            user_prompt=task.user_prompt, llm_cfg=cfg, use_llm=True,
        )
        if updated["llmStatus"] == "not_configured":
            raise llm_service.LLMError("尚未配置 API Key，请先在右上角「AI 模型设置」中填入密钥。")
        if updated["llmStatus"] == "failed":
            raise llm_service.LLMError(updated["plainSummary"].get("llmError") or "AI 解读生成未完成。")
        task.llm_status = updated["llmStatus"]
        task.status = updated["status"]
        task.result_json = json.dumps(updated, ensure_ascii=False)
        db.commit()
        rows = list(db.scalars(
            select(ReviewRecord).where(ReviewRecord.task_id == task.id).order_by(ReviewRecord.id.desc())
        ))
        users_map = {u.id: u for u in db.scalars(select(User))} if rows else {}
        return task_detail_json(task, [review_json(r, users_map) for r in rows])

    @app.post("/api/projects/{project_id}/analyses/{task_id}/reviews", status_code=201)
    def create_review(task_id: int, data: ReviewInput, project=Depends(project_access),
                      user=Depends(reviewer_role), db=Depends(db_session)):
        task = db.get(AnalysisTask, task_id)
        if not task or task.project_id != project.id:
            raise HTTPException(404, "审阅记录不存在。")
        if not data.comment.strip():
            raise HTTPException(422, "请填写具体的审阅意见。")
        if data.test_status != "not_run" and not data.test_notes.strip():
            raise HTTPException(422, "记录测试结果时，请补充验证步骤或结果说明。")
        record = ReviewRecord(
            task_id=task.id,
            author_id=user.id,
            verdict=data.verdict,
            comment=data.comment.strip(),
            test_status=data.test_status,
            test_notes=data.test_notes.strip(),
            created_at=timestamp(),
        )
        db.add(record)
        db.commit()
        return review_json(record, {user.id: user})

    @app.get("/api/projects/{project_id}/notes")
    def list_notes(project=Depends(project_access), db=Depends(db_session)):
        rows = list(db.scalars(
            select(MaintenanceNote).where(MaintenanceNote.project_id == project.id).order_by(MaintenanceNote.id.desc())
        ))
        users_map = {u.id: u for u in db.scalars(select(User))} if rows else {}
        return [note_json(r, users_map) for r in rows]

    @app.post("/api/projects/{project_id}/notes", status_code=201)
    def create_note(data: NoteInput, project=Depends(project_access),
                    user=Depends(current_user), db=Depends(db_session)):
        if not data.title.strip() or not data.content.strip():
            raise HTTPException(422, "便签标题与内容不能为空。")
        note = MaintenanceNote(
            project_id=project.id,
            author_id=user.id,
            target_type=data.target_type,
            target_key=data.target_key.strip(),
            target_label=data.target_label.strip(),
            kind=data.kind,
            title=data.title.strip(),
            content=data.content.strip(),
            resolved=0,
            created_at=timestamp(),
        )
        db.add(note)
        db.commit()
        return note_json(note, {user.id: user})

    @app.patch("/api/projects/{project_id}/notes/{note_id}")
    def update_note(note_id: int, data: NoteUpdate, project=Depends(project_access),
                    _=Depends(current_user), db=Depends(db_session)):
        note = db.get(MaintenanceNote, note_id)
        if not note or note.project_id != project.id:
            raise HTTPException(404, "维护便签不存在。")
        note.resolved = 1 if data.resolved else 0
        db.commit()
        users_map = {u.id: u for u in db.scalars(select(User).where(User.id == note.author_id))}
        return note_json(note, users_map)

    @app.delete("/api/projects/{project_id}/notes/{note_id}", status_code=204)
    def delete_note(note_id: int, project=Depends(project_access),
                    _=Depends(current_user), db=Depends(db_session)):
        note = db.get(MaintenanceNote, note_id)
        if not note or note.project_id != project.id:
            raise HTTPException(404, "维护便签不存在。")
        db.delete(note)
        db.commit()

    @app.post("/api/projects/{project_id}/ask")
    def ask_repo(data: AskInput, project=Depends(project_access),
                 path=Depends(project_repository), db=Depends(db_session)):
        if not data.question.strip():
            raise HTTPException(422, "请输入你想了解的问题。")
        active_notes = [
            {"title": n.title, "content": n.content, "target_label": n.target_label}
            for n in db.scalars(
                select(MaintenanceNote).where(MaintenanceNote.project_id == project.id, MaintenanceNote.resolved == 0)
            )
        ]
        cfg = llm_service.get_llm_config(db, settings)
        return repo_analyzer.ask_repository(
            path, project.name, data.question.strip(), revision=data.revision.strip(),
            target_path=data.target_path.strip(), target_line=data.target_line,
            target_label=data.target_label.strip(), notes=active_notes, llm_cfg=cfg,
        )

    if settings.frontend_dist.is_dir():
        app.mount("/assets", StaticFiles(directory=settings.frontend_dist / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(settings.frontend_dist / "index.html")

    return app
