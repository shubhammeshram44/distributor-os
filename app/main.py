import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.router import api_router
from app.database import engine, Base
from app.utils.origin_policy import ALLOWED_ORIGINS as _POLICY_ORIGINS, is_origin_allowed

# Create tables on startup unless SKIP_SCHEMA_INIT is set.
# In production with Alembic, set SKIP_SCHEMA_INIT=1 and run `alembic upgrade head` instead.
if not os.getenv("SKIP_SCHEMA_INIT"):
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Distributor OS API",
    description="Multi-tenant backend platform for supply chain distributors",
    version="1.0.0"
)

# Fix for AUTH-4: this list previously drifted out of sync with the
# separate ALLOWED_ORIGINS list in app/api/v1/auth.py (this one was
# missing the production https://distroos.in domains entirely, relying
# only on the ALLOWED_ORIGINS env var actually being set to add them).
# Now built from the single shared app/utils/origin_policy module, with
# the local dev origins this file already explicitly supported preserved
# alongside it.
allowed_origins = list(dict.fromkeys([
    *_POLICY_ORIGINS,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]))

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


# Fix for AUTH-4: origin-based CSRF validation (_validate_origin in
# app/api/v1/auth.py) previously was only ever invoked by POST /auth/refresh
# and POST /auth/logout. Every other cookie-authenticated, state-changing
# endpoint across the rest of the API (orders, customers, payments,
# shipments, etc.) had NO origin validation at all -- yet production
# cookies are set with samesite="none" (required for this app's
# cross-origin frontend/backend deployment), which fully disables
# SameSite's own CSRF protection and leaves origin validation as the only
# real backstop. A single, centrally-enforced check here closes that gap
# for the whole API at once, instead of requiring every route handler in
# every router to remember to call a per-endpoint check individually.
#
# Scope: only applies to state-changing methods (POST/PUT/PATCH/DELETE)
# where the request is actually relying on cookie-based auth (carries an
# access_token cookie) AND presents an Origin header that doesn't match
# an allowed origin. Requests with no access_token cookie (e.g. bearer-
# token API clients, which aren't vulnerable to CSRF since a cross-site
# attacker can't set an Authorization header on the victim's behalf) and
# requests with no Origin header at all (server-to-server webhooks,
# non-browser clients -- consistent with _validate_origin's existing
# "only check if an Origin header is actually present" semantics) are
# left completely unaffected.
_CSRF_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def enforce_origin_for_cookie_auth(request: Request, call_next):
    if request.method in _CSRF_PROTECTED_METHODS:
        origin = request.headers.get("origin")
        has_session_cookie = "access_token" in request.cookies
        if origin and has_session_cookie and not is_origin_allowed(origin):
            return JSONResponse(
                status_code=403,
                content={"detail": "CORS validation failed: Origin not allowed for this request."},
            )
    return await call_next(request)


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
