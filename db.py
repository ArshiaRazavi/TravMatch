# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)   # <— important
except Exception:
    pass

DB_URL = os.getenv("DATABASE_URL", "sqlite:///travmatch.db")

# SQLite needs this connect arg
if DB_URL.startswith("sqlite"):
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DB_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
