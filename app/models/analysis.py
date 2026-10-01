from sqlalchemy import Column, Integer, String, Text, JSON, func, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from app.core import Base

class Analysis(Base):
    __tablename__ = "analysis"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    created_by = Column(String(255), index=True)
    created_at = Column(String, server_default=func.now())
    updated_at = Column(DateTime)
