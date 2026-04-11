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


class WallPost(Base):
    __tablename__ = "wall_posts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    climb_id = Column(Integer, nullable=True)
    duration_fmt = Column(String, nullable=True)
    mood = Column(Integer, nullable=True)   # 1–5
    message = Column(String, nullable=True)
    photo_filename = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
