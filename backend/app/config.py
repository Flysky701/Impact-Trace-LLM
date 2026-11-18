import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    repository_roots: tuple[Path, ...]
    session_seconds: int = 8 * 60 * 60
    secure_cookies: bool = False
    frontend_dist: Path = ROOT / "frontend" / "dist"
    llm_provider: str = "openai_compatible"
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    @classmethod
    def from_env(cls, env_file: Path | None = None):
        dotenv_path = env_file if env_file is not None else ROOT / ".env"
        if dotenv_path.is_file():
            load_dotenv(dotenv_path, override=False)
        local = ROOT / "data" / "local"
        local.mkdir(parents=True, exist_ok=True)
        roots = os.environ.get("IMPACT_REPOSITORY_ROOTS", str(local))
        return cls(
            database_url=os.environ.get("IMPACT_DATABASE_URL", f"sqlite:///{local / 'impacttrace.db'}"),
            repository_roots=tuple(Path(p).resolve() for p in roots.split(os.pathsep) if p.strip()),
            secure_cookies=os.environ.get("IMPACT_SECURE_COOKIES") == "1",
            llm_provider=os.environ.get("IMPACT_LLM_PROVIDER", "openai_compatible").strip() or "openai_compatible",
            llm_base_url=os.environ.get("IMPACT_LLM_BASE_URL", "https://api.deepseek.com/v1").strip(),
            llm_api_key=os.environ.get("IMPACT_LLM_API_KEY", "").strip(),
            llm_model=os.environ.get("IMPACT_LLM_MODEL", "deepseek-chat").strip() or "deepseek-chat",
        )
