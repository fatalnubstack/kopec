import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc, text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Climb

Base.metadata.create_all(bind=engine)

# Jednoduchá migrace — přidá sloupec city pokud ještě neexistuje
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE climbs ADD COLUMN city VARCHAR"))
        conn.commit()
except Exception:
    pass  # sloupec už existuje

app = FastAPI(title="Bořen Tracker")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
security = HTTPBasic()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "boren2024")

BLACKLIST = {
    "pica","picus","píca","píčus","zmrd","kokot","kunda","pizda",
    "negr","cigan","cigán","nigger","retard","debil","idiot","píča",
    "kurva","courat","curat","hovno","srac","srač","zkurvysyn","bastard",
}

def contains_banned(text_: str) -> bool:
    normalized = text_.lower()
    for word in BLACKLIST:
        if word in normalized:
            return True
    return False


# ── helpers ──────────────────────────────────────────────────────────────────

def period_cutoff(days: Optional[int]) -> Optional[datetime]:
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def build_leaderboard(db: Session, days: Optional[int] = None):
    cutoff = period_cutoff(days)

    q = db.query(Climb).filter(Climb.completed == True)  # noqa: E712
    if cutoff:
        q = q.filter(Climb.finish_time >= cutoff)

    fastest = (
        q.order_by(Climb.duration_seconds.asc())
        .limit(20)
        .all()
    )

    count_q = db.query(
        Climb.name,
        func.count(Climb.id).label("total"),
        func.min(Climb.duration_seconds).label("best"),
    ).filter(Climb.completed == True)  # noqa: E712
    if cutoff:
        count_q = count_q.filter(Climb.finish_time >= cutoff)

    most = (
        count_q.group_by(Climb.name)
        .order_by(desc("total"))
        .limit(20)
        .all()
    )

    return fastest, most


def fmt_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# ── pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/preview-siluety", response_class=HTMLResponse)
async def preview_siluety(request: Request):
    return templates.TemplateResponse("preview_siluety.html", {"request": request})


@app.get("/preview-pocasi", response_class=HTMLResponse)
async def preview_pocasi(request: Request):
    return templates.TemplateResponse("preview_pocasi.html", {"request": request})


@app.get("/start", response_class=HTMLResponse)
async def start_page(request: Request):
    return templates.TemplateResponse("start.html", {"request": request})


@app.get("/finish", response_class=HTMLResponse)
async def finish_page(request: Request):
    return templates.TemplateResponse("finish.html", {"request": request})


@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request):
    return templates.TemplateResponse("leaderboard.html", {"request": request})


# ── API ───────────────────────────────────────────────────────────────────────

@app.post("/api/start")
async def api_start(name: str = Form(...), city: str = Form(""), db: Session = Depends(get_db)):
    name = name.strip()
    city = city.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Jméno nesmí být prázdné")
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="Jméno je příliš dlouhé")
    if len(city) > 60:
        raise HTTPException(status_code=400, detail="Název města je příliš dlouhý")
    if contains_banned(name) or contains_banned(city):
        raise HTTPException(status_code=400, detail="Jméno obsahuje nevhodné slovo")

    climb = Climb(name=name, city=city or None, start_time=datetime.now(timezone.utc))
    db.add(climb)
    db.commit()
    db.refresh(climb)

    return {"climb_id": climb.id, "name": climb.name, "city": climb.city, "start_time": climb.start_time.isoformat()}


@app.post("/api/finish")
async def api_finish(climb_id: int = Form(...), db: Session = Depends(get_db)):
    climb = db.get(Climb, climb_id)
    if not climb:
        raise HTTPException(status_code=404, detail="Záznam nenalezen")
    if climb.completed:
        # Already finished — return existing result
        return {
            "name": climb.name,
            "duration_seconds": climb.duration_seconds,
            "duration_fmt": fmt_duration(climb.duration_seconds),
            "already_finished": True,
        }

    now = datetime.now(timezone.utc)
    start = climb.start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    duration = int((now - start).total_seconds())

    if duration < 300:
        raise HTTPException(status_code=400, detail="Čas je příliš krátký. Na Bořen se chodí průměrně 30 minut.")

    climb.finish_time = now
    climb.duration_seconds = duration
    climb.completed = True
    db.commit()

    # Rank in all-time fastest
    rank = (
        db.query(func.count(Climb.id))
        .filter(Climb.completed == True, Climb.duration_seconds < duration)  # noqa: E712
        .scalar()
    ) + 1

    return {
        "name": climb.name,
        "duration_seconds": duration,
        "duration_fmt": fmt_duration(duration),
        "rank": rank,
        "already_finished": False,
    }


@app.get("/api/stats")
async def api_stats(db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    count = (
        db.query(func.count(Climb.id))
        .filter(Climb.completed == True, Climb.finish_time >= cutoff)  # noqa: E712
        .scalar()
    )
    return {"last_24h": count}


@app.get("/api/leaderboard")
async def api_leaderboard(days: Optional[int] = None, db: Session = Depends(get_db)):
    fastest, most = build_leaderboard(db, days)

    return {
        "fastest": [
            {
                "rank": i + 1,
                "name": c.name,
                "city": c.city or "",
                "duration_seconds": c.duration_seconds,
                "duration_fmt": fmt_duration(c.duration_seconds),
                "date": c.finish_time.strftime("%d.%m.%Y") if c.finish_time else "",
            }
            for i, c in enumerate(fastest)
        ],
        "most": [
            {
                "rank": i + 1,
                "name": row.name,
                "total": row.total,
                "best_fmt": fmt_duration(row.best) if row.best else "—",
            }
            for i, row in enumerate(most)
        ],
    }


# ── admin ─────────────────────────────────────────────────────────────────────

def check_admin(credentials: HTTPBasicCredentials = Depends(security)):
    ok = secrets.compare_digest(credentials.password.encode(), ADMIN_PASSWORD.encode())
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Špatné heslo",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db), _=Depends(check_admin)):
    climbs = db.query(Climb).order_by(desc(Climb.start_time)).limit(200).all()
    rows = [
        {
            "id": c.id,
            "name": c.name,
            "start": c.start_time.strftime("%d.%m.%Y %H:%M"),
            "finish": c.finish_time.strftime("%d.%m.%Y %H:%M") if c.finish_time else "—",
            "duration": fmt_duration(c.duration_seconds) if c.duration_seconds else "—",
            "completed": c.completed,
        }
        for c in climbs
    ]
    return templates.TemplateResponse("admin.html", {"request": request, "rows": rows})


@app.post("/admin/delete/{climb_id}")
async def admin_delete(climb_id: int, db: Session = Depends(get_db), _=Depends(check_admin)):
    climb = db.get(Climb, climb_id)
    if not climb:
        raise HTTPException(status_code=404, detail="Záznam nenalezen")
    db.delete(climb)
    db.commit()
    return RedirectResponse("/admin", status_code=303)
