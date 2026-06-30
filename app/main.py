import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.database import engine, Base

# CRITICAL: Force table lifecycle creation on server startup
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


async def scheduled_reminder_sweep():
    from app.database import SessionLocal
    from app.services.payment_reminder_service import run_payment_reminder_sweep
    db = SessionLocal()
    try:
        await run_payment_reminder_sweep(db)
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    if os.getenv("SEED_DEMO_DATA", "false").lower() == "true":
        from app.database import SessionLocal
        from app.services.demo_service import ensure_demo_data
        from app.services.tenant_service import DEMO_TENANT_ID
        db = SessionLocal()
        try:
            ensure_demo_data(db, DEMO_TENANT_ID)
        finally:
            db.close()

    if os.getenv("ENABLE_PAYMENT_REMINDER_SCHEDULER", "true").lower() == "true":
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(scheduled_reminder_sweep, "cron", hour=10, minute=0)
        scheduler.start()


@app.get("/")
def read_root():
    return {"status": "healthy", "service": "Distributor OS Backend Core"}

@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok"}
