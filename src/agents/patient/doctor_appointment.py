"""
Doctor Appointment Agent

Intelligent doctor search and appointment booking:
- Schedule-based availability (Day + Timing)
- Specialization and city filtering
- Rating and experience-based recommendations
- Appointment booking and management
- Integration with Doctor Availability Service
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ...core.agent import Agent, AgentMessage, AgentResponse
from ...core.logger import get_agent_logger, LogLevel, LogCategory
from ...core.context_store import get_context_store, ContextStore
from ...services.doctor_availability import (
    DoctorAvailabilityService,
    get_doctor_availability_service,
    DoctorInfo
)
from ...services.a2a_messaging import (
    get_a2a_messaging_service,
    A2AMessage
)


class AppointmentState(Enum):
    """States in the appointment conversation"""
    INITIAL = "initial"
    SEARCHING_DOCTORS = "searching_doctors"
    SHOWING_RESULTS = "showing_results"
    SELECTING_DOCTOR = "selecting_doctor"
    SELECTING_SLOT = "selecting_slot"
    CONFIRMING_APPOINTMENT = "confirming_appointment"
    COMPLETED = "completed"


@dataclass
class AppointmentSession:
    """Tracks appointment conversation state"""
    phone_number: str
    patient_name: str = ""
    patient_id: str = ""
    state: AppointmentState = AppointmentState.INITIAL

    # Search criteria
    city: str = ""
    specialization: str = ""
    preferred_day: str = ""
    max_fee: Optional[float] = None

    # Selected doctor and slot
    selected_doctor_id: Optional[int] = None
    selected_doctor_name: str = ""
    selected_date: str = ""
    selected_time: str = ""

    # Search results cache
    search_results: List[Dict] = field(default_factory=list)
    available_slots: List[str] = field(default_factory=list)
    showing_other_cities: bool = False  # Track if showing doctors from other cities

    # Booking info
    appointment_id: Optional[str] = None
    reason: str = ""

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class DoctorAppointmentAgent(Agent):
    """
    Doctor Appointment Agent

    Features:
    - Intelligent doctor search by specialty, city, availability
    - Schedule-aware booking (respects doctor's working days/hours)
    - Patient-friendly interface with recommendations
    - Appointment management (book, cancel, reschedule)
    - Integration with Dr. Sameer for medical context
    """

    def __init__(self):
        super().__init__(
            agent_id="agent-003-doctor-appointment",
            name="Doctor Appointment Agent",
            role="appointment",
            organization="sehat-saathi-patient-side",
            system_prompt=self._get_system_prompt(),
            tools=["search_doctors", "check_availability", "book_appointment", "cancel_appointment"],
        )

        # Initialize services
        self.doctor_service = get_doctor_availability_service()
        self.messaging_service = get_a2a_messaging_service()
        self.logger = get_agent_logger()
        self.context_store = get_context_store()

        # Patient sessions
        self.sessions: Dict[str, AppointmentSession] = {}

        # Register with A2A messaging
        self.messaging_service.register_agent(
            agent_id=self.agent_id,
            agent_name=self.name,
            agent_type="doctor_appointment",
            capabilities=["search_doctors", "book_appointment", "check_availability"],
            handler=self._handle_a2a_message
        )

        # Register message handlers
        self.register_message_handler("search_doctors", self.handle_search_doctors)
        self.register_message_handler("book_appointment", self.handle_book_appointment)
        self.register_message_handler("cancel_appointment", self.handle_cancel_appointment)
        self.register_message_handler("handoff_from_dr_sameer", self.handle_dr_sameer_handoff)

        # Cache available specializations and cities for LLM context
        self._available_specializations = self.doctor_service.get_specializations()
        self._available_cities = self.doctor_service.get_cities()

        # Initialize Gemini for intelligent extraction
        import google.generativeai as genai
        from ...core.config import settings
        genai.configure(api_key=settings.gemini_api_key)
        self._extraction_model = genai.GenerativeModel(settings.gemini_model)

        print(f"Doctor Appointment Agent initialized with {len(self.doctor_service.doctors)} doctors")

    def _get_system_prompt(self) -> str:
        return """You are the Doctor Appointment Agent for Sehat Saathi, Pakistan's healthcare system.

YOUR MISSION:
Help patients find the right doctor and book appointments based on their needs.

KEY RESPONSIBILITIES:
1. Search doctors by specialization, city, availability
2. Show doctor ratings, experience, and fees
3. Check real-time availability based on schedules
4. Book appointments for specific dates/times
5. Manage appointment cancellations and rescheduling
6. Provide recommendations based on patient needs

SEARCH INTELLIGENCE:
- Match common terms to specializations (heart -> Cardiologist)
- Consider patient's budget (max fee)
- Prioritize highly-rated doctors
- Show availability for the requested day/time
- Suggest alternatives if preferred doctor is busy

BOOKING PROCESS:
1. Identify specialization needed
2. Determine city/location
3. Show available doctors with ratings
4. Let patient select doctor
5. Show available slots for selected doctor
6. Confirm appointment with all details

PAKISTAN CONTEXT:
- Many patients prefer female doctors for women's health
- Budget is important - show fees clearly
- Language: Mix of English and simple Urdu
- Sehat Card coverage matters for affordability
- Senior/experienced doctors often preferred

COMMUNICATION STYLE:
- Be helpful and patient-friendly
- Explain doctor credentials simply
- Show wait times and fees clearly
- Confirm all details before booking
- Provide hospital address for navigation
"""

    def get_or_create_session(self, phone_number: str) -> AppointmentSession:
        """Get existing session or create new one"""
        if phone_number not in self.sessions:
            self.sessions[phone_number] = AppointmentSession(phone_number=phone_number)
        return self.sessions[phone_number]

    def clear_session(self, phone_number: str):
        """Clear session after conversation ends"""
        if phone_number in self.sessions:
            del self.sessions[phone_number]

    # ==================== Main Processing ====================

    def process_message(
        self,
        phone_number: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """Main entry point for appointment agent messages"""
        session = self.get_or_create_session(phone_number)

        # Log user input
        self.logger.log_user_input(
            session_id=phone_number,
            message=message,
            agent_name=self.name
        )

        # Update context if provided
        if context:
            if "patient_name" in context:
                session.patient_name = context["patient_name"]
            if "patient_id" in context:
                session.patient_id = context["patient_id"]
            if "specialization" in context:
                session.specialization = context["specialization"]
            if "city" in context:
                session.city = context["city"]
            if "reason" in context:
                session.reason = context["reason"]

        # Process based on state
        return self._process_by_state(session, message)

    def _process_by_state(self, session: AppointmentSession, message: str) -> AgentResponse:
        """Process message based on current state"""
        handlers = {
            AppointmentState.INITIAL: self._handle_initial,
            AppointmentState.SEARCHING_DOCTORS: self._handle_searching,
            AppointmentState.SHOWING_RESULTS: self._handle_results_followup,
            AppointmentState.SELECTING_DOCTOR: self._handle_doctor_selection,
            AppointmentState.SELECTING_SLOT: self._handle_slot_selection,
            AppointmentState.CONFIRMING_APPOINTMENT: self._handle_confirmation,
        }

        handler = handlers.get(session.state, self._handle_initial)
        return handler(session, message)

    def _extract_search_criteria_with_llm(self, message: str) -> Dict[str, Any]:
        """Use LLM to intelligently extract search criteria from user message"""
        # Get major cities first (sort by frequency in doctor data)
        major_cities = ["KARACHI", "LAHORE", "ISLAMABAD", "RAWALPINDI", "FAISALABAD", "MULTAN", "PESHAWAR", "QUETTA", "HYDERABAD", "GUJRANWALA"]
        other_cities = [c for c in self._available_cities if c not in major_cities]

        prompt = f"""Extract doctor search criteria from the following user message.
The user is looking for a doctor in Pakistan.

User message: "{message}"

Available specializations in our database:
{', '.join(self._available_specializations[:50])}

Major cities: {', '.join(major_cities)}
Other cities: {', '.join(other_cities[:20])}

Instructions:
1. Identify the medical specialization the user needs. Understand Urdu/Roman Urdu terms:
   - "sans/saans" (breathing) -> Pulmonologist or Chest Specialist
   - "dil" (heart) -> Cardiologist
   - "jild" (skin) -> Dermatologist
   - "pet/maida" (stomach) -> Gastroenterologist
   - "haddi" (bone) -> Orthopedic
   - "bachay/bacha" (children) -> Pediatrician
   - "ankh" (eye) -> Ophthalmologist
   - "daant" (teeth) -> Dentist
   - "dimagh" (brain) -> Neurologist
   - "gurda" (kidney) -> Nephrologist
   - "sugar/cheeni" (diabetes) -> Diabetologist
   - "peshab" (urine) -> Urologist
   - "kaan/naak/gala" (ear/nose/throat) -> ENT Specialist
2. Identify the city - match to available cities (case insensitive). Common Pakistani cities: Karachi, Lahore, Islamabad, etc.
3. Identify preferred day if mentioned

Return ONLY a JSON object (no markdown, no explanation):
{{"specialization": "exact match from list or null", "city": "UPPERCASE CITY or null", "day": "Day or null"}}"""

        try:
            response = self._extraction_model.generate_content(prompt)
            result_text = response.text.strip()

            # Clean up response - extract JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            import json
            extracted = json.loads(result_text)

            # Validate specialization against available ones (fuzzy match)
            if extracted.get("specialization"):
                spec = extracted["specialization"]
                # Check if it's in available specializations (case-insensitive partial match)
                matched_spec = None
                for available_spec in self._available_specializations:
                    if spec.lower() in available_spec.lower() or available_spec.lower() in spec.lower():
                        matched_spec = available_spec
                        break
                extracted["specialization"] = matched_spec

            # Validate city
            if extracted.get("city"):
                city = extracted["city"].upper()
                if city not in self._available_cities:
                    # Try partial match
                    for available_city in self._available_cities:
                        if city in available_city or available_city in city:
                            extracted["city"] = available_city
                            break
                    else:
                        extracted["city"] = None
                else:
                    extracted["city"] = city

            return extracted

        except Exception as e:
            self.logger.log_error(
                session_id="extraction",
                agent_name=self.name,
                error=f"LLM extraction failed: {e}",
                category=LogCategory.AGENT
            )
            return {"specialization": None, "city": None, "day": None}

    def _handle_initial(self, session: AppointmentSession, message: str) -> AgentResponse:
        """Handle initial message - identify search criteria using LLM"""

        # Use LLM to extract search criteria
        extracted = self._extract_search_criteria_with_llm(message)

        specialization = extracted.get("specialization")
        city = extracted.get("city")
        preferred_day = extracted.get("day")

        # Handle day extraction (fallback if LLM didn't extract)
        message_lower = message.lower()
        if not preferred_day:
            if "today" in message_lower:
                preferred_day = datetime.now().strftime("%A")
            elif "tomorrow" in message_lower:
                preferred_day = (datetime.now() + timedelta(days=1)).strftime("%A")

        # Update session
        if specialization:
            session.specialization = specialization
        if city:
            session.city = city
        if preferred_day:
            session.preferred_day = preferred_day

        # If we have enough to search
        if session.specialization:
            session.state = AppointmentState.SEARCHING_DOCTORS
            return self._search_and_present_doctors(session)

        # Need more information
        return self._ask_for_search_criteria(session)

    def _ask_for_search_criteria(self, session: AppointmentSession) -> AgentResponse:
        """Ask user for search criteria"""
        # Get available specializations
        specs = self.doctor_service.get_specializations()[:15]  # Top 15
        cities = self.doctor_service.get_cities()[:10]  # Top 10

        patient_message = """*Doctor Appointment Booking - Sehat Saathi*

I'll help you find and book a doctor!

*Please tell me:*
1. What type of doctor do you need?
2. Which city?

*Available Specializations:*
""" + ", ".join(specs[:10]) + """

*Available Cities:*
""" + ", ".join(cities[:5]) + """

*Examples:*
- "Find cardiologist in Karachi"
- "Skin doctor in Lahore for tomorrow"
- "Dermatologist available on Monday"

_Aap ko kaisa doctor chahiye aur kis sheher mein?_"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "need_search_criteria",
                "patient_message": patient_message,
                "available_specializations": specs,
                "available_cities": cities,
                "state": session.state.value
            },
            reasoning="Asking for search criteria",
            confidence=0.9
        )

    def _handle_searching(self, session: AppointmentSession, message: str) -> AgentResponse:
        """Handle additional search input"""
        message_lower = message.lower()

        # Try to extract missing city
        if not session.city:
            cities = self.doctor_service.get_cities()
            for c in cities:
                if c.lower() in message_lower:
                    session.city = c
                    break

        # Try to extract specialization if still missing
        if not session.specialization:
            for keyword, spec in self.specialization_aliases.items():
                if keyword in message_lower:
                    session.specialization = spec
                    break

        if session.specialization:
            return self._search_and_present_doctors(session)
        else:
            return self._ask_for_search_criteria(session)

    def _search_and_present_doctors(self, session: AppointmentSession) -> AgentResponse:
        """Search for doctors and present results"""
        self.logger.log_reasoning(
            session_id=session.phone_number,
            agent_name=self.name,
            thought=f"Searching doctors: {session.specialization} in {session.city or 'all cities'}",
            category=LogCategory.ROUTING
        )

        # Search doctors with exact city match first
        results = self.doctor_service.search_doctors(
            city=session.city,
            specialization=session.specialization,
            day=session.preferred_day,
            max_fee=session.max_fee,
            limit=10
        )

        # Track if we're showing results from other cities
        showing_other_cities = False

        if not results and session.city:
            # No results in specified city - inform user and show alternatives
            showing_other_cities = True
            results = self.doctor_service.search_doctors(
                specialization=session.specialization,
                limit=10
            )

        if not results:
            patient_message = f"""*No Doctors Found*

Sorry, no {session.specialization} doctors found{f' in {session.city}' if session.city else ''}.

*Try:*
- Different city
- Different specialization
- Different day

_Maafi, doctor nahi mile. Doosri city ya din try karein._"""

            return AgentResponse(
                success=False,
                data={
                    "response_type": "no_results",
                    "patient_message": patient_message
                },
                reasoning="No doctors found matching criteria",
                confidence=0.7
            )

        # Cache results
        session.search_results = results
        session.state = AppointmentState.SHOWING_RESULTS
        session.showing_other_cities = showing_other_cities

        # Format results - adjust header based on whether showing other cities
        if showing_other_cities:
            lines = [f"*No {session.specialization} in {session.city}*"]
            lines.append(f"_Showing {session.specialization} doctors from other cities:_\n")
        else:
            lines = [f"*{session.specialization} Doctors" + (f" in {session.city}" if session.city else "") + "*\n"]

        for i, doc in enumerate(results[:5], 1):
            lines.append(f"*{i}. {doc['name']}*")
            # Show city prominently when showing other cities
            if showing_other_cities:
                lines.append(f"   🏙️ *{doc['city']}*")
            address = doc['hospital_address'] if doc['hospital_address'] and doc['hospital_address'] != 'No Address Available' else doc['city']
            lines.append(f"   📍 {address[:50]}{'...' if len(address) > 50 else ''}")
            lines.append(f"   ⭐ {doc['satisfaction_rate']}% ({doc['total_reviews']} reviews)")
            lines.append(f"   📅 {doc['schedule']['day']} {doc['schedule']['timing']}")
            lines.append(f"   💰 Rs. {int(doc['fee'])}")
            lines.append(f"   🎓 {doc['experience_years']} years experience")
            lines.append("")

        lines.append("---")
        lines.append("*Reply with doctor number (1-5) to see available slots*")
        lines.append("*Or type 'more' to see more options*")
        lines.append("")
        lines.append("_Doctor ka number likhein appointment ke liye_")

        self.logger.log_agent_output(
            session_id=session.phone_number,
            agent_name=self.name,
            message=f"Found {len(results)} doctors",
            response_type="doctor_results"
        )

        # Set context store: awaiting doctor selection (1-5)
        num_results = min(len(results), 5)
        valid_inputs = [str(i) for i in range(1, num_results + 1)] + ["more"]
        self.context_store.set_agent_state(
            phone_number=session.phone_number,
            agent_type="doctor_appointment",
            agent_name=self.name,
            state=session.state.value,
            awaiting_input=True,
            awaiting_input_type="selection",
            valid_inputs=valid_inputs,
            context_data={
                "search_results_count": len(results),
                "specialization": session.specialization,
                "city": session.city
            }
        )

        return AgentResponse(
            success=True,
            data={
                "response_type": "doctor_results",
                "results": results[:5],
                "total_found": len(results),
                "patient_message": "\n".join(lines),
                "state": session.state.value
            },
            reasoning=f"Found {len(results)} doctors matching criteria",
            confidence=0.85
        )

    def _handle_results_followup(self, session: AppointmentSession, message: str) -> AgentResponse:
        """Handle followup after showing results"""
        message_lower = message.lower().strip()

        # Check for doctor selection (1-5)
        try:
            selection = int(message)
            if 1 <= selection <= len(session.search_results):
                selected = session.search_results[selection - 1]
                session.selected_doctor_id = selected['id']
                session.selected_doctor_name = selected['name']
                session.state = AppointmentState.SELECTING_SLOT

                return self._show_available_slots(session, selected)
        except ValueError:
            pass

        # Check for 'more' request
        if "more" in message_lower:
            if len(session.search_results) > 5:
                return self._show_more_doctors(session)
            else:
                return AgentResponse(
                    success=True,
                    data={
                        "response_type": "no_more_results",
                        "patient_message": "No more doctors available. Please select from the list (1-5).\n\n_List mein se select karein_"
                    },
                    reasoning="No more doctors to show",
                    confidence=0.8
                )

        # Invalid response
        return AgentResponse(
            success=True,
            data={
                "response_type": "invalid_selection",
                "patient_message": "Please reply with a number (1-5) to select a doctor.\n\n_Doctor ka number likhein_"
            },
            reasoning="Invalid selection",
            confidence=0.7
        )

    def _show_more_doctors(self, session: AppointmentSession) -> AgentResponse:
        """Show more doctors from search results"""
        remaining = session.search_results[5:10]

        if not remaining:
            return AgentResponse(
                success=True,
                data={
                    "response_type": "no_more",
                    "patient_message": "No more doctors available."
                },
                reasoning="No more doctors",
                confidence=0.9
            )

        lines = ["*More Doctors:*\n"]

        for i, doc in enumerate(remaining, 6):
            lines.append(f"*{i}. {doc['name']}*")
            # Show city if we're showing doctors from other cities
            if session.showing_other_cities:
                lines.append(f"   🏙️ *{doc['city']}*")
            address = doc['hospital_address'] if doc['hospital_address'] and doc['hospital_address'] != 'No Address Available' else doc['city']
            lines.append(f"   📍 {address[:40]}{'...' if len(address) > 40 else ''}")
            lines.append(f"   ⭐ {doc['satisfaction_rate']}%")
            lines.append(f"   📅 {doc['schedule']['day']} | Rs. {int(doc['fee'])}")
            lines.append("")

        lines.append("_Number likhein appointment ke liye_")

        return AgentResponse(
            success=True,
            data={
                "response_type": "more_results",
                "patient_message": "\n".join(lines)
            },
            reasoning="Showing more doctors",
            confidence=0.85
        )

    def _show_available_slots(self, session: AppointmentSession, doctor: Dict) -> AgentResponse:
        """Show available slots for selected doctor"""
        # Find next available date
        next_available = self.doctor_service.get_next_available_slot(doctor['id'])

        if not next_available.get("available_slots"):
            return AgentResponse(
                success=True,
                data={
                    "response_type": "no_slots",
                    "patient_message": f"*{doctor['name']}* has no available slots in the next 4 weeks.\n\nPlease select another doctor."
                },
                reasoning="No slots available",
                confidence=0.7
            )

        session.selected_date = next_available['next_date']
        session.available_slots = next_available['available_slots']

        lines = [f"*Appointment with {doctor['name']}*\n"]
        lines.append(f"📅 *Next Available:* {next_available['day']}, {next_available['next_date']}")
        lines.append(f"📍 {next_available['hospital'][:60]}")
        lines.append(f"💰 Fee: Rs. {int(next_available['fee'])}")
        lines.append("")
        lines.append("*Available Time Slots:*")

        slots = next_available['available_slots'][:8]  # Show up to 8 slots
        for i, slot in enumerate(slots, 1):
            lines.append(f"   {i}. {slot}")

        session.available_slots = slots
        lines.append("")
        lines.append("---")
        lines.append("*Reply with slot number (1-8) to book*")
        lines.append("*Or 'different day' for other dates*")
        lines.append("")
        lines.append("_Waqt ka number likhein booking ke liye_")

        # Set context store: awaiting slot selection
        valid_inputs = [str(i) for i in range(1, len(slots) + 1)] + ["different", "other"]
        self.context_store.set_agent_state(
            phone_number=session.phone_number,
            agent_type="doctor_appointment",
            agent_name=self.name,
            state=session.state.value,
            awaiting_input=True,
            awaiting_input_type="slot_selection",
            valid_inputs=valid_inputs,
            context_data={
                "doctor_id": session.selected_doctor_id,
                "doctor_name": session.selected_doctor_name,
                "date": session.selected_date,
                "slots": slots
            }
        )

        return AgentResponse(
            success=True,
            data={
                "response_type": "available_slots",
                "doctor": doctor,
                "date": next_available['next_date'],
                "slots": slots,
                "patient_message": "\n".join(lines),
                "state": session.state.value
            },
            reasoning=f"Showing {len(slots)} available slots",
            confidence=0.9
        )

    def _handle_doctor_selection(self, session: AppointmentSession, message: str) -> AgentResponse:
        """Handle doctor selection"""
        return self._handle_results_followup(session, message)

    def _handle_slot_selection(self, session: AppointmentSession, message: str) -> AgentResponse:
        """Handle time slot selection"""
        message_lower = message.lower().strip()

        # Check for different day request
        if "different" in message_lower or "other" in message_lower:
            return self._show_other_dates(session)

        # Check for slot selection
        try:
            selection = int(message)
            if 1 <= selection <= len(session.available_slots):
                session.selected_time = session.available_slots[selection - 1]
                session.state = AppointmentState.CONFIRMING_APPOINTMENT

                return self._confirm_appointment_request(session)
        except ValueError:
            pass

        return AgentResponse(
            success=True,
            data={
                "response_type": "invalid_slot",
                "patient_message": f"Please select a time slot (1-{len(session.available_slots)}).\n\n_Sahi number likhein_"
            },
            reasoning="Invalid slot selection",
            confidence=0.7
        )

    def _show_other_dates(self, session: AppointmentSession) -> AgentResponse:
        """Show other available dates"""
        # Get schedule for next 4 weeks
        schedule = self.doctor_service.get_doctor_schedule_view(
            session.selected_doctor_id,
            weeks=4
        )

        available_dates = []
        for date_str, info in schedule.get("schedule", {}).items():
            if info["working"] and info["available"] > 0:
                available_dates.append({
                    "date": date_str,
                    "day": info["day"],
                    "slots": info["available"]
                })

        if not available_dates:
            return AgentResponse(
                success=True,
                data={
                    "response_type": "no_dates",
                    "patient_message": "No other dates available in the next 4 weeks. Please select another doctor."
                },
                reasoning="No other dates available",
                confidence=0.7
            )

        lines = ["*Other Available Dates:*\n"]
        for i, d in enumerate(available_dates[:5], 1):
            lines.append(f"{i}. {d['day']} {d['date']} ({d['slots']} slots)")

        lines.append("")
        lines.append("_Reply with number to select date_")

        return AgentResponse(
            success=True,
            data={
                "response_type": "other_dates",
                "dates": available_dates[:5],
                "patient_message": "\n".join(lines)
            },
            reasoning="Showing other available dates",
            confidence=0.85
        )

    def _confirm_appointment_request(self, session: AppointmentSession) -> AgentResponse:
        """Ask for appointment confirmation"""
        patient_message = f"""*Confirm Appointment*

*Doctor:* {session.selected_doctor_name}
*Date:* {session.selected_date}
*Time:* {session.selected_time}

Please provide your name for the appointment:
(Or reply 'confirm' if name already provided)

_Apna naam likhein ya 'confirm' likhein_"""

        valid_inputs = ["yes", "no", "confirm", "cancel", "haan", "nahi", "ji", "na"]

        # If we already have patient name, ask for confirmation directly
        if session.patient_name:
            patient_message = f"""*Confirm Appointment*

*Doctor:* {session.selected_doctor_name}
*Date:* {session.selected_date}
*Time:* {session.selected_time}
*Patient:* {session.patient_name}

Reply *'yes'* to confirm or *'no'* to cancel

_'yes' ya 'no' likhein_"""
        else:
            # Awaiting patient name - any input is valid
            valid_inputs = []  # Accept any input as name

        # Set context store: awaiting confirmation
        self.context_store.set_agent_state(
            phone_number=session.phone_number,
            agent_type="doctor_appointment",
            agent_name=self.name,
            state=session.state.value,
            awaiting_input=True,
            awaiting_input_type="confirmation" if session.patient_name else "patient_name",
            valid_inputs=valid_inputs,
            context_data={
                "doctor_id": session.selected_doctor_id,
                "doctor_name": session.selected_doctor_name,
                "date": session.selected_date,
                "time": session.selected_time
            }
        )

        return AgentResponse(
            success=True,
            data={
                "response_type": "confirm_appointment",
                "patient_message": patient_message,
                "state": session.state.value
            },
            reasoning="Asking for confirmation",
            confidence=0.9
        )

    def _handle_confirmation(self, session: AppointmentSession, message: str) -> AgentResponse:
        """Handle appointment confirmation"""
        message_lower = message.lower().strip()

        # If we don't have patient name, treat message as name
        if not session.patient_name and message_lower not in ["yes", "no", "confirm", "cancel", "haan", "nahi"]:
            session.patient_name = message.strip()
            return self._confirm_appointment_request(session)

        if message_lower in ["yes", "confirm", "haan", "ji"]:
            # Book the appointment
            result = self.doctor_service.book_appointment(
                doctor_id=session.selected_doctor_id,
                patient_id=session.patient_id or session.phone_number,
                patient_name=session.patient_name or "Patient",
                patient_phone=session.phone_number,
                appointment_date=session.selected_date,
                appointment_time=session.selected_time,
                reason=session.reason
            )

            if result["success"]:
                session.appointment_id = result["appointment"]["appointment_id"]
                session.state = AppointmentState.COMPLETED

                patient_message = f"""*Appointment Confirmed!*

*Appointment ID:* {session.appointment_id}
*Doctor:* {session.selected_doctor_name}
*Date:* {session.selected_date}
*Time:* {session.selected_time}
*Hospital:* {result['hospital'][:60]}
*Fee:* Rs. {int(result['fee'])}

*Instructions:*
1. Arrive 15 minutes early
2. Bring your CNIC
3. Bring previous medical records if any

📞 *Emergency:* 1122

_Yeh appointment details save kar lein_"""

                # Clear context store - conversation completed
                self.context_store.clear_agent_state(session.phone_number)

                # Publish event
                self.messaging_service.publish_event(
                    from_agent_id=self.agent_id,
                    event_type="appointment_booked",
                    event_data={
                        "appointment_id": session.appointment_id,
                        "doctor_id": session.selected_doctor_id,
                        "date": session.selected_date,
                        "time": session.selected_time
                    }
                )

                self.logger.log_agent_output(
                    session_id=session.phone_number,
                    agent_name=self.name,
                    message=f"Appointment confirmed: {session.appointment_id}",
                    response_type="appointment_confirmed"
                )

                return AgentResponse(
                    success=True,
                    data={
                        "response_type": "appointment_confirmed",
                        "appointment_id": session.appointment_id,
                        "appointment": result["appointment"],
                        "patient_message": patient_message,
                        "state": session.state.value
                    },
                    reasoning="Appointment booked successfully",
                    confidence=1.0
                )
            else:
                return AgentResponse(
                    success=False,
                    data={
                        "response_type": "booking_failed",
                        "error": result.get("error"),
                        "patient_message": f"Booking failed: {result.get('error')}\n\nPlease try a different time slot."
                    },
                    reasoning=f"Booking failed: {result.get('error')}",
                    confidence=0.5
                )

        elif message_lower in ["no", "cancel", "nahi", "na"]:
            session.state = AppointmentState.INITIAL
            # Clear context store - user cancelled
            self.context_store.clear_agent_state(session.phone_number)
            return AgentResponse(
                success=True,
                data={
                    "response_type": "cancelled",
                    "patient_message": "Appointment cancelled. Let me know if you want to search again.\n\n_Kuch aur chahiye?_"
                },
                reasoning="User cancelled",
                confidence=0.9
            )

        return AgentResponse(
            success=True,
            data={
                "response_type": "invalid_response",
                "patient_message": "Please reply 'yes' to confirm or 'no' to cancel.\n\n_'yes' ya 'no' likhein_"
            },
            reasoning="Invalid confirmation response",
            confidence=0.7
        )

    # ==================== Handler Methods ====================

    def handle_search_doctors(self, message: AgentMessage) -> AgentResponse:
        """Handle doctor search request"""
        payload = message.payload
        return self.process_message(
            phone_number=payload.get("phone", "unknown"),
            message=payload.get("message", ""),
            context=payload.get("context")
        )

    def handle_book_appointment(self, message: AgentMessage) -> AgentResponse:
        """Handle direct booking request"""
        payload = message.payload

        result = self.doctor_service.book_appointment(
            doctor_id=payload.get("doctor_id"),
            patient_id=payload.get("patient_id"),
            patient_name=payload.get("patient_name", "Patient"),
            patient_phone=payload.get("phone"),
            appointment_date=payload.get("date"),
            appointment_time=payload.get("time"),
            reason=payload.get("reason", "")
        )

        return AgentResponse(
            success=result.get("success", False),
            data=result,
            reasoning=result.get("message", ""),
            confidence=1.0 if result.get("success") else 0.5
        )

    def handle_cancel_appointment(self, message: AgentMessage) -> AgentResponse:
        """Handle appointment cancellation"""
        payload = message.payload
        appointment_id = payload.get("appointment_id")
        reason = payload.get("reason", "User requested cancellation")

        result = self.doctor_service.cancel_appointment(appointment_id, reason)

        return AgentResponse(
            success=result.get("success", False),
            data=result,
            reasoning=result.get("message", ""),
            confidence=1.0 if result.get("success") else 0.5
        )

    def handle_dr_sameer_handoff(self, message: AgentMessage) -> AgentResponse:
        """Handle handoff from Dr. Sameer with medical context"""
        payload = message.payload
        phone = payload.get("phone", "unknown")
        context = payload.get("context", {})

        self.logger.log_handoff(
            session_id=phone,
            from_agent="Dr. Sameer",
            to_agent="Doctor Appointment Agent",
            reason=f"Doctor referral - Specialty: {context.get('recommended_specialty')}",
            context=context
        )

        session = self.get_or_create_session(phone)
        session.specialization = context.get("recommended_specialty", "")
        session.reason = context.get("symptoms", "")

        if session.specialization:
            session.state = AppointmentState.SEARCHING_DOCTORS
            return self._search_and_present_doctors(session)

        return self._ask_for_search_criteria(session)

    def _handle_a2a_message(self, message: A2AMessage) -> Dict[str, Any]:
        """Handle incoming A2A messages"""
        action = message.action

        if action == "search_doctors":
            return self._handle_a2a_search(message.payload)
        elif action == "check_availability":
            return self._handle_a2a_availability(message.payload)

        return {"status": "unhandled", "action": action}

    def _handle_a2a_search(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle A2A doctor search"""
        results = self.doctor_service.search_doctors(
            city=payload.get("city"),
            specialization=payload.get("specialization"),
            day=payload.get("day"),
            limit=5
        )
        return {"results": results}

    def _handle_a2a_availability(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle A2A availability check"""
        availability = self.doctor_service.get_doctor_availability(
            payload.get("doctor_id"),
            payload.get("date")
        )
        return availability

    # ==================== Patient Appointment Methods ====================

    def get_patient_appointments(self, phone_number: str) -> List[Dict]:
        """Get all appointments for a patient"""
        return self.doctor_service.get_patient_appointments(phone_number)
