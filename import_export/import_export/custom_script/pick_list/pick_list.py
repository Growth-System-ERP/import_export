import frappe

def pick_list_validate(doc, method):
    """Validate pick list for export orders"""
    if not doc.sales_order:
        return
    
    # Check if this is an export order
    gst_category = frappe.db.get_value("Sales Order", doc.sales_order, "gst_category")
    
    if gst_category == "Overseas":
        # Ensure packing calculation is done before submission
        if doc.docstatus == 1 and (not doc.get("carton_assignments") or len(doc.carton_assignments) == 0):
            frappe.msgprint(_(
                "Warning: Packing calculation not done for export order. "
                "Please run packing calculation before creating export documents."
            ), indicator="orange", alert=True)
