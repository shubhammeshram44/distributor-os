"""
Permission Service — single source of truth for RBAC.

ALL permission keys are defined here.
Default role permissions are seeded from DEFAULT_ROLE_PERMISSIONS.
"""

from app.models.permission import Permission, RolePermission
from sqlalchemy.orm import Session
import uuid

# ── ALL PERMISSION KEYS ──────────────────────────────────────────────────────

ALL_PERMISSIONS = [
    # Orders
    {"key": "orders.view",    "label": "View Orders",    "category": "Orders",   "description": "View all orders"},
    {"key": "orders.confirm", "label": "Confirm Orders", "category": "Orders",   "description": "Confirm pending orders"},
    {"key": "orders.cancel",  "label": "Cancel Orders",  "category": "Orders",   "description": "Cancel confirmed orders"},
    {"key": "orders.review",  "label": "Review Orders",  "category": "Orders",   "description": "Review and fix unmatched orders"},
    # Products
    {"key": "products.view",  "label": "View Products",  "category": "Products", "description": "View product catalog"},
    {"key": "products.edit",  "label": "Edit Products",  "category": "Products", "description": "Add and edit products"},
    {"key": "products.delete","label": "Delete Products","category": "Products", "description": "Soft-delete products"},
    # Customers
    {"key": "customers.view", "label": "View Customers", "category": "Customers","description": "View customer list"},
    {"key": "customers.edit", "label": "Edit Customers", "category": "Customers","description": "Add and edit customers"},
    # Inventory
    {"key": "inventory.view", "label": "View Inventory", "category": "Inventory","description": "View stock levels"},
    {"key": "inventory.edit", "label": "Edit Inventory", "category": "Inventory","description": "Update stock levels"},
    # Collections
    {"key": "collections.view",   "label": "View Collections",   "category": "Collections", "description": "View payment collections"},
    {"key": "collections.record", "label": "Record Payments",    "category": "Collections", "description": "Record manual payments"},
    # Van Sales
    {"key": "van_sales.create", "label": "Create Van Sale", "category": "Sales", "description": "Create instant van sale transactions"},
    # Reports
    {"key": "reports.view",   "label": "View Reports",   "category": "Reports",  "description": "Access sales reports and analytics"},
    # Settings
    {"key": "settings.view",  "label": "View Settings",  "category": "Settings", "description": "Access settings pages"},
    {"key": "settings.edit",  "label": "Edit Settings",  "category": "Settings", "description": "Modify business settings"},
    # Integrations
    {"key": "integrations.view", "label": "View Integrations", "category": "Settings", "description": "View integration settings"},
    {"key": "integrations.edit", "label": "Edit Integrations", "category": "Settings", "description": "Connect/disconnect integrations"},
    # Users
    {"key": "users.view",   "label": "View Team Members", "category": "Users", "description": "View team members"},
    {"key": "users.invite", "label": "Invite Users",      "category": "Users", "description": "Invite new team members"},
    {"key": "users.edit",   "label": "Edit User Roles",   "category": "Users", "description": "Change user roles and access"},
    # Shipments
    {"key": "shipments.view",   "label": "View Shipments",   "category": "Shipments", "description": "View shipments"},
    {"key": "shipments.manage", "label": "Manage Shipments", "category": "Shipments", "description": "Create and update shipments"},
]

# ── DEFAULT ROLE PERMISSIONS ─────────────────────────────────────────────────

DEFAULT_ROLE_PERMISSIONS = {
    "SUPER_ADMIN": {p["key"]: True for p in ALL_PERMISSIONS},  # all True

    "OPERATOR": {
        "orders.view": True,
        "orders.confirm": True,
        "orders.cancel": True,
        "orders.review": True,
        "products.view": True,
        "products.edit": True,
        "products.delete": False,
        "customers.view": True,
        "customers.edit": True,
        "inventory.view": True,
        "inventory.edit": True,
        "collections.view": True,
        "collections.record": True,
        "van_sales.create": True,
        "shipments.view": True,
        "shipments.manage": True,
        "reports.view": False,
        "settings.view": False,
        "settings.edit": False,
        "integrations.view": False,
        "integrations.edit": False,
        "users.view": False,
        "users.invite": False,
        "users.edit": False,
    },

    "FINANCE": {
        "orders.view": True,
        "orders.confirm": False,
        "orders.cancel": False,
        "orders.review": False,
        "products.view": True,
        "products.edit": False,
        "products.delete": False,
        "customers.view": True,
        "customers.edit": False,
        "inventory.view": True,
        "inventory.edit": False,
        "collections.view": True,
        "collections.record": True,
        "van_sales.create": False,
        "shipments.view": True,
        "shipments.manage": False,
        "reports.view": True,
        "settings.view": False,
        "settings.edit": False,
        "integrations.view": False,
        "integrations.edit": False,
        "users.view": False,
        "users.invite": False,
        "users.edit": False,
    },

    "DRIVER": {
        "orders.view": True,
        "orders.confirm": False,
        "orders.cancel": False,
        "orders.review": False,
        "products.view": True,
        "products.edit": False,
        "products.delete": False,
        "customers.view": True,
        "customers.edit": False,
        "inventory.view": False,
        "inventory.edit": False,
        "collections.view": False,
        "collections.record": False,
        "van_sales.create": True,
        "shipments.view": True,
        "shipments.manage": False,
        "reports.view": False,
        "settings.view": False,
        "settings.edit": False,
        "integrations.view": False,
        "integrations.edit": False,
        "users.view": False,
        "users.invite": False,
        "users.edit": False,
    },
}


def seed_permissions(db: Session):
    """
    Seeds the permissions master table.
    Safe to run multiple times — skips existing entries.
    """
    for perm_data in ALL_PERMISSIONS:
        existing = db.query(Permission).filter(
            Permission.key == perm_data["key"]
        ).first()
        if not existing:
            db.add(Permission(**perm_data, id=uuid.uuid4()))
    db.commit()


def seed_role_permissions_for_tenant(db: Session, tenant_id: uuid.UUID):
    """
    Seeds default role permissions for a new tenant.
    Called when a new tenant is created.
    Safe to run multiple times — skips existing entries.
    Optimized: skips entirely if any permissions are already mapped for this tenant.
    """
    existing_count = db.query(RolePermission).filter(
        RolePermission.tenant_id == tenant_id
    ).count()
    if existing_count > 0:
        return

    for role, permissions in DEFAULT_ROLE_PERMISSIONS.items():
        for permission_key, is_allowed in permissions.items():
            db.add(RolePermission(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                role=role,
                permission_key=permission_key,
                is_allowed=is_allowed
            ))
    db.commit()


def check_permission(
    db: Session,
    tenant_id: uuid.UUID,
    role: str,
    permission_key: str
) -> bool:
    """
    Checks if a role has a specific permission for a tenant.
    SUPER_ADMIN always returns True without DB lookup.
    Falls back to False if no mapping exists.
    """
    if role == "SUPER_ADMIN":
        return True

    mapping = db.query(RolePermission).filter(
        RolePermission.tenant_id == tenant_id,
        RolePermission.role == role,
        RolePermission.permission_key == permission_key
    ).first()

    return mapping.is_allowed if mapping else False


def get_user_permissions(
    db: Session,
    tenant_id: uuid.UUID,
    role: str
) -> list[str]:
    """
    Returns list of all allowed permission keys for a user.
    Used by frontend to show/hide features.
    """
    if role == "SUPER_ADMIN":
        return [p["key"] for p in ALL_PERMISSIONS]

    mappings = db.query(RolePermission).filter(
        RolePermission.tenant_id == tenant_id,
        RolePermission.role == role,
        RolePermission.is_allowed == True
    ).all()

    return [m.permission_key for m in mappings]
