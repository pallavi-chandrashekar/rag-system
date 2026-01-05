import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import routes
from backend.database import engine
from backend.models import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Database Tables (Simple "Auto-Migration" for dev)
# In production, use Alembic instead.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Enterprise RAG Platform")

# Enable CORS (Allows the frontend to talk to the backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include our routes
app.include_router(routes.router)

@app.get("/health")
def health_check():
    return {"status": "healthy"}