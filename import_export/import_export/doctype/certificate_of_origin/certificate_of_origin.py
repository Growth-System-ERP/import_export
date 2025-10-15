import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate


class CertificateofOrigin(Document):
    def validate(self):
        self.validate_commercial_invoice()
        self.calculate_validity()
        self.set_status()
    
    def on_submit(self):
        self.status = "Submitted"
    
    def on_cancel(self):
        self.status = "Cancelled"
    
    def validate_commercial_invoice(self):
        """Validate that commercial invoice exists"""
        if not self.commercial_invoice:
            frappe.throw(_("Commercial Invoice is required"))
        
        ci_status = frappe.db.get_value(
            "Commercial Invoice Export", 
            self.commercial_invoice, 
            "docstatus"
        )
        
        if ci_status != 1:
            frappe.throw(_("Commercial Invoice must be submitted"))
    
    def calculate_validity(self):
        """Calculate validity end date"""
        if self.certificate_date and self.validity_period:
            self.valid_until = add_days(
                self.certificate_date, 
                self.validity_period
            )
    
    def set_status(self):
        """Set document status"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1:
            # Check if attested
            if self.attestation_status == "Attested":
                self.status = "Attested"
            else:
                self.status = "Submitted"
            
            # Check if expired
            if self.valid_until and getdate(self.valid_until) < getdate():
                self.status = "Expired"
        elif self.docstatus == 2:
            self.status = "Cancelled"


@frappe.whitelist()
def get_products_from_commercial_invoice(commercial_invoice):
    """Fetch products from Commercial Invoice"""
    if not commercial_invoice:
        return []
    
    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)
    products = []
    
    for item in ci.items:
        products.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "hs_code": item.hs_code,
            "quantity": item.qty,
            "uom": item.uom,
            "country_of_origin": item.country_of_origin,
            "value": item.amount
        })
    
    return products


@frappe.whitelist()
def update_attestation_status(certificate_name, status, attestation_number=None, attested_date=None):
    """Update attestation status from external system or manual entry"""
    doc = frappe.get_doc("Certificate of Origin", certificate_name)
    
    if status not in ["Submitted", "Attested", "Rejected"]:
        frappe.throw(_("Invalid status"))
    
    doc.attestation_status = status
    
    if status == "Attested":
        doc.attestation_number = attestation_number
        doc.attested_date = attested_date or frappe.utils.today()
    
    doc.save()
    
    return {"message": "Attestation status updated successfully"}