import os
import json
import bcrypt
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException
from jose import jwt
from pydantic import BaseModel

SECRET_KEY = os.getenv("SECRET_KEY", "mariastudy-dev-secret-change-in-prod")
ALGORITHM = "HS256"
EXPIRE_DAYS = 30

router = APIRouter()

USERS_FILE = Path("data/users.json")


def _load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    return json.loads(USERS_FILE.read_text(encoding="utf-8"))


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    display_name: str


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest):
    users = _load_users()
    user = users.get(body.username)
    if not user or not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Utilizador ou senha incorretos")
    token = jwt.encode(
        {
            "sub": body.username,
            "exp": datetime.utcnow() + timedelta(days=EXPIRE_DAYS),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return {
        "token": token,
        "username": body.username,
        "display_name": user.get("display_name", body.username),
    }
