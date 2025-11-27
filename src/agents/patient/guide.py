"""
Guide - Navigation & Appointment Booking Agent

A sophisticated navigation agent that:
- Helps patients find nearby hospitals/clinics using location-aware search
- Resolves location from text, coordinates, or WhatsApp location shares
- Shows distance-sorted results with Google Maps links
- Handles handoffs from Dr. Sameer with medical context
- Books appointments with doctors
- Comprehensive logging for debugging and UI display
"""
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ...core.agent import Agent, AgentMessage, AgentResponse
from ...core.logger import get_agent_logger, LogLevel, LogCategory
from ...tools.hospital_search import HospitalSearchTool, HospitalResult, get_hospital_search
from ...tools.location_resolver import LocationResolver, ResolvedLocation, get_location_resolver
from ...database.manager import get_db_manager
from ...database.models import Appointment


class GuideState(Enum):
    """States in the Guide conversation"""
    INITIAL = "initial"
    AWAITING_LOCATION = "awaiting_location"
    SHOWING_RESULTS = "showing_results"
    AWAITING_SELECTION = "awaiting_selection"
    BOOKING_APPOINTMENT = "booking_appointment"
    PROVIDING_DIRECTIONS = "providing_directions"
    COMPLETED = "completed"


@dataclass
class GuideSession:
    """Tracks Guide conversation state"""
    phone_number: str
    state: GuideState = GuideState.INITIAL
    search_context: Dict[str, Any] = field(default_factory=dict)  # From Dr. Sameer handoff
    resolved_location: Optional[ResolvedLocation] = None
    search_results: List[HospitalResult] = field(default_factory=list)
    selected_hospital: Optional[HospitalResult] = None
    specialty_needed: Optional[str] = None
    urgency: str = "MODERATE"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class GuideAgent(Agent):
    """
    Guide - Navigation & Appointment Booking Agent

    Features:
    - Location-aware hospital search with haversine distance
    - Capability inference (emergency, ICU, cardiac, etc.)
    - WhatsApp location share support
    - Integration with Dr. Sameer's care plans
    - Google Maps navigation links
    """

    def __init__(self):
        super().__init__(
            agent_id="agent-002-guide",
            name="Guide",
            role="navigation",
            organization="sehat-saathi-patient-side",
            system_prompt=self._get_system_prompt(),
            tools=["search_hospitals", "resolve_location", "get_directions", "book_appointment"],
        )

        # Initialize tools
        self.hospital_search = get_hospital_search()
        self.location_resolver = get_location_resolver()
        self.db = get_db_manager()
        self.logger = get_agent_logger()

        # Patient sessions
        self.sessions: Dict[str, GuideSession] = {}

        # Register message handlers
        self.register_message_handler("find_hospital", self.handle_find_hospital)
        self.register_message_handler("book_appointment", self.handle_book_appointment)
        self.register_message_handler("handoff_from_dr_sameer", self.handle_dr_sameer_handoff)

        print(f"✓ Guide Agent initialized with location-aware hospital search")

    def _get_system_prompt(self) -> str:
        return """You are Guide, a navigation and appointment specialist for Sehat Saathi.

YOUR MISSION:
Help patients find the nearest and most suitable healthcare facilities quickly.

KEY RESPONSIBILITIES:
1. Find appropriate hospitals based on patient location and needs
2. Show distance-sorted results with directions
3. Book appointments with doctors
4. Provide clear navigation guidance
5. Handle emergency routing with priority

DECISION FACTORS FOR HOSPITAL SELECTION:
1. Distance from patient (minimize travel)
2. Required specialty/capability
3. Emergency services availability
4. Doctor availability
5. Hospital tier (teaching > general > clinic)

PAKISTAN CONTEXT:
- Many patients rely on rickshaws or public transport
- Distance is crucial for low-income families
- Sehat Sahulat Card coverage matters
- Provide directions in simple Urdu/English

COMMUNICATION STYLE:
- Be warm and reassuring
- Provide step-by-step directions
- Always include emergency numbers for urgent cases
- Offer alternatives if first choice isn't available
- Use landmarks people recognize

Remember: Quick access to healthcare saves lives. Your job is to minimize the time between "I need help" and "patient arrives at hospital"."""

    def get_or_create_session(self, phone_number: str) -> GuideSession:
        """Get existing session or create new one"""
        if phone_number not in self.sessions:
            self.sessions[phone_number] = GuideSession(phone_number=phone_number)
        return self.sessions[phone_number]

    def clear_session(self, phone_number: str):
        """Clear session after conversation ends"""
        if phone_number in self.sessions:
            del self.sessions[phone_number]

    def process_message(
        self,
        phone_number: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        location_coords: Optional[Tuple[float, float]] = None
    ) -> AgentResponse:
        """
        Main entry point for Guide agent messages.

        Args:
            phone_number: User's phone number
            message: User's message
            context: Context from Dr. Sameer handoff (optional)
            location_coords: Direct coordinates from WhatsApp location share (optional)
        """
        session = self.get_or_create_session(phone_number)

        # Log user input
        self.logger.log_user_input(
            session_id=phone_number,
            message=message,
            agent_name="Guide"
        )

        self.logger.log_reasoning(
            session_id=phone_number,
            agent_name="Guide",
            thought=f"Processing message in state: {session.state.value}",
            category=LogCategory.ROUTING,
            data={"state": session.state.value, "has_context": bool(context), "has_coords": bool(location_coords)}
        )

        # Update context if provided (from Dr. Sameer handoff)
        if context:
            session.search_context = context
            session.specialty_needed = context.get("recommended_specialty")
            session.urgency = context.get("urgency", "MODERATE")
            session.state = GuideState.AWAITING_LOCATION
            self.logger.log_reasoning(
                session_id=phone_number,
                agent_name="Guide",
                thought=f"Received handoff context. Specialty: {session.specialty_needed}, Urgency: {session.urgency}",
                category=LogCategory.HANDOFF
            )

        # Handle direct location coordinates
        if location_coords:
            lat, long = location_coords
            self.logger.log_reasoning(
                session_id=phone_number,
                agent_name="Guide",
                thought=f"Direct WhatsApp coordinates received: ({lat:.4f}, {long:.4f})",
                category=LogCategory.LOCATION
            )
            session.resolved_location = self.location_resolver.resolve(
                message, lat=lat, long=long, session_id=phone_number
            )
            return self._search_hospitals(session)

        # Process based on state
        return self._process_by_state(session, message)

    def _process_by_state(self, session: GuideSession, message: str) -> AgentResponse:
        """Process message based on current conversation state"""

        handlers = {
            GuideState.INITIAL: self._handle_initial,
            GuideState.AWAITING_LOCATION: self._handle_location_input,
            GuideState.SHOWING_RESULTS: self._handle_results_followup,
            GuideState.AWAITING_SELECTION: self._handle_selection,
            GuideState.PROVIDING_DIRECTIONS: self._handle_directions_request,
        }

        handler = handlers.get(session.state, self._handle_initial)
        return handler(session, message)

    def _handle_initial(self, session: GuideSession, message: str) -> AgentResponse:
        """Handle initial message - ask for location or search intent"""
        session.state = GuideState.AWAITING_LOCATION

        # Check if message contains location info
        resolved = self.location_resolver.resolve(message)
        if resolved.confidence in ["high", "medium"]:
            session.resolved_location = resolved
            return self._search_hospitals(session)

        # Need to ask for location
        patient_message = """🏥 *Hospital Search - Sehat Saathi*

I'll help you find hospitals near you!

*Please share your location:*

📍 *Option 1:* Share WhatsApp location
   (Tap + → Location → Share Live Location)

📍 *Option 2:* Type your area and city
   Example: "Gulistan-e-Jauhar, Karachi"
   Example: "DHA Phase 5, Lahore"
   Example: "F-8, Islamabad"

_Aap ka area batayein taake qareeb ke hospital dhund sakein_"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "awaiting_location",
                "state": session.state.value,
                "patient_message": patient_message
            },
            reasoning="Asked user for location to search hospitals",
            confidence=0.9
        )

    def _handle_location_input(self, session: GuideSession, message: str) -> AgentResponse:
        """Handle location input from user"""
        # Try to resolve the location
        self.logger.log_reasoning(
            session_id=session.phone_number,
            agent_name="Guide",
            thought=f"Attempting to resolve location from text: '{message}'",
            category=LogCategory.LOCATION
        )

        resolved = self.location_resolver.resolve(message, session_id=session.phone_number)

        if resolved.confidence == "none":
            # Couldn't resolve, ask again
            self.logger.log_reasoning(
                session_id=session.phone_number,
                agent_name="Guide",
                thought=f"Location resolution failed. Asking user for clarification.",
                category=LogCategory.LOCATION,
                data={"input": message, "confidence": "none"}
            )

            patient_message = f"""I couldn't find that location.

Please try:
1. Share your WhatsApp location (most accurate)
2. Type your area with city name
   Example: "Gulistan-e-Jauhar, Karachi"

{resolved.clarification_needed or ''}"""

            return AgentResponse(
                success=True,
                data={
                    "response_type": "location_not_found",
                    "patient_message": patient_message
                },
                reasoning="Could not resolve location, asking for clarification",
                confidence=0.5
            )

        # Location resolved
        session.resolved_location = resolved
        self.logger.log_reasoning(
            session_id=session.phone_number,
            agent_name="Guide",
            thought=f"Location resolved: {resolved.area or resolved.city} (confidence: {resolved.confidence})",
            category=LogCategory.LOCATION,
            data={"lat": resolved.lat, "long": resolved.long, "city": resolved.city, "source": resolved.source}
        )

        # If low confidence, confirm with user but proceed
        if resolved.confidence == "low":
            return self._search_hospitals(session, confirm_location=True)

        return self._search_hospitals(session)

    def _search_hospitals(
        self,
        session: GuideSession,
        confirm_location: bool = False
    ) -> AgentResponse:
        """Search for hospitals based on session context"""
        location = session.resolved_location

        if not location or not location.lat:
            return self._handle_initial(session, "")

        # Determine search parameters
        specialty = session.specialty_needed
        max_distance = 10.0 if session.urgency in ["CRITICAL", "HIGH"] else 15.0
        requires_emergency = session.urgency == "CRITICAL"

        self.logger.log_reasoning(
            session_id=session.phone_number,
            agent_name="Guide",
            thought=f"Initiating hospital search. Urgency: {session.urgency}, Specialty: {specialty or 'General'}",
            category=LogCategory.HOSPITAL,
            data={
                "lat": location.lat,
                "long": location.long,
                "city": location.city,
                "max_distance": max_distance,
                "requires_emergency": requires_emergency
            }
        )

        # Search hospitals
        results = self.hospital_search.search(
            user_lat=location.lat,
            user_long=location.long,
            city=location.city,
            max_distance_km=max_distance,
            limit=5,
            specialty=specialty,
            requires_emergency=requires_emergency,
            session_id=session.phone_number
        )

        session.search_results = results
        session.state = GuideState.SHOWING_RESULTS

        # Build response
        if not results:
            # No hospitals found, try wider search
            self.logger.log_reasoning(
                session_id=session.phone_number,
                agent_name="Guide",
                thought="No hospitals found in initial radius. Expanding search to 25km.",
                category=LogCategory.HOSPITAL
            )
            results = self.hospital_search.search(
                user_lat=location.lat,
                user_long=location.long,
                max_distance_km=25.0,  # Wider search
                limit=5,
                session_id=session.phone_number
            )
            session.search_results = results

        # Format results
        formatted_results = self._format_hospital_results(results, session)

        # Add location confirmation if needed
        location_note = ""
        if confirm_location:
            location_note = f"📍 _Searching near {location.city or 'your location'}_ (Confirm if this is correct)\n\n"

        # Add urgency note
        urgency_note = ""
        if session.urgency == "CRITICAL":
            urgency_note = "🚨 *EMERGENCY* - Showing hospitals with emergency services first.\n📞 *Call 1122 for ambulance*\n\n"
        elif session.urgency == "HIGH":
            urgency_note = "⚠️ *Urgent* - Please visit soon.\n\n"

        # Add specialty note
        specialty_note = ""
        if specialty:
            specialty_note = f"🔍 *Looking for:* {specialty}\n\n"

        patient_message = f"""{urgency_note}{specialty_note}{location_note}{formatted_results}

*Reply with:*
1️⃣ - 5️⃣  Get directions to hospital
📍 Send new location to search again
"book" - Book appointment"""

        # Log agent output
        self.logger.log_agent_output(
            session_id=session.phone_number,
            agent_name="Guide",
            message=f"Showing {len(results)} hospitals near {location.city or 'location'}",
            response_type="hospital_results"
        )

        return AgentResponse(
            success=True,
            data={
                "response_type": "hospital_results",
                "results": [r.to_dict() for r in results],
                "location": location.to_dict(),
                "specialty": specialty,
                "urgency": session.urgency,
                "patient_message": patient_message
            },
            reasoning=f"Found {len(results)} hospitals near {location.city or 'location'}",
            confidence=0.85
        )

    def _format_hospital_results(
        self,
        results: List[HospitalResult],
        session: GuideSession
    ) -> str:
        """Format hospital results for display"""
        if not results:
            return """❌ No hospitals found nearby.

Please try:
• Share a different location
• Search in a nearby city
• Call 1122 for emergency assistance"""

        lines = ["🏥 *Nearest Hospitals:*\n"]

        for i, hospital in enumerate(results[:5], 1):
            lines.append(f"*{i}. {hospital.name}*")

            # Location info
            if hospital.area:
                lines.append(f"   📍 {hospital.area}, {hospital.city}")
            else:
                lines.append(f"   📍 {hospital.city}")

            # Distance
            lines.append(f"   🚗 *{hospital.distance_km:.1f} km* door")

            # Contact
            if hospital.contact:
                lines.append(f"   📞 {hospital.contact}")

            # Capabilities badges
            caps = []
            if hospital.capabilities.get("emergency"):
                caps.append("🚨Emergency")
            if hospital.capabilities.get("icu"):
                caps.append("🏥ICU")
            if hospital.capabilities.get("cardiac"):
                caps.append("❤️Cardiac")
            if hospital.capabilities.get("pediatric"):
                caps.append("👶Pediatric")
            if hospital.capabilities.get("maternity"):
                caps.append("🤰Maternity")

            if caps:
                lines.append(f"   {' '.join(caps[:3])}")

            # Google Maps link
            if hospital.google_maps_link:
                lines.append(f"   🗺️ [Open in Maps]({hospital.google_maps_link})")

            lines.append("")

        # Add emergency info for urgent cases
        if session.urgency in ["CRITICAL", "HIGH"]:
            lines.append("📞 *Emergency Helpline: 1122*")
            lines.append("🚑 *Edhi Ambulance: 115*")

        return "\n".join(lines)

    def _handle_results_followup(self, session: GuideSession, message: str) -> AgentResponse:
        """Handle followup after showing results"""
        message_lower = message.lower().strip()

        # Check for hospital selection (1-5)
        if message in ["1", "2", "3", "4", "5"]:
            idx = int(message) - 1
            if idx < len(session.search_results):
                session.selected_hospital = session.search_results[idx]
                return self._provide_directions(session)

        # Check for booking request
        if any(word in message_lower for word in ["book", "appointment", "appoint"]):
            session.state = GuideState.BOOKING_APPOINTMENT
            return self._initiate_booking(session, message)

        # Check if it's a new location
        resolved = self.location_resolver.resolve(message)
        if resolved.confidence in ["high", "medium"]:
            session.resolved_location = resolved
            return self._search_hospitals(session)

        # Default: show options again
        return AgentResponse(
            success=True,
            data={
                "response_type": "options_reminder",
                "patient_message": """Please reply with:

1️⃣ - 5️⃣  Get directions to that hospital
📍 Share new location to search again
"book" - Book an appointment

_Aap ka jawab samajh nahi aaya. Dobara try karein._"""
            },
            reasoning="User response not understood, showing options",
            confidence=0.7
        )

    def _handle_selection(self, session: GuideSession, message: str) -> AgentResponse:
        """Handle hospital selection"""
        return self._handle_results_followup(session, message)

    def _provide_directions(self, session: GuideSession) -> AgentResponse:
        """Provide directions to selected hospital"""
        hospital = session.selected_hospital
        location = session.resolved_location

        if not hospital:
            return self._handle_initial(session, "")

        session.state = GuideState.PROVIDING_DIRECTIONS

        # Format directions
        lines = [
            f"🏥 *{hospital.name}*\n",
            f"📍 *Address:*",
            f"{hospital.address}\n",
        ]

        # Distance and contact
        lines.append(f"🚗 *Distance:* {hospital.distance_km:.1f} km")
        if hospital.contact:
            lines.append(f"📞 *Phone:* {hospital.contact}")

        lines.append("")

        # Navigation options
        lines.append("*🗺️ Navigation Options:*")

        if hospital.google_maps_link:
            lines.append(f"• [Open in Google Maps]({hospital.google_maps_link})")

        # Rickshaw/taxi instructions
        lines.append("")
        lines.append("*🚕 For Rickshaw/Taxi:*")
        lines.append(f'_"{hospital.name} le chalein, {hospital.area or hospital.city} mein hai"_')

        # Capabilities
        caps = []
        if hospital.capabilities.get("emergency"):
            caps.append("🚨 Emergency Available")
        if hospital.capabilities.get("icu"):
            caps.append("🏥 ICU Available")

        if caps:
            lines.append("")
            lines.append("*Available Services:*")
            for cap in caps:
                lines.append(f"  {cap}")

        lines.append("")
        lines.append("---")
        lines.append("📞 *Emergency: 1122*")
        lines.append("")
        lines.append("_Type 'search' to find more hospitals_")
        lines.append("_Type 'book' to book appointment_")

        return AgentResponse(
            success=True,
            data={
                "response_type": "directions",
                "hospital": hospital.to_dict(),
                "patient_message": "\n".join(lines)
            },
            reasoning=f"Provided directions to {hospital.name}",
            confidence=0.9
        )

    def _handle_directions_request(self, session: GuideSession, message: str) -> AgentResponse:
        """Handle follow-up after directions"""
        message_lower = message.lower()

        if "search" in message_lower or "find" in message_lower:
            session.state = GuideState.INITIAL
            return self._handle_initial(session, message)

        if "book" in message_lower:
            return self._initiate_booking(session, message)

        # Check if new location
        resolved = self.location_resolver.resolve(message)
        if resolved.confidence in ["high", "medium"]:
            session.resolved_location = resolved
            session.state = GuideState.AWAITING_LOCATION
            return self._search_hospitals(session)

        # Show selected hospital again
        return self._provide_directions(session)

    def _initiate_booking(self, session: GuideSession, message: str) -> AgentResponse:
        """Initiate appointment booking process"""
        hospital = session.selected_hospital

        if not hospital:
            # No hospital selected, ask to select first
            return AgentResponse(
                success=True,
                data={
                    "response_type": "select_hospital_first",
                    "patient_message": """Please select a hospital first by replying with 1-5.

Then I can help you book an appointment."""
                },
                reasoning="No hospital selected for booking",
                confidence=0.8
            )

        # For now, show contact info - full booking requires scheduler integration
        patient_message = f"""📅 *Book Appointment - {hospital.name}*

To book an appointment:

1️⃣ *Call directly:*
   📞 {hospital.contact or 'Contact not available'}

2️⃣ *Visit in person:*
   📍 {hospital.address}

*Working Hours:* Usually 9 AM - 5 PM
*Tip:* Go early morning for shorter wait times

---

_Full online booking coming soon!_
_For urgent cases, go directly to Emergency._"""

        session.state = GuideState.COMPLETED

        return AgentResponse(
            success=True,
            data={
                "response_type": "booking_info",
                "hospital": hospital.to_dict(),
                "patient_message": patient_message
            },
            reasoning="Provided booking information",
            confidence=0.85
        )

    # ==================== Handler Methods ====================

    def handle_find_hospital(self, message: AgentMessage) -> AgentResponse:
        """Handle find hospital request from other agents"""
        phone = message.payload.get("phone", "unknown")
        location_text = message.payload.get("location", "")
        specialty = message.payload.get("specialty")
        context = message.payload.get("context", {})

        session = self.get_or_create_session(phone)
        session.search_context = context
        session.specialty_needed = specialty

        return self.process_message(phone, location_text, context)

    def handle_book_appointment(self, message: AgentMessage) -> AgentResponse:
        """Handle appointment booking request"""
        return AgentResponse(
            success=True,
            data={"status": "booking_initiated"},
            reasoning="Booking request received",
            confidence=0.8,
        )

    def handle_dr_sameer_handoff(self, message: AgentMessage) -> AgentResponse:
        """Handle handoff from Dr. Sameer with medical context"""
        phone = message.payload.get("phone", "unknown")
        context = message.payload.get("context", {})

        # Log handoff
        self.logger.log_handoff(
            session_id=phone,
            from_agent="Dr. Sameer",
            to_agent="Guide",
            reason=f"Hospital referral - Specialty: {context.get('recommended_specialty')}, Urgency: {context.get('urgency')}",
            context=context
        )

        session = self.get_or_create_session(phone)
        session.search_context = context
        session.specialty_needed = context.get("recommended_specialty")
        session.urgency = context.get("urgency", "MODERATE")
        session.state = GuideState.AWAITING_LOCATION

        self.logger.log_reasoning(
            session_id=phone,
            agent_name="Guide",
            thought=f"Received handoff from Dr. Sameer. Setting up session for hospital search.",
            category=LogCategory.HANDOFF,
            data={"specialty": session.specialty_needed, "urgency": session.urgency}
        )

        # Return initial prompt
        specialty_text = f" *({session.specialty_needed})*" if session.specialty_needed else ""
        urgency_emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MODERATE": "📋", "LOW": "✅"}.get(session.urgency, "📋")

        patient_message = f"""{urgency_emoji} *Finding Hospital for You*{specialty_text}

Based on Dr. Sameer's assessment, I'll help you find the right hospital.

*Please share your location:*

📍 Share WhatsApp location (recommended)
   OR
📍 Type your area, e.g., "DHA Phase 5, Karachi"

_Jaldi se apna location batayein taake qareeb ka hospital dhund sakein_"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "handoff_received",
                "context": context,
                "patient_message": patient_message
            },
            reasoning=f"Received handoff from Dr. Sameer. Specialty: {session.specialty_needed}, Urgency: {session.urgency}",
            confidence=0.9
        )

    # ==================== Legacy Methods (backward compatibility) ====================

    def find_nearby_hospitals(
        self,
        patient_location: str,
        specialty: Optional[str] = None,
        max_distance_km: float = 10.0,
        patient_preferences: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """Legacy method - find nearby hospitals"""
        results, resolved = self.hospital_search.search_by_location_text(
            location_text=patient_location,
            specialty=specialty,
            max_distance_km=max_distance_km,
            requires_emergency=patient_preferences.get("needs_emergency", False) if patient_preferences else False
        )

        if not results:
            return AgentResponse(
                success=False,
                data=None,
                reasoning=f"No hospitals found near {patient_location}",
                confidence=0.0,
            )

        return AgentResponse(
            success=True,
            data={
                "hospitals": [r.to_dict() for r in results],
                "location": resolved.to_dict(),
                "patient_message": self.hospital_search.format_results_for_patient(results)
            },
            reasoning=f"Found {len(results)} hospitals",
            confidence=0.85
        )

    def find_doctors(
        self,
        city: str,
        specialization: str,
        patient_preferences: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """Find doctors based on specialty and preferences"""
        preferences = patient_preferences or {}

        doctors = self.db.search_doctors(
            city=city,
            specialization=specialization,
            gender=preferences.get('gender_preference'),
            max_fee=preferences.get('max_budget'),
            min_satisfaction=preferences.get('min_satisfaction', 90.0),
            limit=5
        )

        if not doctors:
            return AgentResponse(
                success=False,
                data=None,
                reasoning=f"No {specialization} doctors found in {city}",
                confidence=0.0,
            )

        return AgentResponse(
            success=True,
            data={
                "doctors": [d.to_dict() for d in doctors]
            },
            reasoning=f"Found {len(doctors)} doctors",
            confidence=0.85
        )

    def generate_directions(
        self,
        from_location: str,
        to_hospital: Dict[str, Any]
    ) -> AgentResponse:
        """Generate directions to hospital"""
        hospital_name = to_hospital.get('name', 'Hospital')
        address = to_hospital.get('address', '')

        prompt = f"""Generate simple directions from {from_location} to {hospital_name} at {address}.

Include:
1. Rickshaw/taxi instructions in Urdu
2. Key landmarks
3. Estimated travel time

Respond in JSON:
{{
    "taxi_instructions": "what to tell driver in Urdu",
    "landmarks": ["nearby landmarks"],
    "estimated_time": "travel time estimate",
    "patient_message": "friendly directions message"
}}"""

        return self.reason(prompt, context={"from": from_location, "to": to_hospital})
