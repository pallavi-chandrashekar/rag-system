import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Get DB URL from environment variables (defined in docker-compose.yml)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Create the engine
engine = create_engine(DATABASE_URL)

# Create a Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency for FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()