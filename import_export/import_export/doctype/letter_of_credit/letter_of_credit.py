import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, add_days, today


class LetterofCredit(Document):
    def validate(self):
        self.calculate_tolerance()
        self.calculate_available_balance()
        self.calculate_total_charges()
        self.update_status()
        self.validate_dates()
    
    def on_submit(self):
        self.status = "Active"
    
    def on_cancel(self):
        self.status = "Cancelled"
    
    def calculate_tolerance(self):
        """Calculate tolerance amount"""
        if self.lc_amount and self.tolerance_percentage:
            self.tolerance_amount = flt(self.lc_amount) * flt(self.tolerance_percentage) / 100
    
    def calculate_available_balance(self):
        """Calculate available balance after utilization"""
        max_amount = flt(self.lc_amount) + flt(self.tolerance_amount)
        
        # Calculate total utilized
        total_utilized = 0
        if self.shipments:
            for shipment in self.shipments:
                if shipment.presentation_status in ["Presented", "Accepted", "Paid"]:
                    total_utilized += flt(shipment.invoice_amount)
        
        self.total_utilized_amount = total_utilized
        self.available_balance = max_amount - total_utilized
        self.remaining_balance = self.available_balance
    
    def calculate_total_charges(self):
        """Calculate total bank charges"""
        self.total_charges = (
            flt(self.opening_charges) +
            flt(self.advising_charges_total) +
            flt(self.confirmation_charges_total) +
            flt(self.amendment_charges) +
            flt(self.other_charges)
        )
        
        # Calculate amendment charges from amendments table
        if self.amendments:
            amendment_charges = sum(flt(amd.charges) for amd in self.amendments if amd.status == "Approved")
            self.amendment_charges = amendment_charges
    
    def update_status(self):
        """Update LC status based on utilization and expiry"""
        if self.docstatus == 0:
            self.status = "Draft"
            return
        
        if self.docstatus == 2:
            self.status = "Cancelled"
            return
        
        # Check expiry
        if getdate(self.lc_expiry_date) < getdate(today()):
            self.status = "Expired"
            return
        
        # Check utilization
        if self.available_balance <= 0:
            self.status = "Fully Utilized"
        elif self.total_utilized_amount > 0:
            self.status = "Partially Utilized"
        else:
            self.status = "Active"
    
    def validate_dates(self):
        """Validate date logic"""
        if getdate(self.latest_shipment_date) > getdate(self.lc_expiry_date):
            frappe.throw(_("Latest Shipment Date cannot be after LC Expiry Date"))
        
        if getdate(self.lc_date) > getdate(self.lc_expiry_date):
            frappe.throw(_("LC Issue Date cannot be after LC Expiry Date"))


@frappe.whitelist()
def add_amendment(lc_name, amendment_number, amendment_date, amendment_type, amendment_details, charges=0):
    """Add amendment to LC"""
    
    lc = frappe.get_doc("Letter of Credit", lc_name)
    
    if lc.docstatus != 1:
        frappe.throw(_("LC must be submitted to add amendments"))
    
    lc.append("amendments", {
        "amendment_number": amendment_number,
        "amendment_date": amendment_date,
        "amendment_type": amendment_type,
        "amendment_details": amendment_details,
        "charges": charges,
        "status": "Pending"
    })
    
    lc.save()
    
    frappe.msgprint(_("Amendment added successfully"))
    return lc.name


@frappe.whitelist()
def approve_amendment(lc_name, amendment_idx):
    """Approve LC amendment"""
    
    lc = frappe.get_doc("Letter of Credit", lc_name)
    
    if amendment_idx >= len(lc.amendments):
        frappe.throw(_("Invalid amendment index"))
    
    amendment = lc.amendments[amendment_idx]
    amendment.status = "Approved"
    
    # Apply amendment based on type
    if amendment.amendment_type == "Amount Increase":
        # Extract amount from details (simple parsing)
        try:
            amount_str = ''.join(filter(str.isdigit, amendment.amendment_details))
            if amount_str:
                increase_amount = float(amount_str)
                lc.lc_amount = flt(lc.lc_amount) + increase_amount
        except:
            pass
    
    elif amendment.amendment_type == "Expiry Extension":
        # This would need manual adjustment
        frappe.msgprint(_("Please manually update the expiry date"))
    
    lc.save()
    
    frappe.msgprint(_("Amendment approved"))


@frappe.whitelist()
def add_shipment(lc_name, shipment_data):
    """Add shipment/presentation to LC"""
    
    import json
    if isinstance(shipment_data, str):
        shipment_data = json.loads(shipment_data)
    
    lc = frappe.get_doc("Letter of Credit", lc_name)
    
    if lc.docstatus != 1:
        frappe.throw(_("LC must be submitted to add shipments"))
    
    # Check available balance
    invoice_amount = flt(shipment_data.get("invoice_amount"))
    if invoice_amount > lc.available_balance:
        frappe.throw(_("Invoice amount {0} exceeds available LC balance {1}").format(
            invoice_amount, lc.available_balance
        ))
    
    # Check shipment date
    shipment_date = getdate(shipment_data.get("shipment_date"))
    if shipment_date > getdate(lc.latest_shipment_date):
        frappe.throw(_("Shipment date is after latest shipment date allowed in LC"))
    
    lc.append("shipments", {
        "shipment_number": shipment_data.get("shipment_number"),
        "shipment_date": shipment_data.get("shipment_date"),
        "invoice_number": shipment_data.get("invoice_number"),
        "invoice_amount": invoice_amount,
        "bl_number": shipment_data.get("bl_number"),
        "bl_date": shipment_data.get("bl_date"),
        "presentation_status": "Pending"
    })
    
    lc.save()
    
    frappe.msgprint(_("Shipment added successfully"))
    return lc.name


@frappe.whitelist()
def present_documents(lc_name, shipment_idx, presentation_date):
    """Mark documents as presented to bank"""
    
    lc = frappe.get_doc("Letter of Credit", lc_name)
    
    if shipment_idx >= len(lc.shipments):
        frappe.throw(_("Invalid shipment index"))
    
    shipment = lc.shipments[shipment_idx]
    
    # Check presentation deadline
    presentation_deadline = add_days(shipment.shipment_date, lc.presentation_days)
    if getdate(presentation_date) > presentation_deadline:
        frappe.msgprint(
            _("Warning: Documents presented after deadline ({0})").format(presentation_deadline),
            indicator="orange",
            alert=True
        )
    
    shipment.presentation_date = presentation_date
    shipment.presentation_status = "Presented"
    
    lc.save()
    
    frappe.msgprint(_("Documents marked as presented"))


@frappe.whitelist()
def mark_discrepancy(lc_name, shipment_idx, discrepancy_details):
    """Mark shipment as having discrepancy"""
    
    lc = frappe.get_doc("Letter of Credit", lc_name)
    
    if shipment_idx >= len(lc.shipments):
        frappe.throw(_("Invalid shipment index"))
    
    shipment = lc.shipments[shipment_idx]
    shipment.presentation_status = "Discrepancy"
    shipment.discrepancy_details = discrepancy_details
    
    lc.save()
    
    frappe.msgprint(_("Discrepancy recorded"), indicator="orange")


@frappe.whitelist()
def accept_documents(lc_name, shipment_idx):
    """Accept documents (no discrepancy)"""
    
    lc = frappe.get_doc("Letter of Credit", lc_name)
    
    if shipment_idx >= len(lc.shipments):
        frappe.throw(_("Invalid shipment index"))
    
    shipment = lc.shipments[shipment_idx]
    shipment.presentation_status = "Accepted"
    
    lc.save()
    
    frappe.msgprint(_("Documents accepted"), indicator="green")


@frappe.whitelist()
def mark_payment_received(lc_name, shipment_idx, payment_date, payment_amount):
    """Mark payment as received"""
    
    lc = frappe.get_doc("Letter of Credit", lc_name)
    
    if shipment_idx >= len(lc.shipments):
        frappe.throw(_("Invalid shipment index"))
    
    shipment = lc.shipments[shipment_idx]
    shipment.presentation_status = "Paid"
    shipment.payment_received_date = payment_date
    shipment.payment_received_amount = payment_amount
    
    lc.save()
    
    frappe.msgprint(_("Payment recorded"), indicator="green")


@frappe.whitelist()
def close_lc(lc_name, closure_reason):
    """Close LC before expiry"""
    
    lc = frappe.get_doc("Letter of Credit", lc_name)
    
    if lc.status in ["Closed", "Cancelled", "Expired"]:
        frappe.throw(_("LC is already {0}").format(lc.status))
    
    lc.status = "Closed"
    lc.closure_date = today()
    lc.closure_reason = closure_reason
    
    lc.save()
    
    frappe.msgprint(_("LC closed successfully"))


@frappe.whitelist()
def get_lc_summary(lc_name):
    """Get LC utilization summary"""
    
    lc = frappe.get_doc("Letter of Credit", lc_name)
    
    summary = {
        "lc_number": lc.lc_number,
        "lc_amount": lc.lc_amount,
        "currency": lc.currency,
        "available_balance": lc.available_balance,
        "total_utilized": lc.total_utilized_amount,
        "utilization_percentage": (lc.total_utilized_amount / lc.lc_amount * 100) if lc.lc_amount else 0,
        "expiry_date": lc.lc_expiry_date,
        "days_to_expiry": (getdate(lc.lc_expiry_date) - getdate(today())).days,
        "status": lc.status,
        "total_shipments": len(lc.shipments) if lc.shipments else 0,
        "pending_presentations": sum(1 for s in lc.shipments if s.presentation_status == "Pending") if lc.shipments else 0,
        "payments_pending": sum(1 for s in lc.shipments if s.presentation_status in ["Presented", "Accepted"]) if lc.shipments else 0
    }
    
    return summary