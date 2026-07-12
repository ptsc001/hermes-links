"""
Hermes Links – Glassmorphism Backend (unter /links/ prefix)
"""
import os, secrets, json, re
from datetime import datetime, timezone
from typing import Optional
import aiosqlite

from fastapi import FastAPI, HTTPException, Depends, Header, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import jinja2

# ── App Setup ──────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(BASE_DIR, "hermes-links.db")
API_KEY = os.environ.get("HERMES_LINKS_KEY") or "hl_" + secrets.token_urlsafe(24)

app = FastAPI(title="Hermes Links", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,
)

# ── Static files unter /links/static/ ──────────────────────────────

app.mount("/links/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Database ───────────────────────────────────────────────────────

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT NOT NULL,
            title       TEXT DEFAULT '',
            note        TEXT DEFAULT '',
            tags        TEXT DEFAULT '[]',
            category    TEXT DEFAULT '',
            is_read     INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_links_created ON links(created_at DESC)")
    await db.commit()
    return db

# ── Auth ────────────────────────────────────────────────────────────

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True

# ── Models ──────────────────────────────────────────────────────────

class LinkCreate(BaseModel):
    url: str
    title: str = ""
    note: str = ""

class LinkUpdate(BaseModel):
    title: Optional[str] = None
    note: Optional[str] = None
    tags: Optional[list[str]] = None
    category: Optional[str] = None
    is_read: Optional[bool] = None
    is_favorite: Optional[bool] = None

# ── Helpers ─────────────────────────────────────────────────────────

def extract_domain(url: str) -> str:
    match = re.search(r'https?://([^/]+)', url)
    return match.group(1) if match else url

# ── API Endpoints ───────────────────────────────────────────────────

@app.get("/links/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

@app.post("/links/api/links", dependencies=[Depends(verify_api_key)])
async def create_link(link: LinkCreate):
    if not link.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")
    now = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    await db.execute(
        "INSERT INTO links (url, title, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (link.url, link.title or extract_domain(link.url), link.note, now, now),
    )
    await db.commit()
    row = await db.execute("SELECT * FROM links ORDER BY id DESC LIMIT 1")
    result = dict(await row.fetchone())
    await db.close()
    return {"status": "created", "link": result}

@app.get("/links/api/links", dependencies=[Depends(verify_api_key)])
async def list_links(
    category: Optional[str] = Query(None),
    is_read: Optional[bool] = Query(None),
    is_favorite: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    limit: int = Query(50),
    offset: int = Query(0),
):
    db = await get_db()
    where = []
    params = []
    if category:
        where.append("category = ?")
        params.append(category)
    if is_read is not None:
        where.append("is_read = ?")
        params.append(1 if is_read else 0)
    if is_favorite is not None:
        where.append("is_favorite = ?")
        params.append(1 if is_favorite else 0)
    if search:
        where.append("(title LIKE ? OR note LIKE ? OR url LIKE ?)")
        params.extend([f"%{search}%"] * 3)

    sql_where = " AND ".join(where) if where else "1=1"
    sort_col = sort if sort in ("created_at", "title", "url") else "created_at"
    sort_dir = "ASC" if order.lower() == "asc" else "DESC"

    rows = await db.execute(
        f"SELECT * FROM links WHERE {sql_where} ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    results = [dict(r) for r in await rows.fetchall()]

    count_row = await db.execute(f"SELECT COUNT(*) FROM links WHERE {sql_where}", params)
    total = (await count_row.fetchone())[0]

    await db.close()
    return {"links": results, "total": total, "limit": limit, "offset": offset}

@app.get("/links/api/links/{link_id}", dependencies=[Depends(verify_api_key)])
async def get_link(link_id: int):
    db = await get_db()
    row = await db.execute("SELECT * FROM links WHERE id = ?", (link_id,))
    result = await row.fetchone()
    await db.close()
    if not result:
        raise HTTPException(status_code=404, detail="Link not found")
    return dict(result)

@app.patch("/links/api/links/{link_id}", dependencies=[Depends(verify_api_key)])
async def update_link(link_id: int, update: LinkUpdate):
    db = await get_db()
    existing = await db.execute("SELECT * FROM links WHERE id = ?", (link_id,))
    if not await existing.fetchone():
        await db.close()
        raise HTTPException(status_code=404, detail="Link not found")

    updates = []
    params = []
    if update.title is not None:
        updates.append("title = ?")
        params.append(update.title)
    if update.note is not None:
        updates.append("note = ?")
        params.append(update.note)
    if update.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(update.tags))
    if update.category is not None:
        updates.append("category = ?")
        params.append(update.category)
    if update.is_read is not None:
        updates.append("is_read = ?")
        params.append(1 if update.is_read else 0)
    if update.is_favorite is not None:
        updates.append("is_favorite = ?")
        params.append(1 if update.is_favorite else 0)

    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(link_id)
        await db.execute(f"UPDATE links SET {', '.join(updates)} WHERE id = ?", params)
        await db.commit()

    row = await db.execute("SELECT * FROM links WHERE id = ?", (link_id,))
    result = dict(await row.fetchone())
    await db.close()
    return {"status": "updated", "link": result}

@app.delete("/links/api/links/{link_id}", dependencies=[Depends(verify_api_key)])
async def delete_link(link_id: int):
    db = await get_db()
    await db.execute("DELETE FROM links WHERE id = ?", (link_id,))
    await db.commit()
    await db.close()
    return {"status": "deleted"}

@app.get("/links/api/stats", dependencies=[Depends(verify_api_key)])
async def stats():
    db = await get_db()
    total = await db.execute("SELECT COUNT(*) FROM links")
    unread = await db.execute("SELECT COUNT(*) FROM links WHERE is_read = 0")
    categories = await db.execute(
        "SELECT category, COUNT(*) as cnt FROM links GROUP BY category ORDER BY cnt DESC"
    )
    cats = {r["category"]: r["cnt"] for r in await categories.fetchall()}
    await db.close()
    return {"total": (await total.fetchone())[0], "unread": (await unread.fetchone())[0], "categories": cats}

@app.get("/links/api/config")
async def config():
    return {"app_name": "Hermes Links", "version": "1.0.0"}

# ── Frontend Dashboard ──────────────────────────────────────────────

@app.get("/links", response_class=HTMLResponse)
@app.get("/links/", response_class=HTMLResponse)
async def dashboard(request: Request):
    tmpl = jinja_env.get_template("dashboard.html")
    return HTMLResponse(content=tmpl.render(api_key=API_KEY))

if __name__ == "__main__":
    import uvicorn
    print(f"\n  🚀  Hermes Links API gestartet")
    print(f"  🔑  API Key: {API_KEY}")
    print(f"  📡  http://127.0.0.1:8877/links\n")
    uvicorn.run(app, host="127.0.0.1", port=8877)
