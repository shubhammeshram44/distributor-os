import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.database import engine, Base

# Create tables on startup unless SKIP_SCHEMA_INIT is set.
# In production with Alembic, set SKIP_SCHEMA_INIT=1 and run `alembic upgrade head` instead.
if not os.getenv("SKIP_SCHEMA_INIT"):
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Distributor OS API",
    description="Multi-tenant backend platform for supply chain distributors",
    version="1.0.0"
)

allowed_origins = [
    "https://distributor-os-ui.onrender.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

env_origins = os.getenv("ALLOWED_ORIGINS")
if env_origins:
    # Use .extend() to ADD to the list, instead of overwriting it!
    env_list = [orig.strip() for orig in env_origins.split(",") if orig.strip()]
    allowed_origins.extend(env_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router, prefix="/api/v1")

# Mount static folder for serving bulk downloadable ZIP files
from fastapi.staticfiles import StaticFiles
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return {"status": "healthy", "service": "Distributor OS Backend Core"}
