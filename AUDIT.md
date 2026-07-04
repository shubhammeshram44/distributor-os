# Distributor OS — Full Codebase Audit

**Date:** 2026-06-30  
**Scope:** Functional completeness, bugs, design/UX  
**Out of scope:** Deployment config, CI/CD, security hardening, ERP integrations

---

## 1. What This App Does

**Distributor OS** is a multi-tenant B2B FMCG distribution SaaS platform built for Indian wholesale distributors. The core workflow:

1. Retail customers (kirana stores) send WhatsApp orders
2. Platform parses orders using Google Gemini AI + regex fallback
3. Orders flow through: Draft → Confirmed → Dispatched → Delivered
4. Inventory, payments (FIFO allocation), shipments, and analytics are tracked

**Target users:** Indian FMCG wholesale distributors managing 50–500 retailers

---

## 2. Architecture

```
Backend: FastAPI (Python 3.12) + SQLAlchemy 2.0 + PostgreSQL/SQLite
Auth: Firebase Phone OTP → custom JWT (HS256, 24h)
AI: Google Gemini (order parsing) + regex fallback
WhatsApp: Evolution API (self-hosted gateway)
PDF: ReportLab
Frontend: Next.js 14 (static export) + Tailwind CSS 3.4 + Recharts
Deploy: Render (backend), static hosting (frontend)
```

### Multi-Tenancy
- `tenant_context` context var injected into every request
- SQLAlchemy `with_loader_criteria` auto-filters by `tenant_id`
- PostgreSQL RLS context vars set for DB-layer isolation
- `TenantMixin` auto-injects `tenant_id` on flush

---

## 3. Data Models (14 entities)

| Model | Status | Notes |
|-------|--------|-------|
| DistributorTenant | ✅ | Workspace profile |
| User | ✅ | Team members with roles (SUPER_ADMIN, FINANCE, OPERATOR, DRIVER) |
| Customer + CustomerAlias | ✅ | B2B retailers with phone aliases |
| Product + ProductAlias + ProductSupplierMapping | ✅ | SKU catalog with fuzzy matching |
| Order + OrderLineItem + OrderStateLedger | ✅ | Immutable state machine |
| Invoice | ✅ | GST/Retail invoices tied to orders |
| Payment + PaymentInvoiceLink | ✅ | FIFO allocation |
| CustomerLedger | ✅ | DEBIT/CREDIT audit trail |
| Inventory | ✅ | Stock with low-stock thresholds |
| Shipment | ✅ | Fulfillment tracking |
| IngestionJob + IngestionStaging | ✅ | Bulk CSV import audit trail |
| BulkJob | ✅ | Async invoice generation jobs |

---

## 4. API Surface (15 routers, 50+ endpoints)

| Router | Status | Notes |
|--------|--------|-------|
| `/auth` | ✅ | Firebase login, JWT, signup, /me |
| `/users` | ✅ | Team management, RBAC |
| `/customers` | ✅ | CRUD, statement, onboard |
| `/products` | ✅ | Catalog CRUD, CSV import, stock adjust |
| `/orders` | ✅ | State machine, triage resolution |
| `/payments` | ✅ | FIFO allocation, reconciliation |
| `/whatsapp` | ✅ | Gemini+regex parsing, Evolution API |
| `/shipments` | ✅ | Fulfillment, tracking |
| `/ingestion` | ✅ | CSV/Excel bulk upload |
| `/analytics` | ✅ | Real aggregations |
| `/inventory` | ⚠️ | Works but no tenant param on some endpoints |
| `/dashboard` | ⚠️ | Demo data seeded on every request |
| `/tenant` | ⚠️ | Uses HTTP 440 (non-standard) |
| `/evolution` | ⚠️ | Hardcoded Render URL fallback |
| `/mocks` | ⚠️ | Tally/Delhivery stubs, unused in production |

---

## 5. Feature Matrix

| Feature | Status | Notes |
|---------|--------|-------|
| Multi-tenant isolation | ✅ | Context var + SQLAlchemy + DB RLS |
| Order state machine | ✅ | Immutable ledger, enforces transitions |
| Inventory guardrails | ✅ | Atomic stock deduction, race-condition safe |
| Credit limit enforcement | ✅ | Aggregate confirmed outstanding |
| Payment FIFO allocation | ✅ | Correct, handles partial payments |
| WhatsApp ingestion (AI) | ✅ | Gemini + regex, product matching |
| Firebase phone auth | ✅ | OTP, JWT session |
| CSV catalog import | ✅ | Transactional UPSERT |
| PDF invoice generation | ✅ | GST + Retail formats |
| Bulk invoice export (ZIP) | ✅ | Async job with progress polling |
| Order cancellation | ❌ | No endpoint, no UI |
| Pagination on list views | ❌ | All orders/customers/products loaded at once |
| Sorting on tables | ❌ | No sort params on any endpoint |
| Search on list views | ❌ | Frontend-only filter, no server search |
| Order CSV export | ❌ | Not implemented |
| Payment history per customer | ❌ | No dedicated endpoint |
| Product soft delete | ❌ | Hard delete only, breaks historical line items |
| Low-stock threshold update | ⚠️ | Only via product update, no dedicated UI |
| Real-time activity feed | ⚠️ | Hardcoded demo entries mixed with real data |
| WhatsApp inbox/messages page | ⚠️ | UI started but thin; uses order thread endpoint |
| Analytics charts | ⚠️ | Backend real, frontend was using mocks |
| LiveDeliveries widget | ❌ | Fully hardcoded fake data |
| Global search | ❌ | Search bar exists but does nothing |
| Toast notifications | ⚠️ | Per-page inline toasts; no global system |
| Empty states | ⚠️ | Some pages have them, most don't |
| Loading skeletons | ⚠️ | Some spinners; no shimmer skeletons |
| Confirmation dialogs | ⚠️ | Some pages have none |
| Mobile responsiveness | ⚠️ | Layout mostly desktop-only |

---

## 6. Bugs Found

### 🔴 Critical (data integrity / silent failures)

| # | Bug | Location | Impact |
|---|-----|----------|--------|
| B1 | `payment_status` setter is a silent no-op (`pass`) | `app/models/order.py`, `app/models/shipment.py` | Writes to `payment_status` silently dropped |
| B2 | Demo data seeded on **every** dashboard/orders/analytics request | `app/services/demo_service.py` | Extra DB query + potential writes on every request |
| B3 | Activity feed mixes hardcoded demo strings with real DB events | `app/api/v1/dashboard.py` | Demo tenant shows fake payment events as real |
| B4 | WhatsApp dedup set is in-memory, resets on restart | `app/api/v1/whatsapp.py` | Duplicate orders possible after server restart |

### 🟡 Bugs (broken functionality)

| # | Bug | Location | Impact |
|---|-----|----------|--------|
| B5 | HTTP 440 (non-standard) instead of 404 | `app/api/v1/tenant.py` | Clients get unexpected status code |
| B6 | Analytics page charts use hardcoded mock data instead of API | `frontend/src/app/dashboard/sales-analytics/page.tsx` | User sees fake metrics |
| B7 | LiveDeliveries widget fully hardcoded | `frontend/src/components/LiveDeliveries.tsx` | User sees fake delivery markers |
| B8 | CollectionsDonut `overdue_60_count` hardcoded to 12 | `frontend/src/components/CollectionsDonut.tsx` | Wrong overdue count shown |
| B9 | Activity feed polls every 5s (150 API calls/5min per user) | `frontend/src/hooks/useDashboardData.ts` | Severe server load |
| B10 | Global search bar does nothing | `frontend/src/components/DashboardHeader.tsx` | Non-functional UI element |
| B11 | "Automations" sidebar link has no href | `frontend/src/components/Sidebar.tsx` | Dead/broken menu item |
| B12 | Error state set in `useDashboardData` but never rendered on dashboard | `frontend/src/app/dashboard/page.tsx` | Silent failures |
| B13 | `GET /products` calls `ensure_demo_data` (side effect on read) | `app/api/v1/products.py` | Unexpected demo seeding on catalog fetch |

### 🔵 Minor Issues

| # | Issue | Location |
|---|-------|----------|
| B14 | MetricCards sparklines are hardcoded decorative SVG paths | `MetricCards.tsx` |
| B15 | Sidebar doesn't highlight active route on sub-pages correctly | `Sidebar.tsx` |
| B16 | Onboarding has only 4 hardcoded business categories | `auth/onboarding/page.tsx` |
| B17 | Auth page shows raw Firebase error strings to users | `auth/page.tsx` |
| B18 | `overflow-hidden` on `<body>` blocks page scrolling | `layout.tsx` |
| B19 | Middleware matcher pattern misses some dashboard sub-routes | `middleware.ts` |

---

## 7. Missing Functionality

| # | Feature | Priority |
|---|---------|----------|
| M1 | Order cancellation (endpoint + UI) | HIGH |
| M2 | Pagination on all list views | HIGH |
| M3 | Column sorting on Orders, Customers, Products tables | MEDIUM |
| M4 | Server-side search on Orders, Customers, Products | MEDIUM |
| M5 | Order CSV export | MEDIUM |
| M6 | Payment history per customer | MEDIUM |
| M7 | Product soft delete (preserve historical line items) | MEDIUM |
| M8 | Loading skeletons on all pages | MEDIUM |
| M9 | Empty states on all list views | MEDIUM |
| M10 | Error banners with retry on all pages | MEDIUM |
| M11 | Confirmation dialogs for destructive actions | MEDIUM |
| M12 | Global toast notification system | LOW |
| M13 | `StatusBadge` shared component (ad-hoc spans everywhere) | LOW |
| M14 | Mobile-responsive layout | LOW |

---

## 8. What's Working Well

✅ **Multi-tenancy** — Context var + SQLAlchemy event hooks, tight isolation  
✅ **Order state machine** — Immutable `OrderStateLedger`, audit trail  
✅ **Inventory guardrails** — Atomic stock deduction (race-condition safe CAS update)  
✅ **Credit limit enforcement** — Aggregates confirmed outstanding dynamically  
✅ **Payment FIFO allocation** — Correct, handles partials  
✅ **WhatsApp ingestion** — Sophisticated Gemini + regex + triage workflow  
✅ **Firebase phone auth** — OTP, HttpOnly JWT cookie  
✅ **CSV catalog import** — Transactional UPSERT with row-level errors  
✅ **PDF invoice generation** — GST + Retail formats, bulk ZIP export  
✅ **Test coverage** — 23 test files, 200+ cases, good happy-path coverage  

---

## 9. Architecture Quality Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Data model design | ⭐⭐⭐⭐ | Well-normalized, immutable ledger pattern |
| API design | ⭐⭐⭐ | Inconsistent pagination/sorting, some wrong status codes |
| Frontend architecture | ⭐⭐⭐ | Functional but lots of copy-pasted patterns per page |
| Error handling | ⭐⭐⭐ | Backend good; frontend inconsistent |
| Test coverage | ⭐⭐⭐⭐ | Good for backend; no frontend tests |
| Performance | ⭐⭐ | No pagination, activity feed polling too aggressive |
| UX polish | ⭐⭐ | Functional but prototype-grade; missing states |
| Mobile | ⭐⭐ | Desktop-first; mobile mostly works but not optimized |

---

## 10. Dependency Inventory

**Backend:** FastAPI 0.110+, SQLAlchemy 2.0, Pydantic v2, Alembic, Firebase Admin 6.4, google-generativeai 0.4, ReportLab 4.1, openpyxl 3.1, httpx 0.27  
**Frontend:** Next.js 14.2, React 18, Firebase 11, Recharts 2.12, Tailwind 3.4, Lucide React  
**No duplicate/conflicting deps detected**

---

*This document was generated as part of the Phase 1 audit pass. See GAP_REPORT.md for what was fixed and what remains.*
