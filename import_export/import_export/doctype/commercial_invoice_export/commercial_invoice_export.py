import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, money_in_words


class CommercialInvoiceExport(Document):
    def validate(self):
        self.validate_items()
        self.calculate_totals()
        self.set_status()
        self.set_in_words()
    
    def on_submit(self):
        self.status = "Submitted"
    
    def on_cancel(self):
        self.status = "Cancelled"
    
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