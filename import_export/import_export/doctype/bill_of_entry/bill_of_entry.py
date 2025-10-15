import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BillofEntry(Document):
    def validate(self):
        if doc.port_code and len(doc.port_code) != 6:
            frappe.msgprint(_(
                "Port Code should be 6 digits as per Indian customs format"
            ), indicator="orange", alert=True)

        self.calculate_duties()
        self.calculate_totals()
        self.set_status()
    
    def on_submit(self):
        self.status = "Submitted"
    
    def on_cancel(self):
        self.status = "Cancelled"
    
    def calculate_duties(self):
        """Calculate customs duty, IGST, and cess for each item"""
        for item in self.items:
            assessable_value = flt(item.assessable_value)
            
            # Calculate customs duty
            if item.customs_duty_rate:
                item.customs_duty = assessable_value * flt(item.customs_duty_rate) / 100
            
            # Calculate IGST (on assessable value + customs duty)
            if item.igst_rate:
                igst_base = assessable_value + flt(item.customs_duty)
                item.igst_amount = igst_base * flt(item.igst_rate) / 100
            
            # Calculate cess
            if item.cess_rate:
                cess_base = assessable_value + flt(item.customs_duty)
                item.cess_amount = cess_base * flt(item.cess_rate) / 100
            
            # Total duty per item
            item.total_duty = (
                flt(item.customs_duty) + 
                flt(item.igst_amount) + 
                flt(item.cess_amount)
            )
    
    def calculate_totals(self):
        """Calculate total assessable value and duties"""
        self.total_assessable_value = sum(
            flt(item.assessable_value) for item in self.items
        )
        
        self.total_customs_duty = sum(
            flt(item.customs_duty) for item in self.items
        )
        
        self.total_igst = sum(
            flt(item.igst_amount) for item in self.items
        )
        
        self.total_cess = sum(
            flt(item.cess_amount) for item in self.items
        )
        
        self.total_duty_payable = (
            flt(self.total_customs_duty) + 
            flt(self.total_igst) + 
            flt(self.total_cess) + 
            flt(self.other_charges)
        )
    
    def set_status(self):
        """Set document status"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1:
            if self.be_status == "Cleared":
                self.status = "Cleared"
            else:
                self.status = "Submitted"
        elif self.docstatus == 2:
            self.status = "Cancelled"


@frappe.whitelist()
def get_items_from_purchase_invoice(purchase_invoice):
    """Fetch items from Purchase Invoice for Bill of Entry"""
    if not purchase_invoice:
        return []
    
    pi = frappe.get_doc("Purchase Invoice", purchase_invoice)
    
    items = []
    for item in pi.items:
        item_doc = frappe.get_doc("Item", item.item_code)
        
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "hs_code": item_doc.get("gst_hsn_code"),
            "quantity": item.qty,
            "uom": item.uom,
            "assessable_value": item.amount
        })
    
    return items


@frappe.whitelist()
def update_customs_clearance(be_name, be_status, be_number=None, 
                             assessment_date=None, out_of_charge_date=None):
    """Update customs clearance status"""
    doc = frappe.get_doc("Bill of Entry", be_name)
    
    if be_status not in ["Filed", "Assessed", "Duty Paid", "Cleared", "Rejected"]:
        frappe.throw(_("Invalid status"))
    
    doc.be_status = be_status
    
    if be_number:
        doc.be_number = be_number
    
    if assessment_date:
        doc.assessment_date = assessment_date
    
    if out_of_charge_date:
        doc.out_of_charge_date = out_of_charge_date
    
    doc.save()
    
    return {"message": "Status updated successfully"}


@frappe.whitelist()
def calculate_duty_estimate(hs_code, assessable_value, country_of_origin):
    """Estimate customs duty based on HS code and country"""
    # This would integrate with customs tariff database
    # For now, return basic structure
    
    # Default rates (to be replaced with actual tariff lookup)
    customs_duty_rate = 10.0  # Default 10%
    igst_rate = 18.0  # Default 18%
    cess_rate = 0.0
    
    # Calculate duties
    customs_duty = flt(assessable_value) * customs_duty_rate / 100
    igst_base = flt(assessable_value) + customs_duty
    igst = igst_base * igst_rate / 100
    cess = igst_base * cess_rate / 100
    
    total_duty = customs_duty + igst + cess
    
    return {
        "customs_duty_rate": customs_duty_rate,
        "customs_duty": customs_duty,
        "igst_rate": igst_rate,
        "igst_amount": igst,
        "cess_rate": cess_rate,
        "cess_amount": cess,
        "total_duty": total_duty,
        "message": "Estimated duties calculated (rates may vary)"
    }
