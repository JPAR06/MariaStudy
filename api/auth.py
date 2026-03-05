"""JWT auth dependency — used by all protected routes."""
import logging
import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

_raw = os.getenv("SECRET_KEY")
if not _raw:
    logger.critical(
        "SECRET_KEY env var is not set — using insecure default. "
        "Set SECRET_KEY in your .env before any public deployment."
    )
SECRET_KEY: str = _raw or "mariastudy-dev-secret-change-in-prod"
ALGORITHM = "HS256"

_bearer = HTTPBearer(auto_error=False)


def require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Returns the username from a valid Bearer token, or raises 401."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Token em falta")
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Token inválido")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
