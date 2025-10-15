import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ShippingBill(Document):
    def validate(self):
        self.validate_commercial_invoice()
        self.calculate_totals()
        self.calculate_incentives()
        self.set_status()
    
    def on_submit(self):
        self.status = "Submitted"
    
    def on_cancel(self):
        self.status = "Cancelled"
    
    def validate_commercial_invoice(self):
        """Validate commercial invoice exists and is submitted"""
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
        """Calculate FOB values from items"""
        self.total_fob_value_inr = 0
        self.total_fob_value_fc = 0
        
        for item in self.items:
            if not item.fob_value_inr:
                item.fob_value_inr = flt(item.fob_value_fc) * flt(self.exchange_rate)
            
            self.total_fob_value_inr += flt(item.fob_value_inr)
            self.total_fob_value_fc += flt(item.fob_value_fc)
            
            # Calculate drawback for each item
            if item.drawback_rate and item.assessable_value:
                item.drawback_amount = (
                    flt(item.assessable_value) * flt(item.drawback_rate) / 100
                )
    
    def calculate_incentives(self):
        """Calculate export incentives"""
        # Calculate RoDTEP if claimed
        if self.rodtep_claimed and self.rodtep_rate:
            self.rodtep_amount = (
                flt(self.total_fob_value_inr) * flt(self.rodtep_rate) / 100
            )
        
        # Calculate total drawback
        if self.duty_drawback_claimed:
            self.drawback_amount = sum(
                flt(item.drawback_amount) for item in self.items
            )
    
    def set_status(self):
        """Set document status"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1:
            if self.sb_status == "Cleared":
                self.status = "Cleared"
            elif self.sb_status == "Filed":
                self.status = "Filed"
            else:
                self.status = "Submitted"
        elif self.docstatus == 2:
            self.status = "Cancelled"


@frappe.whitelist()
def get_items_from_commercial_invoice(commercial_invoice):
    """Fetch items from Commercial Invoice for Shipping Bill"""
    if not commercial_invoice:
        return []
    
    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)
    
    items = []
    for item in ci.items:
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "hs_code": item.hs_code,
            "quantity": item.qty,
            "uom": item.uom,
            "fob_value_fc": item.amount,
            "fob_value_inr": flt(item.amount) * flt(ci.conversion_rate),
            "assessable_value": flt(item.amount) * flt(ci.conversion_rate)
        })
    
    return items


@frappe.whitelist()
def update_customs_status(shipping_bill_name, sb_status, leo_date=None, 
                          shipping_bill_no=None, assessment_date=None):
    """Update customs processing status"""
    doc = frappe.get_doc("Shipping Bill", shipping_bill_name)
    
    if sb_status not in ["Filed", "Assessed", "Cleared", "Shipped", "Rejected"]:
        frappe.throw(_("Invalid status"))
    
    doc.sb_status = sb_status
    
    if shipping_bill_no:
        doc.shipping_bill_no = shipping_bill_no
    
    if leo_date:
        doc.leo_date = leo_date
    
    if assessment_date:
        doc.assessment_date = assessment_date
    
    doc.save()
    
    return {"message": "Status updated successfully"}
