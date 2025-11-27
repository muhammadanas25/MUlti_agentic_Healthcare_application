"""
Doctor Availability Service

Provides intelligent doctor search and appointment management:
- Schedule-based availability (Day + Timing from CSV)
- Specialization matching
- City-based filtering
- Rating and experience sorting
- Appointment slot management
"""
import json
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, time
from pathlib import Path
from enum import Enum
import random
import uuid


class DayOfWeek(Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"


@dataclass
class DoctorSchedule:
    """Doctor's schedule for a specific day"""
    day: str
    start_time: str  # HH:MM format
    end_time: str
    patients_per_day: int
    slot_duration_mins: int = 15

    @property
    def available_slots(self) -> List[str]:
        """Generate available time slots"""
        slots = []
        try:
            start = datetime.strptime(self.start_time, "%H:%M")
            end = datetime.strptime(self.end_time, "%H:%M")
            current = start
            while current < end:
                slots.append(current.strftime("%H:%M"))
                current += timedelta(minutes=self.slot_duration_mins)
        except:
            pass
        return slots


@dataclass
class DoctorInfo:
    """Complete doctor information with schedule"""
    id: int
    name: str
    city: str
    specialization: str
    qualification: str
    experience_years: int
    total_reviews: int
    satisfaction_rate: float
    avg_time_per_patient: int
    wait_time: int
    hospital_address: str
    fee: float
    link: str
    schedule: DoctorSchedule

    def to_dict(self) -> dict:
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
            "link": self.link,
            "schedule": {
                "day": self.schedule.day,
                "timing": f"{self.schedule.start_time}-{self.schedule.end_time}",
                "patients_per_day": self.schedule.patients_per_day
            }
        }


@dataclass
class DoctorAppointment:
    """Appointment record"""
    appointment_id: str
    doctor_id: int
    doctor_name: str
    patient_id: str
    patient_name: str
    patient_phone: str
    appointment_date: str  # YYYY-MM-DD
    appointment_time: str  # HH:MM
    status: str = "scheduled"  # scheduled, confirmed, completed, cancelled, no_show
    reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class DoctorAvailabilityService:
    """
    Service for doctor availability and appointment management.

    Features:
    - Load doctors from CSV with schedule data
    - Search by specialization, city, day, time
    - Check real-time availability
    - Book and manage appointments
    - Doctor dashboard data
    """

    def __init__(self):
        self.doctors: Dict[int, DoctorInfo] = {}
        self.appointments: Dict[str, DoctorAppointment] = {}
        self.doctor_appointments: Dict[int, List[str]] = {}  # doctor_id -> [appointment_ids]
        self._appointment_counter = 0

        # Load doctors from CSV
        self._load_doctors()

        print(f"Doctor Availability Service initialized with {len(self.doctors)} doctors")

    def _load_doctors(self):
        """Load doctors from CSV file"""
        csv_path = Path(__file__).parent.parent.parent / "data" / "Appointment-Doctors_with_Availabilty.csv"

        try:
            df = pd.read_csv(csv_path)

            for idx, row in df.iterrows():
                doctor_id = idx + 1

                # Parse timing (e.g., "09:00-13:00")
                timing = str(row.get("Timing", "09:00-17:00"))
                try:
                    start_time, end_time = timing.split("-")
                except:
                    start_time, end_time = "09:00", "17:00"

                schedule = DoctorSchedule(
                    day=str(row.get("Day", "Monday")),
                    start_time=start_time.strip(),
                    end_time=end_time.strip(),
                    patients_per_day=int(row.get("PatientsPerDay", 20)) if pd.notna(row.get("PatientsPerDay")) else 20
                )

                doctor = DoctorInfo(
                    id=doctor_id,
                    name=str(row.get("Doctor Name", f"Dr. {doctor_id}")),
                    city=str(row.get("City", "")).upper(),
                    specialization=str(row.get("Specialization", "General Physician")),
                    qualification=str(row.get("Doctor Qualification", "")),
                    experience_years=int(row.get("Experience(Years)", 0)) if pd.notna(row.get("Experience(Years)")) else 0,
                    total_reviews=int(row.get("Total_Reviews", 0)) if pd.notna(row.get("Total_Reviews")) else 0,
                    satisfaction_rate=float(row.get("Patient Satisfaction Rate(%age)", 90)) if pd.notna(row.get("Patient Satisfaction Rate(%age)")) else 90,
                    avg_time_per_patient=int(row.get("Avg Time to Patients(mins)", 15)) if pd.notna(row.get("Avg Time to Patients(mins)")) else 15,
                    wait_time=int(row.get("Wait Time(mins)", 10)) if pd.notna(row.get("Wait Time(mins)")) else 10,
                    hospital_address=str(row.get("Hospital Address", "")),
                    fee=float(row.get("Fee(PKR)", 1000)) if pd.notna(row.get("Fee(PKR)")) else 1000,
                    link=str(row.get("Doctors Link", "")) if pd.notna(row.get("Doctors Link")) else "",
                    schedule=schedule
                )

                self.doctors[doctor_id] = doctor
                self.doctor_appointments[doctor_id] = []

        except Exception as e:
            print(f"Error loading doctors: {e}")
            # Create some default doctors
            for i in range(1, 11):
                schedule = DoctorSchedule(
                    day=list(DayOfWeek)[i % 7].value,
                    start_time="09:00",
                    end_time="17:00",
                    patients_per_day=20
                )
                self.doctors[i] = DoctorInfo(
                    id=i,
                    name=f"Dr. Sample {i}",
                    city="KARACHI",
                    specialization="General Physician",
                    qualification="MBBS",
                    experience_years=5,
                    total_reviews=100,
                    satisfaction_rate=90,
                    avg_time_per_patient=15,
                    wait_time=10,
                    hospital_address="Sample Hospital, Karachi",
                    fee=1000,
                    link="",
                    schedule=schedule
                )
                self.doctor_appointments[i] = []

    # ==================== Search Methods ====================

    def search_doctors(
        self,
        city: Optional[str] = None,
        specialization: Optional[str] = None,
        day: Optional[str] = None,
        max_fee: Optional[float] = None,
        min_satisfaction: float = 0,
        min_experience: int = 0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for doctors based on various criteria.

        Args:
            city: Filter by city
            specialization: Filter by specialization (partial match)
            day: Filter by available day (Monday, Tuesday, etc.)
            max_fee: Maximum consultation fee
            min_satisfaction: Minimum satisfaction rate
            min_experience: Minimum years of experience
            limit: Maximum results to return
        """
        results = []

        for doctor in self.doctors.values():
            # City filter
            if city and city.upper() not in doctor.city.upper():
                continue

            # Specialization filter (partial match)
            if specialization:
                spec_lower = specialization.lower()
                if spec_lower not in doctor.specialization.lower():
                    continue

            # Day filter
            if day and day.lower() != doctor.schedule.day.lower():
                continue

            # Fee filter
            if max_fee and doctor.fee > max_fee:
                continue

            # Satisfaction filter
            if doctor.satisfaction_rate < min_satisfaction:
                continue

            # Experience filter
            if doctor.experience_years < min_experience:
                continue

            results.append(doctor.to_dict())

        # Sort by satisfaction rate and reviews
        results.sort(key=lambda x: (x["satisfaction_rate"], x["total_reviews"]), reverse=True)

        return results[:limit]

    def get_doctor(self, doctor_id: int) -> Optional[Dict[str, Any]]:
        """Get doctor by ID"""
        doctor = self.doctors.get(doctor_id)
        return doctor.to_dict() if doctor else None

    def get_specializations(self, city: Optional[str] = None) -> List[str]:
        """Get list of available specializations"""
        specializations = set()
        for doctor in self.doctors.values():
            if city and city.upper() not in doctor.city.upper():
                continue
            # Handle comma-separated specializations
            for spec in doctor.specialization.split(","):
                specializations.add(spec.strip())
        return sorted(list(specializations))

    def get_cities(self) -> List[str]:
        """Get list of available cities"""
        cities = set()
        for doctor in self.doctors.values():
            cities.add(doctor.city)
        return sorted(list(cities))

    def find_available_doctors_today(
        self,
        city: Optional[str] = None,
        specialization: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find doctors available today"""
        today = datetime.now().strftime("%A")
        return self.search_doctors(
            city=city,
            specialization=specialization,
            day=today
        )

    def find_available_next_days(
        self,
        city: Optional[str] = None,
        specialization: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Find doctors available in the next N days"""
        results = {}
        today = datetime.now()

        for i in range(days):
            date = today + timedelta(days=i)
            day_name = date.strftime("%A")

            doctors = self.search_doctors(
                city=city,
                specialization=specialization,
                day=day_name,
                limit=20
            )

            if doctors:
                results[date.strftime("%Y-%m-%d")] = {
                    "day": day_name,
                    "doctors": doctors
                }

        return results

    # ==================== Availability Methods ====================

    def get_doctor_availability(
        self,
        doctor_id: int,
        date: str  # YYYY-MM-DD
    ) -> Dict[str, Any]:
        """Get available slots for a doctor on a specific date"""
        doctor = self.doctors.get(doctor_id)
        if not doctor:
            return {"error": "Doctor not found"}

        # Check if the date matches the doctor's working day
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            day_name = date_obj.strftime("%A")
        except:
            return {"error": "Invalid date format"}

        if day_name.lower() != doctor.schedule.day.lower():
            return {
                "doctor_id": doctor_id,
                "doctor_name": doctor.name,
                "date": date,
                "available": False,
                "reason": f"Doctor is only available on {doctor.schedule.day}",
                "next_available_day": doctor.schedule.day
            }

        # Get booked slots for this doctor on this date
        booked_slots = set()
        for apt_id in self.doctor_appointments.get(doctor_id, []):
            apt = self.appointments.get(apt_id)
            if apt and apt.appointment_date == date and apt.status not in ["cancelled", "no_show"]:
                booked_slots.add(apt.appointment_time)

        # Generate available slots
        all_slots = doctor.schedule.available_slots
        available_slots = [s for s in all_slots if s not in booked_slots]

        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor.name,
            "date": date,
            "day": day_name,
            "available": len(available_slots) > 0,
            "total_slots": len(all_slots),
            "booked_slots": len(booked_slots),
            "available_slots": available_slots,
            "timing": f"{doctor.schedule.start_time}-{doctor.schedule.end_time}",
            "fee": doctor.fee,
            "hospital": doctor.hospital_address
        }

    def get_next_available_slot(
        self,
        doctor_id: int,
        from_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get the next available slot for a doctor"""
        doctor = self.doctors.get(doctor_id)
        if not doctor:
            return {"error": "Doctor not found"}

        # Start from today or specified date
        if from_date:
            try:
                start = datetime.strptime(from_date, "%Y-%m-%d")
            except:
                start = datetime.now()
        else:
            start = datetime.now()

        # Look ahead up to 4 weeks
        for i in range(28):
            date = start + timedelta(days=i)
            day_name = date.strftime("%A")

            if day_name.lower() == doctor.schedule.day.lower():
                availability = self.get_doctor_availability(doctor_id, date.strftime("%Y-%m-%d"))
                if availability.get("available") and availability.get("available_slots"):
                    return {
                        "doctor_id": doctor_id,
                        "doctor_name": doctor.name,
                        "next_date": date.strftime("%Y-%m-%d"),
                        "day": day_name,
                        "available_slots": availability["available_slots"],
                        "fee": doctor.fee,
                        "hospital": doctor.hospital_address
                    }

        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor.name,
            "available": False,
            "reason": "No available slots in the next 4 weeks"
        }

    # ==================== Appointment Methods ====================

    def book_appointment(
        self,
        doctor_id: int,
        patient_id: str,
        patient_name: str,
        patient_phone: str,
        appointment_date: str,
        appointment_time: str,
        reason: str = ""
    ) -> Dict[str, Any]:
        """Book an appointment with a doctor"""
        doctor = self.doctors.get(doctor_id)
        if not doctor:
            return {"success": False, "error": "Doctor not found"}

        # Check availability
        availability = self.get_doctor_availability(doctor_id, appointment_date)
        if not availability.get("available"):
            return {"success": False, "error": availability.get("reason", "Doctor not available")}

        if appointment_time not in availability.get("available_slots", []):
            return {"success": False, "error": f"Slot {appointment_time} is not available"}

        # Create appointment
        self._appointment_counter += 1
        appointment_id = f"APT-{doctor_id}-{self._appointment_counter:05d}"

        appointment = DoctorAppointment(
            appointment_id=appointment_id,
            doctor_id=doctor_id,
            doctor_name=doctor.name,
            patient_id=patient_id,
            patient_name=patient_name,
            patient_phone=patient_phone,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason=reason,
            status="scheduled"
        )

        self.appointments[appointment_id] = appointment
        self.doctor_appointments[doctor_id].append(appointment_id)

        return {
            "success": True,
            "appointment": appointment.to_dict(),
            "message": f"Appointment booked with {doctor.name} on {appointment_date} at {appointment_time}",
            "hospital": doctor.hospital_address,
            "fee": doctor.fee
        }

    def cancel_appointment(
        self,
        appointment_id: str,
        reason: str = ""
    ) -> Dict[str, Any]:
        """Cancel an appointment"""
        appointment = self.appointments.get(appointment_id)
        if not appointment:
            return {"success": False, "error": "Appointment not found"}

        if appointment.status in ["completed", "cancelled"]:
            return {"success": False, "error": f"Cannot cancel appointment with status: {appointment.status}"}

        appointment.status = "cancelled"
        appointment.notes += f"\nCancelled: {reason}"

        return {
            "success": True,
            "appointment": appointment.to_dict(),
            "message": f"Appointment {appointment_id} cancelled"
        }

    def complete_appointment(
        self,
        appointment_id: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Mark appointment as completed"""
        appointment = self.appointments.get(appointment_id)
        if not appointment:
            return {"success": False, "error": "Appointment not found"}

        appointment.status = "completed"
        appointment.notes = notes

        return {
            "success": True,
            "appointment": appointment.to_dict(),
            "message": f"Appointment {appointment_id} completed"
        }

    def get_appointment(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        """Get appointment details"""
        appointment = self.appointments.get(appointment_id)
        return appointment.to_dict() if appointment else None

    def get_patient_appointments(
        self,
        patient_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all appointments for a patient"""
        results = []
        for appointment in self.appointments.values():
            if appointment.patient_id == patient_id:
                if status is None or appointment.status == status:
                    results.append(appointment.to_dict())
        # Sort by date and time
        results.sort(key=lambda x: (x["appointment_date"], x["appointment_time"]))
        return results

    # ==================== Doctor Dashboard Methods ====================

    def get_doctor_dashboard(
        self,
        doctor_id: int,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get dashboard data for a doctor"""
        doctor = self.doctors.get(doctor_id)
        if not doctor:
            return {"error": "Doctor not found"}

        # Default to today
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # Get today's appointments
        today_appointments = []
        upcoming_appointments = []
        completed_today = 0
        cancelled_today = 0

        for apt_id in self.doctor_appointments.get(doctor_id, []):
            apt = self.appointments.get(apt_id)
            if apt:
                if apt.appointment_date == date:
                    today_appointments.append(apt.to_dict())
                    if apt.status == "completed":
                        completed_today += 1
                    elif apt.status == "cancelled":
                        cancelled_today += 1
                elif apt.appointment_date > date and apt.status == "scheduled":
                    upcoming_appointments.append(apt.to_dict())

        # Sort today's by time
        today_appointments.sort(key=lambda x: x["appointment_time"])
        upcoming_appointments.sort(key=lambda x: (x["appointment_date"], x["appointment_time"]))

        # Calculate stats
        total_appointments = len(self.doctor_appointments.get(doctor_id, []))
        all_completed = len([
            apt for apt_id in self.doctor_appointments.get(doctor_id, [])
            for apt in [self.appointments.get(apt_id)]
            if apt and apt.status == "completed"
        ])

        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor.name,
            "specialization": doctor.specialization,
            "date": date,
            "schedule": {
                "working_day": doctor.schedule.day,
                "timing": f"{doctor.schedule.start_time}-{doctor.schedule.end_time}",
                "patients_per_day": doctor.schedule.patients_per_day
            },
            "today": {
                "total": len(today_appointments),
                "scheduled": len([a for a in today_appointments if a["status"] == "scheduled"]),
                "completed": completed_today,
                "cancelled": cancelled_today,
                "appointments": today_appointments[:20]  # Limit for dashboard
            },
            "upcoming": {
                "total": len(upcoming_appointments),
                "next_7_days": upcoming_appointments[:10]  # Next 10 appointments
            },
            "stats": {
                "total_appointments": total_appointments,
                "total_completed": all_completed,
                "satisfaction_rate": doctor.satisfaction_rate,
                "total_reviews": doctor.total_reviews
            }
        }

    def get_doctor_schedule_view(
        self,
        doctor_id: int,
        start_date: Optional[str] = None,
        weeks: int = 4
    ) -> Dict[str, Any]:
        """Get schedule view for a doctor (calendar view data)"""
        doctor = self.doctors.get(doctor_id)
        if not doctor:
            return {"error": "Doctor not found"}

        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")

        start = datetime.strptime(start_date, "%Y-%m-%d")
        schedule_data = {}

        for i in range(weeks * 7):
            date = start + timedelta(days=i)
            day_name = date.strftime("%A")
            date_str = date.strftime("%Y-%m-%d")

            is_working_day = day_name.lower() == doctor.schedule.day.lower()

            if is_working_day:
                availability = self.get_doctor_availability(doctor_id, date_str)
                schedule_data[date_str] = {
                    "day": day_name,
                    "working": True,
                    "total_slots": availability.get("total_slots", 0),
                    "booked": availability.get("booked_slots", 0),
                    "available": len(availability.get("available_slots", []))
                }
            else:
                schedule_data[date_str] = {
                    "day": day_name,
                    "working": False,
                    "total_slots": 0,
                    "booked": 0,
                    "available": 0
                }

        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor.name,
            "working_day": doctor.schedule.day,
            "timing": f"{doctor.schedule.start_time}-{doctor.schedule.end_time}",
            "schedule": schedule_data
        }


# Global instance
_doctor_availability_service: Optional[DoctorAvailabilityService] = None


def get_doctor_availability_service() -> DoctorAvailabilityService:
    """Get or create the doctor availability service instance"""
    global _doctor_availability_service
    if _doctor_availability_service is None:
        _doctor_availability_service = DoctorAvailabilityService()
    return _doctor_availability_service
