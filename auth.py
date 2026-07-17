"""
Hermes Brain – Authentication Layer
- bcrypt password hashing
- Fernet-signed session tokens (stateless, survive restarts)
- API key for programmatic access (Siri Shortcuts, Hermes)
"""
import os, json, secrets, bcrypt
from datetime import datetime, timezone, timedelta
from cryptography.fernet import Fernet

# ── Password ────────────────────────────────────────────────────

_BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
_PASSWORD_FILE = os.path.join(_BRAIN_DIR, ".brain_password")

_MASTER_PASSWORD = os.environ.get("BRAIN_PASSWORD")
if not _MASTER_PASSWORD and os.path.exists(_PASSWORD_FILE):
    _MASTER_PASSWORD = open(_PASSWORD_FILE).read().strip()
if not _MASTER_PASSWORD:
    # Generate one on first run and save it
    _MASTER_PASSWORD = "brain_" + secrets.token_urlsafe(8)
    with open(_PASSWORD_FILE, "w") as f:
        f.write(_MASTER_PASSWORD + "\n")

# bcrypt hash of the password
_PASSWORD_HASH = bcrypt.hashpw(_MASTER_PASSWORD.encode(), bcrypt.gensalt(rounds=12))


def get_master_password() -> str:
    """Return the current master password (needed for encryption key init)."""
    return _MASTER_PASSWORD


def verify_password(password: str) -> bool:
    """Check a password attempt against the stored bcrypt hash."""
    return bcrypt.checkpw(password.encode(), _PASSWORD_HASH)


# ── API Key ──────────────────────────────────────────────────────

_API_KEY = os.environ.get("BRAIN_API_KEY") or "bk_" + secrets.token_urlsafe(32)


def get_api_key() -> str:
    return _API_KEY


def verify_api_key(key: str) -> bool:
    """Constant-time-ish comparison of API key."""
    return key == _API_KEY


# ── Session Tokens (Fernet-signed, stateless) ───────────────────

_SESSION_SECRET = Fernet.generate_key()
_session_fernet = Fernet(_SESSION_SECRET)
_SESSION_TTL = timedelta(days=30)


def create_session() -> str:
    """Create a signed session token valid for 30 days."""
    payload = json.dumps({
        "sub": "admin",
        "exp": (datetime.now(timezone.utc) + _SESSION_TTL).timestamp(),
        "jti": secrets.token_urlsafe(16),
    })
    return _session_fernet.encrypt(payload.encode()).decode()


def verify_session(token: str) -> bool:
    """Verify a session token. Returns True if valid and not expired."""
    try:
        raw = _session_fernet.decrypt(token.encode())
        data = json.loads(raw)
        exp = data.get("exp", 0)
        return exp > datetime.now(timezone.utc).timestamp()
    except Exception:
        return False


# ── Session Cookie Name ──────────────────────────────────────────

SESSION_COOKIE = "brain_session"
