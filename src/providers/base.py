"""Base Provider API interface - All providers implement this"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime


class BaseHospitalAPI(ABC):
    """
    Base interface for Hospital Management System (HMS) APIs.

    To integrate with a real hospital:
    1. Create a new class that inherits from this
    2. Implement all abstract methods
    3. Replace MockHospitalManagementSystem with your implementation
    """

    @abstractmethod
    def get_bed_availability(self, hospital_id: str) -> Dict[str, Any]:
        """Get real-time bed availability"""
        pass

    @abstractmethod
    def get_doctor_schedule(self, doctor_id: str, date: str) -> List[Dict[str, Any]]:
        """Get doctor's available slots for a date"""
        pass

    @abstractmethod
    def book_appointment(self, patient_id: str, doctor_id: str, slot_id: str) -> Dict[str, Any]:
        """Book an appointment slot"""
        pass

    @abstractmethod
    def cancel_appointment(self, appointment_id: str) -> bool:
        """Cancel an appointment"""
        pass

    @abstractmethod
    def get_emergency_capacity(self, hospital_id: str) -> Dict[str, Any]:
        """Get emergency department capacity"""
        pass


class BasePharmacyAPI(ABC):
    """
    Base interface for Pharmacy System APIs.
    """

    @abstractmethod
    def check_stock(self, medicine_name: str, location: str) -> Dict[str, Any]:
        """Check medicine stock at location"""
        pass

    @abstractmethod
    def reserve_medicine(self, medicine_id: str, quantity: int, patient_id: str) -> Dict[str, Any]:
        """Reserve medicine for pickup"""
        pass

    @abstractmethod
    def get_price(self, medicine_id: str) -> Dict[str, Any]:
        """Get medicine price"""
        pass


class BaseInsuranceAPI(ABC):
    """
    Base interface for Insurance/Sehat Sahulat APIs.
    """

    @abstractmethod
    def verify_eligibility(self, cnic: str) -> Dict[str, Any]:
        """Verify patient's insurance eligibility"""
        pass

    @abstractmethod
    def check_coverage(self, cnic: str, treatment_code: str) -> Dict[str, Any]:
        """Check if treatment is covered"""
        pass

    @abstractmethod
    def pre_authorize(self, cnic: str, treatment_code: str, estimated_cost: float) -> Dict[str, Any]:
        """Pre-authorize treatment"""
        pass
