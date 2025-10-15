import frappe
from frappe import _


def sales_order_validate(doc, method):
    """Validate export sales orders"""
    if doc.gst_category == "Overseas":
        validate_export_order(doc)


def validate_export_order(doc):
    """Validate export-specific fields"""
    # Check incoterm
    if not doc.get("incoterm"):
        frappe.throw(_("Incoterm is mandatory for export orders"))
    
    # Check payment method
    # if not doc.get("payment_method"):
    #     frappe.throw(_("Payment Method is mandatory for export orders"))
    
    # Validate HS codes for all items
    missing_hs_codes = []
    for item in doc.items:
        hs_code = frappe.db.get_value("Item", item.item_code, "gst_hsn_code")
        if not hs_code:
            missing_hs_codes.append(item.item_code)
    
    if missing_hs_codes:
        frappe.throw(_(
            "Following items are missing HS codes: {0}. "
            "HS codes are mandatory for export orders."
        ).format(", ".join(missing_hs_codes)))
    
    # Validate country of origin for items (warning only)
    missing_origin = []
    for item in doc.items:
        country_of_origin = frappe.db.get_value("Item", item.item_code, "country_of_origin")
        if not country_of_origin:
            missing_origin.append(item.item_code)
    
    if missing_origin:
        frappe.msgprint(_(
            "Warning: Following items are missing Country of Origin: {0}. "
            "This may be required for customs clearance."
        ).format(", ".join(missing_origin)), indicator="orange", alert=True)
