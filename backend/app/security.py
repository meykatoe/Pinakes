import contextlib
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import settings


@lru_cache
def _key() -> bytes:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path = settings.data_dir / "secret.key"
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
        with contextlib.suppress(OSError):
            path.chmod(0o600)
    return path.read_bytes()


@lru_cache
def _fernet() -> Fernet:
    return Fernet(_key())


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def signing_key() -> bytes:
    return hashlib.sha256(b"pinakes-session:" + _key()).digest()
