import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, add_days


class LCApplication(Document):
    def validate(self):
        self.calculate_tolerance()
        self.calculate_total_charges()
        self.set_status()
    
    def on_submit(self):
        self.status = "Submitted to Bank"
    
    def on_cancel(self):
        self.status = "Cancelled"
    
    def calculate_tolerance(self):
        """Calculate tolerance amount based on percentage"""
        if self.lc_amount and self.tolerance_percentage:
            self.tolerance_amount = flt(self.lc_amount) * flt(self.tolerance_percentage) / 100
    
    def calculate_total_charges(self):
        """Calculate total bank charges"""
        self.total_charges = (
            flt(self.opening_charges) +
            flt(self.advising_charges) +
            flt(self.confirmation_charges) +
            flt(self.other_charges)
        )
    
    def set_status(self):
        """Set application status"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 2:
            self.status = "Cancelled"


@frappe.whitelist()
def create_from_commercial_invoice(commercial_invoice):
    """Auto-create LC Application from Commercial Invoice"""
    
    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)
    
    # Check if already exists
    existing = frappe.db.exists("LC Application", {
        "commercial_invoice": commercial_invoice,
        "docstatus": ["!=", 2]
    })
    
    if existing:
        frappe.throw(_("LC Application already exists for this Commercial Invoice: {0}").format(existing))
    
    # Create LC Application
    lc_app = frappe.new_doc("LC Application")
    lc_app.application_date = frappe.utils.today()
    lc_app.company = ci.company
    lc_app.sales_order = ci.sales_order
    lc_app.commercial_invoice = ci.name
    
    # Applicant (Buyer)
    lc_app.applicant_name = ci.customer_name
    lc_app.applicant_address = ci.consignee_address
    lc_app.applicant_country = ci.consignee_country
    
    # Beneficiary (Your company)
    lc_app.beneficiary_name = ci.exporter_name
    lc_app.beneficiary_address = ci.exporter_address
    
    # Copy bank details from CI
    lc_app.beneficiary_bank = ci.beneficiary_bank
    lc_app.beneficiary_account_no = ci.account_number
    lc_app.beneficiary_swift_code = ci.swift_code
    
    # LC Details
    lc_app.lc_amount = ci.grand_total
    lc_app.currency = ci.currency
    lc_app.incoterm = ci.incoterm
    
    # Shipping
    lc_app.port_of_loading = ci.port_of_loading
    lc_app.port_of_discharge = ci.port_of_discharge
    lc_app.description_of_goods = f"As per Commercial Invoice {ci.name}"
    
    # Dates
    if ci.get("latest_shipment_date"):
        lc_app.latest_shipment_date = ci.latest_shipment_date
    else:
        lc_app.latest_shipment_date = add_days(frappe.utils.today(), 30)
    
    # Add standard required documents
    add_standard_documents(lc_app)
    
    lc_app.insert(ignore_mandatory=True)
    
    return lc_app.name


def add_standard_documents(lc_app):
    """Add standard export documents required for LC"""
    standard_docs = [
        {"document_type": "Commercial Invoice", "number_of_originals": 3, "number_of_copies": 2},
        {"document_type": "Packing List", "number_of_originals": 1, "number_of_copies": 2},
        {"document_type": "Bill of Lading", "number_of_originals": 3, "number_of_copies": 0},
        {"document_type": "Certificate of Origin", "number_of_originals": 1, "number_of_copies": 2},
        {"document_type": "Inspection Certificate", "number_of_originals": 1, "number_of_copies": 1},
    ]
    
    for doc in standard_docs:
        lc_app.append("required_documents", doc)


@frappe.whitelist()
def mark_lc_received(application_name, lc_number, lc_date):
    """Mark LC as received and create Letter of Credit doctype"""
    
    lc_app = frappe.get_doc("LC Application", application_name)
    
    if lc_app.status != "Approved" and lc_app.status != "Submitted to Bank":
        frappe.throw(_("LC Application must be approved before marking as received"))
    
    # Create Letter of Credit
    lc = frappe.new_doc("Letter of Credit")
    
    # Copy all fields from application
    lc.lc_number = lc_number
    lc.lc_date = lc_date
    lc.lc_application = lc_app.name
    lc.company = lc_app.company
    lc.sales_order = lc_app.sales_order
    lc.commercial_invoice = lc_app.commercial_invoice
    
    # Copy applicant details
    lc.applicant_name = lc_app.applicant_name
    lc.applicant_address = lc_app.applicant_address
    lc.applicant_country = lc_app.applicant_country
    lc.applicant_bank = lc_app.applicant_bank
    lc.applicant_account_no = lc_app.applicant_account_no
    
    # Copy beneficiary details
    lc.beneficiary_name = lc_app.beneficiary_name
    lc.beneficiary_address = lc_app.beneficiary_address
    lc.beneficiary_country = lc_app.beneficiary_country
    lc.beneficiary_bank = lc_app.beneficiary_bank
    lc.beneficiary_account_no = lc_app.beneficiary_account_no
    lc.beneficiary_swift_code = lc_app.beneficiary_swift_code
    
    # Copy LC details
    lc.lc_type = lc_app.lc_type
    lc.lc_amount = lc_app.lc_amount
    lc.currency = lc_app.currency
    lc.tolerance_percentage = lc_app.tolerance_percentage
    lc.partial_shipment = lc_app.partial_shipment
    lc.transhipment = lc_app.transhipment
    
    # Validity
    lc.lc_expiry_date = add_days(lc_date, lc_app.requested_validity_days)
    lc.latest_shipment_date = lc_app.latest_shipment_date
    lc.presentation_days = lc_app.presentation_days
    lc.expiry_place = lc_app.expiry_place
    
    # Payment terms
    lc.payment_terms = lc_app.payment_terms
    lc.tenor_days = lc_app.tenor_days
    lc.deferred_payment_date = lc_app.deferred_payment_date
    lc.interest_rate = lc_app.interest_rate
    
    # Shipment
    lc.port_of_loading = lc_app.port_of_loading
    lc.port_of_discharge = lc_app.port_of_discharge
    lc.incoterm = lc_app.incoterm
    lc.description_of_goods = lc_app.description_of_goods
    
    # Special conditions
    lc.special_conditions = lc_app.special_conditions
    
    # Copy required documents
    for doc in lc_app.required_documents:
        lc.append("required_documents", {
            "document_type": doc.document_type,
            "number_of_originals": doc.number_of_originals,
            "number_of_copies": doc.number_of_copies,
            "remarks": doc.remarks
        })
    
    # Charges
    lc.opening_charges = lc_app.opening_charges
    lc.advising_charges = lc_app.advising_charges
    lc.confirmation_charges = lc_app.confirmation_charges
    lc.other_charges = lc_app.other_charges
    
    lc.insert(ignore_mandatory=True)
    
    # Update application
    lc_app.status = "LC Received"
    lc_app.lc_number = lc_number
    lc_app.lc_received_date = lc_date
    lc_app.received_lc = lc.name
    lc_app.save()
    
    return lc.name


@frappe.whitelist()
def approve_application(application_name):
    """Approve LC Application"""
    lc_app = frappe.get_doc("LC Application", application_name)
    
    if lc_app.status != "Submitted to Bank":
        frappe.throw(_("Only submitted applications can be approved"))
    
    lc_app.status = "Approved"
    lc_app.save()
    
    frappe.msgprint(_("LC Application approved successfully"))


@frappe.whitelist()
def reject_application(application_name, rejection_reason):
    """Reject LC Application"""
    lc_app = frappe.get_doc("LC Application", application_name)
    
    lc_app.status = "Rejected"
    lc_app.rejection_reason = rejection_reason
    lc_app.save()
    
    frappe.msgprint(_("LC Application rejected"))