"""
Hospital Resource Management Service

Provides mock data and APIs for hospital resource management:
- Beds (General, ICU, Emergency, Pediatric, Maternity)
- Blood Bank (all blood types)
- Equipment (Ventilators, Oxygen, Dialysis, etc.)
- Staff tracking
"""
import json
import random
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum


class ResourceType(Enum):
    BED = "bed"
    BLOOD = "blood"
    EQUIPMENT = "equipment"
    STAFF = "staff"


class BedType(Enum):
    GENERAL = "general"
    ICU = "icu"
    EMERGENCY = "emergency"
    PEDIATRIC = "pediatric"
    MATERNITY = "maternity"
    CARDIAC = "cardiac"


class BloodType(Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class EquipmentType(Enum):
    VENTILATOR = "ventilator"
    OXYGEN_CYLINDER = "oxygen_cylinder"
    DIALYSIS = "dialysis"
    DEFIBRILLATOR = "defibrillator"
    MONITOR = "cardiac_monitor"
    XRAY = "xray"
    CT_SCAN = "ct_scan"
    MRI = "mri"
    AMBULANCE = "ambulance"


@dataclass
class ResourceStatus:
    """Status of a resource"""
    total: int
    available: int
    reserved: int = 0
    in_use: int = 0
    under_maintenance: int = 0

    @property
    def utilization_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.in_use / self.total) * 100

    @property
    def is_critical(self) -> bool:
        """Check if resource is critically low (< 10% available)"""
        if self.total == 0:
            return True
        return (self.available / self.total) < 0.1


@dataclass
class HospitalResources:
    """Complete resource inventory for a hospital"""
    hospital_id: int
    hospital_name: str
    city: str

    # Beds by type
    beds: Dict[str, ResourceStatus] = field(default_factory=dict)

    # Blood bank
    blood_bank: Dict[str, ResourceStatus] = field(default_factory=dict)

    # Equipment
    equipment: Dict[str, ResourceStatus] = field(default_factory=dict)

    # Staff on duty
    staff: Dict[str, int] = field(default_factory=dict)

    # Last update timestamp
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        result = {
            "hospital_id": self.hospital_id,
            "hospital_name": self.hospital_name,
            "city": self.city,
            "last_updated": self.last_updated,
            "beds": {},
            "blood_bank": {},
            "equipment": {},
            "staff": self.staff
        }
        for key, status in self.beds.items():
            result["beds"][key] = asdict(status)
        for key, status in self.blood_bank.items():
            result["blood_bank"][key] = asdict(status)
        for key, status in self.equipment.items():
            result["equipment"][key] = asdict(status)
        return result


@dataclass
class ResourceBooking:
    """A resource booking record"""
    booking_id: str
    hospital_id: int
    resource_type: str  # bed, blood, equipment
    resource_subtype: str  # icu, A+, ventilator
    patient_id: str
    patient_name: str
    status: str = "pending"  # pending, confirmed, completed, cancelled
    quantity: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    confirmed_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class HospitalResourceService:
    """
    Service for managing hospital resources with mock data.

    Features:
    - Real-time resource tracking (simulated)
    - Booking management
    - Resource alerts
    - Inter-hospital coordination
    """

    def __init__(self):
        self.hospitals: Dict[int, HospitalResources] = {}
        self.bookings: Dict[str, ResourceBooking] = {}
        self._booking_counter = 0

        # Load hospitals and initialize mock resources
        self._initialize_mock_data()

        print(f"Hospital Resource Service initialized with {len(self.hospitals)} hospitals")

    def _initialize_mock_data(self):
        """Initialize mock resource data for hospitals"""
        # Load from Hospitals_updated.csv
        csv_path = Path(__file__).parent.parent.parent / "data" / "Hospitals_updated.csv"

        try:
            import pandas as pd
            df = pd.read_csv(csv_path)

            # Initialize resources for each hospital
            for idx, row in df.iterrows():
                hospital_id = idx + 1
                hospital_name = row.get("HOSPITAL NAME", f"Hospital {hospital_id}")
                city = row.get("CITY", "Karachi")

                self.hospitals[hospital_id] = self._create_mock_resources(
                    hospital_id, hospital_name, city
                )

                # Limit to first 50 hospitals for demo
                if hospital_id >= 50:
                    break

        except Exception as e:
            print(f"Error loading hospitals: {e}")
            # Create some default hospitals
            for i in range(1, 11):
                self.hospitals[i] = self._create_mock_resources(
                    i, f"Hospital {i}", "Karachi"
                )

    def _create_mock_resources(
        self,
        hospital_id: int,
        hospital_name: str,
        city: str
    ) -> HospitalResources:
        """Create mock resources for a hospital"""
        # Randomize based on hospital tier
        is_large = random.random() > 0.6

        # Beds
        beds = {}
        for bed_type in BedType:
            if bed_type == BedType.GENERAL:
                total = random.randint(50, 150) if is_large else random.randint(20, 50)
            elif bed_type == BedType.ICU:
                total = random.randint(15, 40) if is_large else random.randint(5, 15)
            elif bed_type == BedType.EMERGENCY:
                total = random.randint(10, 25) if is_large else random.randint(5, 10)
            else:
                total = random.randint(5, 20) if is_large else random.randint(2, 8)

            available = random.randint(int(total * 0.1), int(total * 0.4))
            in_use = total - available - random.randint(0, 2)

            beds[bed_type.value] = ResourceStatus(
                total=total,
                available=available,
                in_use=max(0, in_use),
                under_maintenance=random.randint(0, 2)
            )

        # Blood bank
        blood_bank = {}
        for blood_type in BloodType:
            # O+ and A+ are common, AB- is rare
            if blood_type in [BloodType.O_POS, BloodType.A_POS]:
                total = random.randint(30, 80)
            elif blood_type in [BloodType.AB_NEG, BloodType.B_NEG]:
                total = random.randint(5, 15)
            else:
                total = random.randint(15, 40)

            available = random.randint(int(total * 0.3), total)

            blood_bank[blood_type.value] = ResourceStatus(
                total=total,
                available=available,
                reserved=random.randint(0, 3),
                in_use=total - available
            )

        # Equipment
        equipment = {}
        for eq_type in EquipmentType:
            if eq_type == EquipmentType.VENTILATOR:
                total = random.randint(10, 30) if is_large else random.randint(3, 10)
            elif eq_type == EquipmentType.OXYGEN_CYLINDER:
                total = random.randint(50, 150) if is_large else random.randint(20, 50)
            elif eq_type in [EquipmentType.MRI, EquipmentType.CT_SCAN]:
                total = random.randint(1, 3) if is_large else random.randint(0, 1)
            elif eq_type == EquipmentType.AMBULANCE:
                total = random.randint(3, 8) if is_large else random.randint(1, 3)
            else:
                total = random.randint(5, 20) if is_large else random.randint(2, 8)

            available = random.randint(int(total * 0.2), int(total * 0.6)) if total > 0 else 0

            equipment[eq_type.value] = ResourceStatus(
                total=total,
                available=max(0, available),
                in_use=total - available if total > 0 else 0,
                under_maintenance=random.randint(0, 1)
            )

        # Staff
        staff = {
            "doctors_on_duty": random.randint(10, 50) if is_large else random.randint(3, 15),
            "nurses_on_duty": random.randint(30, 100) if is_large else random.randint(10, 30),
            "technicians_on_duty": random.randint(5, 20) if is_large else random.randint(2, 8),
            "support_staff": random.randint(20, 50) if is_large else random.randint(5, 15),
        }

        return HospitalResources(
            hospital_id=hospital_id,
            hospital_name=hospital_name,
            city=city,
            beds=beds,
            blood_bank=blood_bank,
            equipment=equipment,
            staff=staff
        )

    # ==================== Query Methods ====================

    def get_hospital_resources(self, hospital_id: int) -> Optional[Dict[str, Any]]:
        """Get all resources for a hospital"""
        hospital = self.hospitals.get(hospital_id)
        if hospital:
            return hospital.to_dict()
        return None

    def get_bed_availability(
        self,
        hospital_id: int,
        bed_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get bed availability for a hospital"""
        hospital = self.hospitals.get(hospital_id)
        if not hospital:
            return {"error": "Hospital not found"}

        if bed_type:
            status = hospital.beds.get(bed_type)
            if status:
                return {
                    "hospital_id": hospital_id,
                    "hospital_name": hospital.hospital_name,
                    "bed_type": bed_type,
                    **asdict(status)
                }
            return {"error": f"Bed type {bed_type} not found"}

        # Return all bed types
        result = {
            "hospital_id": hospital_id,
            "hospital_name": hospital.hospital_name,
            "beds": {}
        }
        for bt, status in hospital.beds.items():
            result["beds"][bt] = asdict(status)
        return result

    def get_blood_availability(
        self,
        hospital_id: int,
        blood_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get blood availability for a hospital"""
        hospital = self.hospitals.get(hospital_id)
        if not hospital:
            return {"error": "Hospital not found"}

        if blood_type:
            status = hospital.blood_bank.get(blood_type)
            if status:
                return {
                    "hospital_id": hospital_id,
                    "hospital_name": hospital.hospital_name,
                    "blood_type": blood_type,
                    **asdict(status),
                    "urgency_level": "critical" if status.is_critical else "normal"
                }
            return {"error": f"Blood type {blood_type} not found"}

        # Return all blood types
        result = {
            "hospital_id": hospital_id,
            "hospital_name": hospital.hospital_name,
            "blood_bank": {}
        }
        for bt, status in hospital.blood_bank.items():
            data = asdict(status)
            data["urgency_level"] = "critical" if status.is_critical else "normal"
            result["blood_bank"][bt] = data
        return result

    def get_equipment_availability(
        self,
        hospital_id: int,
        equipment_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get equipment availability for a hospital"""
        hospital = self.hospitals.get(hospital_id)
        if not hospital:
            return {"error": "Hospital not found"}

        if equipment_type:
            status = hospital.equipment.get(equipment_type)
            if status:
                return {
                    "hospital_id": hospital_id,
                    "hospital_name": hospital.hospital_name,
                    "equipment_type": equipment_type,
                    **asdict(status)
                }
            return {"error": f"Equipment type {equipment_type} not found"}

        result = {
            "hospital_id": hospital_id,
            "hospital_name": hospital.hospital_name,
            "equipment": {}
        }
        for eq, status in hospital.equipment.items():
            result["equipment"][eq] = asdict(status)
        return result

    def search_available_resources(
        self,
        resource_type: str,  # bed, blood, equipment
        resource_subtype: str,  # icu, A+, ventilator
        city: Optional[str] = None,
        min_quantity: int = 1
    ) -> List[Dict[str, Any]]:
        """Search for available resources across hospitals"""
        results = []

        for hospital_id, hospital in self.hospitals.items():
            if city and hospital.city.lower() != city.lower():
                continue

            status = None
            if resource_type == "bed":
                status = hospital.beds.get(resource_subtype)
            elif resource_type == "blood":
                status = hospital.blood_bank.get(resource_subtype)
            elif resource_type == "equipment":
                status = hospital.equipment.get(resource_subtype)

            if status and status.available >= min_quantity:
                results.append({
                    "hospital_id": hospital_id,
                    "hospital_name": hospital.hospital_name,
                    "city": hospital.city,
                    "resource_type": resource_type,
                    "resource_subtype": resource_subtype,
                    "available": status.available,
                    "total": status.total,
                    "utilization_rate": status.utilization_rate
                })

        # Sort by availability (most available first)
        results.sort(key=lambda x: x["available"], reverse=True)
        return results

    # ==================== Booking Methods ====================

    def create_booking(
        self,
        hospital_id: int,
        resource_type: str,
        resource_subtype: str,
        patient_id: str,
        patient_name: str,
        quantity: int = 1,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Create a resource booking"""
        hospital = self.hospitals.get(hospital_id)
        if not hospital:
            return {"success": False, "error": "Hospital not found"}

        # Check availability
        status = None
        if resource_type == "bed":
            status = hospital.beds.get(resource_subtype)
        elif resource_type == "blood":
            status = hospital.blood_bank.get(resource_subtype)
        elif resource_type == "equipment":
            status = hospital.equipment.get(resource_subtype)

        if not status:
            return {"success": False, "error": f"{resource_subtype} not found"}

        if status.available < quantity:
            return {
                "success": False,
                "error": f"Not enough {resource_subtype} available. Requested: {quantity}, Available: {status.available}"
            }

        # Create booking
        self._booking_counter += 1
        booking_id = f"BK-{hospital_id}-{self._booking_counter:05d}"

        booking = ResourceBooking(
            booking_id=booking_id,
            hospital_id=hospital_id,
            resource_type=resource_type,
            resource_subtype=resource_subtype,
            patient_id=patient_id,
            patient_name=patient_name,
            quantity=quantity,
            notes=notes,
            status="pending"
        )

        self.bookings[booking_id] = booking

        # Reserve the resource
        status.available -= quantity
        status.reserved += quantity

        return {
            "success": True,
            "booking": booking.to_dict(),
            "message": f"Booking created for {quantity} {resource_subtype} at {hospital.hospital_name}"
        }

    def confirm_booking(self, booking_id: str) -> Dict[str, Any]:
        """Confirm a pending booking"""
        booking = self.bookings.get(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}

        if booking.status != "pending":
            return {"success": False, "error": f"Cannot confirm booking with status: {booking.status}"}

        hospital = self.hospitals.get(booking.hospital_id)
        if not hospital:
            return {"success": False, "error": "Hospital not found"}

        # Update booking status
        booking.status = "confirmed"
        booking.confirmed_at = datetime.now().isoformat()

        # Move from reserved to in_use
        status = None
        if booking.resource_type == "bed":
            status = hospital.beds.get(booking.resource_subtype)
        elif booking.resource_type == "blood":
            status = hospital.blood_bank.get(booking.resource_subtype)
        elif booking.resource_type == "equipment":
            status = hospital.equipment.get(booking.resource_subtype)

        if status:
            status.reserved -= booking.quantity
            status.in_use += booking.quantity

        return {
            "success": True,
            "booking": booking.to_dict(),
            "message": f"Booking {booking_id} confirmed"
        }

    def cancel_booking(self, booking_id: str, reason: str = "") -> Dict[str, Any]:
        """Cancel a booking"""
        booking = self.bookings.get(booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}

        hospital = self.hospitals.get(booking.hospital_id)
        if not hospital:
            return {"success": False, "error": "Hospital not found"}

        # Return resources
        status = None
        if booking.resource_type == "bed":
            status = hospital.beds.get(booking.resource_subtype)
        elif booking.resource_type == "blood":
            status = hospital.blood_bank.get(booking.resource_subtype)
        elif booking.resource_type == "equipment":
            status = hospital.equipment.get(booking.resource_subtype)

        if status:
            if booking.status == "pending":
                status.reserved -= booking.quantity
                status.available += booking.quantity
            elif booking.status == "confirmed":
                status.in_use -= booking.quantity
                status.available += booking.quantity

        booking.status = "cancelled"
        booking.notes += f"\nCancelled: {reason}"

        return {
            "success": True,
            "booking": booking.to_dict(),
            "message": f"Booking {booking_id} cancelled"
        }

    def get_booking(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """Get booking details"""
        booking = self.bookings.get(booking_id)
        return booking.to_dict() if booking else None

    def get_hospital_bookings(
        self,
        hospital_id: int,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all bookings for a hospital"""
        results = []
        for booking in self.bookings.values():
            if booking.hospital_id == hospital_id:
                if status is None or booking.status == status:
                    results.append(booking.to_dict())
        return results

    # ==================== Dashboard Methods ====================

    def get_dashboard_stats(self, hospital_id: int) -> Dict[str, Any]:
        """Get dashboard statistics for hospital manager"""
        hospital = self.hospitals.get(hospital_id)
        if not hospital:
            return {"error": "Hospital not found"}

        # Calculate bed stats
        total_beds = sum(s.total for s in hospital.beds.values())
        available_beds = sum(s.available for s in hospital.beds.values())
        occupied_beds = sum(s.in_use for s in hospital.beds.values())

        # Critical resources
        critical_resources = []
        for bed_type, status in hospital.beds.items():
            if status.is_critical:
                critical_resources.append({
                    "type": "bed",
                    "subtype": bed_type,
                    "available": status.available,
                    "total": status.total
                })

        for blood_type, status in hospital.blood_bank.items():
            if status.is_critical:
                critical_resources.append({
                    "type": "blood",
                    "subtype": blood_type,
                    "available": status.available,
                    "total": status.total
                })

        for eq_type, status in hospital.equipment.items():
            if status.is_critical and status.total > 0:
                critical_resources.append({
                    "type": "equipment",
                    "subtype": eq_type,
                    "available": status.available,
                    "total": status.total
                })

        # Booking stats
        hospital_bookings = self.get_hospital_bookings(hospital_id)
        pending_bookings = len([b for b in hospital_bookings if b["status"] == "pending"])
        confirmed_bookings = len([b for b in hospital_bookings if b["status"] == "confirmed"])

        return {
            "hospital_id": hospital_id,
            "hospital_name": hospital.hospital_name,
            "last_updated": hospital.last_updated,
            "summary": {
                "total_beds": total_beds,
                "available_beds": available_beds,
                "occupied_beds": occupied_beds,
                "bed_occupancy_rate": round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0,
                "ventilators_available": hospital.equipment.get("ventilator", ResourceStatus(0, 0)).available,
                "icu_beds_available": hospital.beds.get("icu", ResourceStatus(0, 0)).available,
            },
            "staff": hospital.staff,
            "critical_resources": critical_resources,
            "bookings": {
                "pending": pending_bookings,
                "confirmed": confirmed_bookings,
                "total_today": pending_bookings + confirmed_bookings
            },
            "beds_breakdown": {k: asdict(v) for k, v in hospital.beds.items()},
            "blood_bank_summary": {k: {"available": v.available, "total": v.total} for k, v in hospital.blood_bank.items()},
            "equipment_summary": {k: {"available": v.available, "total": v.total} for k, v in hospital.equipment.items()}
        }

    def get_all_hospitals_summary(self, city: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get summary of all hospitals (for admin dashboard)"""
        results = []
        for hospital_id, hospital in self.hospitals.items():
            if city and hospital.city.lower() != city.lower():
                continue

            total_beds = sum(s.total for s in hospital.beds.values())
            available_beds = sum(s.available for s in hospital.beds.values())

            results.append({
                "hospital_id": hospital_id,
                "hospital_name": hospital.hospital_name,
                "city": hospital.city,
                "total_beds": total_beds,
                "available_beds": available_beds,
                "icu_available": hospital.beds.get("icu", ResourceStatus(0, 0)).available,
                "ventilators_available": hospital.equipment.get("ventilator", ResourceStatus(0, 0)).available,
                "has_critical_shortage": any(s.is_critical for s in hospital.beds.values())
            })

        return results


# Global instance
_hospital_resource_service: Optional[HospitalResourceService] = None


def get_hospital_resource_service() -> HospitalResourceService:
    """Get or create the hospital resource service instance"""
    global _hospital_resource_service
    if _hospital_resource_service is None:
        _hospital_resource_service = HospitalResourceService()
    return _hospital_resource_service
