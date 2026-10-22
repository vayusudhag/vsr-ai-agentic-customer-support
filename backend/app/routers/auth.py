from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import LoginIn
from app.security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    return {"access_token": create_access_token(u), "token_type": "bearer", "user": user_out(u)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.get("/demo-accounts")
def demo_accounts():
    """Synthetic demo credentials (shown on the sign-in screen)."""
    return [
        {"label": "Pardha Saradhi (customer)", "email": "pardha.saradhi@example.com", "password": "demo1234"},
        {"label": "Pavan Y (customer)", "email": "pavan.y@example.com", "password": "demo1234"},
        {"label": "Gopireddy VSR (admin)", "email": "gopireddy.vsr@example.com", "password": "admin1234"},
    ]
