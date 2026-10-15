import hashlib
import hmac
import secrets
import time

from fastapi import Request
from sqlmodel import Session

from app.security import signing_key
from app.services import settings_store

COOKIE = "pinakes_session"
MAX_AGE = 30 * 86400
MIN_LENGTH = 6
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
MAX_FAILS = 5
FAIL_WINDOW = 300

_fails: dict[str, list[float]] = {}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **SCRYPT)
    return hmac.compare_digest(calc.hex(), digest)


def _sign(expiry: int, stored: str) -> str:
    msg = f"{expiry}:{stored}".encode()
    return hmac.new(signing_key(), msg, hashlib.sha256).hexdigest()


def make_token(stored: str, now: float | None = None) -> str:
    expiry = int(now if now is not None else time.time()) + MAX_AGE
    return f"{expiry}.{_sign(expiry, stored)}"


def check_token(token: str, stored: str, now: float | None = None) -> bool:
    try:
        raw, sig = token.split(".", 1)
        expiry = int(raw)
    except ValueError:
        return False
    if expiry < (now if now is not None else time.time()):
        return False
    return hmac.compare_digest(sig, _sign(expiry, stored))


def stored_hash(session: Session) -> str:
    return settings_store.get_value(session, "auth_password")


def is_authenticated(request: Request, stored: str) -> bool:
    if not stored:
        return True
    return check_token(request.cookies.get(COOKIE, ""), stored)


def throttled(ip: str, now: float | None = None) -> bool:
    now = now if now is not None else time.time()
    recent = [t for t in _fails.get(ip, []) if now - t < FAIL_WINDOW]
    _fails[ip] = recent
    return len(recent) >= MAX_FAILS


def record_fail(ip: str) -> None:
    _fails.setdefault(ip, []).append(time.time())


def clear_fails(ip: str) -> None:
    _fails.pop(ip, None)
