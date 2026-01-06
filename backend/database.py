from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database Connection URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@rag-db:5432/ragdb")

# Create the Engine
engine = create_engine(DATABASE_URL)

# Create Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- DEFINE BASE HERE ---
Base = declarative_base()

# Dependency for API Routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()