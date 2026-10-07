from sqlalchemy import Column, Integer, String, Text, JSON, func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base, SessionLocal

import json

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), index=True)
    session_id = Column(String(255), unique=True, index=True)
    created_at = Column(String, server_default=func.now())