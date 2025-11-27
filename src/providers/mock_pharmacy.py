"""
Mock Pharmacy System API

Simulates pharmacy inventory and ordering systems.
Replace with real pharmacy chain APIs when available.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import hashlib
from .base import BasePharmacyAPI


class MockPharmacySystem(BasePharmacyAPI):
    """
    Mock Pharmacy System with realistic, deterministic responses.

    Simulates:
    - Dawaai.pk style online pharmacy
    - Local pharmacy chains
    - Hospital pharmacies
    """

    # Pharmacy profiles
    PHARMACY_PROFILES = {
        "online": {
            "name_prefix": "Dawaai",
            "delivery_available": True,
            "delivery_time_hours": (2, 6),
            "stock_level": "high",
            "discount_percentage": (5, 15),
        },
        "chain": {
            "name_prefix": "Fazal Din",
            "delivery_available": True,
            "delivery_time_hours": (1, 3),
            "stock_level": "medium",
            "discount_percentage": (0, 10),
        },
        "local": {
            "name_prefix": "Local Pharmacy",
            "delivery_available": False,
            "delivery_time_hours": (0, 0),
            "stock_level": "variable",
            "discount_percentage": (0, 5),
        },
        "hospital": {
            "name_prefix": "Hospital Pharmacy",
            "delivery_available": False,
            "delivery_time_hours": (0, 0),
            "stock_level": "high",
            "discount_percentage": (0, 0),
        }
    }

    def __init__(self):
        self._reservations: Dict[str, Dict] = {}

    def _get_seed(self, key: str) -> int:
        """Generate deterministic seed"""
        return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    def check_stock(self, medicine_name: str, location: str) -> Dict[str, Any]:
        """
        Check medicine stock across pharmacies in location.

        In production: GET /api/v1/medicines/search?name={name}&location={location}
        """
        seed = self._get_seed(f"{medicine_name}_{location}")

        # Generate multiple pharmacy responses
        pharmacies = []
        pharmacy_types = ["online", "chain", "local", "hospital"]

        for i, ptype in enumerate(pharmacy_types):
            profile = self.PHARMACY_PROFILES[ptype]
            pharmacy_seed = self._get_seed(f"{medicine_name}_{location}_{ptype}")

            # Stock availability (varies by type)
            if profile["stock_level"] == "high":
                in_stock = (pharmacy_seed % 10) < 9  # 90% available
                quantity = 20 + (pharmacy_seed % 80)
            elif profile["stock_level"] == "medium":
                in_stock = (pharmacy_seed % 10) < 7  # 70% available
                quantity = 5 + (pharmacy_seed % 30)
            else:  # variable
                in_stock = (pharmacy_seed % 10) < 5  # 50% available
                quantity = 1 + (pharmacy_seed % 10)

            if not in_stock:
                quantity = 0

            # Base price with variation
            base_price = 100 + (pharmacy_seed % 400)  # Rs. 100-500 base
            discount = profile["discount_percentage"]
            discount_pct = discount[0] + (pharmacy_seed % (discount[1] - discount[0] + 1))
            final_price = base_price * (1 - discount_pct / 100)

            # Delivery time
            if profile["delivery_available"]:
                dt = profile["delivery_time_hours"]
                delivery_hours = dt[0] + (pharmacy_seed % (dt[1] - dt[0] + 1))
            else:
                delivery_hours = None

            pharmacies.append({
                "pharmacy_id": f"PH-{ptype.upper()}-{location[:3].upper()}-{pharmacy_seed % 1000:03d}",
                "name": f"{profile['name_prefix']} - {location}",
                "type": ptype,
                "in_stock": in_stock,
                "quantity_available": quantity,
                "price": round(final_price, 2),
                "mrp": base_price,
                "discount_percentage": discount_pct if in_stock else 0,
                "delivery_available": profile["delivery_available"] and in_stock,
                "delivery_time_hours": delivery_hours if in_stock else None,
                "pickup_available": in_stock,
                "distance_km": round(0.5 + (pharmacy_seed % 50) / 10, 1),
                "rating": round(3.5 + (pharmacy_seed % 15) / 10, 1),
                "is_generic_available": (pharmacy_seed % 3) == 0
            })

        # Sort by price
        pharmacies.sort(key=lambda x: (not x["in_stock"], x["price"]))

        return {
            "medicine_name": medicine_name,
            "location": location,
            "timestamp": datetime.now().isoformat(),
            "pharmacies": pharmacies,
            "total_found": len([p for p in pharmacies if p["in_stock"]]),
            "cheapest_price": min([p["price"] for p in pharmacies if p["in_stock"]], default=None),
            "fastest_delivery": min([p["delivery_time_hours"] for p in pharmacies
                                    if p["delivery_time_hours"]], default=None)
        }

    def reserve_medicine(self, medicine_id: str, quantity: int, patient_id: str) -> Dict[str, Any]:
        """
        Reserve medicine for pickup/delivery.

        In production: POST /api/v1/medicines/reserve
        """
        reservation_id = f"MR-{hashlib.md5(f'{medicine_id}{patient_id}{datetime.now()}'.encode()).hexdigest()[:8].upper()}"

        reservation = {
            "reservation_id": reservation_id,
            "medicine_id": medicine_id,
            "quantity": quantity,
            "patient_id": patient_id,
            "status": "reserved",
            "expires_at": (datetime.now() + timedelta(hours=2)).isoformat(),
            "created_at": datetime.now().isoformat()
        }

        self._reservations[reservation_id] = reservation

        return {
            "success": True,
            "reservation": reservation,
            "message": f"Medicine reserved for 2 hours. Reservation ID: {reservation_id}"
        }

    def get_price(self, medicine_id: str) -> Dict[str, Any]:
        """Get medicine price details"""
        seed = self._get_seed(medicine_id)
        base_price = 100 + (seed % 500)

        return {
            "medicine_id": medicine_id,
            "mrp": base_price,
            "sale_price": round(base_price * 0.9, 2),
            "discount_percentage": 10,
            "generic_available": (seed % 3) == 0,
            "generic_price": round(base_price * 0.5, 2) if (seed % 3) == 0 else None
        }

    def search_generic_alternatives(self, medicine_name: str) -> List[Dict[str, Any]]:
        """
        Search for generic alternatives.

        In production: GET /api/v1/medicines/{name}/generics
        """
        seed = self._get_seed(medicine_name)

        alternatives = []
        num_generics = 1 + (seed % 4)  # 1-4 generics

        for i in range(num_generics):
            alt_seed = self._get_seed(f"{medicine_name}_generic_{i}")
            brand_price = 100 + (seed % 500)
            generic_price = brand_price * (0.3 + (alt_seed % 30) / 100)  # 30-60% of brand

            alternatives.append({
                "generic_name": f"Generic-{medicine_name[:4].upper()}-{i+1}",
                "manufacturer": f"Pharma Co. {alt_seed % 10}",
                "price": round(generic_price, 2),
                "savings_percentage": round((1 - generic_price / brand_price) * 100, 1),
                "drap_approved": True,
                "bioequivalent": True,
                "rating": round(3.5 + (alt_seed % 15) / 10, 1)
            })

        alternatives.sort(key=lambda x: x["price"])

        return alternatives


# Global instance
_mock_pharmacy: Optional[MockPharmacySystem] = None


def get_pharmacy_system() -> MockPharmacySystem:
    """Get or create pharmacy system instance"""
    global _mock_pharmacy
    if _mock_pharmacy is None:
        _mock_pharmacy = MockPharmacySystem()
    return _mock_pharmacy
