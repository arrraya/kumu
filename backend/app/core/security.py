"""Password hashing, tokens, and resolving who is asking.

Kumu was a single public dataset until now. Everything here exists so that a
request can be attributed to an organisation, because that is what makes
"your players" mean anything.
"""
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 12
PUBLIC_SLUG = "public"

# Set JWT_SECRET in the environment. The fallback exists so a local checkout
# runs, and is deliberately obvious in logs if it ever reaches production.
SECRET_KEY = os.environ.get("JWT_SECRET", "insecure-development-secret-change-me")

# auto_error=False so anonymous callers reach the endpoint instead of being
# rejected: the public dataset stays browsable without an account, which is
# what keeps the demo usable.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _prepare(password: str) -> bytes:
    """bcrypt refuses anything over 72 bytes, and silently ignoring the excess
    would make two different long passwords interchangeable. Hashing first
    gives a fixed-length input, so passwords of any length work and none is
    truncated."""
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return digest.encode("ascii")


def hash_password(password: str) -> str:
    """bcrypt is used directly rather than through passlib: passlib has been
    unmaintained since 2020 and breaks against current bcrypt releases, which
    would have failed in production exactly as it did locally."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def create_access_token(user: models.User) -> str:
    payload = {
        "sub": str(user.id),
        "org": user.organization_id,
        "email": user.email,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_public_org_id(db: Session) -> Optional[int]:
    org = (
        db.query(models.Organization)
        .filter(models.Organization.slug == PUBLIC_SLUG)
        .first()
    )
    return org.id if org else None


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """Whoever is asking, or None for an anonymous visitor."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        return None
    if not user_id:
        return None
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    return user if user and user.is_active else None


def require_user(
    user: Optional[models.User] = Depends(get_current_user),
) -> models.User:
    """For anything that writes. Anonymous visitors read; they never write."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def readable_org_ids(
    user: Optional[models.User] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """Which tenants the caller may read: their own, plus the public one.

    A client needs the public population to have anything to compare against
    before they upload data of their own, and an anonymous visitor sees only
    the public set.
    """
    ids = []
    public_id = get_public_org_id(db)
    if public_id:
        ids.append(public_id)
    if user and user.organization_id not in ids:
        ids.append(user.organization_id)
    return ids


def writable_org_id(user: models.User = Depends(require_user)) -> int:
    """Where a write lands: always the caller's own organisation."""
    return user.organization_id
