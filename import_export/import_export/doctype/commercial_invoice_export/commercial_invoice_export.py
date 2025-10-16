# File: import_export/import_export/doctype/commercial_invoice_export/commercial_invoice_export.py
# Enhanced with perfect auto-population

import frappe
from frappe import _
from frappe.utils import flt, money_in_words
from frappe.model.document import Document

class CommercialInvoiceExport(Document):
    def validate(self):
        self.set_exporter_details()
        self.set_consignee_details()
        self.calculate_totals()
        self.set_amount_in_words()
        self.set_status()

    def on_submit(self):
        self.validate_items()
        self.validate_imp_fields()
        self.check_duplicate_commercial_invoice()

    def validate_imp_fields(self):
        """Validate commercial invoice before save/submit"""
        # Validate required shipping fields
        if not self.country_of_origin:
            frappe.throw(_("Country of Origin is required"))

        if not self.port_of_loading:
            frappe.throw(_("Port of Loading is required"))

        if not self.port_of_discharge:
            frappe.throw(_("Port of Discharge is required"))

    def validate_items(self):
        """Validate that items exist and have required fields"""
        if not self.items:
            frappe.throw(_("Please add at least one item"))

        for item in self.items:
            if not item.item_code:
                frappe.throw(_("Row {0}: Item Code is required").format(item.idx))

            if not item.hs_code:
                frappe.throw(_("Row {0}: HS Code is required for export").format(item.idx))

            if flt(item.qty) <= 0:
                frappe.throw(_("Row {0}: Quantity must be greater than zero").format(item.idx))

            if flt(item.rate) <= 0:
                frappe.throw(_("Row {0}: Rate must be greater than zero").format(item.idx))


    def check_duplicate_commercial_invoice(self):
        """Ensure only one Commercial Invoice per Sales Order"""
        if not self.sales_order:
            return

        existing = frappe.db.count("Commercial Invoice Export", {
            "sales_order": self.sales_order,
            "name": ["!=", self.name],
            "docstatus": ["!=", 2]
        })

        if existing > 0:
            frappe.msgprint(_(
                "Warning: Another Commercial Invoice already exists for Sales Order {0}"
            ).format(self.sales_order), indicator="orange", alert=True)

    def set_exporter_details(self):
        """Auto-populate exporter details from company"""
        if not self.exporter_name and self.company:
            company = frappe.get_doc("Company", self.company)
            self.exporter_name = company.company_name

            # Get IEC code if custom field exists
            if hasattr(company, 'iec_code'):
                self.iec_code = company.iec_code

    def set_consignee_details(self):
        """Set consignee address display"""
        if self.consignee_address_name:
            address = frappe.get_doc("Address", self.consignee_address_name)
            self.consignee_address = address.get_display()
            if not self.consignee_country:
                self.consignee_country = address.country

    def calculate_totals(self):
        """Calculate all totals"""
        self.total_quantity = 0
        self.total_net_weight = 0
        self.total_gross_weight = 0
        self.total_volume_cbm = 0
        self.subtotal = 0

        for item in self.items:
            self.total_quantity += flt(item.qty)
            self.total_net_weight += flt(item.net_weight)
            self.total_gross_weight += flt(item.gross_weight)
            self.total_volume_cbm += flt(item.volume_per_unit) * flt(item.qty) / 1000000  # Convert cm³ to m³
            self.subtotal += flt(item.amount)

        # Calculate grand total
        self.grand_total = (
            self.subtotal +
            flt(self.freight_charges) +
            flt(self.insurance_charges) +
            flt(self.other_charges)
        )

        # Set FOB and CIF values
        self.total_fob_value = self.subtotal
        self.total_cif_value = self.grand_total

    def set_amount_in_words(self):
        """Set amount in words"""
        if self.grand_total:
            self.in_words = money_in_words(self.grand_total, self.currency)

    def set_status(self):
        """Set document status"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1:
            self.status = "Submitted"
        elif self.docstatus == 2:
            self.status = "Cancelled"


# ==================== AUTO-CREATION FROM SALES ORDER ====================

@frappe.whitelist()
def create_from_sales_order(sales_order):
    """
    Create Commercial Invoice from Sales Order with complete data population
    Returns: name of created Commercial Invoice
    """

    # Get and validate Sales Order
    so = frappe.get_doc("Sales Order", sales_order)

    # Check if export order
    if so.customer_group != "EXPORTER":
        frappe.throw(_("This is not an export order. Customer Group must be 'EXPORTER'"))

    # Check if already submitted
    if so.docstatus != 1:
        frappe.throw(_("Sales Order must be submitted first"))

    # Check if Commercial Invoice already exists
    existing = frappe.db.exists("Commercial Invoice Export", {
        "sales_order": sales_order,
        "docstatus": ["!=", 2]
    })

    if existing:
        frappe.throw(_(
            "Commercial Invoice {0} already exists for this Sales Order"
        ).format(existing))

    # Create new Commercial Invoice
    ci = frappe.new_doc("Commercial Invoice Export")

    # ========== BASIC INFO ==========
    ci.sales_order = so.name
    ci.company = so.company
    ci.invoice_date = frappe.utils.today()
    ci.invoice_type = "Commercial"
    ci.currency = so.currency
    ci.conversion_rate = so.conversion_rate

    # ========== EXPORTER DETAILS ==========
    company_doc = frappe.get_doc("Company", so.company)
    ci.exporter_name = company_doc.company_name

    # Get company address
    if hasattr(so, 'company_address') and so.company_address:
        company_address = frappe.get_doc("Address", so.company_address)
        ci.exporter_address_name = so.company_address
        ci.exporter_address = company_address.get_display()
        ci.exporter_gstin = company_address.gstin if hasattr(company_address, 'gstin') else None

    # Get IEC code from company if exists
    if hasattr(company_doc, 'iec_code'):
        ci.iec_code = company_doc.iec_code

    # ========== CONSIGNEE DETAILS ==========
    ci.customer = so.customer
    ci.customer_name = so.customer_name

    # Get customer address
    if so.customer_address:
        customer_address = frappe.get_doc("Address", so.customer_address)
        ci.consignee_address_name = so.customer_address
        ci.consignee_address = customer_address.get_display()
        ci.consignee_country = customer_address.country

        # Get tax ID if exists
        if hasattr(customer_address, 'tax_id'):
            ci.consignee_tax_id = customer_address.tax_id

    # Get customer contact details
    if so.contact_person:
        contact = frappe.get_doc("Contact", so.contact_person)
        ci.consignee_email = contact.email_id
        ci.consignee_phone = contact.phone or contact.mobile_no

    # ========== SHIPPING DETAILS ==========
    # Get from Sales Order if custom fields exist
    if hasattr(so, 'incoterm'):
        ci.incoterm = so.incoterm

    # Port details - try to get from company defaults
    if hasattr(company_doc, 'default_port_of_export'):
        ci.port_of_loading = company_doc.default_port_of_export

    # Country of origin
    ci.country_of_origin = company_doc.country

    # ========== PAYMENT TERMS ==========
    if hasattr(so, 'payment_method'):
        ci.payment_terms = so.payment_method

    # ========== ITEMS ==========
    for so_item in so.items:
        # Get item master details
        item_master = frappe.get_doc("Item", so_item.item_code)

        # Calculate weights
        weight_per_unit = flt(item_master.weight_per_unit) if hasattr(item_master, 'weight_per_unit') else 0
        net_weight = weight_per_unit * flt(so_item.qty)
        gross_weight = net_weight * 1.1  # Assume 10% tare weight

        # Get volume
        volume_per_unit = 0
        if hasattr(item_master, 'volume_per_unit') and item_master.volume_per_unit:
            volume_per_unit = flt(item_master.volume_per_unit)
        elif hasattr(item_master, 'length') and hasattr(item_master, 'width') and hasattr(item_master, 'height'):
            # Calculate from dimensions (in cm)
            volume_per_unit = flt(item_master.length) * flt(item_master.width) * flt(item_master.height)

        ci.append("items", {
            "item_code": so_item.item_code,
            "item_name": so_item.item_name,
            "description": so_item.description or so_item.item_name,
            "hs_code": item_master.gst_hsn_code if hasattr(item_master, 'gst_hsn_code') else None,
            "country_of_origin": item_master.country_of_origin if hasattr(item_master, 'country_of_origin') else ci.country_of_origin,
            "qty": so_item.qty,
            "uom": so_item.uom,
            "rate": so_item.rate,
            "amount": so_item.amount,
            "net_weight": net_weight,
            "gross_weight": gross_weight,
            "volume_per_unit": volume_per_unit,
            "sales_order_item": so_item.name
        })

    # ========== BANK DETAILS ==========
    # Try to get from company defaults if exists
    if hasattr(company_doc, 'default_bank_account'):
        bank_account = frappe.get_doc("Bank Account", company_doc.default_bank_account)
        ci.beneficiary_bank = bank_account.bank
        ci.swift_code = bank_account.swift_number if hasattr(bank_account, 'swift_number') else None
        ci.account_number = bank_account.bank_account_no
        ci.iban = bank_account.iban if hasattr(bank_account, 'iban') else None

    # Insert and return
    ci.insert()
    frappe.db.commit()

    return ci.name


# ==================== GET ITEMS FROM SALES ORDER (for manual use) ====================

@frappe.whitelist()
def get_items_from_sales_order(sales_order):
    """
    Fetch items from Sales Order for manual entry
    Returns: list of items with complete details
    """
    if not sales_order:
        return []

    so = frappe.get_doc("Sales Order", sales_order)
    items = []

    for item in so.items:
        # Get item master
        item_doc = frappe.get_doc("Item", item.item_code)

        # Calculate weights and volumes
        weight_per_unit = flt(item_doc.weight_per_unit) if hasattr(item_doc, 'weight_per_unit') else 0
        net_weight = weight_per_unit * flt(item.qty)
        gross_weight = net_weight * 1.1

        volume_per_unit = 0
        if hasattr(item_doc, 'volume_per_unit') and item_doc.volume_per_unit:
            volume_per_unit = flt(item_doc.volume_per_unit)

        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description or item.item_name,
            "hs_code": item_doc.gst_hsn_code if hasattr(item_doc, 'gst_hsn_code') else "",
            "country_of_origin": item_doc.country_of_origin if hasattr(item_doc, 'country_of_origin') else "",
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "amount": item.amount,
            "net_weight": net_weight,
            "gross_weight": gross_weight,
            "volume_per_unit": volume_per_unit,
            "sales_order_item": item.name
        })

    return items


# ==================== STATUS & WORKFLOW HELPERS ====================

@frappe.whitelist()
def get_export_readiness(name):
    """
    Check export document readiness
    Returns: status of all related documents
    """
    doc = frappe.get_doc("Commercial Invoice Export", name)

    status = {
        "commercial_invoice": {
            "exists": True,
            "submitted": doc.docstatus == 1,
            "name": doc.name
        },
        "packing_list": check_doc_exists("Packing List Export", "commercial_invoice", name),
        "certificate_of_origin": check_doc_exists("Certificate of Origin", "commercial_invoice", name),
        "shipping_bill": check_doc_exists("Shipping Bill", "commercial_invoice", name),
        "bill_of_lading": check_doc_exists("Bill of Lading", "commercial_invoice", name)
    }

    # Calculate completion
    docs_ready = sum(1 for v in status.values() if v.get("submitted", False))
    total_docs = len(status)
    completion_percentage = (docs_ready / total_docs) * 100

    # Find missing documents
    missing_documents = [k.replace("_", " ").title() for k, v in status.items() if not v.get("submitted", False)]

    return {
        "status": status,
        "completion_percentage": completion_percentage,
        "missing_documents": missing_documents,
        "is_ready": completion_percentage == 100
    }


def check_doc_exists(doctype, filter_field, filter_value):
    """Helper to check if related document exists and is submitted"""
    doc = frappe.db.get_value(doctype,
        {filter_field: filter_value, "docstatus": ["!=", 2]},
        ["name", "docstatus"],
        as_dict=True
    )

    if doc:
        return {
            "exists": True,
            "submitted": doc.docstatus == 1,
            "name": doc.name
        }
    else:
        return {
            "exists": False,
            "submitted": False,
            "name": None
        }


@frappe.whitelist()
def create_next_document(commercial_invoice, doctype):
    """
    Smart document creation - finds the right source and calls the appropriate creation method

    Flow:
    - Packing List → Created from CI (checks for Pick List internally)
    - Certificate of Origin → Created from CI
    - Shipping Bill → Created from CI
    - Bill of Lading → Created from Packing List (needs packing data)
    """

    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)

    if ci.docstatus != 1:
        frappe.throw(_("Commercial Invoice must be submitted first"))

    # Route to the correct creation function
    if doctype == "Packing List Export":
        # Direct creation from CI (it will find Pick List internally)
        from import_export.import_export.doctype.packing_list_export.packing_list_export import create_from_commercial_invoice
        return create_from_commercial_invoice(commercial_invoice)

    elif doctype == "Certificate of Origin":
        # Direct creation from CI
        from import_export.import_export.doctype.certificate_of_origin.certificate_of_origin import create_from_commercial_invoice
        return create_from_commercial_invoice(commercial_invoice)

    elif doctype == "Shipping Bill":
        # Direct creation from CI
        from import_export.import_export.doctype.shipping_bill.shipping_bill import create_from_commercial_invoice
        return create_from_commercial_invoice(commercial_invoice)

    elif doctype == "Bill of Lading":
        # B/L needs Packing List - find or create it first
        packing_list = frappe.db.get_value(
            "Packing List Export",
            {"commercial_invoice": commercial_invoice, "docstatus": 1},
            "name"
        )

        if not packing_list:
            frappe.throw(_(
                "Packing List must be created and submitted before Bill of Lading. "
                "Please create Packing List first."
            ))

        # Create B/L from Packing List
        from import_export.import_export.doctype.bill_of_lading.bill_of_lading import create_from_packing_list
        return create_from_packing_list(packing_list)

    else:
        frappe.throw(_("Unknown document type: {0}").format(doctype))
