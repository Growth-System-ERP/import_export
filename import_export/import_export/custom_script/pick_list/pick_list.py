import frappe
from frappe import _

def pick_list_validate(doc, method):
    """Validate pick list for export orders"""
    sales_orders = set([d.sales_order for d in doc.locations])

    if not sales_orders:
        return

    # Check if this is an export order
    gst_category = frappe.db.get_value("Sales Order", sales_orders, "gst_category")

    if gst_category == "Overseas":
        if len(sales_orders) > 1:
            frappe.throw(_("Can't combine multiple sales orders in export"))

        # Ensure packing calculation is done before submission
        if doc.docstatus == 1 and (not doc.get("carton_assignments") or len(doc.carton_assignments) == 0):
            frappe.msgprint(_(
                "Warning: Packing calculation not done for export order. "
                "Please run packing calculation before creating export documents."
            ), indicator="orange", alert=True)
