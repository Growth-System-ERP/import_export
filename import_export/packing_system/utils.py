import frappe
from frappe.utils import flt

def calc_vol(doc, method=""):
    doc.volume_per_unit = flt(doc.length) * flt(doc.width) * flt(doc.height)

    if doc.volume_per_unit and not doc.dimension_uom:
        doc.dimension_uom = frappe.db.get_single_value("Packing Settings", "default_dimension_uom")
