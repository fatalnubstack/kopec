import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, Request, Form, File, UploadFile, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc, text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Climb, WallPost

Base.metadata.create_all(bind=engine)

# Migrace — přidá sloupce pokud neexistují
for stmt in [
    "ALTER TABLE climbs ADD COLUMN city VARCHAR",
    "ALTER TABLE climbs ADD COLUMN group_size INTEGER NOT NULL DEFAULT 1",
]:
    try:
        with engine.connect() as conn:
            conn.execute(text(stmt))
            conn.commit()
    except Exception:
        pass

# Upload adresář — odvozený ze stejného místa jako SQLite databáze (= Railway volume)
_db_url = os.getenv("DATABASE_URL", "sqlite:///./data/boren.db")
if _db_url.startswith("sqlite:///"):
    _db_path = _db_url.replace("sqlite:///", "")
    DATA_DIR = os.path.dirname(os.path.abspath(_db_path))
else:
    DATA_DIR = os.getenv("DATA_DIR", "app/data")

UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MAX_PHOTO_BYTES = 8 * 1024 * 1024  # 8 MB

app = FastAPI(title="Bořen Tracker")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
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


@app.get("/preview-ikony", response_class=HTMLResponse)
async def preview_ikony(request: Request):
    return templates.TemplateResponse("preview_ikony.html", {"request": request})


@app.get("/preview-skupina", response_class=HTMLResponse)
async def preview_skupina(request: Request):
    return templates.TemplateResponse("preview_skupina.html", {"request": request})


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


@app.get("/nastenka", response_class=HTMLResponse)
async def nastenka_page(request: Request):
    return templates.TemplateResponse("nastenka.html", {"request": request})


# ── API ───────────────────────────────────────────────────────────────────────

def cleanup_expired_climbs(db: Session):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    db.query(Climb).filter(
        Climb.completed == False,  # noqa: E712
        Climb.start_time < cutoff,
    ).delete()
    db.commit()


@app.post("/api/start")
async def api_start(name: str = Form(...), city: str = Form(""), group_size: int = Form(1), db: Session = Depends(get_db)):
    cleanup_expired_climbs(db)

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
    group_size = max(1, min(99, group_size))

    climb = Climb(name=name, city=city or None, start_time=datetime.now(timezone.utc), group_size=group_size)
    db.add(climb)
    db.commit()
    db.refresh(climb)

    return {"climb_id": climb.id, "name": climb.name, "city": climb.city, "start_time": climb.start_time.isoformat(), "group_size": climb.group_size}


@app.post("/api/finish")
async def api_finish(climb_id: int = Form(...), db: Session = Depends(get_db)):
    climb = db.get(Climb, climb_id)
    if not climb:
        raise HTTPException(status_code=404, detail="Záznam nenalezen")
    if climb.completed:
        return {
            "name": climb.name,
            "duration_seconds": climb.duration_seconds,
            "duration_fmt": fmt_duration(climb.duration_seconds),
            "group_size": climb.group_size,
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

    rank = (
        db.query(func.count(Climb.id))
        .filter(Climb.completed == True, Climb.duration_seconds < duration)  # noqa: E712
        .scalar()
    ) + 1

    return {
        "name": climb.name,
        "duration_seconds": duration,
        "duration_fmt": fmt_duration(duration),
        "group_size": climb.group_size,
        "rank": rank,
        "already_finished": False,
    }


@app.get("/api/stats")
async def api_stats(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)

    def count_since(dt):
        return (
            db.query(func.coalesce(func.sum(Climb.group_size), 0))
            .filter(Climb.completed == True, Climb.finish_time >= dt)  # noqa: E712
            .scalar()
        )

    today_start   = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start    = now - timedelta(days=now.weekday())
    week_start    = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start   = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return {
        "last_24h": count_since(now - timedelta(hours=24)),
        "today":    count_since(today_start),
        "week":     count_since(week_start),
        "month":    count_since(month_start),
    }


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


@app.post("/api/wall")
async def api_wall_post(
    name: str = Form(...),
    climb_id: Optional[int] = Form(None),
    duration_fmt: Optional[str] = Form(None),
    mood: Optional[int] = Form(None),
    message: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    name = name.strip()[:80]
    if not name:
        raise HTTPException(status_code=400, detail="Jméno nesmí být prázdné")
    if contains_banned(name):
        raise HTTPException(status_code=400, detail="Jméno obsahuje nevhodné slovo")
    if message:
        message = message.strip()[:500]
        if contains_banned(message):
            raise HTTPException(status_code=400, detail="Vzkaz obsahuje nevhodné slovo")
    if mood is not None and not (1 <= mood <= 5):
        mood = None

    photo_filename = None
    if photo and photo.filename:
        ext = os.path.splitext(photo.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400, detail="Nepodporovaný formát fotky (použij JPG nebo PNG)")
        content = await photo.read()
        if len(content) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=400, detail="Fotka je příliš velká (max 8 MB)")
        photo_filename = f"{secrets.token_hex(16)}{ext}"
        with open(os.path.join(UPLOAD_DIR, photo_filename), "wb") as f:
            f.write(content)

    post = WallPost(
        name=name,
        climb_id=climb_id,
        duration_fmt=duration_fmt,
        mood=mood,
        message=message or None,
        photo_filename=photo_filename,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    return {"ok": True, "post_id": post.id}


@app.get("/api/wall")
async def api_wall_list(db: Session = Depends(get_db)):
    posts = db.query(WallPost).order_by(desc(WallPost.created_at)).limit(50).all()
    MOOD_EMOJI = {1: "😮‍💨", 2: "😕", 3: "🙂", 4: "😄", 5: "🤩"}
    return [
        {
            "id": p.id,
            "name": p.name,
            "duration_fmt": p.duration_fmt or "",
            "mood": p.mood,
            "mood_emoji": MOOD_EMOJI.get(p.mood, "") if p.mood else "",
            "message": p.message or "",
            "photo_url": f"/uploads/{p.photo_filename}" if p.photo_filename else None,
            "date": p.created_at.strftime("%d.%m.%Y"),
        }
        for p in posts
    ]


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

    MOOD_EMOJI = {1: "😮‍💨", 2: "😕", 3: "🙂", 4: "😄", 5: "🤩"}
    wall_posts = db.query(WallPost).order_by(desc(WallPost.created_at)).limit(200).all()
    posts = [
        {
            "id": p.id,
            "name": p.name,
            "date": p.created_at.strftime("%d.%m.%Y %H:%M"),
            "mood": MOOD_EMOJI.get(p.mood, "—") if p.mood else "—",
            "message": p.message or "—",
            "photo_filename": p.photo_filename or "",
            "duration_fmt": p.duration_fmt or "—",
        }
        for p in wall_posts
    ]

    # Analytika — dokončené výstupy
    completed = db.query(Climb).filter(Climb.completed == True).all()  # noqa: E712

    DAY_NAMES = ["Pondělí","Úterý","Středa","Čtvrtek","Pátek","Sobota","Neděle"]
    by_day   = [0] * 7
    by_hour  = [0] * 24
    by_day_hour = {}  # (day, hour) -> count

    for c in completed:
        ft = c.finish_time
        if ft is None:
            continue
        if ft.tzinfo is None:
            ft = ft.replace(tzinfo=timezone.utc)
        # Převod na pražský čas (UTC+1 nebo UTC+2, použijeme jednoduše +1)
        local = ft + timedelta(hours=1)
        d = local.weekday()   # 0=Po … 6=Ne
        h = local.hour
        by_day[d]  += 1
        by_hour[h] += 1
        by_day_hour[(d, h)] = by_day_hour.get((d, h), 0) + 1

    # Peak den a hodina
    peak_day  = DAY_NAMES[by_day.index(max(by_day))]  if any(by_day)  else "—"
    peak_hour = f"{by_hour.index(max(by_hour))}:00"   if any(by_hour) else "—"
    peak_combo = max(by_day_hour, key=by_day_hour.get) if by_day_hour else None
    peak_combo_str = f"{DAY_NAMES[peak_combo[0]]} {peak_combo[1]}:00" if peak_combo else "—"

    max_day  = max(by_day)  if any(by_day)  else 1
    max_hour = max(by_hour) if any(by_hour) else 1

    analytics = {
        "total": len(completed),
        "by_day":  [{"day": DAY_NAMES[i], "count": by_day[i],  "bar": int(by_day[i]  / max_day  * 120)} for i in range(7)],
        "by_hour": [{"hour": f"{i}:00",   "count": by_hour[i], "bar": int(by_hour[i] / max_hour * 120)} for i in range(24)],
        "peak_day": peak_day,
        "peak_hour": peak_hour,
        "peak_combo": peak_combo_str,
    }

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "rows": rows,
        "posts": posts,
        "analytics": analytics,
    })


@app.post("/admin/delete/{climb_id}")
async def admin_delete(climb_id: int, db: Session = Depends(get_db), _=Depends(check_admin)):
    climb = db.get(Climb, climb_id)
    if not climb:
        raise HTTPException(status_code=404, detail="Záznam nenalezen")
    db.delete(climb)
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/wall/delete/{post_id}")
async def admin_wall_delete(post_id: int, db: Session = Depends(get_db), _=Depends(check_admin)):
    post = db.get(WallPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Příspěvek nenalezen")
    if post.photo_filename:
        try:
            os.remove(os.path.join(UPLOAD_DIR, post.photo_filename))
        except FileNotFoundError:
            pass
    db.delete(post)
    db.commit()
    return RedirectResponse("/admin", status_code=303)
