"""Create local demo users once; passwords are random and saved outside version control."""
import secrets
from pathlib import Path

from sqlalchemy import select

from .config import ROOT, Settings
from .models import User, database
from .security import PASSWORDS


def bootstrap(settings=None, credential_file: Path | None = None):
    settings = settings or Settings.from_env()
    credential_file = credential_file or ROOT / "data/local/demo-credentials.txt"
    engine, sessions = database(settings.database_url)
    created = []
    try:
        with sessions() as db:
            for name, role in (("developer", "developer"), ("reviewer", "reviewer")):
                if db.scalar(select(User).where(User.username == name)):
                    continue
                password = secrets.token_urlsafe(18)
                db.add(User(username=name, role=role, password_hash=PASSWORDS.hash(password)))
                created.append((name, password))
            if created:
                credential_file.parent.mkdir(parents=True, exist_ok=True)
                with credential_file.open("a", encoding="utf-8") as output:
                    output.write("\n".join(f"{name}: {password}" for name, password in created) + "\n")
                db.commit()
    finally:
        engine.dispose()
    return len(created), credential_file


if __name__ == "__main__":
    count, path = bootstrap()
    print(f"Created {count} demo accounts. Credentials: {path}")
