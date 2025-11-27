"""
Mock Hospital Management System (HMS) API

This simulates a real hospital's HMS API. When integrating with actual hospitals,
create a new class implementing BaseHospitalAPI and swap it out.

The mock data is DETERMINISTIC based on hospital_id to ensure consistent behavior.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import hashlib
from .base import BaseHospitalAPI


class MockHospitalManagementSystem(BaseHospitalAPI):
    """
    Mock HMS that provides realistic, deterministic responses.

    Data is generated based on hospital_id hash to ensure:
    - Same hospital always returns same capacity
    - Consistent behavior across requests
    - Easy to swap with real API later
    """

    # Hospital configurations (based on real Pakistan hospital types)
    HOSPITAL_PROFILES = {
        "large": {  # Major hospitals like Jinnah, Aga Khan
            "total_beds": (200, 500),
            "icu_beds": (20, 50),
            "emergency_beds": (30, 60),
            "occupancy_rate": (0.7, 0.9),
            "has_cardiology": True,
            "has_neurology": True,
            "has_trauma": True,
        },
        "medium": {  # District hospitals, private hospitals
            "total_beds": (50, 150),
            "icu_beds": (5, 15),
            "emergency_beds": (10, 25),
            "occupancy_rate": (0.6, 0.85),
            "has_cardiology": True,
            "has_neurology": False,
            "has_trauma": True,
        },
        "small": {  # BHUs, clinics
            "total_beds": (10, 40),
            "icu_beds": (0, 5),
            "emergency_beds": (2, 10),
            "occupancy_rate": (0.4, 0.7),
            "has_cardiology": False,
            "has_neurology": False,
            "has_trauma": False,
        }
    }

    def __init__(self):
        # In-memory state for appointments and reservations
        self._appointments: Dict[str, Dict] = {}
        self._bed_reservations: Dict[str, Dict] = {}

    def _get_hospital_seed(self, hospital_id: str) -> int:
        """Generate deterministic seed from hospital_id"""
        return int(hashlib.md5(str(hospital_id).encode()).hexdigest()[:8], 16)

    def _get_hospital_profile(self, hospital_id: str) -> str:
        """Determine hospital size profile based on ID"""
        seed = self._get_hospital_seed(hospital_id)
        # Distribution: 20% large, 40% medium, 40% small
        if seed % 10 < 2:
            return "large"
        elif seed % 10 < 6:
            return "medium"
        return "small"

    def _generate_value_in_range(self, hospital_id: str, key: str, range_tuple: tuple) -> int:
        """Generate deterministic value within range"""
        seed = self._get_hospital_seed(hospital_id + key)
        min_val, max_val = range_tuple
        return min_val + (seed % (max_val - min_val + 1))

    def get_bed_availability(self, hospital_id: str) -> Dict[str, Any]:
        """
        Get real-time bed availability.

        Returns deterministic data based on hospital_id.
        In production, this would call: GET /api/v1/hospitals/{id}/beds
        """
        profile_name = self._get_hospital_profile(hospital_id)
        profile = self.HOSPITAL_PROFILES[profile_name]

        # Generate deterministic totals
        total_beds = self._generate_value_in_range(hospital_id, "beds", profile["total_beds"])
        icu_beds = self._generate_value_in_range(hospital_id, "icu", profile["icu_beds"])
        emergency_beds = self._generate_value_in_range(hospital_id, "emergency", profile["emergency_beds"])

        # Calculate availability based on time of day (more realistic)
        hour = datetime.now().hour
        # Higher occupancy during day (8am-8pm)
        base_occupancy = 0.75 if 8 <= hour <= 20 else 0.6

        # Use seed for slight variation
        seed = self._get_hospital_seed(hospital_id + str(datetime.now().date()))
        occupancy_variation = (seed % 20 - 10) / 100  # -10% to +10%
        occupancy = min(0.95, max(0.3, base_occupancy + occupancy_variation))

        available_beds = max(0, int(total_beds * (1 - occupancy)))
        available_icu = max(0, int(icu_beds * (1 - occupancy - 0.1)))  # ICU usually more occupied
        available_emergency = max(1, int(emergency_beds * (1 - occupancy + 0.1)))  # Keep some emergency

        # Account for reservations
        reserved = len([r for r in self._bed_reservations.values()
                       if r.get("hospital_id") == hospital_id])

        return {
            "hospital_id": hospital_id,
            "timestamp": datetime.now().isoformat(),
            "profile": profile_name,
            "beds": {
                "general": {
                    "total": total_beds,
                    "occupied": total_beds - available_beds,
                    "available": max(0, available_beds - reserved),
                    "reserved": reserved
                },
                "icu": {
                    "total": icu_beds,
                    "occupied": icu_beds - available_icu,
                    "available": available_icu,
                    "ventilators_available": max(0, available_icu - 1)
                },
                "emergency": {
                    "total": emergency_beds,
                    "occupied": emergency_beds - available_emergency,
                    "available": available_emergency
                }
            },
            "capabilities": {
                "has_cardiology": profile["has_cardiology"],
                "has_neurology": profile["has_neurology"],
                "has_trauma": profile["has_trauma"],
                "has_lab": True,
                "has_xray": True,
                "has_ct_scan": profile_name in ["large", "medium"],
                "has_mri": profile_name == "large"
            },
            "status": "operational",
            "last_updated": datetime.now().isoformat()
        }

    def get_doctor_schedule(self, doctor_id: str, date: str) -> List[Dict[str, Any]]:
        """
        Get doctor's available slots for a date.

        In production: GET /api/v1/doctors/{id}/schedule?date={date}
        """
        seed = self._get_hospital_seed(f"{doctor_id}_{date}")

        # Generate slots based on seed
        base_slots = [
            ("09:00", "09:30"), ("09:30", "10:00"), ("10:00", "10:30"),
            ("10:30", "11:00"), ("11:00", "11:30"), ("11:30", "12:00"),
            ("14:00", "14:30"), ("14:30", "15:00"), ("15:00", "15:30"),
            ("15:30", "16:00"), ("16:00", "16:30"), ("16:30", "17:00"),
        ]

        slots = []
        for i, (start, end) in enumerate(base_slots):
            slot_seed = self._get_hospital_seed(f"{doctor_id}_{date}_{i}")
            # 70% of slots are available
            is_available = (slot_seed % 10) < 7

            # Check if already booked in our system
            slot_id = f"{doctor_id}_{date}_{start.replace(':', '')}"
            if slot_id in self._appointments:
                is_available = False

            slots.append({
                "slot_id": slot_id,
                "date": date,
                "start_time": start,
                "end_time": end,
                "duration_minutes": 30,
                "available": is_available,
                "doctor_id": doctor_id,
                "consultation_type": "in_person"
            })

        return slots

    def book_appointment(self, patient_id: str, doctor_id: str, slot_id: str) -> Dict[str, Any]:
        """
        Book an appointment slot.

        In production: POST /api/v1/appointments
        """
        # Check if slot exists and is available
        if slot_id in self._appointments:
            return {
                "success": False,
                "error": "SLOT_ALREADY_BOOKED",
                "message": "This slot has already been booked"
            }

        appointment_id = f"APT-{hashlib.md5(f'{patient_id}{slot_id}'.encode()).hexdigest()[:8].upper()}"

        appointment = {
            "appointment_id": appointment_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "slot_id": slot_id,
            "status": "confirmed",
            "created_at": datetime.now().isoformat(),
            "confirmation_code": f"SS-{appointment_id[-6:]}"
        }

        self._appointments[slot_id] = appointment

        return {
            "success": True,
            "appointment": appointment,
            "message": "Appointment booked successfully"
        }

    def cancel_appointment(self, appointment_id: str) -> bool:
        """Cancel an appointment"""
        for slot_id, apt in list(self._appointments.items()):
            if apt.get("appointment_id") == appointment_id:
                apt["status"] = "cancelled"
                del self._appointments[slot_id]
                return True
        return False

    def get_emergency_capacity(self, hospital_id: str) -> Dict[str, Any]:
        """
        Get emergency department capacity.

        In production: GET /api/v1/hospitals/{id}/emergency
        """
        beds = self.get_bed_availability(hospital_id)
        profile_name = self._get_hospital_profile(hospital_id)
        profile = self.HOSPITAL_PROFILES[profile_name]

        # Calculate ETA based on current load
        emergency_available = beds["beds"]["emergency"]["available"]
        if emergency_available > 5:
            eta_minutes = 5
            status = "accepting"
        elif emergency_available > 2:
            eta_minutes = 15
            status = "accepting"
        elif emergency_available > 0:
            eta_minutes = 30
            status = "limited"
        else:
            eta_minutes = 60
            status = "diverting"

        return {
            "hospital_id": hospital_id,
            "timestamp": datetime.now().isoformat(),
            "emergency_department": {
                "status": status,
                "beds_available": emergency_available,
                "estimated_wait_minutes": eta_minutes,
                "current_patients": beds["beds"]["emergency"]["occupied"],
                "ambulance_bay_available": emergency_available > 0
            },
            "icu": {
                "beds_available": beds["beds"]["icu"]["available"],
                "ventilators_available": beds["beds"]["icu"]["ventilators_available"],
                "can_accept_critical": beds["beds"]["icu"]["available"] > 0
            },
            "capabilities": beds["capabilities"],
            "on_call_specialties": self._get_on_call_specialties(hospital_id, profile),
            "recommendation": "accept" if status == "accepting" else "standby"
        }

    def _get_on_call_specialties(self, hospital_id: str, profile: dict) -> List[str]:
        """Get specialties available on call"""
        specialties = ["emergency_medicine", "general_surgery"]
        if profile["has_cardiology"]:
            specialties.append("cardiology")
        if profile["has_neurology"]:
            specialties.append("neurology")
        if profile["has_trauma"]:
            specialties.append("trauma_surgery")
        return specialties

    def reserve_bed(self, hospital_id: str, bed_type: str, patient_id: str,
                    duration_minutes: int = 30) -> Dict[str, Any]:
        """
        Reserve a bed temporarily.

        In production: POST /api/v1/hospitals/{id}/beds/reserve
        """
        beds = self.get_bed_availability(hospital_id)

        if bed_type == "icu":
            available = beds["beds"]["icu"]["available"]
        elif bed_type == "emergency":
            available = beds["beds"]["emergency"]["available"]
        else:
            available = beds["beds"]["general"]["available"]

        if available <= 0:
            return {
                "success": False,
                "error": "NO_BEDS_AVAILABLE",
                "message": f"No {bed_type} beds available"
            }

        reservation_id = f"RES-{hashlib.md5(f'{hospital_id}{patient_id}{datetime.now()}'.encode()).hexdigest()[:8].upper()}"

        reservation = {
            "reservation_id": reservation_id,
            "hospital_id": hospital_id,
            "bed_type": bed_type,
            "patient_id": patient_id,
            "expires_at": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "status": "active"
        }

        self._bed_reservations[reservation_id] = reservation

        return {
            "success": True,
            "reservation": reservation,
            "message": f"{bed_type.upper()} bed reserved for {duration_minutes} minutes"
        }


# Global instance
_mock_hms: Optional[MockHospitalManagementSystem] = None


def get_hms() -> MockHospitalManagementSystem:
    """Get or create HMS instance"""
    global _mock_hms
    if _mock_hms is None:
        _mock_hms = MockHospitalManagementSystem()
    return _mock_hms
