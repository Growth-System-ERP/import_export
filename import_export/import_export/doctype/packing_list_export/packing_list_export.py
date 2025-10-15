import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
import json


class PackingListExport(Document):
    def validate(self):
        self.validate_commercial_invoice()
        self.calculate_totals()
        self.set_carton_numbers()
        self.set_status()
    
    def on_submit(self):
        self.status = "Packed"
    
    def on_cancel(self):
        self.status = "Cancelled"
    
    def validate_commercial_invoice(self):
        """Validate that commercial invoice exists and is submitted"""
        if not self.commercial_invoice:
            frappe.throw(_("Commercial Invoice is required"))
        
        ci_status = frappe.db.get_value(
            "Commercial Invoice Export", 
            self.commercial_invoice, 
            "docstatus"
        )
        
        if ci_status != 1:
            frappe.throw(_("Commercial Invoice must be submitted before creating packing list"))
    
    def calculate_totals(self):
        """Calculate all totals from cartons"""
        self.total_quantity = 0
        self.total_net_weight = 0
        self.total_gross_weight = 0
        self.total_volume_cbm = 0
        self.total_cartons = 0
        
        if not self.cartons:
            return
        
        for carton in self.cartons:
            # Calculate total items across all cartons of this pattern
            items_per_pattern = flt(carton.items_per_carton)
            num_cartons = flt(carton.carton_count)
            total_items_this_pattern = items_per_pattern * num_cartons
            
            self.total_quantity += total_items_this_pattern
            
            # Calculate volume
            carton_volume = (
                flt(carton.length) * flt(carton.width) * flt(carton.height)
            ) / 1000000  # Convert cm³ to m³
            
            self.total_volume_cbm += carton_volume * num_cartons
            
            # Add to carton count
            self.total_cartons += num_cartons
        
        self.total_packages = self.total_cartons
    
    def set_carton_numbers(self):
        """Set carton number range - for export docs we show total range"""
        if self.total_cartons:
            self.carton_numbers_from = 1
            self.carton_numbers_to = int(self.total_cartons)
    
    def set_status(self):
        """Set document status"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1:
            self.status = "Packed"
        elif self.docstatus == 2:
            self.status = "Cancelled"


@frappe.whitelist()
def create_from_pick_list(pick_list_name, commercial_invoice):
    """
    Create Packing List Export from Pick List with packing calculation
    This integrates with your existing packing algorithm
    """
    if not pick_list_name or not commercial_invoice:
        frappe.throw(_("Pick List and Commercial Invoice are required"))
    
    # Validate access
    if not frappe.has_permission("Pick List", "read", pick_list_name):
        frappe.throw(_("Not permitted to access this Pick List"))
    
    pick_list = frappe.get_doc("Pick List", pick_list_name)
    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)
    
    # Check if Pick List has packing calculations
    if not pick_list.get("carton_assignments"):
        frappe.throw(_("""Pick List does not have packing calculations. 
            Please run packing calculation first."""))
    
    # Create new Packing List Export
    packing_list = frappe.new_doc("Packing List Export")
    packing_list.company = pick_list.company
    packing_list.commercial_invoice = commercial_invoice
    packing_list.packing_date = frappe.utils.today()
    
    # Copy from Commercial Invoice
    packing_list.sales_order = ci.sales_order
    packing_list.delivery_note = pick_list.name  # Link to Pick List as delivery reference
    
    # Copy shipper/consignee details
    packing_list.shipper_name = ci.exporter_name
    packing_list.shipper_address = ci.exporter_address
    packing_list.consignee_name = ci.customer_name
    packing_list.consignee_address = ci.consignee_address
    
    # Copy shipping info
    packing_list.port_of_loading = ci.port_of_loading
    packing_list.port_of_discharge = ci.port_of_discharge
    packing_list.vessel_flight_no = ci.vessel_flight_no
    packing_list.shipping_marks = ci.shipping_marks
    
    # Import carton assignments from Pick List
    for assignment in pick_list.carton_assignments:
        carton_row = packing_list.append("cartons", {})
        
        carton_row.carton_id = assignment.carton_id
        carton_row.carton_count = assignment.carton_count or 1
        carton_row.items_per_carton = assignment.get("items_per_carton", 0)
        carton_row.pattern_signature = assignment.get("pattern_signature", "")
        carton_row.packing_efficiency = assignment.packing_efficiency or 0
        carton_row.utilization = assignment.utilization or 0
        
        # Carton dimensions
        carton_row.length = assignment.length
        carton_row.width = assignment.width
        carton_row.height = assignment.height
        carton_row.weight_limit = assignment.weight_limit
        carton_row.cost_per_unit = assignment.cost_per_unit
        
        # Costs and items
        carton_row.total_cost = assignment.get("total_cost", 0)
        carton_row.total_items = assignment.get("total_items", 0)
        carton_row.item_summary = assignment.item_summary or ""
        
        # Copy 3D positions for visualization
        if hasattr(assignment, 'positions_3d') and assignment.positions_3d:
            carton_row.positions_3d = assignment.positions_3d
    
    # Set container info if available
    if pick_list.get("fcl_lcl"):
        packing_list.fcl_lcl = pick_list.fcl_lcl
    if pick_list.get("container_size"):
        packing_list.container_size = pick_list.container_size
    
    packing_list.insert()
    
    return packing_list.name


@frappe.whitelist()
def get_3d_visualization_data(packing_list_name, carton_idx=0):
    """
    Get 3D visualization data for a specific carton pattern
    Compatible with your existing 3D viewer
    """
    if not frappe.has_permission("Packing List Export", "read", packing_list_name):
        frappe.throw(_("Not permitted to view this Packing List"))
    
    packing_list = frappe.get_doc("Packing List Export", packing_list_name)
    carton_idx = int(carton_idx)
    
    if carton_idx >= len(packing_list.cartons):
        frappe.throw(_("Invalid carton index"))
    
    # Get selected carton pattern
    selected_carton = packing_list.cartons[carton_idx]
    
    # Get carton info
    carton_info = frappe.db.get_value(
        "Carton", 
        selected_carton.carton_id, 
        ["*"], 
        as_dict=True
    )
    
    # Parse 3D positions
    patterns = []
    if selected_carton.positions_3d:
        try:
            positions_data = json.loads(selected_carton.positions_3d)
            
            patterns.append({
                "positions_3d": positions_data,
                "carton_count": selected_carton.carton_count,
                "items_per_carton": selected_carton.items_per_carton,
                "pattern_signature": selected_carton.pattern_signature,
                "efficiency": selected_carton.packing_efficiency
            })
        except Exception as e:
            frappe.log_error(f"Failed to parse 3D positions: {str(e)}")
    
    # Get item information
    item_info = {}
    if patterns and patterns[0]["positions_3d"]:
        for item_code in patterns[0]["positions_3d"].keys():
            try:
                item_doc = frappe.get_doc("Item", item_code)
                item_info[item_code] = {
                    "name": item_doc.item_name,
                    "length": getattr(item_doc, 'length', 10),
                    "width": getattr(item_doc, 'width', 10),
                    "height": getattr(item_doc, 'height', 10),
                    "color": get_item_color(item_code)
                }
            except:
                continue
    
    return {
        "carton": carton_info,
        "patterns": patterns,
        "item_info": item_info,
        "total_patterns": len(patterns),
        "show_multiple": False  # Only showing one pattern per carton type in export
    }


def get_item_color(item_code):
    """Generate consistent color for item"""
    colors = [
        '#3498db', '#e74c3c', '#2ecc71', '#f39c12',
        '#9b59b6', '#1abc9c', '#e67e22', '#34495e'
    ]
    hash_val = hash(item_code) % len(colors)
    return colors[hash_val]


@frappe.whitelist()
def get_items_from_commercial_invoice(commercial_invoice):
    """Fetch items from Commercial Invoice"""
    if not commercial_invoice:
        return []
    
    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)
    
    items = []
    for item in ci.items:
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": item.qty,
            "uom": item.uom,
            "net_weight": item.net_weight,
            "gross_weight": item.gross_weight
        })
    
    return items
