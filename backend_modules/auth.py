"""Shared password gate for the small, single-process POC API.

Tokens live only in memory, so a Render restart signs everyone out.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import OrderedDict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/auth", tags=["access"])
bearer = HTTPBearer(auto_error=False)

TOKEN_SECONDS = 4 * 60 * 60
MAX_TOKENS = 8
MAX_FAILED_ATTEMPTS = 8
FAILED_WINDOW_SECONDS = 15 * 60

_tokens: OrderedDict[str, float] = OrderedDict()
_failed: dict[str, list[float]] = {}
_lock = threading.Lock()


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


def _password() -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).parents[1] / ".env", override=False)
    except ImportError:
        pass
    return os.getenv("POC_ACCESS_PASSWORD", "")


def _configured_password() -> str:
    password = _password()
    if len(password) < 12:
        raise HTTPException(status_code=503, detail="Demo access is not configured. Set POC_ACCESS_PASSWORD to at least 12 characters.")
    return password


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _cleanup(now: float) -> None:
    """Called with _lock held."""
    for digest, expires in list(_tokens.items()):
        if now >= expires:
            _tokens.pop(digest, None)
    for address, attempts in list(_failed.items()):
        recent = [attempt for attempt in attempts if now - attempt < FAILED_WINDOW_SECONDS]
        if recent:
            _failed[address] = recent
        else:
            _failed.pop(address, None)


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    """Dependency attached to every data router in backend_modules.main."""
    _configured_password()  # fail closed when the shared password is missing
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in to use this demo.", headers={"WWW-Authenticate": "Bearer"})
    with _lock:
        _cleanup(time.monotonic())
        if _digest(credentials.credentials) not in _tokens:
            raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.", headers={"WWW-Authenticate": "Bearer"})


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    expected = _configured_password()
    address = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        _cleanup(now)
        if len(_failed.get(address, [])) >= MAX_FAILED_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again later.")
        if not hmac.compare_digest(body.password.encode("utf-8"), expected.encode("utf-8")):
            _failed.setdefault(address, []).append(now)
            raise HTTPException(status_code=401, detail="Incorrect demo password.")
        token = secrets.token_urlsafe(32)
        _failed.pop(address, None)
        while len(_tokens) >= MAX_TOKENS:
            _tokens.popitem(last=False)
        _tokens[_digest(token)] = now + TOKEN_SECONDS
    response.headers["Cache-Control"] = "no-store"
    return {"token": token, "expires_in": TOKEN_SECONDS}


@router.get("/me", dependencies=[Depends(require_auth)])
def me(response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True}


@router.post("/logout", dependencies=[Depends(require_auth)])
def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    with _lock:
        _tokens.pop(_digest(credentials.credentials), None)
    return {"authenticated": False}
