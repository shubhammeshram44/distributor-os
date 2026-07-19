import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session, aliased
from app.models.inventory import Inventory
from app.models.product import Product, ProductSupplierMapping
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.customer import Customer
from app.database import tenant_context

class InventoryService:
    def calculate_current_stock(self, db: Session, product_id: uuid.UUID) -> Dict[str, int]:
        """
        Calculates physical stock levels and net available quantity.
        """
        stmt = select(Inventory).where(Inventory.sku_id == product_id)
        inv = db.execute(stmt).scalar_one_or_none()
        if not inv:
            return {
                "quantity_on_hand": 0,
                "quantity_committed": 0,
                "net_available": 0,
                "low_stock_threshold": 10
            }
        return {
            "quantity_on_hand": inv.quantity_on_hand,
            "quantity_committed": inv.quantity_committed,
            "net_available": inv.quantity_on_hand - inv.quantity_committed,
            "low_stock_threshold": inv.low_stock_threshold
        }

    def alert_low_stock(self, db: Session, product_id: uuid.UUID) -> bool:
        """
        Triggers an alert if quantity on hand drops below or matches the threshold.
        """
        levels = self.calculate_current_stock(db, product_id)
        return levels["quantity_on_hand"] < levels["low_stock_threshold"]

    def calculate_sales_velocity(self, db: Session, product_id: uuid.UUID, timeframe_days: int = 30) -> float:
        """
        Calculates quantity sold per day for a product based on confirmed/dispatched orders.
        """
        if timeframe_days <= 0:
            timeframe_days = 30

        cutoff_date = datetime.utcnow() - timedelta(days=timeframe_days)

        # Query all confirmed or dispatched line items for this product
        # Note: Order status is determined dynamically from the latest ledger state.
        # But we can query orders created in the timeframe and check their current status.
        stmt = (
            select(func.sum(OrderLineItem.quantity))
            .join(Order, OrderLineItem.order_id == Order.id)
            .where(
                and_(
                    OrderLineItem.product_id == product_id,
                    Order.created_at >= cutoff_date
                )
            )
        )
        # Verify status is confirmed, picked or dispatched (not Draft)
        # We check the latest state in the ledger
        ledger_alias = aliased(OrderStateLedger)
        subq = (
            select(OrderStateLedger.order_id)
            .where(
                and_(
                    OrderStateLedger.to_status != "Draft",
                    OrderStateLedger.timestamp == (
                        select(func.max(ledger_alias.timestamp))
                        .where(ledger_alias.order_id == OrderStateLedger.order_id)
                        .scalar_subquery()
                    )
                )
            )
        )

        stmt = stmt.where(Order.id.in_(subq))
        total_sold = db.execute(stmt).scalar() or 0

        return round(float(total_sold) / timeframe_days, 2)

    def _evaluate_reorder_for_product(
        self, db: Session, product: Product, lead_time_days: int
    ) -> Optional[Dict[str, Any]]:
        """
        Core reorder-point math shared by both the per-supplier and tenant-wide
        suggestion methods. Returns None if no reorder is currently needed.
        """
        stock = self.calculate_current_stock(db, product.id)
        available = stock["net_available"]
        on_hand = stock["quantity_on_hand"]

        # Calculate 30-day velocity
        velocity = self.calculate_sales_velocity(db, product.id, timeframe_days=30)

        # Reorder Point (ROP) = Velocity * Lead Time * Safety Factor (1.5)
        rop = velocity * lead_time_days * 1.5

        reorder_needed = False
        suggested_qty = 0

        # If velocity > 0 and stock falls below ROP
        if velocity > 0:
            if available <= rop:
                reorder_needed = True
                # Target stock is 30 days of inventory coverage
                target_stock = velocity * 30
                suggested_qty = int(max(0, target_stock - available))
        else:
            # Fallback: if velocity is 0, check if physical stock is below the low stock threshold
            if on_hand < stock["low_stock_threshold"]:
                reorder_needed = True
                # Order a default bulk coverage
                suggested_qty = stock["low_stock_threshold"] * 5

        if not reorder_needed or suggested_qty <= 0:
            return None

        return {
            "product_id": str(product.id),
            "sku_id": product.sku_id,
            "brand": product.brand,
            "category": product.category,
            "current_quantity_on_hand": on_hand,
            "current_net_available": available,
            "sales_velocity_per_day": velocity,
            "reorder_point": round(rop, 2),
            "suggested_reorder_quantity": suggested_qty,
        }

    def get_ai_reorder_suggestions(self, db: Session, supplier_id: uuid.UUID, lead_time_days: int = 7) -> List[Dict[str, Any]]:
        """
        Analyzes sales velocity and stock levels for all products mapped to a supplier
        and recommends purchase order quantities.
        """
        suggestions = []

        # Find all products mapped to this supplier
        mapping_stmt = select(ProductSupplierMapping).where(ProductSupplierMapping.supplier_id == supplier_id)
        mappings = db.execute(mapping_stmt).scalars().all()

        for mapping in mappings:
            product = db.get(Product, mapping.product_id)
            if not product:
                continue

            suggestion = self._evaluate_reorder_for_product(db, product, lead_time_days)
            if suggestion:
                suggestion["is_primary_supplier"] = mapping.is_primary
                suggestions.append(suggestion)

        return suggestions

    def get_tenant_reorder_suggestions(
        self, db: Session, tenant_id: uuid.UUID, lead_time_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Tenant-wide version of get_ai_reorder_suggestions: evaluates every
        product that has a supplier mapping for this tenant (regardless of
        which supplier), and attaches the mapped supplier's name/phone so the
        caller can act on the suggestion (e.g. message the supplier) without
        an extra round trip. Results are sorted most-urgent first.
        """
        mapping_stmt = select(ProductSupplierMapping).where(ProductSupplierMapping.tenant_id == tenant_id)
        mappings = db.execute(mapping_stmt).scalars().all()
        if not mappings:
            return []

        # Batch-fetch products and suppliers referenced by the mappings to avoid N+1 lookups.
        product_ids = {m.product_id for m in mappings}
        supplier_ids = {m.supplier_id for m in mappings}

        products_by_id = {
            p.id: p for p in db.execute(select(Product).where(Product.id.in_(product_ids))).scalars().all()
        }
        suppliers_by_id = {
            c.id: c for c in db.execute(select(Customer).where(Customer.id.in_(supplier_ids))).scalars().all()
        }

        # Only evaluate each product once, even if mapped to multiple suppliers
        # (prefer the primary supplier mapping when one exists).
        best_mapping_per_product: Dict[uuid.UUID, ProductSupplierMapping] = {}
        for mapping in mappings:
            existing = best_mapping_per_product.get(mapping.product_id)
            if existing is None or (mapping.is_primary and not existing.is_primary):
                best_mapping_per_product[mapping.product_id] = mapping

        suggestions = []
        for product_id, mapping in best_mapping_per_product.items():
            product = products_by_id.get(product_id)
            if not product:
                continue

            suggestion = self._evaluate_reorder_for_product(db, product, lead_time_days)
            if not suggestion:
                continue

            supplier = suppliers_by_id.get(mapping.supplier_id)
            suggestion["is_primary_supplier"] = mapping.is_primary
            suggestion["supplier_id"] = str(mapping.supplier_id)
            suggestion["supplier_name"] = supplier.retailer_name if supplier else "Unknown Supplier"
            suggestion["supplier_phone"] = supplier.phone_number if supplier else None
            suggestions.append(suggestion)

        # Most urgent first: lowest net-available-to-reorder-point ratio surfaces first.
        def urgency_key(s: Dict[str, Any]):
            rop = s["reorder_point"] or 1
            return s["current_net_available"] / rop if rop else -1

        suggestions.sort(key=urgency_key)
        return suggestions
