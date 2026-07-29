# DistributorOS — Product Status & Roadmap
*Last updated: July 2026*

---

## What's Working
- Credit Risk Alerts widget on dashboard ✅ (shows top at-risk customers with overdue days, outstanding, risk level)
- WhatsApp disconnect detection + dashboard banner ✅ (auto-detects disconnect, shows reconnect banner)
- Tally XML export ✅ (download Tally-compatible voucher file from orders page)
- Resend OTP on auth page ✅
- Onboarding checklist on empty dashboard ✅
- Google Analytics 4 + Microsoft Clarity ✅ (tracking distroos.in)
- Per-tenant Razorpay connection ✅ (each distributor connects own keys, AES-256 encrypted)
- 4-phase hybrid product matching ✅ (exact → word overlap → fuzzy → self-learning aliases)
- Timezone-aware timestamps ✅ (all timestamps in user's local timezone via browser API)
- GSTIN validation on settings ✅ (format validation with state detection)
- Unique WhatsApp instance per tenant ✅ (dist-{tenant_id} naming prevents cross-tenant contamination)
- Marketing website live at distroos.in ✅
- Custom domain distroos.in connected to Render ✅

---

## What We've Built

### 1. WhatsApp Order Ingestion Pipeline ✅
The core product. A distributor connects their WhatsApp number, and customers place orders by sending messages like *"bhaiya, 25 unit of detergent bhejna"* or *"send 2000 units liril soap gst bill"*.

**How it works:**
- Customer WhatsApps the distributor's number
- Evolution API (hosted on GCP VM) receives the message and forwards to backend via webhook
- 5-layer filter: JID type check → self-message drop → length filter → Gemini intent check → customer whitelist
- Gemini AI parses the order text into structured items + quantities (handles Hindi-English mix, Indian number formats like "1 lakh")
- Fuzzy product matching (RapidFuzz, threshold 82%) maps colloquial names to catalog SKUs
- Order created as `Draft` (fully matched) or `pending_review` (unmatched items)
- Self-learning: successful matches saved as `ProductAlias` for future auto-matching

**Key technical detail:** Evolution API v2.3.7 required (not v2.2.3) — resolves `@lid` Android JIDs to real phone numbers via `remoteJidAlt` field.

---

### 2. Order Management Dashboard ✅
Full order lifecycle management for distributors.

**Features:**
- Order list with status badges: Confirmed (X of Y allocated), Pending, Needs Review, Confirmed — Out of Stock
- Order detail panel with credit intelligence widget (risk score, outstanding balance, overdue days, recommendation)
- Unmatched item resolution — distributor can select correct SKU from dropdown
- Invoice type toggle (GST Bill / Retail Bill) per order
- Batch confirm with inventory allocation
- PDF invoice download (GST-compliant with CGST/SGST, or retail)

**Inventory allocation logic:**
- On confirmation: allocate `min(requested, available)` units
- Partial allocation allowed — `allocated_quantity` stored separately from `quantity`
- `DemandGap` created for shortfall (type: `STOCK_SHORTAGE`)
- `quantity_on_hand` decremented, `quantity_committed` incremented on confirmation
- `restore_inventory_for_order()` exists but not called — ready for future cancel/reject flow

---

### 3. WhatsApp Notifications ✅
Two categories of notifications, separately controllable per tenant and per customer.

**Operational (order lifecycle):**
- Order Received → sent immediately on ingestion (only if ≥1 item matched)
- Order Confirmed → sent after distributor confirms, shows allocated quantities + total
- Order Dispatched → sent when shipment created
- Order Delivered → sent when marked delivered
- New Order Alert → sent to distributor on every new WhatsApp order

**Financial (collections):**
- Payment reminders at 4 tiers based on days overdue (upcoming, just_overdue, moderately_overdue, severely_overdue)
- Includes Razorpay payment link for specific invoice
- Includes consolidated outstanding link (pay all dues)
- 3-day frequency cap per customer
- Respects customer payment terms (Net 7/15/30/COD)

**Notification settings page:** Full toggle control per event type, split into Operational and Financial sections.

---

### 4. Inventory Management ✅
- Product catalog with SKUs, brand, category, pack size, base price
- Inventory inward (stock addition)
- `quantity_on_hand` + `quantity_committed` tracked separately
- Low stock threshold alerts
- Sales velocity calculation
- AI reorder suggestions
- DemandGap tracking — lost revenue from stock shortage and credit limit blocks

---

### 5. Payment Collections ✅
Full digital collections stack.

**Manual collection voucher:**
- Distributor records cash/UPI/cheque payments
- FIFO reconciliation against oldest unpaid invoices
- Customer outstanding balance updated

**Razorpay online payment:**
- Payment session created eagerly on order confirmation
- Three options: pay specific invoice / pay full outstanding / custom amount
- Razorpay webhook auto-reconciles payment → invoice marked PAID → customer balance updated
- Preferred invoice paid first, remainder via FIFO
- Sessions expire after 7 days, auto-regenerated on next reminder

**Payment reminder sweep:**
- Triggered via `POST /api/v1/payments/trigger-reminder-sweep`
- Evaluates all tenants and customers daily
- Tier-based WhatsApp reminders with embedded payment links
- Frequency cap: max 1 reminder per customer per 3 days

---

### 6. Shipments & Delivery ✅
- Create delivery (assign to driver, create shipment)
- Mark dispatched → WhatsApp notification fired
- Mark delivered → WhatsApp notification fired
- Delivery event endpoint accepts source: manual / shiprocket / dunzo / porter (future logistics integrations)

---

### 7. Customer Management ✅
- Customer onboarding with credit limit, payment terms, GSTIN
- Customer aliases for WhatsApp phone number matching
- Per-customer WhatsApp notification opt-out
- Outstanding balance tracking
- Customer statement PDF

---

### 8. Analytics & Dashboard ✅
- Sales metrics with date filtering
- Collections donut chart (outstanding vs collected)
- Recent orders feed
- DemandGap summary card (lost revenue by reason)
- Inventory summary

---

### 9. Infrastructure ✅
- **Backend:** FastAPI on Render (free tier, kept alive via UptimeRobot pinging `/health` every 5 mins)
- **Frontend:** Next.js on Render
- **WhatsApp:** Evolution API v2.3.7 on GCP VM (e2-small, `34.158.60.42:8080`)
- **Database:** Neon PostgreSQL with PgBouncer connection pooling
- **Payments:** Razorpay (test mode, `rzp_test_T8IGojHXkgbkAf`)
- **AI:** Gemini Flash for order parsing + intent classification
- **CI:** GitHub Actions (`migration-parity.yml`) — 116+ tests

---

## Recently Built (July 2026)

### WhatsApp Disconnect Detection
- `connection.update` state:close handled in webhook
- `whatsapp_connection_status` column on DistributorTenant
- Red banner on dashboard when disconnected
- Auto-clears when reconnected
- Only shows for tenants who previously had WhatsApp connected

### Credit Risk Alerts Dashboard Widget
- New endpoint: GET /api/v1/dashboard/credit-risk-alerts
- Shows top 5 at-risk customers
- Risk levels: HIGH RISK (45+ days overdue) / CAUTION (15-45 days)
- Visual: color-coded cards, overdue progress bar, summary counts
- Robust payment terms parser (handles Net X, X-Y Days, COD formats)

### 4-Phase Hybrid Product Matching
- Phase 1: Exact alias match
- Phase 2: Word overlap scoring (fixes multi-word products like "hibiscus green tea")
- Phase 3: Fuzzy match via rapidfuzz (handles misspellings)
- Phase 4: Self-learning alias registration
- Batch pre-loading of aliases/products for O(1) DB queries per order

### Per-Tenant Razorpay Connection
- Distributors connect their own Razorpay account
- AES-256 encryption via Fernet for secret key storage
- Auto-detects test/live mode from key prefix
- ENCRYPTION_KEY env var on Render backend

### Multi-Tenant WhatsApp Isolation
- Instance names now unique per tenant: dist-{tenant_id[:8]}
- Owner phone fallback requires instance name match (prevents cross-tenant contamination)
- Critical fix: previously all tenants shared "default-bot" instance

### Timezone-Aware Timestamps
- Backend sends raw ISO UTC strings (not pre-formatted)
- Frontend `formatDateTime()` utility in `frontend/src/utils/datetime.ts`
- Formats: datetime | date | time | relative
- Works for any timezone — India, US, UAE, etc.

### Tally XML Export
- GET /api/v1/orders/export/tally endpoint
- Date range filtering
- Correct Tally Sales Voucher XML schema
- Stock item names: "Brand (SKU)" format
- Skips zero-value and Draft/Cancelled orders

### Marketing Website
- distroos.in live on Render
- Google Analytics 4 + Microsoft Clarity tracking
- Firebase authorized domain updated for distroos.in
- CORS updated to allow distroos.in on backend

---

## What's Not Built Yet (Priority Order)

### P1 — Business Critical (blocks revenue)

**[NEW P1] Order needs review alert to distributor**
When order goes to pending_review, send WhatsApp notification to distributor immediately.
Prevents silent order loss — biggest week-1 churn risk.

**[NEW P1] Manual order entry with voice input**  
Distributor creates order on behalf of retailer (phone call scenario).
Phase 1: Search + recently ordered + quantity picker
Phase 2: Voice input via Web Speech API → existing Gemini parser
Zero extra AI cost — transcription runs in browser.

**1. GST-Compliant Invoice Gaps**
Current invoice has issues:
- GST rate hardcoded at 18% — different products have different rates (5%, 12%, 18%, 28%)
- No CGST/SGST split — only shows total GST (not legally compliant)
- Distributor GSTIN missing from invoice header
- No HSN codes on line items
- Invoice number not in sequential financial year format (INV/2026-27/001)

**2. Payment Reminder Cron Job**
The sweep exists but runs manually only. No automatic daily trigger. Need external cron — recommend cron-job.org (free) pointing at `/api/v1/payments/trigger-reminder-sweep` daily at 9 AM.

**3. Zero-Value Invoice Cleanup**
Many invoices created with `total_amount = 0.00` (from orders with 0 allocated units). These pollute the payment reminder sweep and customer outstanding balance. Fix: don't create invoice if billing total = 0.

---

### P2 — High Value (distributor delight)

**[NEW P2] Today's Actions card on dashboard**
3 actionable items: pending orders count, overdue customers, low stock alerts.
All data exists — pure frontend card.

**4. Order Fulfillment States (GPT recommendation)**
Current `Confirmed` status conflates commercial acceptance with physical fulfillment. Proposed states:
- `Confirmed` — 100% allocated, ready to dispatch
- `Partially Confirmed` — partial allocation, dispatch what's available
- `Awaiting Stock` — 0 allocated, waiting for inventory arrival

DemandGap engine should auto-suggest fulfillment when stock arrives:
- Stock inward → check open DemandGaps → surface allocation queue → one-click approve

**5. Payment Link in Order Detail UI**
Distributor should be able to copy/share Razorpay payment link directly from order panel. Currently only accessible via API. Add "Copy Payment Link" button next to "Download B2B Invoice".

**6. Tally Export**
Every serious FMCG FMCG distributor uses Tally. Need XML voucher export compatible with Tally ERP 9 / Tally Prime. Can be generated without a live Tally account — just generate the XML format.

---

### P3 — Intelligence (moat building)

**7. Behavioral Payment Intelligence**
Currently reminders fire based on fixed thresholds. Should fire based on customer behavior:
- Customer always pays on 15th → don't send reminder on Day 1
- Chronic defaulter → escalate immediately
- Weekly settler → send one consolidated reminder, not per-invoice
Requires 3-6 months of payment data to be meaningful. Build framework now, let it learn.

**8. Consolidated Outstanding Reminder**
For customers with 5+ deliveries per week, sending per-invoice reminders trains them to ignore it. Send one weekly consolidated reminder covering all outstanding invoices with a single "pay all" Razorpay link.

**9. Promise-to-Pay Tracking**
When customer replies "I'll pay by Friday" — parse the reply via Gemini, log the promise, set follow-up reminder for Friday + 1 day, track fulfilment rate per customer.

**10. Cash Flow Forecasting**
Show distributor: "Expected collections this week: ₹3,42,000 | At risk: ₹67,000"
Based on payment patterns, promises, and aging buckets.

**11. Intelligent Stock Allocation Priority**
When inventory < demand from multiple customers, show distributor a ranked list:
- Rank by customer score (payment consistency, order frequency, relationship value)
- One-click approve allocation

---

### P4 — Platform (future)

**12. Salesman Mobile PWA**
Field agents need a simple mobile view: today's orders, customer list, mark delivered, add manual order. No desktop complexity.

**13. Multi-tenant Onboarding Flow**
Currently one distributor tenant manually created. Need self-serve signup: distributor signs up → connects WhatsApp → adds products → goes live. Full onboarding wizard.

**14. WhatsApp Business Cloud API Option**
Alternative to Baileys (current). No QR scanning, no session management, no bans. Requires Meta Business account. Better for production scale.

**15. Logistics Partner Integrations**
Delivery event endpoint already accepts `source: shiprocket / dunzo / porter`. Need translator webhooks for each partner.

---

## Known Issues & Tech Debt

| Issue | Status |
|---|---|
| WhatsApp session drops silently | ✅ Fixed — disconnect banner added |
| Timestamps showing UTC not local time | ✅ Fixed — browser timezone conversion |
| GSTIN not validated | ✅ Fixed — format validation added |
| All tenants sharing `default-bot` instance | ✅ Fixed — unique instance per tenant |
| `quantity_committed` not released on dispatch | Still open |
| Awaiting Stock status not implemented | Still open |
| GST rate hardcoded at 18% | Still open |
| No CGST/SGST split on invoice | Still open |
| No order cancel/reject UI | Still open |
| `datetime.utcnow()` deprecated (40+ instances) | Still open |

---

## Architecture Decisions Log

| Decision | Rationale |
|---|---|
| Inventory deducted on confirmation not dispatch | Simpler for MVP; flag `INVENTORY_DEDUCTION_TRIGGER` marks where to change |
| Baileys over WhatsApp Business API | Faster to implement, no Meta approval needed for testing |
| GCP VM for Evolution API | Railway/Render IPs blocked by WhatsApp; GCP residential-ish IPs work |
| Razorpay per-distributor model (future) | Razorpay Route — each distributor connects own account, money never touches DistributorOS |
| FIFO with preferred invoice | Supports both per-invoice and bulk payment scenarios |
| Separate operational/financial notifications | Distributor can silence payment chasing for VIP customers without affecting delivery alerts |
| `pending_review` canonical status (not `NEEDS_REVIEW`) | Standardized during audit; `NEEDS_REVIEW` rows in DB should be migrated |

---

## Latest Builds (July 19-25, 2026)

### WhatsApp Connection — Architectural Fixes
- **Strict instance-name-only tenant lookup** — `connection.update` webhook now ONLY finds tenant by `whatsapp_phone_id == instance_name` or short-ID regex fallback. Phone number NEVER used to find a tenant — only to update. Eliminates cross-tenant contamination permanently.
- **Phone mismatch protection fixed** — Now only blocks if new phone belongs to a DIFFERENT tenant. Legitimate reconnects with new numbers work correctly.
- **Stale phone UI fix** — Frontend re-fetches tenant data immediately after QR scan confirmed connected. No page refresh needed.
- **`dist-None` prevention** — Provision endpoint returns 401 immediately if tenant resolution fails. Instance name always derived server-side as `dist-{tenant_id[:8]}`.
- **Disconnected state in UI** — New `disconnected` state separate from `idle`. Shows red banner with "Reconnect WhatsApp" button and last connected number. Different from fresh `idle` state (never connected).

### GST-Compliant Invoices (CTO — commit 7480ec4)
- CGST/SGST split on invoices (9%+9% for intra-state, 18% IGST for inter-state)
- Per-product GST rates (not hardcoded 18%)
- HSN codes on products and invoices
- Sequential invoice numbering

### Order Lifecycle Integrity (CTO — commit c65c86f)
- Needs-review WhatsApp alert to distributor when order goes to `pending_review`
- Fulfillment states: `Confirmed`, `Partially Confirmed`, `Awaiting Stock`
- Inventory release on order cancel

### Collections Automation (CTO — commit a074709)
- Consolidated payment reminders
- Cash flow forecast endpoint
- Promise-to-pay parsing from WhatsApp replies

### Promise-to-Pay Tracking (CTO — commit 0fbdcc6)
- Gemini parses "I'll pay by Friday" from retailer WhatsApp replies
- Logs promise with follow-up date
- Tracks fulfilment rate per customer

### Intelligent Stock Allocation (CTO — commit cd41872)
- When inventory < demand from multiple customers
- Ranks by customer score (payment history, order frequency)
- One-click approve allocation

### Dashboard Updates
- Top Products revenue widget added
- Metric cards row removed from main dashboard
- Messages tab gated behind feature flag (disabled by default)
- Decision Focus card as primary dashboard widget
- Business Health Score with 5 weighted signals

### Integrations Page V2
- Productboard-style card layout (All / Communication / Payments tabs)
- Connected/Disconnected/Coming Soon status badges
- Request Integration form (mailto)
- V1 deprecated, V2 now default
- Coming Soon: Tally Prime, Shiprocket, Marg ERP, GST Portal

### Marketing Page
- Privacy Policy at `/privacy` ✅
- Terms of Service at `/terms` ✅
- Calendly demo link: `https://calendly.com/consultme44/distributor-os-free-demo`
- Font: Figtree
- Broader positioning: "Distributors" not "FMCG Distributors"

---

## Updated Architecture Decisions

| Decision | Rationale |
|---|---|
| Instance name = `dist-{tenant_id[:8]}` — DEFINITIVE | Server-side only, never from frontend. Prevents `dist-None` and cross-tenant issues |
| Phone number = UPDATE only, never LOOKUP | The only correct architecture. Phone belongs to a person, not a tenant |
| `connection.update` webhook = strict instance-name lookup | Cross-tenant contamination impossible if instance name is always correct |
| LedgerService single entry point | `record_transaction()` always recomputes `outstanding_balance` from full ledger |
| Integrations V2 = default | V1 deprecated. V2 is Productboard-style, scales to future integrations |
| Dashboard = operational only | Performance metrics moved to Sales Analytics page |

---

## Updated Known Issues & Tech Debt

| Issue | Status |
|---|---|
| WhatsApp cross-tenant contamination | ✅ Fixed — strict instance-name lookup |
| Phone not updating after reconnect | ✅ Fixed — mismatch protection loosened |
| Stale phone in UI after reconnect | ✅ Fixed — re-fetch after connection |
| GST rate hardcoded at 18% | ✅ Fixed by CTO — per-product rates |
| No CGST/SGST split on invoice | ✅ Fixed by CTO |
| No HSN codes | ✅ Fixed by CTO |
| Order needs-review alert missing | ✅ Fixed by CTO |
| `quantity_committed` not released | Decided: ignore — redundant field |
| `datetime.utcnow()` deprecated | Still open — 40+ instances |
| Evolution API GCP VM HTTP-only | Still open — no Nginx/SSL |
| Gemini called for all messages | Still open — no pre-filter |
| Dashboard 8+ parallel API calls | Still open — consolidation planned |
| Order confirmation still ~8s | Still open — CTO profiling |

---

## Latest Builds (July 26-29, 2026)

### Van Sales — Instant Transaction (Phase 1) ✅
Field salesmen can create orders, deliver goods, and collect payment on-site in under 30 seconds.

**Features built:**
- 3-screen mobile-optimized modal (Select Customer → Build Order → Collect Payment → Success)
- Voice input via Web Speech API (Hindi + English `hi-IN`)
- Recently ordered items shown first for quick reorder
- "Already Delivered" toggle — skips dispatch, marks as `Delivered` immediately
- Three payment paths: Cash, UPI (Razorpay link), Credit
- Inline customer creation with ₹0 credit limit default
- Idempotency key (UUID) with DB-level unique constraint — prevents duplicate transactions
- Atomic DB transaction — rollback everything if any step fails
- Credit limit check before order creation
- WhatsApp notification to retailer after transaction
- Orders appear as `VAN-XXXX-XXXX` in orders list
- "🚚 Van Sale" button on Orders page header

**New endpoint:** `POST /api/v1/orders/instant-transaction`
**New component:** `frontend/src/components/VanSalesModal.tsx`
**New endpoint:** `GET /api/v1/customers/{id}/recent-products`
**DB change:** `idempotency_key` column on `orders` table

**4 tests added:**
- Atomicity/rollback
- Credit limit boundary
- Cash vs Collections consistency  
- Idempotency replay

---

### RBAC Phase 1 — Dynamic Permissions Architecture (REVERTED — in progress)
Built on `feature/rbac-permissions` branch. Reverted from main due to sidebar rendering bug.

**What was built (on feature branch):**
- `permissions` table — master list of all permission keys
- `role_permissions` table — per-tenant role→permission mapping
- `permission_service.py` — seed, check, get permissions
- `rbac.py` — FastAPI dependency `get_current_user_with_permission()`
- `usePermissions.ts` — frontend hook with isLoading state
- `GET /api/v1/users/permissions` endpoint
- Sidebar integration with permission-based show/hide

**Bug:** `usePermissions` hook not storing permissions correctly in localStorage — sidebar shows only 3 items instead of all items for SUPER_ADMIN.

**Status:** Fix in progress on `feature/rbac-permissions`. Do NOT merge to main until tested locally.

**Tech Debt:** Orphaned tables `permissions`, `role_permissions` and `users.email` column exist in production Neon DB without migration files. When re-implementing RBAC, use `IF NOT EXISTS` in migrations.

---

### Order Header Cleanup (Pending)
Orders page header has 6 buttons — too cluttered.
Proposed: Group Export CSV, Export Tally, Download Invoices, Refresh into "⋮ More" dropdown.
Keep only: `[⋮ More ▼]` `[🚚 Van Sale]` `[+ New Order]`

---

### WhatsApp Connection — Final Fixes ✅
- Strict instance-name-only tenant lookup — cross-tenant contamination eliminated
- Phone mismatch protection loosened — only blocks if phone belongs to another tenant
- Stale phone UI fixed — re-fetches tenant data after QR scan
- `dist-None` prevention — 401 returned if tenant resolution fails
- Disconnected state in UI — red banner, "Reconnect WhatsApp" button

---

## Updated Tech Debt

| Issue | Status |
|---|---|
| RBAC sidebar bug | Open — on feature/rbac-permissions branch |
| Orphaned DB tables (permissions, role_permissions, users.email) | Open — use IF NOT EXISTS when re-implementing |
| Order confirmation still ~8s | Open — CTO profiling |
| `datetime.utcnow()` deprecated 40+ instances | Open |
| Evolution API GCP VM HTTP-only (no SSL) | Open |
| Gemini pre-filter for non-orders | Open |
| Van Sales UPI QR code shown inline | Open — roadmap |
| Order header too many buttons | Open |
| Tally auto-sync agent | Open — roadmap |
| `quantity_committed` cleanup | Decided: ignore |

---

## Development Standards (Established)

### RBAC Rule — Every Feature Needs a Permission Key
```
Every new feature prompt must include:
RBAC: Add permission key "[module].[action]" to permission_service.py
SUPER_ADMIN: True, OPERATOR: [T/F], FINANCE: [T/F], DRIVER: [T/F]
Frontend: use has("[module].[action]") to show/hide
```

### Branch Strategy
- All new features on `feature/xxx` branch
- Test locally before merging to main
- Verify for multiple roles before merge
- Revert command: `git revert HEAD && git push origin main`

### Merge Checklist
```
1. py -m pytest tests/ -x -q passes ✅
2. npm run build passes ✅
3. Tested on localhost:3000 ✅
4. Verified for 2+ roles ✅
5. THEN merge to main
```
