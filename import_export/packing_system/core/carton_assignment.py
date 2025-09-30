from typing import List, Dict, Optional

class CartonAssignment:
    """Manages carton assignment with 3D positioning data"""

    def __init__(self, carton_id: str, carton_data: Dict):
        self.carton_id = carton_id
        self.carton_data = carton_data
        self.carton_count = 0
        self.assigned_volume = 0
        self.efficiency_scores = []
        self.item_details = []
        self.positions_3d = []  # Store 3D positions if available
        self.total_cost = 0

    def add_items(self, item_code: str, qty: int, volume_per_unit: float, 
                  cartons_needed: int, efficiency: float, positions_3d: Optional[List[Dict]] = None):
        """Add items with optional 3D positions"""
        self.carton_count += cartons_needed
        total_volume = qty * volume_per_unit
        self.assigned_volume += total_volume
        self.efficiency_scores.append(efficiency)
        self.total_cost += self.carton_data.get("cost_per_unit", 0) * cartons_needed

        # Track item details
        existing_item = next((item for item in self.item_details if item["item_code"] == item_code), None)
        if existing_item:
            existing_item["qty"] += qty
            existing_item["total_volume"] += total_volume
        else:
            self.item_details.append({
                "item_code": item_code,
                "qty": qty,
                "volume_per_unit": volume_per_unit,
                "total_volume": total_volume
            })

        # Store 3D positions if provided
        if positions_3d:
            colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#34495e"]
            color = colors[len(set(item["item_code"] for item in self.item_details)) % len(colors)]

            for i, pos in enumerate(positions_3d[:int(qty)]):
                self.positions_3d.append({
                    "item_code": item_code,
                    "position": [pos["x"], pos["y"], pos["z"]],
                    "dimensions": [pos["length"], pos["width"], pos["height"]],
                    "rotated": pos["rotated"],
                    "color": color,
                    "index": i + 1
                })

    def get_average_efficiency(self) -> float:
        if not self.efficiency_scores:
            return 0
        return sum(self.efficiency_scores) / len(self.efficiency_scores)

    def get_item_summary(self) -> str:
        if not self.item_details:
            return ""

        summary_parts = []
        for item in self.item_details:
            summary_parts.append(f"{item['item_code']} (×{item['qty']})")

        return "; ".join(summary_parts)

    def get_utilization(self) -> float:
        """Calculate carton space utilization percentage"""
        if self.carton_data["volume"] <= 0:
            return 0
        return (self.assigned_volume / self.carton_data["volume"]) * 100

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        return {
            "carton": self.carton_data,
            "carton_count": self.carton_count,
            "assigned_volume": self.assigned_volume,
            "packing_efficiency": f"{self.get_average_efficiency():.1f}%",
            "utilization": f"{self.get_utilization():.1f}%",
            "item_summary": self.get_item_summary(),
            "total_items": sum(item["qty"] for item in self.item_details),
            "total_cost": self.total_cost,
            "items": [
                {
                    "item_code": item["item_code"],
                    "quantity": item["qty"],
                    "positions": [
                        pos for pos in self.positions_3d 
                        if pos["item_code"] == item["item_code"]
                    ]
                }
                for item in self.item_details
            ],
            "efficiency": self.get_average_efficiency()
        }