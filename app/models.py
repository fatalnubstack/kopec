from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from .database import Base


class Climb(Base):
    __tablename__ = "climbs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    finish_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    completed = Column(Boolean, default=False)
    group_size = Column(Integer, default=1, nullable=False)


class PrintOrder(Base):
    __tablename__ = "print_orders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    email = Column(String, nullable=True)
    photo_filename = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    printed_at = Column(DateTime, nullable=True)
    packed_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)


class WallPost(Base):
    __tablename__ = "wall_posts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    climb_id = Column(Integer, nullable=True)
    duration_fmt = Column(String, nullable=True)
    mood = Column(Integer, nullable=True)   # 1–5
    message = Column(String, nullable=True)
    photo_filename = Column(String, nullable=True)
    likes = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
