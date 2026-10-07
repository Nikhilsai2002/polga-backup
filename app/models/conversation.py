from sqlalchemy import Column, Integer, String, Text, JSON,ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base
 

class Conversation(Base):
    __tablename__ = "conversation"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analysis.id"))
    user_question = Column(Text)
    sql_generated = Column(Text)
    execution_output = Column(Text)
    summary = Column(Text)
    created_at = Column(String, server_default=func.now())