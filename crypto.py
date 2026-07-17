"""
Hermes Brain – Encryption Layer
Fernet (AES-128-CBC + HMAC-SHA256) + PBKDF2 Key Derivation
"""
import os, base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# ── Key Management ──────────────────────────────────────────────

_encryption_key: bytes | None = None
_key_salt: bytes | None = None
_SALT_FILE = os.path.join(os.path.dirname(__file__), ".brain_salt")


def _load_or_create_salt() -> bytes:
    """Load existing salt from disk or create one."""
    if os.path.exists(_SALT_FILE):
        with open(_SALT_FILE, "rb") as f:
            return f.read()
    salt = os.urandom(16)
    with open(_SALT_FILE, "wb") as f:
        f.write(salt)
    return salt


def _derive_key(master_secret: str) -> tuple[bytes, bytes]:
    """Derive a Fernet key from the master secret using PBKDF2-HMAC-SHA256.

    Returns: (key, salt) where key is base64-urlsafe-encoded 32 bytes.
    """
    salt = _load_or_create_salt()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,  # OWASP recommended minimum
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_secret.encode()))
    return key, salt


def init_encryption(master_secret: str):
    """Initialize encryption with the master password-derived key."""
    global _encryption_key, _key_salt
    _encryption_key, _key_salt = _derive_key(master_secret)


def is_initialized() -> bool:
    return _encryption_key is not None


# ── Encrypt / Decrypt ────────────────────────────────────────────


def encrypt(text: str) -> str:
    """Encrypt plaintext → Fernet token (base64 string).

    Returns empty string on empty input.
    """
    if not text:
        return ""
    if _encryption_key is None:
        raise RuntimeError("Encryption not initialized")
    f = Fernet(_encryption_key)
    return f.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt Fernet token → plaintext.

    Returns empty string on empty input.
    """
    if not token:
        return ""
    if _encryption_key is None:
        raise RuntimeError("Encryption not initialized")
    f = Fernet(_encryption_key)
    return f.decrypt(token.encode()).decode()
