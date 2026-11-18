from sqlalchemy import ForeignKey, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(String(20))


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[int]


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(default="")
    repository_path: Mapped[str]
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[int]


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[int] = mapped_column(default=0)


class RepoOverview(Base):
    __tablename__ = "repo_overviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    revision: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(40))
    source_mode: Mapped[str] = mapped_column(String(30), default="heuristic")
    model_name: Mapped[str] = mapped_column(String(100), default="")
    overview_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int]


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    task_type: Mapped[str] = mapped_column(String(30), default="commit_compare")
    title: Mapped[str] = mapped_column(String(200))
    user_prompt: Mapped[str] = mapped_column(Text, default="")
    raw_log: Mapped[str] = mapped_column(Text, default="")
    base_ref: Mapped[str] = mapped_column(String(100))
    head_ref: Mapped[str] = mapped_column(String(100))
    base_sha: Mapped[str] = mapped_column(String(64))
    head_sha: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="completed")
    llm_status: Mapped[str] = mapped_column(String(30), default="not_requested")
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int]


class ReviewRecord(Base):
    __tablename__ = "review_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("analysis_tasks.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    verdict: Mapped[str] = mapped_column(String(30))
    comment: Mapped[str] = mapped_column(Text)
    test_status: Mapped[str] = mapped_column(String(30), default="not_run")
    test_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[int]


class MaintenanceNote(Base):
    __tablename__ = "maintenance_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    target_type: Mapped[str] = mapped_column(String(30), default="module")
    target_key: Mapped[str] = mapped_column(String(300))
    target_label: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), default="pitfall")
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    resolved: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[int]


def database(url):
    kwargs = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite://", "sqlite:///:memory:"):
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)
