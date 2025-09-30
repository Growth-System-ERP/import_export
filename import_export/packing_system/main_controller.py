import json
import math
from typing import Dict, List, Optional, Tuple
from .core.calculator import PackingCalculator
from .core.optimizer import PackingOptimizer
from .core.carton_assignment import CartonAssignment

class PackingController:
    """Main controller for packing operations with pattern optimization"""

    def __init__(self):
        self.calculator = PackingCalculator()

    def suggest_cartons(self, items_data: List[Dict], cartons_data: List[Dict],
                    strategy: str = "minimize_cartons", enable_3d: bool = True) -> Dict:
        """
        Enhanced packing calculation with pattern deduplication
        """
        if not items_data:
            raise ValueError("No valid items found for packing calculation")

        if not cartons_data:
            raise ValueError("No cartons available for packing")

        optimizer = PackingOptimizer(strategy)

        items_for_grouping = []
        for item_entry in items_data:
            item = item_entry["item"]
            qty = item_entry["quantity"]
            item_with_qty = {**item, "qty": qty}
            items_for_grouping.append(item_with_qty)

        item_groups = optimizer.group_similar_items(items_for_grouping)
        pattern_registry = {}
        unpacked_items = []

        for group in item_groups:
            remaining_qty = group["total_qty"]
            item = group["sample_item"]

            while remaining_qty > 0:
                assignment = optimizer.find_optimal_carton_assignment(item, cartons_data, remaining_qty)

                if not assignment:
                    for group_item in group["items"]:
                        unpacked_items.append({
                            "item": {k: v for k, v in group_item.items() if k != "qty"},
                            "quantity": group_item["qty"] if remaining_qty >= group_item["qty"] else remaining_qty
                        })
                    break

                # Generate pattern based on FULL CAPACITY
                if enable_3d:
                    units_fit, full_capacity_positions = self.calculator.max_units_fit_with_3d_positions(
                        item, assignment["carton"]
                    )
                    pattern_sig = self.calculator.create_pattern_signature(
                        item["id"],
                        assignment["carton"]["id"],
                        full_capacity_positions
                    )
                    items_per_carton = units_fit
                else:
                    full_capacity_positions = None
                    pattern_sig = None
                    items_per_carton = assignment["fit_capacity"]

                # CRITICAL FIX: Calculate cartons for THIS BATCH only
                units_this_batch = min(remaining_qty, items_per_carton * 10000)  # Process in large batches
                cartons_for_this_batch = math.ceil(units_this_batch / items_per_carton) if items_per_carton > 0 else 0

                if cartons_for_this_batch > 0:
                    carton_id = assignment["carton"]["id"]

                    # Check if pattern exists
                    if pattern_sig and pattern_sig in pattern_registry:
                        # Add to existing pattern
                        pattern_registry[pattern_sig]["carton_count"] += cartons_for_this_batch
                        pattern_registry[pattern_sig]["total_cost"] += assignment["carton"].get("cost_per_unit", 0) * cartons_for_this_batch
                        pattern_registry[pattern_sig]["total_items"] += units_this_batch
                    else:
                        # New pattern
                        pattern_key = pattern_sig if pattern_sig else f"{carton_id}_{item['id']}_{len(pattern_registry)}"

                        pattern_registry[pattern_key] = {
                            "carton": assignment["carton"],
                            "carton_id": carton_id,
                            "carton_name": assignment["carton"].get("carton_name", carton_id),
                            "carton_count": cartons_for_this_batch,
                            "efficiency": assignment["efficiency"],
                            "packing_efficiency": assignment["efficiency"],
                            "utilization": assignment["efficiency"],
                            "pattern_signature": pattern_sig,
                            "total_items": units_this_batch,
                            "items_per_carton": items_per_carton,
                            "total_cost": assignment["carton"].get("cost_per_unit", 0) * cartons_for_this_batch,
                            "item_summary": f"{item['id']} (×{items_per_carton} per carton)",
                            "items": [{
                                "item_code": item["id"],
                                "quantity": items_per_carton,
                                "positions": full_capacity_positions if enable_3d else []
                            }],
                            "positions_3d": {
                                item["id"]: full_capacity_positions
                            } if enable_3d else {},
                            "item_info": {
                                item["id"]: {
                                    "name": item.get("name", item["id"]),
                                    "length": item["length"],
                                    "width": item["width"],
                                    "height": item["height"],
                                    "color": item.get("color", "#3498db")
                                }
                            } if enable_3d else {}
                        }

                remaining_qty -= units_this_batch

        # Convert to list
        carton_assignments = list(pattern_registry.values())

        total_cartons = sum(p["carton_count"] for p in carton_assignments)
        total_cost = sum(p["total_cost"] for p in carton_assignments)
        efficiency_scores = [p["efficiency"] for p in carton_assignments]
        average_efficiency = sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0

        result = {
            "carton_assignments": carton_assignments,
            "total_cartons": total_cartons,
            "unique_patterns": len(carton_assignments),
            "total_cost": total_cost,
            "average_efficiency": average_efficiency,
            "unpacked_items": unpacked_items,
            "strategy_used": f"{strategy}_pattern_optimized",
            "items_processed": sum(item_entry["quantity"] for item_entry in items_data),
            "cartons_evaluated": len(cartons_data)
        }

        return result

    def validate_packing_request(self, request_data: Dict) -> Tuple[bool, str]:
        """Validate packing request data"""

        if "items" not in request_data:
            return False, "Missing 'items' in request"

        if "cartons" not in request_data:
            return False, "Missing 'cartons' in request"

        items = request_data["items"]
        if not isinstance(items, list) or len(items) == 0:
            return False, "Items must be a non-empty list"

        cartons = request_data["cartons"]
        if not isinstance(cartons, list) or len(cartons) == 0:
            return False, "Cartons must be a non-empty list"

        # Validate each item
        for i, item_entry in enumerate(items):
            if "item" not in item_entry or "quantity" not in item_entry:
                return False, f"Item {i} missing 'item' or 'quantity' field"

            item = item_entry["item"]
            required_fields = ["id", "length", "width", "height", "weight", "volume"]
            for field in required_fields:
                if field not in item:
                    return False, f"Item {i} missing required field: {field}"

            if item_entry["quantity"] <= 0:
                return False, f"Item {i} quantity must be positive"

        # Validate each carton
        for i, carton in enumerate(cartons):
            required_fields = ["id", "length", "width", "height", "volume", "weight_limit", "cost_per_unit"]
            for field in required_fields:
                if field not in carton:
                    return False, f"Carton {i} missing required field: {field}"

        return True, "Valid request"
