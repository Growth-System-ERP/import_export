import math
from typing import List, Dict, Tuple, Optional
import hashlib

class PackingCalculator:
    """Core calculation logic for carton packing with 3D positions"""

    @staticmethod
    def calc_item_volume(length: float, width: float, height: float) -> float:
        """Calculate volume of an item"""
        return float(length) * float(width) * float(height)

    @staticmethod
    def max_units_fit(item: Dict, carton: Dict) -> int:
        """Calculate max units that can fit in a carton considering all orientations"""
        if not all([item.get("length"), item.get("width"), item.get("height")]):
            return 0
        if not all([carton.get("length"), carton.get("width"), carton.get("height")]):
            return 0

        orientations = [
            (item["length"], item["width"], item["height"]),
            (item["length"], item["height"], item["width"]),
            (item["width"], item["length"], item["height"]),
            (item["width"], item["height"], item["length"]),
            (item["height"], item["length"], item["width"]),
            (item["height"], item["width"], item["length"]),
        ]
        best_fit = 0

        for l, w, h in orientations:
            fit_x = int(carton["length"] // l) if l > 0 else 0
            fit_y = int(carton["width"] // w) if w > 0 else 0
            fit_z = int(carton["height"] // h) if h > 0 else 0

            if fit_x == 0 or fit_y == 0 or fit_z == 0:
                continue

            fit_by_dim = fit_x * fit_y * fit_z
            fit_by_vol = int(carton["volume"] // item["volume"]) if item.get("volume", 0) > 0 else float('inf')
            fit_by_wt = (
                int(carton["weight_limit"] // item["weight"])
                if carton.get("weight_limit") and item.get("weight", 0) > 0
                else float('inf')
            )

            units = min(fit_by_dim, fit_by_vol, fit_by_wt)
            best_fit = max(best_fit, units)

        return best_fit

    @staticmethod
    def max_units_fit_with_3d_positions(item: Dict, carton: Dict) -> Tuple[int, List[Dict]]:
        """Enhanced version that returns 3D positions for visualization"""
        orientations = [
            (item["length"], item["width"], item["height"]),
            (item["length"], item["height"], item["width"]),
            (item["width"], item["length"], item["height"]),
            (item["width"], item["height"], item["length"]),
            (item["height"], item["length"], item["width"]),
            (item["height"], item["width"], item["length"]),
        ]

        best_fit = 0
        best_positions = []
        best_orientation = None

        for l, w, h in orientations:
            fit_x = int(carton["length"] // l) if l > 0 else 0
            fit_y = int(carton["width"] // w) if w > 0 else 0
            fit_z = int(carton["height"] // h) if h > 0 else 0

            if fit_x == 0 or fit_y == 0 or fit_z == 0:
                continue

            fit_by_dim = fit_x * fit_y * fit_z
            fit_by_vol = int(carton["volume"] // item["volume"]) if item.get("volume", 0) > 0 else float('inf')
            fit_by_wt = (
                int(carton["weight_limit"] // item["weight"])
                if carton.get("weight_limit") and item.get("weight", 0) > 0
                else float('inf')
            )

            units = min(fit_by_dim, fit_by_vol, fit_by_wt)

            if units > best_fit:
                best_fit = units
                best_orientation = (l, w, h)

                # Calculate 3D positions
                positions = []
                for z in range(fit_z):
                    for y in range(fit_y):
                        for x in range(fit_x):
                            if len(positions) >= units:
                                break

                            positions.append({
                                "x": x * l,
                                "y": y * w,
                                "z": z * h,
                                "length": l,
                                "width": w,
                                "height": h,
                                "rotated": (l, w, h) != (item["length"], item["width"], item["height"])
                            })

                best_positions = positions

        return best_fit, best_positions

    @staticmethod
    def calculate_packing_efficiency(item_volume: float, carton_volume: float, units_packed: int) -> float:
        """Calculate how efficiently we're using the carton space"""
        if carton_volume <= 0:
            return 0
        used_volume = item_volume * units_packed
        return (used_volume / carton_volume) * 100

    @staticmethod
    def create_pattern_signature(item_id: str, carton_id: str, positions: List[Dict]) -> str:
        """
        Create a unique signature for a packing pattern
        This allows detection of identical patterns across multiple cartons
        """
        # Sort positions to ensure consistent hashing
        sorted_positions = sorted(positions, key=lambda p: (p['x'], p['y'], p['z']))

        # Create signature from item, carton, and positions
        signature_parts = [f"{item_id}:{carton_id}"]
        for pos in sorted_positions:
            signature_parts.append(
                f"{pos['x']:.2f},{pos['y']:.2f},{pos['z']:.2f},"
                f"{pos['length']:.2f},{pos['width']:.2f},{pos['height']:.2f},"
                f"{int(pos['rotated'])}"
            )

        signature_string = "|".join(signature_parts)
        return hashlib.md5(signature_string.encode()).hexdigest()[:12]
