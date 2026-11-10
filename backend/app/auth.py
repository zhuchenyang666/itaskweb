import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .database import CHINA
from .models import LoginSession, User
from .security import hash_password, token_hash, verify_password

router = APIRouter(prefix="/api/auth", tags=["认证"])
COOKIE = "itime_session"


def get_db(request: Request):
    yield from request.app.state.database.session()


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class PasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


def public_user(user):
    return {key: getattr(user, key) for key in ("id", "username", "name", "position", "role", "must_change_password")}


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    login = db.get(LoginSession, token_hash(token)) if token else None
    if not login or login.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(401, "登录已过期，请重新登录")
    user = db.get(User, login.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "账号已停用")
    return user


@router.post("/login")
def login(body: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    stored = user.password_hash if user else request.app.state.dummy_password
    valid = verify_password(body.password, stored)
    if not user or not valid or not user.is_active:
        raise HTTPException(401, "账号或密码错误，或账号已停用")
    now = datetime.now(CHINA)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    expires = midnight.astimezone(timezone.utc)
    token = secrets.token_urlsafe(32)
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(old)))
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now.astimezone(timezone.utc).replace(tzinfo=None)))
    db.add(LoginSession(token_hash=token_hash(token), user_id=user.id, expires_at=expires.replace(tzinfo=None)))
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", expires=expires, path="/api")
    return public_user(user)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return public_user(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(token)))
        db.commit()
    response.delete_cookie(COOKIE, path="/api")


@router.post("/password", status_code=204)
def change_password(body: PasswordInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "当前密码不正确")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = body.new_password == "123456"
    db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    db.commit()
