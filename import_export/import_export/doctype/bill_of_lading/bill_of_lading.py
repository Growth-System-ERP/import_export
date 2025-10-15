import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BillofLading(Document):
    def validate(self):
        self.validate_commercial_invoice()
        self.calculate_totals()
        self.set_status()
    
    def on_submit(self):
        self.bl_status = "Issued"
    
    def on_cancel(self):
        self.bl_status = "Cancelled"
    
    def validate_commercial_invoice(self):
        """Validate commercial invoice exists"""
        if not self.commercial_invoice:
            frappe.throw(_("Commercial Invoice is required"))
        
        ci_status = frappe.db.get_value(
            "Commercial Invoice Export", 
            self.commercial_invoice, 
            "docstatus"
        )
        
        if ci_status != 1:
            frappe.throw(_("Commercial Invoice must be submitted"))
    
    def calculate_totals(self):
        """Calculate totals from containers"""
        if not self.containers:
            return
        
        self.total_packages = sum(
            flt(container.no_of_packages) for container in self.containers
        )
        
        self.total_gross_weight = sum(
            flt(container.gross_weight) for container in self.containers
        )
    
    def set_status(self):
        """Set document status"""
        if self.docstatus == 0:
            self.bl_status = "Draft"
        elif self.docstatus == 1:
            self.bl_status = "Issued"
        elif self.docstatus == 2:
            self.bl_status = "Cancelled"


@frappe.whitelist()
def get_containers_from_packing_list(commercial_invoice):
    """Get container details from Packing List"""
    if not commercial_invoice:
        return []
    
    # Find packing list linked to this commercial invoice
    packing_lists = frappe.get_all(
        "Packing List Export",
        filters={"commercial_invoice": commercial_invoice, "docstatus": 1},
        limit=1
    )
    
    if not packing_lists:
        return []
    
    packing_list = frappe.get_doc("Packing List Export", packing_lists[0].name)
    
    # Get container info from Commercial Invoice
    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)
    
    containers = []
    if ci.container_nos:
        # Parse container numbers (comma-separated)
        container_numbers = [c.strip() for c in ci.container_nos.split(",")]
        
        for container_no in container_numbers:
            containers.append({
                "container_no": container_no,
                "seal_no": "",  # To be filled manually
                "container_size": packing_list.container_size or "40ft",
                "container_type": "Dry",
                "no_of_packages": int(packing_list.total_cartons) if packing_list.total_cartons else 0,
                "gross_weight": flt(packing_list.total_gross_weight)
            })
    
    return containers


@frappe.whitelist()
def surrender_bl(bl_name):
    """Mark B/L as surrendered (for telex release)"""
    doc = frappe.get_doc("Bill of Lading", bl_name)
    
    if doc.docstatus != 1:
        frappe.throw(_("Only submitted B/L can be surrendered"))
    
    doc.bl_status = "Surrendered"
    doc.save()
    
    return {"message": "B/L surrendered successfully"}
