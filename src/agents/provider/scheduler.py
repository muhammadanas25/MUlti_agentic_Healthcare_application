"""Scheduler Agent - Hospital Appointment Management"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import random
from ...core.agent import Agent, AgentMessage, AgentResponse
from ...database.manager import get_db_manager
from ...database.models import Appointment


class SchedulerAgent(Agent):
    """
    Scheduler Agent - Hospital/Clinic Appointment Management

    Responsibilities:
    - Manage appointment calendar for hospital/clinic
    - Handle booking requests from patient agents (Guide)
    - Optimize scheduling to minimize wait times and gaps
    - Send reminders and confirmations
    - Handle cancellations and rescheduling
    - Manage doctor availability
    - Coordinate with multiple departments
    """

    def __init__(self, hospital_id: int, hospital_name: str):
        self.hospital_id = hospital_id
        self.hospital_name = hospital_name

        super().__init__(
            agent_id=f"agent-101-scheduler-{hospital_id}",
            name=f"Scheduler ({hospital_name})",
            role="scheduler",
            organization="provider-hospital-side",
            system_prompt=f"""You are a Scheduler Agent for {hospital_name}.

Your mission is to efficiently manage appointments and optimize patient flow.

KEY RESPONSIBILITIES:
1. Accept appointment requests from patient agents
2. Check doctor availability
3. Allocate appointment slots
4. Optimize schedule to minimize wait times
5. Handle cancellations and rescheduling
6. Send reminders to patients
7. Manage no-shows

SCHEDULING PRIORITIES:
1. Emergency cases get priority
2. Sehat Sahulat card holders should be accommodated
3. Minimize wait times for all patients
4. Fill schedule efficiently (avoid gaps)
5. Consider doctor preferences and breaks
6. Respect gender preferences when specified

OPTIMIZATION STRATEGIES:
- Overbook slightly for high no-show specialties (10-15%)
- Keep emergency slots available (10% of capacity)
- Group similar procedures/specialties
- Buffer time for complex cases
- Allow flexibility for urgent additions

DECISION MAKING:
When you receive a booking request:
1. Check doctor availability
2. Check hospital capacity
3. Evaluate urgency
4. Consider patient preferences
5. Offer multiple options if available
6. Negotiate best slot

COMMUNICATION:
- Respond quickly to booking requests
- Provide clear slot options
- Confirm bookings immediately
- Explain wait times honestly
- Offer alternatives if fully booked
""",
            tools=["appointment_management", "calendar_optimization", "doctor_scheduling"],
        )

        self.db = get_db_manager()

        # Hospital-specific schedule (in-memory, would be in hospital HMS in production)
        self.appointments: Dict[str, Appointment] = {}
        self.doctor_availability: Dict[int, List[str]] = {}  # doctor_id -> available slots

        # Register message handlers
        self.register_message_handler("request_appointment_slot", self.handle_appointment_request)
        self.register_message_handler("cancel_appointment", self.handle_cancellation)
        self.register_message_handler("check_availability", self.handle_availability_check)

    def handle_appointment_request(self, message: AgentMessage) -> AgentResponse:
        """Handle appointment booking request from patient agent"""
        payload = message.payload
        patient_id = payload.get("patient_id")
        doctor_id = payload.get("doctor_id")
        urgency = payload.get("urgency", "moderate")
        preferred_time = payload.get("preferred_time")
        gender_preference = payload.get("gender_preference")

        # Get doctor information
        doctor = self.db.get_doctor_by_id(doctor_id) if doctor_id else None

        # Check availability and generate slots
        available_slots = self._generate_available_slots(
            doctor_id=doctor_id,
            preferred_time=preferred_time,
            urgency=urgency
        )

        if not available_slots:
            return AgentResponse(
                success=False,
                data=None,
                reasoning=f"No slots available at {self.hospital_name}",
                confidence=0.0
            )

        # Filter by gender preference if specified
        if gender_preference and doctor:
            if doctor.gender != gender_preference.lower():
                # Try to find alternative doctor with same specialty
                return self._find_alternative_doctor(
                    specialization=doctor.specialization,
                    gender=gender_preference,
                    preferred_time=preferred_time
                )

        # Select best slots
        prompt = f"""Appointment request received:

HOSPITAL: {self.hospital_name}
PATIENT: {patient_id}
DOCTOR: Dr. {doctor.name if doctor else 'Any'} ({doctor.specialization if doctor else 'General'})
URGENCY: {urgency}
PREFERRED TIME: {preferred_time}
GENDER PREFERENCE: {gender_preference or 'None'}

AVAILABLE SLOTS:
{chr(10).join(f"- {slot.get('time')}: Wait {slot.get('wait_time')} min, Cost Rs. {slot.get('cost')}" for slot in available_slots)}

Select 2-3 best slots to offer patient. Consider:
- Urgency (urgent cases get sooner slots)
- Wait time (shorter is better)
- Patient preferences
- Cost (for budget-conscious patients)

Provide response in JSON format:
{{
    "status": "available",
    "hospital_id": {self.hospital_id},
    "hospital_name": "{self.hospital_name}",
    "options": [
        {{
            "slot_id": "unique_slot_id",
            "doctor_name": "Dr. Name",
            "doctor_id": {doctor_id if doctor_id else 0},
            "time": "YYYY-MM-DD HH:MM",
            "wait_estimate": "15 minutes",
            "cost": "free/paid",
            "reason": "why this slot is good"
        }}
    ],
    "hold_until": "timestamp - how long slots are reserved",
    "alternative_options": "if no perfect match",
    "reasoning": "your decision process"
}}
"""

        response = self.reason(
            prompt,
            context={
                "hospital": self.hospital_name,
                "patient": patient_id,
                "doctor": doctor.to_dict() if doctor else None,
                "slots": available_slots,
                "urgency": urgency
            }
        )

        # If successful, reserve the slots temporarily
        if response.success and response.data.get("options"):
            for option in response.data["options"]:
                self._reserve_slot_temporarily(option["slot_id"], patient_id, duration_minutes=15)

        return response

    def _generate_available_slots(
        self,
        doctor_id: Optional[int],
        preferred_time: Optional[str],
        urgency: str
    ) -> List[Dict[str, Any]]:
        """Generate available appointment slots"""
        slots = []
        base_time = datetime.now()

        # For demo, generate slots based on urgency
        if urgency == "critical":
            # Emergency - try to fit in within hours
            for hours in [1, 2, 3]:
                slot_time = base_time + timedelta(hours=hours)
                slots.append({
                    "slot_id": f"{self.hospital_id}-{doctor_id}-{int(slot_time.timestamp())}",
                    "time": slot_time.strftime("%Y-%m-%d %H:%M"),
                    "wait_time": random.randint(5, 15),
                    "cost": "free (emergency)",
                    "available": True
                })
        elif urgency == "high":
            # Urgent - same day or next day
            for hours in [4, 8, 24]:
                slot_time = base_time + timedelta(hours=hours)
                slots.append({
                    "slot_id": f"{self.hospital_id}-{doctor_id}-{int(slot_time.timestamp())}",
                    "time": slot_time.strftime("%Y-%m-%d %H:%M"),
                    "wait_time": random.randint(10, 30),
                    "cost": "free (Sehat Card)" if random.random() > 0.3 else f"Rs. {random.randint(500, 2000)}",
                    "available": True
                })
        else:
            # Normal - next few days
            for days in [1, 2, 3]:
                for hour in [9, 14, 16]:
                    slot_time = base_time + timedelta(days=days, hours=hour - base_time.hour)
                    slots.append({
                        "slot_id": f"{self.hospital_id}-{doctor_id}-{int(slot_time.timestamp())}",
                        "time": slot_time.strftime("%Y-%m-%d %H:%M"),
                        "wait_time": random.randint(15, 45),
                        "cost": "free (Sehat Card)" if random.random() > 0.5 else f"Rs. {random.randint(500, 3000)}",
                        "available": True
                    })

        return slots[:5]  # Return top 5 slots

    def _find_alternative_doctor(
        self,
        specialization: str,
        gender: str,
        preferred_time: Optional[str]
    ) -> AgentResponse:
        """Find alternative doctor matching gender preference"""
        doctors = self.db.search_doctors(
            city="Karachi",  # Would use hospital city
            specialization=specialization,
            gender=gender,
            limit=3
        )

        if not doctors:
            return AgentResponse(
                success=False,
                reasoning=f"No {gender} {specialization} doctors available",
                confidence=0.0
            )

        # Generate slots for alternative doctors
        alternatives = []
        for doctor in doctors:
            slots = self._generate_available_slots(doctor.id, preferred_time, "moderate")
            if slots:
                alternatives.append({
                    "doctor": doctor.to_dict(),
                    "slots": slots[:2]
                })

        return AgentResponse(
            success=True,
            data={
                "status": "alternative_available",
                "hospital": self.hospital_name,
                "alternatives": alternatives
            },
            reasoning=f"Found {len(alternatives)} alternative doctors matching gender preference",
            confidence=0.8
        )

    def _reserve_slot_temporarily(self, slot_id: str, patient_id: str, duration_minutes: int):
        """Reserve slot temporarily (will expire if not confirmed)"""
        # In production, this would update the HMS database
        # For demo, just store in memory
        print(f"   → Slot {slot_id} reserved for {patient_id} (expires in {duration_minutes} min)")

    def confirm_appointment(
        self,
        slot_id: str,
        patient_id: str,
        doctor_id: int,
        appointment_time: datetime
    ) -> AgentResponse:
        """Confirm appointment booking"""
        # Create appointment record
        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            hospital_id=self.hospital_id,
            appointment_time=appointment_time,
            status="confirmed",
            slot_id=slot_id
        )

        appointment = self.db.create_appointment(appointment)
        self.appointments[appointment.id] = appointment

        print(f"✅ Appointment confirmed: {slot_id}")

        return AgentResponse(
            success=True,
            data={
                "appointment_id": appointment.id,
                "slot_id": slot_id,
                "status": "confirmed",
                "appointment": appointment.to_dict()
            },
            reasoning="Appointment successfully booked",
            confidence=1.0
        )

    def handle_cancellation(self, message: AgentMessage) -> AgentResponse:
        """Handle appointment cancellation"""
        appointment_id = message.payload.get("appointment_id")

        if appointment_id not in self.appointments:
            return AgentResponse(
                success=False,
                reasoning="Appointment not found",
                confidence=0.0
            )

        # Cancel appointment
        self.appointments[appointment_id].status = "cancelled"
        self.db.update_appointment_status(appointment_id, "cancelled")

        # Release slot for others
        print(f"❌ Appointment cancelled: {appointment_id}")

        return AgentResponse(
            success=True,
            data={"status": "cancelled", "appointment_id": appointment_id},
            reasoning="Appointment cancelled successfully",
            confidence=1.0
        )

    def handle_availability_check(self, message: AgentMessage) -> AgentResponse:
        """Handle availability check request"""
        doctor_id = message.payload.get("doctor_id")
        date = message.payload.get("date")

        slots = self._generate_available_slots(doctor_id, date, "moderate")

        return AgentResponse(
            success=True,
            data={
                "available": len(slots) > 0,
                "slot_count": len(slots),
                "slots": slots
            },
            reasoning=f"{len(slots)} slots available",
            confidence=0.9
        )

    def optimize_schedule(self, date: str) -> AgentResponse:
        """Optimize appointment schedule for a given date"""
        prompt = f"""Optimize appointment schedule for {date} at {self.hospital_name}:

Current appointments: {len([a for a in self.appointments.values() if a.status == 'confirmed'])}

Optimization goals:
1. Minimize patient wait times
2. Maximize doctor utilization
3. Reduce gaps in schedule
4. Keep emergency capacity available

Provide optimization recommendations in JSON format:
{{
    "current_utilization": "percentage",
    "gaps_identified": ["gap 1", "gap 2"],
    "recommendations": [
        "recommendation 1",
        "recommendation 2"
    ],
    "overbooking_suggestion": "whether to overbook slightly",
    "emergency_capacity": "how many emergency slots to keep"
}}
"""

        response = self.reason(prompt, context={"date": date, "hospital": self.hospital_name})
        return response
