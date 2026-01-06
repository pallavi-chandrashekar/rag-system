from sqlalchemy import Column, String, Text, ForeignKey, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import datetime

from pgvector.sqlalchemy import Vector

from backend.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    tenant_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    
    embedding = Column(Vector(384)) 
   
    
    metadata_ = Column("metadata", JSON, nullable=True)

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, index=True)
    title = Column(String) # First user message usually
    history = Column(JSON) # Stores list of messages [{"role": "user", ...}]
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)