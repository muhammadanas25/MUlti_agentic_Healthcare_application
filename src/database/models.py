"""Database models for Sehat Saathi"""
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class Hospital:
    """Hospital model"""
    id: Optional[int] = None
    name: str = ""
    city: str = ""
    area: str = ""
    address: str = ""
    contact: str = ""
    num_doctors: int = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Mock provider-side data (can be updated via provider interface)
    total_beds: int = 50
    available_beds: int = 10
    icu_beds: int = 10
    available_icu_beds: int = 2
    has_emergency: bool = True
    has_cardiology: bool = True
    has_lab: bool = True
    operating_hours: str = "24/7"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "area": self.area,
            "address": self.address,
            "contact": self.contact,
            "num_doctors": self.num_doctors,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "total_beds": self.total_beds,
            "available_beds": self.available_beds,
            "icu_beds": self.icu_beds,
            "available_icu_beds": self.available_icu_beds,
            "has_emergency": self.has_emergency,
            "has_cardiology": self.has_cardiology,
            "has_lab": self.has_lab,
            "operating_hours": self.operating_hours,
        }


@dataclass
class Doctor:
    """Doctor model"""
    id: Optional[int] = None
    name: str = ""
    city: str = ""
    specialization: str = ""
    qualification: str = ""
    experience_years: float = 0.0
    total_reviews: int = 0
    satisfaction_rate: float = 0.0
    avg_time_per_patient: int = 15
    wait_time: int = 10
    hospital_address: str = ""
    fee: float = 0.0
    gender: Optional[str] = None  # Can be inferred from name or set manually

    # Mock availability (can be updated via provider interface)
    available_days: List[str] = None
    available_slots: List[str] = None
    is_available_now: bool = True

    def __post_init__(self):
        if self.available_days is None:
            self.available_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        if self.available_slots is None:
            self.available_slots = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "specialization": self.specialization,
            "qualification": self.qualification,
            "experience_years": self.experience_years,
            "total_reviews": self.total_reviews,
            "satisfaction_rate": self.satisfaction_rate,
            "avg_time_per_patient": self.avg_time_per_patient,
            "wait_time": self.wait_time,
            "hospital_address": self.hospital_address,
            "fee": self.fee,
            "gender": self.gender,
            "available_days": self.available_days,
            "available_slots": self.available_slots,
            "is_available_now": self.is_available_now,
        }


@dataclass
class Medicine:
    """Medicine model"""
    id: Optional[int] = None
    name: str = ""
    company: str = ""
    pack_size: str = ""
    link: str = ""
    sale_price: float = 0.0
    mrp: float = 0.0
    letter: str = ""

    # Mock pharmacy stock (can be updated via provider interface)
    stock_available: int = 50
    generic_alternative: Optional[str] = None
    requires_prescription: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "company": self.company,
            "pack_size": self.pack_size,
            "link": self.link,
            "sale_price": self.sale_price,
            "mrp": self.mrp,
            "letter": self.letter,
            "stock_available": self.stock_available,
            "generic_alternative": self.generic_alternative,
            "requires_prescription": self.requires_prescription,
        }


@dataclass
class Appointment:
    """Appointment model for booking system"""
    id: Optional[str] = None
    patient_id: str = ""
    doctor_id: int = 0
    hospital_id: int = 0
    appointment_time: datetime = None
    status: str = "pending"  # pending, confirmed, completed, cancelled
    slot_id: str = ""
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "hospital_id": self.hospital_id,
            "appointment_time": self.appointment_time.isoformat() if self.appointment_time else None,
            "status": self.status,
            "slot_id": self.slot_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class EmergencyCase:
    """Emergency case tracking"""
    id: Optional[str] = None
    patient_id: str = ""
    symptoms: List[str] = None
    severity: str = "moderate"  # low, moderate, high, critical
    location: tuple = None  # (latitude, longitude)
    assigned_hospital_id: Optional[int] = None
    status: str = "open"  # open, assigned, admitted, closed
    created_at: datetime = None

    def __post_init__(self):
        if self.symptoms is None:
            self.symptoms = []
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "symptoms": self.symptoms,
            "severity": self.severity,
            "location": self.location,
            "assigned_hospital_id": self.assigned_hospital_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
