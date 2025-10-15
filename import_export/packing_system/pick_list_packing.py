import frappe
import json
from frappe import _
from frappe.utils import flt, ceil
from .main_controller import PackingController


def get_available_cartons():
    """Get available cartons from Carton doctype or return demo data"""
    cartons = frappe.get_all("Carton",
        filters={"disabled": 0},
        fields=["name", "length", "width", "height",
                "weight_limit", "cost_per_unit", "volume", "carton_type",
                "material", "fragile_safe", "max_stack_height", "uom"]
    )

    cartons_data = []
    for carton in cartons:
        cartons_data.append({
            "id": carton.name,
            "carton_name": carton.name,
            "disabled": False,
            "weight_limit": carton.weight_limit,
            "cost_per_unit": carton.cost_per_unit,
            "height": carton.height,
            "width": carton.width,
            "length": carton.length,
            "uom": carton.uom or "cm",
            "volume": carton.volume or (carton.length * carton.width * carton.height),
            "carton_type": carton.carton_type or "Standard",
            "max_stack_height": carton.max_stack_height or 100,
            "material": carton.material or "Cardboard",
            "fragile_safe": carton.fragile_safe or False
        })

    return cartons_data


@frappe.whitelist()
def calculate_pick_list_packing(pick_list_name, strategy="minimize_cartons", enable_3d=True):
    """
    Calculate packing with pattern deduplication
    """
    pick_list = frappe.get_doc("Pick List", pick_list_name)

    # Extract items from locations child table
    items_data = []
    for location in pick_list.locations:
        if location.qty > 0:
            item_doc = frappe.get_doc("Item", location.item_code)
            items_data.append({
                "item": {
                    "id": location.item_code,
                    "name": item_doc.item_name or location.item_code,
                    "length": getattr(item_doc, 'length', 10),
                    "width": getattr(item_doc, 'width', 10),
                    "height": getattr(item_doc, 'height', 5),
                    "weight": getattr(item_doc, 'weight_per_unit', 0.5),
                    "volume": getattr(item_doc, 'volume_per_unit', 0) or (
                        getattr(item_doc, 'length', 10) *
                        getattr(item_doc, 'width', 10) *
                        getattr(item_doc, 'height', 5)
                    ),
                    "area": getattr(item_doc, 'area', 0) or (
                        getattr(item_doc, 'length', 10) * getattr(item_doc, 'width', 10)
                    ),
                    "fragile": getattr(item_doc, 'fragile', False),
                    "color": f"#{hash(location.item_code) % 0xFFFFFF:06x}"
                },
                "quantity": int(location.qty)
            })

    if not items_data:
        frappe.throw(_("No items found in Pick List locations"))

    cartons_data = get_available_cartons()
    if not cartons_data:
        frappe.throw(_("No cartons available for packing"))

    # Run packing calculation with pattern deduplication
    controller = PackingController()
    result = controller.suggest_cartons(
        items_data=items_data,
        cartons_data=cartons_data,
        strategy=strategy,
        enable_3d=enable_3d
    )

    # Clear existing carton assignments
    pick_list.carton_assignments = []

    # Update Pick List with DEDUPLICATED carton assignments
    for assignment in result["carton_assignments"]:
        carton_assignment = pick_list.append("carton_assignments", {})

        # Set carton fields
        carton_assignment.carton = assignment["carton"]["id"]
        carton_assignment.carton_id = assignment["carton"]["id"]
        carton_assignment.carton_name = assignment["carton"]["id"]
        carton_assignment.carton_type = assignment["carton"].get("carton_type", "Standard")
        carton_assignment.carton_count = assignment["carton_count"]  # Now represents pattern repetitions
        carton_assignment.total_cost = assignment["total_cost"]
        carton_assignment.packing_efficiency = assignment["efficiency"]
        carton_assignment.utilization = float(str(assignment.get("utilization", "0")).replace("%", ""))
        carton_assignment.item_summary = assignment.get("item_summary", "")
        carton_assignment.total_items = assignment.get("total_items", 0)
        carton_assignment.length = assignment["carton"]["length"]
        carton_assignment.width = assignment["carton"]["width"]
        carton_assignment.height = assignment["carton"]["height"]
        carton_assignment.weight_limit = assignment["carton"]["weight_limit"]
        carton_assignment.cost_per_unit = assignment["carton"]["cost_per_unit"]
        carton_assignment.items_per_carton = assignment.get("items_per_carton", 0)
        carton_assignment.pattern_signature = assignment.get("pattern_signature", "")

        # Store COMPRESSED 3D positions (SINGLE PATTERN only, not all cartons)
        if assignment.get("items") and enable_3d:
            positions_data = {}
            for item in assignment["items"]:
                # Store only the pattern positions (not repeated for each carton)
                positions_data[item["item_code"]] = item["positions"]

            carton_assignment.positions_3d = json.dumps(positions_data)
        else:
            carton_assignment.positions_3d = ""

    # Update summary fields
    pick_list.total_cartons = result["total_cartons"]
    pick_list.unique_packing_patterns = result.get("unique_patterns", len(result["carton_assignments"]))
    pick_list.total_packing_cost = result["total_cost"]
    pick_list.average_efficiency = result["average_efficiency"]
    pick_list.packing_strategy = result["strategy_used"]

    pick_list.flags.ignore_validate = True
    pick_list.flags.ignore_mandatory = True
    pick_list.save()

    return {
        "success": True,
        "message": _("Packing calculation completed successfully"),
        "pick_list": pick_list.as_dict(),
        "summary": {
            "total_cartons": result["total_cartons"],
            "unique_patterns": result.get("unique_patterns", 0),
            "total_cost": result["total_cost"],
            "average_efficiency": f"{result['average_efficiency']:.1f}%",
            "unpacked_items": len(result["unpacked_items"])
        }
    }



@frappe.whitelist()
def get_pick_list_packing_data(pick_list_name):
    """Get packing summary data with pattern information"""
    if not frappe.has_permission("Pick List", "read", pick_list_name):
        frappe.throw(_("Not permitted to view this Pick List"))

    pick_list = frappe.get_doc("Pick List", pick_list_name)

    carton_assignments = []
    total_cartons = 0
    efficiency_scores = []

    for assignment in pick_list.carton_assignments:
        carton = frappe.db.get_value("Carton", assignment.carton_id, ["*"], as_dict=True)

        carton_assignment = {
            "carton": carton,
            "carton_id": assignment.carton_id,
            "carton_name": assignment.carton_id,
            "carton_count": getattr(assignment, 'carton_count', 1),
            "items_per_carton": ceil(getattr(assignment, 'total_items', 0) / getattr(assignment, 'carton_count', 1)),
            "pattern_signature": getattr(assignment, 'pattern_signature', ''),  # NEW
            "efficiency": assignment.packing_efficiency or 0,
            "packing_efficiency": assignment.packing_efficiency or 0,
            "utilization": assignment.utilization or 0,
            "item_summary": assignment.item_summary or "",
            "length": carton.length,
            "width": carton.width,
            "height": carton.height,
        }

        carton_assignments.append(carton_assignment)
        total_cartons += getattr(assignment, 'carton_count', 1)
        efficiency_scores.append(assignment.packing_efficiency or 0)

    average_efficiency = sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0

    return {
        "success": True,
        "pick_list_name": pick_list_name,
        "pick_list_title": pick_list.name,
        "total_cartons": total_cartons,
        "unique_patterns": len(carton_assignments),  # NEW
        "total_packing_cost": getattr(pick_list, 'total_packing_cost', None),
        "average_efficiency": average_efficiency,
        "packing_strategy": getattr(pick_list, 'packing_strategy', 'Default'),
        "carton_assignments": carton_assignments
    }


@frappe.whitelist()
def get_pick_list_3d_data(pick_list_name, carton_idx=0):
    """
    Get ALL patterns for the selected carton type (not just one assignment)
    """
    if not frappe.has_permission("Pick List", "read", pick_list_name):
        frappe.throw(_("Not permitted to view this Pick List"))

    pick_list = frappe.get_doc("Pick List", pick_list_name)
    carton_idx = int(carton_idx)

    if carton_idx >= len(pick_list.carton_assignments):
        frappe.throw(_("Invalid carton assignment index"))

    # Get the selected assignment
    selected_assignment = pick_list.carton_assignments[carton_idx]
    carton_info = frappe.db.get_value("Carton", selected_assignment.carton_id, ["*"], as_dict=True)

    # Collect ALL patterns for this carton_id
    patterns = []
    for assgn in pick_list.carton_assignments:
        if assgn.carton_id == selected_assignment.carton_id and assgn.positions_3d:
            try:
                positions_data = json.loads(assgn.positions_3d) if isinstance(assgn.positions_3d, str) else assgn.positions_3d

                patterns.append({
                    "positions_3d": positions_data,
                    "carton_count": getattr(assgn, 'carton_count', 1),
                    "items_per_carton": getattr(assgn, 'items_per_carton', 0),
                    "pattern_signature": getattr(assgn, 'pattern_signature', ''),
                    "efficiency": assgn.packing_efficiency or 0
                })
            except Exception as e:
                frappe.log_error(f"Failed to parse positions for pattern: {str(e)}")
                continue

    # Get item info from all patterns
    item_info = {}
    for pattern in patterns:
        for item_code in pattern["positions_3d"].keys():
            if item_code not in item_info:
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
        "patterns": patterns,  # Multiple patterns
        "item_info": item_info,
        "total_patterns": len(patterns),
        "show_multiple": len(patterns) > 1
    }

def get_item_color(item_code):
    """Generate consistent color for item based on item code"""
    colors = [
        '#3498db', '#e74c3c', '#2ecc71', '#f39c12',
        '#9b59b6', '#1abc9c', '#e67e22', '#34495e',
        '#f1c40f', '#e74c3c', '#2980b9', '#27ae60'
    ]
    # Use hash of item code to get consistent color
    hash_val = hash(item_code) % len(colors)
    return colors[hash_val]
