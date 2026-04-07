from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from .database import Base


class Climb(Base):
    __tablename__ = "climbs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    finish_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    completed = Column(Boolean, default=False)
