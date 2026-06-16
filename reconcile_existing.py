import uuid
from app.database import SessionLocal, tenant_context
from app.models.tenant import DistributorTenant
from app.services.payment_service import reconcile_payments_and_invoices

def reconcile_all():
    db = SessionLocal()
    try:
        tenants = db.query(DistributorTenant).all()
        print(f"Found {len(tenants)} tenants to reconcile.")
        for tenant in tenants:
            print(f"Reconciling tenant: {tenant.name} ({tenant.id})...")
            # Set the tenant context so RLS/filtering works correctly
            token = tenant_context.set(tenant.id)
            try:
                reconcile_payments_and_invoices(db, tenant.id)
            finally:
                tenant_context.reset(token)
        print("Reconciliation successfully completed for all tenants!")
    except Exception as e:
        print(f"Error during reconciliation: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reconcile_all()
