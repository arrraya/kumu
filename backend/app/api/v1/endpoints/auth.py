"""Sign-up, login, and who am I."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core import security
from app.db import models
from app.db.database import get_db

router = APIRouter()


class SignupRequest(BaseModel):
    organization_name: str = Field(..., min_length=2)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    # Consent for the aggregate benchmark, asked at sign-up because asking
    # later is far harder — and because the benchmark is what makes Kumu worth
    # more than the sum of its clients.
    allows_aggregate: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    organization: str
    email: str


def _slugify(name: str) -> str:
    base = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return base[:50] or "org"


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Create an organisation and its first user.

    Sign-up creates an ORGANISATION, not a lone user: a club is several people
    sharing one dataset, and modelling that later would mean migrating every row.
    """
    existing = db.query(models.User).filter(models.User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="That email is already registered")

    slug = _slugify(request.organization_name)
    if db.query(models.Organization).filter(models.Organization.slug == slug).first():
        suffix = db.query(models.Organization).count() + 1
        slug = f"{slug}-{suffix}"

    org = models.Organization(
        name=request.organization_name,
        slug=slug,
        kind="client",
        allows_aggregate=request.allows_aggregate,
    )
    db.add(org)
    db.flush()

    user = models.User(
        organization_id=org.id,
        email=request.email,
        password_hash=security.hash_password(request.password),
        full_name=request.full_name,
        role="owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=security.create_access_token(user),
        organization=org.name,
        email=user.email,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.email).first()
    # Same message either way: distinguishing "no such account" from "wrong
    # password" tells an attacker which emails are registered.
    if not user or not security.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled")

    return TokenResponse(
        access_token=security.create_access_token(user),
        organization=user.organization.name,
        email=user.email,
    )


@router.get("/me")
def me(user: Optional[models.User] = Depends(security.get_current_user)):
    """Who the caller is. Anonymous visitors get a body saying so rather than
    a 401, because browsing the public dataset without an account is allowed."""
    if not user:
        return {"authenticated": False, "scope": "public reference data only"}
    return {
        "authenticated": True,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "organization": {
            "id": user.organization_id,
            "name": user.organization.name,
            "allows_aggregate": user.organization.allows_aggregate,
        },
    }
