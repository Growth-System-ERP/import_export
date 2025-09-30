import math
from typing import List, Dict, Optional, Tuple
from .calculator import PackingCalculator

class PackingOptimizer:
    """Handles optimization strategies for carton assignment"""
    
    def __init__(self, strategy: str = "minimize_cartons"):
        self.strategy = strategy
        self.calculator = PackingCalculator()
    
    def find_optimal_carton_assignment(self, item: Dict, cartons: List[Dict], remaining_qty: int) -> Optional[Dict]:
        """Find optimal carton assignment considering multiple factors"""
        options = []
        
        for carton in cartons:
            # Skip disabled cartons
            if carton.get("disabled", False):
                continue
                
            # Check fragile compatibility
            if item.get("fragile", False) and not carton.get("fragile_safe", False):
                continue
                
            fit_capacity = self.calculator.max_units_fit(item, carton)
            if fit_capacity <= 0:
                continue
                
            # Calculate different scenarios
            units_to_pack = min(remaining_qty, fit_capacity)
            cartons_needed = math.ceil(remaining_qty / fit_capacity)
            waste_units = (cartons_needed * fit_capacity) - remaining_qty
            efficiency = self.calculator.calculate_packing_efficiency(
                item["volume"], carton["volume"], units_to_pack
            )
            
            options.append({
                "carton": carton,
                "fit_capacity": fit_capacity,
                "units_to_pack": units_to_pack,
                "cartons_needed": cartons_needed,
                "waste_units": waste_units,
                "efficiency": efficiency,
                "cost_score": carton.get('cost_per_unit', 1) * cartons_needed
            })

        if not options:
            return None
            
        # Sort based on strategy
        if self.strategy == "minimize_waste":
            options.sort(key=lambda x: (x["waste_units"], -x["efficiency"], x["cost_score"]))
        elif self.strategy == "maximize_efficiency":
            options.sort(key=lambda x: (-x["efficiency"], x["waste_units"], x["cost_score"]))
        else:  # "minimize_cartons"
            options.sort(key=lambda x: (x["cartons_needed"], x["waste_units"], x["cost_score"]))
        
        return options[0]
    
    def group_similar_items(self, items: List[Dict]) -> List[Dict]:
        """Group items with identical dimensions to optimize packing"""
        grouped = {}
        
        for item in items:
            # Create a key based on dimensions (sorted to handle rotations)
            dims = tuple(sorted([item["length"], item["width"], item["height"]]))
            key = (dims, item.get("weight", 0), item.get("volume", 0), item.get("fragile", False))
            
            if key not in grouped:
                grouped[key] = {
                    "items": [],
                    "total_qty": 0,
                    "sample_item": item
                }
            
            grouped[key]["items"].append(item)
            grouped[key]["total_qty"] += item.get("qty", 1)
        
        return list(grouped.values())
