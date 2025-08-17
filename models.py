# models.py (SQLite-friendly)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import (
    Column, Integer, Text, Boolean, Date, TIMESTAMP, ForeignKey
)
from sqlalchemy.sql import func
from sqlalchemy.types import JSON  # JSON works on SQLite (stored as TEXT)

Base = declarative_base()

class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = {"sqlite_autoincrement": True}

    id = Column(Integer, primary_key=True, autoincrement=True)   # <-- Integer
    telegram_id = Column(Integer, unique=True, index=True)       # can stay Integer for SQLite
    username = Column(Text)
    display_name = Column(Text)
    lang = Column(Text, default="fa")
    is_verified = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    posts = relationship("Post", backref="user", lazy="selectin")

class Post(Base):
    __tablename__ = "post"
    __table_args__ = {"sqlite_autoincrement": True}

    id = Column(Integer, primary_key=True, autoincrement=True)   # <-- Integer
    chat_id = Column(Integer, index=True, nullable=True)
    message_id = Column(Integer, index=True, nullable=True)
    posted_at = Column(TIMESTAMP(timezone=True))
    posted_by = Column(Integer, ForeignKey("app_user.id"))       # <-- Integer FK
    raw_text = Column(Text, nullable=False)
    lang = Column(Text)
    type_tag = Column(Text)
    contact_handles = Column(JSON)
    contact_phones  = Column(JSON)

    trip = relationship("Trip", uselist=False, backref="post", lazy="joined")

class Trip(Base):
    __tablename__ = "trip"
    __table_args__ = {"sqlite_autoincrement": True}

    id = Column(Integer, primary_key=True, autoincrement=True)   # <-- Integer
    post_id = Column(Integer, ForeignKey("post.id", ondelete="CASCADE"), unique=True, index=True)
    origin_city = Column(Text)
    origin_area = Column(Text)
    origin_code = Column(Text)
    destination_city = Column(Text)
    destination_area = Column(Text)
    destination_code = Column(Text)
    airline = Column(Text)
    flight_date_text = Column(Text)
    flight_time_text = Column(Text)
    flight_date = Column(Date)
