import uuid

from app.database import tenant_context
from app.models.customer import Customer, CustomerAlias
from app.models.tenant import DistributorTenant


def test_inline_van_sales_customer_inherits_tenant_defaults_and_alias(db_session):
    tenant = DistributorTenant(
        name="Van Sales Defaults Tenant",
        default_customer_credit_limit=7500.0,
        default_customer_payment_terms="Net 21",
    )
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    # This is the exact temporary signature currently used by
    # /orders/instant-transaction for an inline-created Van Sales customer.
    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        retailer_name="Inline Kirana",
        phone_number="9876543210",
        credit_limit=0.0,
        outstanding_balance=0.0,
        payment_terms="Net 0",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    assert float(customer.credit_limit) == 7500.0
    assert customer.payment_terms == "Net 21"

    alias = db_session.query(CustomerAlias).filter(
        CustomerAlias.tenant_id == tenant.id,
        CustomerAlias.customer_id == customer.id,
    ).one()
    assert alias.alias_value == "+919876543210"


def test_customer_defaults_fall_back_to_product_defaults(db_session):
    tenant = DistributorTenant(name="Default Defaults Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        retailer_name="Default Kirana",
        phone_number="9123456789",
        credit_limit=0.0,
        outstanding_balance=0.0,
        payment_terms="Net 0",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    assert float(customer.credit_limit) == 5000.0
    assert customer.payment_terms == "Net 30"


def test_non_inline_customer_keeps_explicit_commercial_terms(db_session):
    tenant = DistributorTenant(
        name="Explicit Terms Tenant",
        default_customer_credit_limit=5000.0,
        default_customer_payment_terms="Net 30",
    )
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        retailer_name="Configured Customer",
        phone_number="9988776655",
        credit_limit=25000.0,
        outstanding_balance=0.0,
        payment_terms="Net 45",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    assert float(customer.credit_limit) == 25000.0
    assert customer.payment_terms == "Net 45"
    # The listener is deliberately scoped to Van Sales inline creation so
    # existing customer creation flows remain unchanged.
    alias_count = db_session.query(CustomerAlias).filter(
        CustomerAlias.customer_id == customer.id
    ).count()
    assert alias_count == 0
