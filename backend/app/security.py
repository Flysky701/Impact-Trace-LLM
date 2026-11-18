import hashlib
import secrets
import time

from pwdlib import PasswordHash
from sqlalchemy import select

from .models import User

PASSWORDS = PasswordHash.recommended()
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def timestamp():
    return int(time.time())


def authenticate(db, username, password):
    user = db.scalar(select(User).where(User.username == username))
    valid = PASSWORDS.verify(password, user.password_hash if user else DUMMY_HASH)
    return user if valid and user else None
