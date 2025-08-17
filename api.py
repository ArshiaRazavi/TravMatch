# api.py — FastAPI search over scraped Telegram posts

import os
from datetime import date
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # <-- added
from sqlalchemy.orm import Session

# Load DB session + models
from db import SessionLocal
from models import Trip, Post

# Optional: load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = FastAPI(title="TravMatch API", version=os.getenv("APP_VERSION", "dev"))

# CORS (open while prototyping)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Serve ./static at /static/... (put your index.html there) ---
app.mount("/static", StaticFiles(directory="static"), name="static")  # <-- added

# ------------------- helpers -------------------

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _parse_iso_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None

# ------------------- endpoints -------------------

@app.get("/health")
def health() -> Dict[str, bool]:
    return {"ok": True}

@app.get("/version")
def version() -> Dict[str, str]:
    return {"version": os.getenv("APP_VERSION", "dev")}

@app.get("/search")
def search(
    origin: Optional[str] = Query(None, description="Origin IATA code, e.g., THR, IKA, YYZ"),
    destination: Optional[str] = Query(None, description="Destination IATA code"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    type_tag: Optional[str] = Query(None, description="e.g., 'مسافر' or 'قبول_بار'"),
    airline: Optional[str] = Query(None, description="Filter by airline text"),
    q: Optional[str] = Query(None, description="Free-text search in original post"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Search parsed trips. Use IATA codes for origin/destination if possible."""
    df = _parse_iso_date(date_from)
    dt = _parse_iso_date(date_to)

    db_gen = get_db()
    db = next(db_gen)

    try:
        qry = db.query(Trip, Post).join(Post, Trip.post_id == Post.id)

        if origin:
            qry = qry.filter(Trip.origin_code == origin.upper())
        if destination:
            qry = qry.filter(Trip.destination_code == destination.upper())
        if df:
            qry = qry.filter(Trip.flight_date >= df)
        if dt:
            qry = qry.filter(Trip.flight_date <= dt)
        if type_tag:
            qry = qry.filter(Post.type_tag == type_tag)
        if airline:
            qry = qry.filter(Trip.airline.ilike(f"%{airline}%"))
        if q:
            qry = qry.filter(Post.raw_text.ilike(f"%{q}%"))

        qry = qry.order_by(Trip.flight_date.is_(None), Trip.flight_date, Post.posted_at.desc())
        total = qry.count()
        rows = qry.offset(offset).limit(limit).all()

        results: List[Dict[str, Any]] = []
        for t, p in rows:
            contacts = sorted(set((p.contact_handles or []) + (p.contact_phones or [])))  # small dedupe
            results.append({
                "message_id": p.message_id,
                "posted_at": p.posted_at,
                "type": p.type_tag,
                "origin": t.origin_city,
                "origin_code": t.origin_code,
                "destination": t.destination_city,
                "destination_code": t.destination_code,
                "date": (None if t.flight_date is None else t.flight_date.isoformat()) or t.flight_date_text,
                "time": t.flight_time_text,
                "airline": t.airline,
                "contacts": contacts,
                "snippet": (p.raw_text or "")[:200],
            })

        return {
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": results,
        }

    finally:
        try:
            next(db_gen)  # close generator
        except StopIteration:
            pass
