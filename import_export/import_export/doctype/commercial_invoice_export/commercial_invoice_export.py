import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, money_in_words


class CommercialInvoiceExport(Document):
    def validate(self):
        self.calculate_totals()
        self.set_status()
        self.set_in_words()
    
    def on_submit(self):
        self.validate_items()
        self.validate_imp_fields()
        self.check_duplicate_commercial_invoice()

        self.status = "Submitted"
    
    def on_cancel(self):
        self.status = "Cancelled"
        # self.check_duplicate_commercial_invoice()

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
    
    def calculate_totals(self):
        """Calculate all totals"""
        self.total_quantity = 0
        self.total_net_weight = 0
        self.total_gross_weight = 0
        self.total_volume_cbm = 0
        self.subtotal = 0
        
        for item in self.items:
            # Calculate item amount
            item.amount = flt(item.qty) * flt(item.rate)
            
            # Calculate weights
            item.total_net_weight = flt(item.qty) * flt(item.net_weight)
            item.total_gross_weight = flt(item.qty) * flt(item.gross_weight)
            
            # Add to totals
            self.total_quantity += flt(item.qty)
            self.total_net_weight += flt(item.total_net_weight)
            self.total_gross_weight += flt(item.total_gross_weight)
            self.subtotal += flt(item.amount)
        
        # Calculate FOB value (subtotal)
        self.total_fob_value = self.subtotal
        
        # Calculate CIF value if applicable
        if self.incoterm == "CIF":
            self.total_cif_value = (
                flt(self.subtotal) + 
                flt(self.freight_charges) + 
                flt(self.insurance_charges)
            )
        
        # Calculate grand total
        self.grand_total = (
            flt(self.subtotal) + 
            flt(self.freight_charges) + 
            flt(self.insurance_charges) + 
            flt(self.other_charges)
        )
    
    def set_in_words(self):
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



@frappe.whitelist()
def get_items_from_sales_order(sales_order):
    """Fetch items from Sales Order"""
    if not sales_order:
        return []
    
    so = frappe.get_doc("Sales Order", sales_order)
    items = []
    
    for item in so.items:
        # Get item details
        item_doc = frappe.get_doc("Item", item.item_code)
        
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "hs_code": item_doc.get("gst_hsn_code"),
            "country_of_origin": item_doc.get("country_of_origin"),
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "amount": item.amount,
            "net_weight": item_doc.get("weight_per_unit"),
            "gross_weight": item_doc.get("gross_weight"),
            "sales_order_item": item.name
        })
    
    return items


@frappe.whitelist()
def create_from_sales_order(sales_order):
    """Create Commercial Invoice from Sales Order"""
    # Check if already exists
    existing = frappe.db.exists("Commercial Invoice Export", {
        "sales_order": sales_order,
        "docstatus": ["!=", 2]
    })

    if existing:
        frappe.throw(_(
            "Commercial Invoice already exists for this Sales Order: {0}"
        ).format(existing))

    # Get Sales Order
    so = frappe.get_doc("Sales Order", sales_order)

    # Validate
    if so.gst_category != "Overseas":
        frappe.throw(_("This Sales Order is not marked as export order"))

    if so.docstatus != 1:
        frappe.throw(_("Sales Order must be submitted first"))

    # Create Commercial Invoice
    ci = frappe.new_doc("Commercial Invoice Export")
    ci.sales_order = so.name
    ci.company = so.company
    ci.customer = so.customer
    ci.customer_name = so.customer_name
    ci.invoice_date = frappe.utils.today()
    ci.currency = so.currency
    ci.conversion_rate = so.conversion_rate
    ci.incoterm = so.get("incoterm")
    ci.payment_terms = so.get("payment_terms_template")

    company_doc = frappe.get_doc("Company", so.company)
    ci.iec_code = company_doc.get("iec_code")

    if so.customer_address:
        address = frappe.get_doc("Address", so.customer_address)
        ci.consignee_address_name = so.customer_address
        ci.consignee_country = address.country

    # Copy items
    for item in so.items:
        item_doc = frappe.get_doc("Item", item.item_code)
        ci.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "hs_code": item_doc.get("gst_hsn_code"),
            "country_of_origin": item_doc.get("country_of_origin"),
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "amount": item.amount,
            "net_weight": item_doc.get("weight_per_unit", 0) * item.qty,
            "gross_weight": item_doc.get("weight_per_unit", 0) * item.qty * 1.1,  # Assuming 10% tare
            "volume_per_unit": item_master.get("volume_per_unit", 0),
            "sales_order_item": item.name
        })

    ci.insert(ignore_mandatory=True)
    # frappe.db.commit()

    return ci.name
