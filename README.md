# Distributor OS

Multi-tenant B2B FMCG distribution platform for wholesale distributors. Retailers place orders via WhatsApp; the platform parses them with Gemini AI, creates digital orders, manages inventory, and tracks payments.

## Stack

| Layer | Tech |
|---|---|
| Backend API | FastAPI + SQLAlchemy 2.0 (Python) |
| Database | PostgreSQL (SQLite for local dev) |
| Migrations | Alembic |
| Auth | Firebase Phone OTP + JWT (HS256) |
| AI Parsing | Gemini Flash 1.5 with regex fallback |
| WhatsApp | Evolution API (self-hosted gateway) |
| Frontend | Next.js 14 + Tailwind CSS + TypeScript |
| SMS | MSG91 / Twilio (pluggable) |

## Local Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL (or use the SQLite fallback for dev)

### Backend

```bash
# Create and activate virtualenv
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env file and fill in values
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Interactive docs: `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend is available at `http://localhost:3000`.

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local` if the API is on a non-default port.

## Key Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string. Falls back to SQLite if unset (dev only). |
| `SECRET_KEY` | Yes | JWT signing secret. Must be random and long. |
| `GEMINI_API_KEY` | Yes | Google Gemini API key for WhatsApp order parsing. |
| `FIREBASE_CREDENTIALS_PATH` | Yes* | Path to Firebase service account JSON (preferred on Render). |
| `FIREBASE_CREDENTIALS_JSON` | Yes* | Firebase service account JSON as a string (alternative). |
| `EVOLUTION_API_URL` | Yes | Base URL of the Evolution API WhatsApp gateway. |
| `EVOLUTION_API_KEY` | Yes | API key for the Evolution API instance. |
| `APP_URL` | Yes | Public URL of this backend (used for webhook registration). |
| `SMS_PROVIDER` | No | `MSG91` (default) or `TWILIO`. |
| `SMS_GATEWAY_API_KEY` | No | API key for the SMS provider. Leave empty to skip OTP SMS. |

*One of `FIREBASE_CREDENTIALS_PATH` or `FIREBASE_CREDENTIALS_JSON` is required.

## Running Tests

```bash
pytest tests/ -q
```

23 test files cover orders, payments, customers, products, WhatsApp ingestion, and regression cases.

## Architecture Overview

```
WhatsApp (retailer)
    │ webhook
    ▼
Evolution API ──► POST /api/v1/whatsapp/webhook
                        │
                   Gemini parse + regex fallback
                        │
                   Order + LineItems → DB
                        │
              ┌─────────┴──────────┐
              │                    │
         Draft order          NEEDS_REVIEW
         (all SKUs             (unmatched SKUs
          matched)              → Triage queue)
```

Multi-tenancy is enforced at the SQLAlchemy layer via `TenantMixin` (context var filtering). PostgreSQL RLS is supported for an additional isolation layer.

## Deployment (Render)

1. Create a PostgreSQL instance and copy the connection string to `DATABASE_URL`.
2. Add a Secret File at `/etc/secrets/firebase.json` with the Firebase service account JSON and set `FIREBASE_CREDENTIALS_PATH=/etc/secrets/firebase.json`.
3. Set all other required env vars in the Render dashboard.
4. The build command: `pip install -r requirements.txt && alembic upgrade head`
5. The start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
