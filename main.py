"""Hermes Brain v2.1 – Universal Inbox
Verschlüsselt, passwortgeschützt, multi-type (notes/links/images/voice).
"""
import os, re, json, secrets, shutil
from datetime import datetime, timezone
from typing import Optional
import mimetypes
import aiosqlite

from fastapi import FastAPI, HTTPException, Depends, Header, Request, Query, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import auth
import crypto

# ── App Setup ──────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "brain.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Hermes Brain", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
static_dir = os.path.join(BASE_DIR, "static")
if os.path.exists(static_dir):
    app.mount("/brain/static", StaticFiles(directory=static_dir), name="brain_static")

crypto.init_encryption(auth.get_master_password())

# ── Database ───────────────────────────────────────────────────────

DB_MIGRATIONS = [
    # v2.1: add type + metadata columns
    "ALTER TABLE notes ADD COLUMN item_type TEXT DEFAULT 'note'",
    "ALTER TABLE notes ADD COLUMN metadata_json TEXT DEFAULT ''",
]

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            encrypted_text  TEXT NOT NULL,
            category        TEXT DEFAULT '',
            has_date        INTEGER DEFAULT 0,
            extracted_date  TEXT,
            action_taken    TEXT DEFAULT '',
            is_done         INTEGER DEFAULT 0,
            is_processed    INTEGER DEFAULT 0,
            source          TEXT DEFAULT 'web',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
    """)
    # Run migrations (safe: ignore errors on already-existing columns)
    for mig in DB_MIGRATIONS:
        try:
            await db.execute(mig)
        except Exception:
            pass
    await db.execute("CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at DESC)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_notes_type ON notes(item_type)")
    await db.commit()
    return db


# ── Auth Dependencies ──────────────────────────────────────────────

async def require_session(request: Request):
    token = request.cookies.get(auth.SESSION_COOKIE)
    if not token or not auth.verify_session(token):
        return RedirectResponse(url="/brain/login", status_code=302)
    return True

async def optional_api_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key is not None:
        if not auth.verify_api_key(x_api_key):
            raise HTTPException(status_code=403, detail="Invalid API key")
        return "api_key"
    return None


# ── Helpers ────────────────────────────────────────────────────────

TYPE_ICONS = {'note': '📝', 'link': '🔗', 'image': '🖼️', 'voice': '🎤', 'message': '💬'}
CAT_ICONS = {'meeting': '📅', 'todo': '📌', 'idea': '💡', 'private': '👤', 'business': '💼'}
CAT_LABELS = {'meeting': 'Termin', 'todo': 'Aufgabe', 'idea': 'Idee', 'private': 'Privat', 'business': 'Business'}

async def fetch_link_title(url: str) -> str:
    """Fetch a webpage title for link preview."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                m = re.search(r'<title[^>]*>([^<]+)</title>', resp.text, re.IGNORECASE)
                if m:
                    return m.group(1).strip()[:200]
    except Exception:
        pass
    return url  # fallback: just show the URL

def extract_date_info(text: str) -> tuple:
    today = datetime.now(timezone.utc)
    t = text.lower()
    if "übermorgen" in t:
        dt = today.replace(hour=9, minute=0, second=0, microsecond=0)
        dt = dt.replace(day=dt.day + 2)
        return (True, dt.isoformat())
    if "morgen" in t:
        dt = today.replace(hour=9, minute=0, second=0, microsecond=0)
        dt = dt.replace(day=dt.day + 1)
        return (True, dt.isoformat())
    if "heute" in t:
        return (True, today.isoformat())
    time_match = re.search(r'(\d{1,2})[.:](\d{2})\s*(?:uhr)?', t)
    if time_match:
        hour, minute = int(time_match.group(1)), int(time_match.group(2))
        dt = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return (True, dt.isoformat())
    hour_match = re.search(r'(?:um\s+)?(\d{1,2})\s*uhr', t)
    if hour_match:
        dt = today.replace(hour=int(hour_match.group(1)), minute=0, second=0, microsecond=0)
        return (True, dt.isoformat())
    date_match = re.search(r'(\d{1,2})[.](\d{1,2})(?:[.](\d{2,4}))?', text)
    if date_match:
        day, month = int(date_match.group(1)), int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            from datetime import date
            d = date(year, month, day)
            dt = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
            return (True, dt.isoformat())
        except ValueError:
            pass
    return (False, "")

def classify_text(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["meeting", "termin", "call", "besprechung", "gespräch"]):
        return "meeting"
    if any(w in t for w in ["todo", "erledigen", "machen", "checken", "anschauen", "prüfen"]):
        return "todo"
    if any(w in t for w in ["idee", "vorschlag", "könnte man", "was wäre"]):
        return "idea"
    if any(w in t for w in ["privat", "bio", "einkaufen", "familie", "kind", "arzt",
                              "garten", "rasen", "pflanzen", "blumen", "helfen",
                              "sandra", "freund", "partner", "eltern", "mutter",
                              "vater", "schwester", "bruder", "oma", "opa"]):
        return "private"
    return "business"

def classify_type(text: str) -> str:
    """Detect if text is a link or regular note."""
    text = text.strip()
    if re.match(r'^https?://', text, re.IGNORECASE):
        return "link"
    return "note"


# ── Web Pages ──────────────────────────────────────────────────────

@app.get("/brain/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token and auth.verify_session(token):
        return RedirectResponse(url="/brain/", status_code=302)
    return templates.TemplateResponse(request, "login.html")

@app.post("/brain/login")
async def login_submit(request: Request, password: str = Form(...)):
    if auth.verify_password(password):
        session_token = auth.create_session()
        resp = RedirectResponse(url="/brain/", status_code=302)
        resp.set_cookie(
            key=auth.SESSION_COOKIE,
            value=session_token,
            max_age=30 * 86400,
            httponly=True,
            secure=False,
            samesite="lax",
        )
        return resp
    return templates.TemplateResponse(
        request, "login.html", {"error": "Falsches Passwort"}, status_code=403,
    )

@app.get("/brain/logout")
async def logout():
    resp = RedirectResponse(url="/brain/login", status_code=302)
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp

@app.get("/brain", response_class=HTMLResponse)
@app.get("/brain/", response_class=HTMLResponse)
async def dashboard(request: Request):
    token = request.cookies.get(auth.SESSION_COOKIE)
    if not token or not auth.verify_session(token):
        return RedirectResponse(url="/brain/login", status_code=302)
    return templates.TemplateResponse(request, "dashboard.html")


# ── Core Processing ────────────────────────────────────────────────

async def _save_item(item_type: str, text: str, category: str = "",
                     metadata: dict = None, source: str = "web") -> dict:
    """Save any item type to the database."""
    encrypted = crypto.encrypt(text)
    has_date, extracted_date = extract_date_info(text)
    now = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)

    if not category:
        category = classify_text(text)

    db = await get_db()
    await db.execute(
        """INSERT INTO notes
           (encrypted_text, category, item_type, metadata_json,
            has_date, extracted_date, source, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (encrypted, category, item_type, meta_json,
         1 if has_date else 0, extracted_date, source, now, now),
    )
    await db.commit()
    row = await db.execute("SELECT * FROM notes ORDER BY id DESC LIMIT 1")
    item = dict(await row.fetchone())
    await db.close()

    item["text"] = crypto.decrypt(item.pop("encrypted_text"))
    item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
    return item

async def _load_items(item_type: str = None, limit: int = 50, offset: int = 0) -> list:
    """Load items with optional type filter."""
    db = await get_db()
    if item_type and item_type != "all":
        rows = await db.execute(
            "SELECT * FROM notes WHERE item_type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (item_type, limit, offset),
        )
    else:
        rows = await db.execute(
            "SELECT * FROM notes ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    items = []
    for r in await rows.fetchall():
        item = dict(r)
        try:
            item["text"] = crypto.decrypt(item.pop("encrypted_text"))
        except Exception:
            continue
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        items.append(item)
    await db.close()
    return items


# ── Session-Auth Endpoints (Web Dashboard) ─────────────────────────

@app.post("/brain/dump")
async def brain_dump(dump: dict, _=Depends(require_session)):
    """Submit a brain dump (auto-detect type)."""
    text = dump.get("text", "").strip()
    source = dump.get("source", "web")
    if not text:
        raise HTTPException(400, "Text required")

    item_type = classify_type(text)
    if item_type == "link":
        title = await fetch_link_title(text)
        item = await _save_item("link", text, metadata={"url": text, "title": title}, source=source)
    else:
        item = await _save_item("note", text, source=source)
    return {"status": "ok", "item": item}

@app.post("/brain/dump/link")
async def brain_dump_link(dump: dict, _=Depends(require_session)):
    """Explicitly save a link with preview."""
    url = dump.get("url", "").strip()
    if not url:
        raise HTTPException(400, "URL required")
    note = dump.get("note", "")
    title = await fetch_link_title(url)
    item = await _save_item("link", url, metadata={"url": url, "title": title, "note": note}, source="web")
    return {"status": "ok", "item": item}

@app.post("/brain/dump/image")
async def brain_dump_image(
    request: Request,
    file: UploadFile = File(...),
    note: str = Form(""),
    _=Depends(require_session),
):
    """Upload an image for processing."""
    # Validate file type
    ext = os.path.splitext(file.filename or ".jpg")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"):
        raise HTTPException(400, "Nicht unterstütztes Bildformat")

    # Save file
    file_id = secrets.token_hex(8)
    filename = f"{file_id}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # Basic metadata
    img_url = f"/brain/static/uploads/{filename}"
    meta = {
        "filename": filename,
        "path": filepath,
        "url": img_url,
        "size": len(content),
        "mime": file.content_type or "image/jpeg",
        "note": note,
    }

    item = await _save_item("image", note or f"Bild: {file.filename}",
                            metadata=meta, source="web")
    return {"status": "ok", "item": item}

@app.get("/brain/history")
async def brain_history(
    type: str = Query("all"),
    limit: int = Query(50),
    offset: int = Query(0),
    _=Depends(require_session),
):
    items = await _load_items(item_type=type, limit=limit, offset=offset)
    return {"items": items, "count": len(items)}

@app.delete("/brain/item/{item_id}")
async def delete_item(item_id: int, _=Depends(require_session)):
    """Delete an item from the database."""
    db = await get_db()
    # Get metadata to clean up any stored files
    row = await db.execute("SELECT metadata_json, item_type FROM notes WHERE id = ?", (item_id,))
    item = await row.fetchone()
    if not item:
        await db.close()
        raise HTTPException(404, "Item not found")

    meta = json.loads(item["metadata_json"] or "{}")
    # Delete associated file if it's an image
    if item["item_type"] == "image" and meta.get("path"):
        try:
            os.remove(meta["path"])
        except Exception:
            pass

    await db.execute("DELETE FROM notes WHERE id = ?", (item_id,))
    await db.commit()
    await db.close()
    return {"status": "ok", "deleted": item_id}


# ── API Endpoints (for Siri Shortcuts / Hermes) ────────────────────

@app.post("/brain/api/dump")
async def api_brain_dump(dump: dict, api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if not api_key or not auth.verify_api_key(api_key):
        raise HTTPException(403, "Valid API key required")
    text = dump.get("text", "").strip()
    source = dump.get("source", "api")
    if not text:
        raise HTTPException(400, "Text required")
    item_type = classify_type(text)
    if item_type == "link":
        title = await fetch_link_title(text)
        item = await _save_item("link", text, metadata={"url": text, "title": title}, source=source)
    else:
        item = await _save_item("note", text, source=source)
    return {"status": "ok", "item": item}

@app.get("/brain/api/health")
async def api_health():
    return {"status": "ok", "version": "2.1.0", "app": "Hermes Brain"}

@app.get("/brain/api/pending")
async def api_pending(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if not api_key or not auth.verify_api_key(api_key):
        raise HTTPException(403, "Valid API key required")
    items = await _load_items(limit=20)
    return {"items": [i for i in items if not i["is_processed"]], "count": 0}

@app.post("/brain/api/process/{item_id}")
async def api_mark_processed(
    item_id: int,
    action_taken: str = Form(""),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    if not api_key or not auth.verify_api_key(api_key):
        raise HTTPException(403, "Valid API key required")
    now = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    await db.execute(
        "UPDATE notes SET is_processed = 1, action_taken = ?, updated_at = ? WHERE id = ?",
        (action_taken, now, item_id),
    )
    await db.commit()
    await db.close()
    return {"status": "ok"}


# ── Legacy redirects ───────────────────────────────────────────────

@app.get("/links", response_class=HTMLResponse)
@app.get("/links/", response_class=HTMLResponse)
async def legacy_redirect():
    return RedirectResponse(url="/brain/", status_code=302)

@app.get("/links/api/health")
async def legacy_health():
    return await api_health()


# ── Start ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    pw = auth.get_master_password()
    ak = auth.get_api_key()
    print(f"\n  🧠  Hermes Brain v2.1 — Universal Inbox")
    print(f"  🔑  Passwort: {pw}")
    print(f"  🔐  API Key:  {ak}")
    print(f"  📡  http://127.0.0.1:8877/brain")
    print(f"  📁  Uploads:  {UPLOAD_DIR}\n")
    uvicorn.run(app, host="127.0.0.1", port=8877)
