"""Database manager for loading and querying data"""
import pandas as pd
import random
from typing import List, Optional, Dict
from pathlib import Path
from .models import Hospital, Doctor, Medicine, Appointment, EmergencyCase
from ..core.config import settings


class DatabaseManager:
    """Manages database operations and queries"""

    def __init__(self):
        self.hospitals_df: Optional[pd.DataFrame] = None
        self.doctors_df: Optional[pd.DataFrame] = None
        self.medicines_df: Optional[pd.DataFrame] = None

        # In-memory storage for runtime data
        self.appointments: Dict[str, Appointment] = {}
        self.emergency_cases: Dict[str, EmergencyCase] = {}

        self._load_data()

    def _load_data(self):
        """Load CSV data into memory"""
        try:
            # Load hospitals
            self.hospitals_df = pd.read_csv(settings.hospitals_csv)
            print(f"✓ Loaded {len(self.hospitals_df)} hospitals")

            # Load doctors
            self.doctors_df = pd.read_csv(settings.doctors_csv)
            print(f"✓ Loaded {len(self.doctors_df)} doctors")

            # Load medicines
            self.medicines_df = pd.read_csv(settings.medicines_csv)
            print(f"✓ Loaded {len(self.medicines_df)} medicines")

        except Exception as e:
            print(f"Error loading data: {e}")
            raise

    # ==================== HOSPITAL QUERIES ====================

    def search_hospitals(
        self,
        city: Optional[str] = None,
        area: Optional[str] = None,
        has_emergency: bool = False,
        has_icu_beds: bool = False,
        limit: int = 10
    ) -> List[Hospital]:
        """Search hospitals by criteria"""
        df = self.hospitals_df.copy()

        # Filter by city
        if city:
            df = df[df['CITY'].str.contains(city, case=False, na=False)]

        # Filter by area
        if area:
            df = df[df['AREA'].str.contains(area, case=False, na=False)]

        # Take top results
        df = df.head(limit)

        # Convert to Hospital objects
        hospitals = []
        for idx, row in df.iterrows():
            hospital = Hospital(
                id=idx,
                name=row.get('HOSPITAL NAME', ''),
                city=row.get('CITY', ''),
                area=row.get('AREA', ''),
                address=row.get('ADDRESS', ''),
                contact=row.get('CONTACT', ''),
                num_doctors=int(row.get('DOCTORS', 0)) if pd.notna(row.get('DOCTORS')) and str(row.get('DOCTORS')).isdigit() else 0,
                # Mock data - in production, this would come from provider systems
                total_beds=random.randint(20, 100),
                available_beds=random.randint(0, 20),
                icu_beds=random.randint(5, 30),
                available_icu_beds=random.randint(0, 5) if not has_icu_beds else random.randint(1, 5),
                has_emergency=True,
                has_cardiology=random.choice([True, False]),
                has_lab=True,
            )
            hospitals.append(hospital)

        return hospitals

    def get_hospital_by_id(self, hospital_id: int) -> Optional[Hospital]:
        """Get hospital by ID"""
        if hospital_id >= len(self.hospitals_df):
            return None

        row = self.hospitals_df.iloc[hospital_id]
        return Hospital(
            id=hospital_id,
            name=row.get('HOSPITAL NAME', ''),
            city=row.get('CITY', ''),
            area=row.get('AREA', ''),
            address=row.get('ADDRESS', ''),
            contact=row.get('CONTACT', ''),
            num_doctors=int(row.get('DOCTORS', 0)) if pd.notna(row.get('DOCTORS')) and str(row.get('DOCTORS')).isdigit() else 0,
        )

    # ==================== DOCTOR QUERIES ====================

    def search_doctors(
        self,
        city: Optional[str] = None,
        specialization: Optional[str] = None,
        gender: Optional[str] = None,
        max_fee: Optional[float] = None,
        min_satisfaction: Optional[float] = None,
        limit: int = 10
    ) -> List[Doctor]:
        """Search doctors by criteria"""
        df = self.doctors_df.copy()

        # Filter by city
        if city:
            df = df[df['City'].str.contains(city, case=False, na=False)]

        # Filter by specialization
        if specialization:
            df = df[df['Specialization'].str.contains(specialization, case=False, na=False)]

        # Filter by fee
        if max_fee:
            df = df[pd.to_numeric(df['Fee(PKR)'], errors='coerce') <= max_fee]

        # Filter by satisfaction
        if min_satisfaction:
            df = df[pd.to_numeric(df['Patient Satisfaction Rate(%age)'], errors='coerce') >= min_satisfaction]

        # Sort by satisfaction rate
        df = df.sort_values('Patient Satisfaction Rate(%age)', ascending=False)

        # Take top results
        df = df.head(limit)

        # Convert to Doctor objects
        doctors = []
        for idx, row in df.iterrows():
            # Infer gender from name (simple heuristic)
            name = row.get('Doctor Name', '')
            inferred_gender = self._infer_gender(name)

            # Apply gender filter if specified
            if gender and inferred_gender != gender.lower():
                continue

            doctor = Doctor(
                id=idx,
                name=name,
                city=row.get('City', ''),
                specialization=row.get('Specialization', ''),
                qualification=row.get('Doctor Qualification', ''),
                experience_years=float(row.get('Experience(Years)', 0)) if pd.notna(row.get('Experience(Years)')) else 0.0,
                total_reviews=int(row.get('Total_Reviews', 0)) if pd.notna(row.get('Total_Reviews')) else 0,
                satisfaction_rate=float(row.get('Patient Satisfaction Rate(%age)', 0)) if pd.notna(row.get('Patient Satisfaction Rate(%age)')) else 0.0,
                avg_time_per_patient=int(row.get('Avg Time to Patients(mins)', 15)) if pd.notna(row.get('Avg Time to Patients(mins)')) else 15,
                wait_time=int(row.get('Wait Time(mins)', 10)) if pd.notna(row.get('Wait Time(mins)')) else 10,
                hospital_address=row.get('Hospital Address', ''),
                fee=float(row.get('Fee(PKR)', 0)) if pd.notna(row.get('Fee(PKR)')) else 0.0,
                gender=inferred_gender,
            )
            doctors.append(doctor)

        return doctors

    def _infer_gender(self, name: str) -> str:
        """Infer gender from doctor name (simple heuristic)"""
        name_lower = name.lower()

        # Common female indicators in Pakistani names
        female_indicators = ['dr.', 'prof.', 'asst.', 'assoc.']
        female_names = ['fatima', 'ayesha', 'khadija', 'zainab', 'maryam', 'sana', 'hina', 'nadia', 'faiza', 'rabia']

        for fname in female_names:
            if fname in name_lower:
                return 'female'

        # Check for common male names
        male_names = ['ahmed', 'ali', 'muhammad', 'usman', 'hassan', 'hussain', 'bilal', 'imran', 'tariq', 'shahid']
        for mname in male_names:
            if mname in name_lower:
                return 'male'

        # Default to male if uncertain (can be improved)
        return 'male'

    def get_doctor_by_id(self, doctor_id: int) -> Optional[Doctor]:
        """Get doctor by ID"""
        if doctor_id >= len(self.doctors_df):
            return None

        row = self.doctors_df.iloc[doctor_id]
        return Doctor(
            id=doctor_id,
            name=row.get('Doctor Name', ''),
            city=row.get('City', ''),
            specialization=row.get('Specialization', ''),
            qualification=row.get('Doctor Qualification', ''),
            fee=float(row.get('Fee(PKR)', 0)) if pd.notna(row.get('Fee(PKR)')) else 0.0,
        )

    # ==================== MEDICINE QUERIES ====================

    def search_medicines(
        self,
        name: Optional[str] = None,
        max_price: Optional[float] = None,
        limit: int = 10
    ) -> List[Medicine]:
        """Search medicines by name"""
        df = self.medicines_df.copy()

        # Filter by name
        if name:
            df = df[df['name'].str.contains(name, case=False, na=False)]

        # Filter by price
        if max_price:
            df = df[pd.to_numeric(df['sale_price'], errors='coerce') <= max_price]

        # Sort by price
        df = df.sort_values('sale_price', ascending=True)

        # Take top results
        df = df.head(limit)

        # Convert to Medicine objects
        medicines = []
        for idx, row in df.iterrows():
            medicine = Medicine(
                id=idx,
                name=row.get('name', ''),
                company=row.get('company', ''),
                pack_size=row.get('pack_size', ''),
                link=row.get('link', ''),
                sale_price=float(row.get('sale_price', 0)) if pd.notna(row.get('sale_price')) else 0.0,
                mrp=float(row.get('mrp', 0)) if pd.notna(row.get('mrp')) else 0.0,
                letter=row.get('letter', ''),
                stock_available=random.randint(0, 100),
            )
            medicines.append(medicine)

        return medicines

    # ==================== APPOINTMENT MANAGEMENT ====================

    def create_appointment(self, appointment: Appointment) -> Appointment:
        """Create a new appointment"""
        import uuid
        appointment.id = str(uuid.uuid4())
        self.appointments[appointment.id] = appointment
        return appointment

    def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        """Get appointment by ID"""
        return self.appointments.get(appointment_id)

    def update_appointment_status(self, appointment_id: str, status: str) -> bool:
        """Update appointment status"""
        if appointment_id in self.appointments:
            self.appointments[appointment_id].status = status
            return True
        return False

    # ==================== EMERGENCY MANAGEMENT ====================

    def create_emergency_case(self, case: EmergencyCase) -> EmergencyCase:
        """Create emergency case"""
        import uuid
        case.id = str(uuid.uuid4())
        self.emergency_cases[case.id] = case
        return case

    def get_emergency_case(self, case_id: str) -> Optional[EmergencyCase]:
        """Get emergency case by ID"""
        return self.emergency_cases.get(case_id)

    def update_emergency_case(self, case_id: str, **updates) -> bool:
        """Update emergency case"""
        if case_id in self.emergency_cases:
            case = self.emergency_cases[case_id]
            for key, value in updates.items():
                if hasattr(case, key):
                    setattr(case, key, value)
            return True
        return False


# Global database manager instance
db_manager = DatabaseManager()


def get_db_manager() -> DatabaseManager:
    """Get database manager instance"""
    return db_manager
