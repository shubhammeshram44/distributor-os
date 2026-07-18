"""
Tally-compatible XML export for confirmed orders/invoices.

Why this exists
----------------
DistributorOS is not trying to replace Tally for GST filing/accounting —
distributors keep using Tally (or hand data to their CA) for that. What was
missing is a bridge: without this, every order captured via WhatsApp still
has to be *manually retyped* into Tally, which defeats the "stop losing
orders in WhatsApp, save time" pitch.

This module generates a real Tally XML import payload (the same
ENVELOPE / IMPORTDATA / TALLYMESSAGE / VOUCHER schema Tally's own XML
import feature expects — verified against Tally's documented Sales
Voucher XML format) so a distributor can import a batch of confirmed
orders as Sales Vouchers directly into Tally with a few clicks, instead
of manual re-entry.

Scope (intentionally): only confirmed sales (Order.status in
CONFIRMED/DISPATCHED/DELIVERED) are exported as Sales Vouchers. Draft/
Cancelled orders are excluded since they aren't real, ledger-worthy sales.
"""
from datetime import datetime
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from app.models.order import Order, OrderLineItem
from app.models.customer import Customer
from app.models.tenant import DistributorTenant

# Only these order lifecycle states represent a real, ledger-worthy sale.
EXPORTABLE_STATUSES = ("Confirmed", "Dispatched", "Delivered")


def _tally_date(dt: datetime) -> str:
    """Tally expects dates as YYYYMMDD (no separators)."""
    return dt.strftime("%Y%m%d")


def _line_item_amount(item: OrderLineItem) -> float:
    qty = item.allocated_quantity if item.allocated_quantity is not None else item.quantity
    return float(qty) * float(item.unit_price)


def build_tally_sales_xml(
    db: Session,
    tenant_id,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> tuple[bytes, int]:
    """
    Returns (xml_bytes, voucher_count) for all exportable orders for the
    tenant within [start_dt, end_dt] (inclusive), oldest first.
    """
    tenant = db.get(DistributorTenant, tenant_id)
    company_name = tenant.name if tenant else "DistributorOS Export"

    query = db.query(Order).filter(
        Order.tenant_id == tenant_id,
        Order.status.in_(EXPORTABLE_STATUSES),
    )
    if start_dt:
        query = query.filter(Order.created_at >= start_dt)
    if end_dt:
        query = query.filter(Order.created_at <= end_dt)
    orders = query.order_by(Order.created_at.asc()).all()

    messages: list[str] = []
    voucher_count = 0

    for order in orders:
        customer = db.get(Customer, order.customer_id)
        if not customer:
            continue

        items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
        if not items:
            continue

        total_amount = sum(_line_item_amount(item) for item in items)
        if total_amount <= 0:
            continue

        party_ledger_name = escape(customer.retailer_name or "Unnamed Customer")
        voucher_number = escape(order.internal_order_id)
        voucher_date = _tally_date(order.created_at)
        narration = escape(f"Sales voucher auto-exported from DistributorOS for order {order.internal_order_id}")

        inventory_entries = []
        for item in items:
            qty = item.allocated_quantity if item.allocated_quantity is not None else item.quantity
            amount = _line_item_amount(item)
            stock_item_name = escape(item.product.sku_id if item.product else (item.unmatched_raw_text or "Unknown Item"))
            inventory_entries.append(f"""
        <ALLINVENTORYENTRIES.LIST>
         <STOCKITEMNAME>{stock_item_name}</STOCKITEMNAME>
         <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
         <RATE>{float(item.unit_price):.2f}/Nos</RATE>
         <AMOUNT>{amount:.2f}</AMOUNT>
         <ACTUALQTY>{qty} Nos</ACTUALQTY>
         <BILLEDQTY>{qty} Nos</BILLEDQTY>
        </ALLINVENTORYENTRIES.LIST>""")

        voucher_xml = f"""
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
     <VOUCHER VCHTYPE="Sales" ACTION="Create">
      <DATE>{voucher_date}</DATE>
      <NARRATION>{narration}</NARRATION>
      <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
      <VOUCHERNUMBER>{voucher_number}</VOUCHERNUMBER>
      <PARTYLEDGERNAME>{party_ledger_name}</PARTYLEDGERNAME>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>{party_ledger_name}</LEDGERNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <AMOUNT>-{total_amount:.2f}</AMOUNT>
      </LEDGERENTRIES.LIST>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>Sales Account</LEDGERNAME>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <AMOUNT>{total_amount:.2f}</AMOUNT>
      </LEDGERENTRIES.LIST>{"".join(inventory_entries)}
     </VOUCHER>
    </TALLYMESSAGE>"""
        messages.append(voucher_xml)
        voucher_count += 1

    xml_doc = f"""<ENVELOPE>
 <HEADER>
  <TALLYREQUEST>Import Data</TALLYREQUEST>
 </HEADER>
 <BODY>
  <IMPORTDATA>
   <REQUESTDESC>
    <REPORTNAME>Vouchers</REPORTNAME>
    <STATICVARIABLES>
     <SVCURRENTCOMPANY>{escape(company_name)}</SVCURRENTCOMPANY>
    </STATICVARIABLES>
   </REQUESTDESC>
   <REQUESTDATA>{"".join(messages)}
   </REQUESTDATA>
  </IMPORTDATA>
 </BODY>
</ENVELOPE>"""

    return xml_doc.encode("utf-8"), voucher_count
