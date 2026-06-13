from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.database import engine, Base
import app.models  # Register all models on Base.metadata

# Auto-initialize database schema
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DistributorOS API Backend",
    description="AI-Native Distribution Operating System for India",
    version="2.0.0"
)

# Enable CORS for frontend web requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API router
app.include_router(api_router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to DistributorOS Backend Core API",
        "documentation": "/docs"
    }
