"""
Hospital Booking Agent

Manages hospital resource bookings:
- Bed bookings (General, ICU, Emergency, etc.)
- Blood bank requests
- Equipment reservations (Ventilators, Dialysis, etc.)
- Coordinates with other hospitals via A2A messaging
- Provides dashboard data for hospital managers
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ...core.agent import Agent, AgentMessage, AgentResponse
from ...core.logger import get_agent_logger, LogLevel, LogCategory
from ...core.context_store import get_context_store, ContextStore
from ...services.hospital_resources import (
    HospitalResourceService,
    get_hospital_resource_service,
    ResourceType,
    BedType,
    BloodType,
    EquipmentType
)
from ...services.a2a_messaging import (
    A2AMessagingService,
    get_a2a_messaging_service,
    A2AMessage,
    MessageType,
    MessagePriority
)


class BookingState(Enum):
    """States in the booking conversation"""
    INITIAL = "initial"
    IDENTIFYING_NEED = "identifying_need"
    SELECTING_RESOURCE = "selecting_resource"
    CONFIRMING_BOOKING = "confirming_booking"
    SEARCHING_ALTERNATIVES = "searching_alternatives"
    COMPLETED = "completed"


@dataclass
class BookingSession:
    """Tracks booking conversation state"""
    phone_number: str
    patient_name: str = ""
    patient_id: str = ""
    state: BookingState = BookingState.INITIAL
    resource_type: str = ""  # bed, blood, equipment
    resource_subtype: str = ""  # icu, A+, ventilator
    hospital_id: Optional[int] = None
    hospital_name: str = ""
    quantity: int = 1
    urgency: str = "normal"  # normal, high, emergency
    booking_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class HospitalBookingAgent(Agent):
    """
    Hospital Booking Agent

    Features:
    - Intelligent resource booking
    - Multi-hospital search for availability
    - A2A coordination for resource sharing
    - Emergency prioritization
    - Dashboard data for hospital managers
    """

    def __init__(self, hospital_id: Optional[int] = None, hospital_name: str = "All Hospitals"):
        self.hospital_id = hospital_id
        self.hospital_name = hospital_name
        self.is_global = hospital_id is None  # True if handles all hospitals

        super().__init__(
            agent_id=f"agent-201-booking-{hospital_id or 'global'}",
            name=f"Hospital Booking Agent ({hospital_name})",
            role="hospital_booking",
            organization="sehat-saathi-provider",
            system_prompt=self._get_system_prompt(),
            tools=["book_bed", "book_blood", "book_equipment", "search_availability", "broadcast_query"],
        )

        # Initialize services
        self.resource_service = get_hospital_resource_service()
        self.messaging_service = get_a2a_messaging_service()
        self.logger = get_agent_logger()
        self.context_store = get_context_store()

        # Patient sessions
        self.sessions: Dict[str, BookingSession] = {}

        # Register with A2A messaging
        self.messaging_service.register_agent(
            agent_id=self.agent_id,
            agent_name=self.name,
            agent_type="hospital_booking",
            capabilities=["book_bed", "book_blood", "book_equipment", "check_availability"],
            handler=self._handle_a2a_message
        )

        # Register message handlers
        self.register_message_handler("book_resource", self.handle_book_resource)
        self.register_message_handler("check_availability", self.handle_check_availability)
        self.register_message_handler("cancel_booking", self.handle_cancel_booking)
        self.register_message_handler("emergency_booking", self.handle_emergency_booking)

        print(f"Hospital Booking Agent initialized for {hospital_name}")

    def _get_system_prompt(self) -> str:
        return f"""You are a Hospital Booking Agent for {self.hospital_name} in the Sehat Saathi system.

YOUR MISSION:
Help patients book hospital resources quickly and efficiently.

KEY RESPONSIBILITIES:
1. Book beds (General, ICU, Emergency, Pediatric, Maternity, Cardiac)
2. Request blood units from blood bank
3. Reserve equipment (Ventilators, Oxygen, Dialysis, etc.)
4. Search across hospitals if resource not available locally
5. Coordinate with other hospitals for resource sharing
6. Handle emergency bookings with priority

RESOURCE TYPES:
- BEDS: general, icu, emergency, pediatric, maternity, cardiac
- BLOOD: A+, A-, B+, B-, AB+, AB-, O+, O-
- EQUIPMENT: ventilator, oxygen_cylinder, dialysis, defibrillator, cardiac_monitor, xray, ct_scan, mri, ambulance

BOOKING PROCESS:
1. Identify resource need (type and subtype)
2. Check local availability
3. If not available, broadcast to nearby hospitals
4. Present options to patient
5. Confirm booking
6. Provide booking confirmation with details

COMMUNICATION STYLE:
- Be empathetic - patients booking resources are often stressed
- Be clear about availability and alternatives
- Provide estimated wait times
- Explain costs/coverage (Sehat Card, etc.)
- For emergencies, act fast and coordinate immediately

PAKISTAN CONTEXT:
- Blood shortages are common - always check multiple hospitals
- ICU beds are limited - be realistic about availability
- Many patients use Sehat Sahulat Card - check coverage
- Emergency cases get priority regardless of payment status
"""

    def get_or_create_session(self, phone_number: str) -> BookingSession:
        """Get existing session or create new one"""
        if phone_number not in self.sessions:
            self.sessions[phone_number] = BookingSession(phone_number=phone_number)
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
        """Main entry point for booking agent messages"""
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
            if "urgency" in context:
                session.urgency = context["urgency"]
            if "hospital_id" in context:
                session.hospital_id = context["hospital_id"]

        # Process based on state
        return self._process_by_state(session, message)

    def _process_by_state(self, session: BookingSession, message: str) -> AgentResponse:
        """Process message based on current state"""
        handlers = {
            BookingState.INITIAL: self._handle_initial,
            BookingState.IDENTIFYING_NEED: self._handle_identifying_need,
            BookingState.SELECTING_RESOURCE: self._handle_selecting_resource,
            BookingState.CONFIRMING_BOOKING: self._handle_confirming_booking,
        }

        handler = handlers.get(session.state, self._handle_initial)
        return handler(session, message)

    def _handle_initial(self, session: BookingSession, message: str) -> AgentResponse:
        """Handle initial message - identify booking need"""
        message_lower = message.lower()

        # Detect resource type from message
        resource_type = None
        resource_subtype = None

        # Check for bed keywords
        bed_keywords = {
            "icu": "icu", "intensive care": "icu",
            "emergency": "emergency", "emergency bed": "emergency",
            "bed": "general", "general ward": "general",
            "pediatric": "pediatric", "children": "pediatric",
            "maternity": "maternity", "delivery": "maternity", "pregnant": "maternity",
            "cardiac": "cardiac", "heart": "cardiac"
        }

        for keyword, bed_type in bed_keywords.items():
            if keyword in message_lower:
                resource_type = "bed"
                resource_subtype = bed_type
                break

        # Check for blood keywords
        blood_types = ["a+", "a-", "b+", "b-", "ab+", "ab-", "o+", "o-"]
        for bt in blood_types:
            if bt in message_lower or bt.replace("+", " positive").replace("-", " negative") in message_lower:
                resource_type = "blood"
                resource_subtype = bt.upper()
                break

        if "blood" in message_lower and not resource_type:
            resource_type = "blood"

        # Check for equipment keywords
        equipment_keywords = {
            "ventilator": "ventilator",
            "oxygen": "oxygen_cylinder",
            "dialysis": "dialysis",
            "ambulance": "ambulance",
            "xray": "xray", "x-ray": "xray",
            "ct scan": "ct_scan", "ct": "ct_scan",
            "mri": "mri"
        }

        for keyword, eq_type in equipment_keywords.items():
            if keyword in message_lower:
                resource_type = "equipment"
                resource_subtype = eq_type
                break

        if resource_type:
            session.resource_type = resource_type
            session.resource_subtype = resource_subtype or ""
            session.state = BookingState.IDENTIFYING_NEED

            if resource_subtype:
                # We know what they need, check availability
                return self._check_and_present_availability(session)
            else:
                # Need more details
                return self._ask_for_details(session)

        # Could not identify need, show options
        patient_message = """*Hospital Resource Booking - Sehat Saathi*

I can help you book:

*1. Beds*
   - General Ward
   - ICU (Intensive Care)
   - Emergency
   - Pediatric
   - Maternity
   - Cardiac

*2. Blood Bank*
   - All blood types (A+, A-, B+, B-, AB+, AB-, O+, O-)

*3. Medical Equipment*
   - Ventilator
   - Oxygen Cylinder
   - Dialysis Machine
   - Ambulance

Please tell me what you need, e.g.:
- "I need an ICU bed"
- "Need O+ blood urgently"
- "Book a ventilator"

_Aap ko kya chahiye? Batayen hum madad karein ge._"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "show_options",
                "patient_message": patient_message,
                "state": session.state.value
            },
            reasoning="Showing booking options to user",
            confidence=0.9
        )

    def _ask_for_details(self, session: BookingSession) -> AgentResponse:
        """Ask for more details about the resource needed"""
        if session.resource_type == "blood":
            patient_message = """*Blood Bank Request*

Please specify the blood type needed:
- A+ (A Positive)
- A- (A Negative)
- B+ (B Positive)
- B- (B Negative)
- AB+ (AB Positive)
- AB- (AB Negative)
- O+ (O Positive)
- O- (O Negative)

Also mention quantity (number of units) if known.

_Khoon ka group batayen aur kitne units chahiye._"""

        elif session.resource_type == "bed":
            patient_message = """*Bed Booking*

Please specify the type of bed needed:
1. General Ward - Regular care
2. ICU - Intensive Care Unit
3. Emergency - Urgent cases
4. Pediatric - Children
5. Maternity - Pregnancy/delivery
6. Cardiac - Heart patients

_Kis tarah ka bed chahiye? Number ya naam likhein._"""

        else:
            patient_message = """*Equipment Booking*

Please specify what equipment you need:
- Ventilator
- Oxygen Cylinder
- Dialysis Machine
- Ambulance

_Kaunsa equipment chahiye?_"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "need_details",
                "patient_message": patient_message,
                "state": session.state.value
            },
            reasoning="Asking for resource details",
            confidence=0.8
        )

    def _handle_identifying_need(self, session: BookingSession, message: str) -> AgentResponse:
        """Handle resource identification"""
        message_lower = message.lower()

        # Try to extract subtype
        if session.resource_type == "bed":
            bed_map = {
                "1": "general", "general": "general", "ward": "general",
                "2": "icu", "icu": "icu", "intensive": "icu",
                "3": "emergency", "emergency": "emergency",
                "4": "pediatric", "pediatric": "pediatric", "children": "pediatric",
                "5": "maternity", "maternity": "maternity", "delivery": "maternity",
                "6": "cardiac", "cardiac": "cardiac", "heart": "cardiac"
            }
            for key, value in bed_map.items():
                if key in message_lower:
                    session.resource_subtype = value
                    break

        elif session.resource_type == "blood":
            blood_types = {
                "a+": "A+", "a positive": "A+", "a-": "A-", "a negative": "A-",
                "b+": "B+", "b positive": "B+", "b-": "B-", "b negative": "B-",
                "ab+": "AB+", "ab positive": "AB+", "ab-": "AB-", "ab negative": "AB-",
                "o+": "O+", "o positive": "O+", "o-": "O-", "o negative": "O-"
            }
            for key, value in blood_types.items():
                if key in message_lower:
                    session.resource_subtype = value
                    break

        elif session.resource_type == "equipment":
            eq_map = {
                "ventilator": "ventilator",
                "oxygen": "oxygen_cylinder",
                "dialysis": "dialysis",
                "ambulance": "ambulance"
            }
            for key, value in eq_map.items():
                if key in message_lower:
                    session.resource_subtype = value
                    break

        if session.resource_subtype:
            return self._check_and_present_availability(session)
        else:
            return self._ask_for_details(session)

    def _check_and_present_availability(self, session: BookingSession) -> AgentResponse:
        """Check availability and present options"""
        self.logger.log_reasoning(
            session_id=session.phone_number,
            agent_name=self.name,
            thought=f"Checking availability for {session.resource_type}:{session.resource_subtype}",
            category=LogCategory.HOSPITAL
        )

        # Search for available resources
        results = self.resource_service.search_available_resources(
            resource_type=session.resource_type,
            resource_subtype=session.resource_subtype,
            city=None,  # Search all cities
            min_quantity=session.quantity
        )

        if not results:
            # Try A2A broadcast to find resources
            return self._broadcast_search(session)

        # Format results
        session.state = BookingState.SELECTING_RESOURCE

        lines = [f"*{session.resource_subtype.upper()} Availability*\n"]

        for i, result in enumerate(results[:5], 1):
            lines.append(f"*{i}. {result['hospital_name']}*")
            lines.append(f"   📍 {result['city']}")
            lines.append(f"   ✅ Available: {result['available']}")
            lines.append(f"   📊 Total: {result['total']}")
            lines.append("")

        lines.append("---")
        lines.append("*Reply with hospital number to book*")
        lines.append("Example: '1' to book at first hospital")
        lines.append("")
        lines.append("_Jis hospital mein book karna hai uska number likhein_")

        # Store results for selection
        session.available_hospitals = results[:5]

        # Set context store: awaiting hospital selection (1-5)
        num_results = min(len(results), 5)
        valid_inputs = [str(i) for i in range(1, num_results + 1)]
        self.context_store.set_agent_state(
            phone_number=session.phone_number,
            agent_type="hospital_booking",
            agent_name=self.name,
            state=session.state.value,
            awaiting_input=True,
            awaiting_input_type="selection",
            valid_inputs=valid_inputs,
            context_data={
                "resource_type": session.resource_type,
                "resource_subtype": session.resource_subtype,
                "available_count": len(results)
            }
        )

        return AgentResponse(
            success=True,
            data={
                "response_type": "availability_results",
                "results": results[:5],
                "patient_message": "\n".join(lines),
                "state": session.state.value
            },
            reasoning=f"Found {len(results)} hospitals with {session.resource_subtype}",
            confidence=0.85
        )

    def _handle_selecting_resource(self, session: BookingSession, message: str) -> AgentResponse:
        """Handle hospital selection"""
        try:
            selection = int(message.strip())
            if 1 <= selection <= len(getattr(session, 'available_hospitals', [])):
                selected = session.available_hospitals[selection - 1]
                session.hospital_id = selected['hospital_id']
                session.hospital_name = selected['hospital_name']
                session.state = BookingState.CONFIRMING_BOOKING

                return self._confirm_booking_request(session)
        except ValueError:
            pass

        return AgentResponse(
            success=True,
            data={
                "response_type": "invalid_selection",
                "patient_message": "Please reply with a valid number (1-5) to select a hospital.\n\n_Sahi number likhein_"
            },
            reasoning="Invalid hospital selection",
            confidence=0.7
        )

    def _confirm_booking_request(self, session: BookingSession) -> AgentResponse:
        """Ask for booking confirmation"""
        resource_label = session.resource_subtype.replace("_", " ").title()

        patient_message = f"""*Confirm Booking*

*Resource:* {resource_label}
*Hospital:* {session.hospital_name}
*Quantity:* {session.quantity}

Please confirm:
- Reply *'yes'* or *'confirm'* to book
- Reply *'no'* or *'cancel'* to cancel

_Kya aap booking confirm karte hain?_"""

        # Set context store: awaiting confirmation
        valid_inputs = ["yes", "no", "confirm", "cancel", "haan", "nahi", "ji", "na", "book"]
        self.context_store.set_agent_state(
            phone_number=session.phone_number,
            agent_type="hospital_booking",
            agent_name=self.name,
            state=session.state.value,
            awaiting_input=True,
            awaiting_input_type="confirmation",
            valid_inputs=valid_inputs,
            context_data={
                "hospital_id": session.hospital_id,
                "hospital_name": session.hospital_name,
                "resource_type": session.resource_type,
                "resource_subtype": session.resource_subtype
            }
        )

        return AgentResponse(
            success=True,
            data={
                "response_type": "confirm_booking",
                "patient_message": patient_message,
                "state": session.state.value
            },
            reasoning="Asking for booking confirmation",
            confidence=0.9
        )

    def _handle_confirming_booking(self, session: BookingSession, message: str) -> AgentResponse:
        """Handle booking confirmation"""
        message_lower = message.lower().strip()

        if message_lower in ["yes", "confirm", "haan", "ji", "book"]:
            # Create booking
            result = self.resource_service.create_booking(
                hospital_id=session.hospital_id,
                resource_type=session.resource_type,
                resource_subtype=session.resource_subtype,
                patient_id=session.patient_id or session.phone_number,
                patient_name=session.patient_name or "Patient",
                quantity=session.quantity,
                notes=f"Booked via Sehat Saathi. Urgency: {session.urgency}"
            )

            if result["success"]:
                session.booking_id = result["booking"]["booking_id"]
                session.state = BookingState.COMPLETED

                # Auto-confirm for demo
                self.resource_service.confirm_booking(session.booking_id)

                resource_label = session.resource_subtype.replace("_", " ").title()

                patient_message = f"""*Booking Confirmed!*

*Booking ID:* {session.booking_id}
*Resource:* {resource_label}
*Hospital:* {session.hospital_name}

*Next Steps:*
1. Visit the hospital with this booking ID
2. Go to the reception desk
3. Show your CNIC and booking ID

📞 *Emergency Helpline:* 1122

_Yeh booking ID save kar lein. Hospital mein dikhana hoga._"""

                # Clear context store - conversation completed
                self.context_store.clear_agent_state(session.phone_number)

                # Publish booking event via A2A
                self.messaging_service.publish_event(
                    from_agent_id=self.agent_id,
                    event_type="booking_created",
                    event_data={
                        "booking_id": session.booking_id,
                        "hospital_id": session.hospital_id,
                        "resource_type": session.resource_type,
                        "resource_subtype": session.resource_subtype
                    }
                )

                self.logger.log_agent_output(
                    session_id=session.phone_number,
                    agent_name=self.name,
                    message=f"Booking confirmed: {session.booking_id}",
                    response_type="booking_confirmed"
                )

                return AgentResponse(
                    success=True,
                    data={
                        "response_type": "booking_confirmed",
                        "booking_id": session.booking_id,
                        "patient_message": patient_message,
                        "state": session.state.value
                    },
                    reasoning="Booking confirmed successfully",
                    confidence=1.0
                )
            else:
                return AgentResponse(
                    success=False,
                    data={
                        "response_type": "booking_failed",
                        "error": result.get("error"),
                        "patient_message": f"Sorry, booking failed: {result.get('error')}\n\nPlease try again or select another hospital."
                    },
                    reasoning=f"Booking failed: {result.get('error')}",
                    confidence=0.5
                )

        elif message_lower in ["no", "cancel", "nahi", "na"]:
            session.state = BookingState.INITIAL
            # Clear context store - user cancelled
            self.context_store.clear_agent_state(session.phone_number)
            return AgentResponse(
                success=True,
                data={
                    "response_type": "booking_cancelled",
                    "patient_message": "Booking cancelled. Let me know if you need anything else.\n\n_Booking cancel ho gai. Kuch aur chahiye?_"
                },
                reasoning="User cancelled booking",
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

    def _broadcast_search(self, session: BookingSession) -> AgentResponse:
        """Broadcast search to other hospitals via A2A"""
        self.logger.log_reasoning(
            session_id=session.phone_number,
            agent_name=self.name,
            thought=f"Resource not found locally, broadcasting to other hospitals",
            category=LogCategory.ORCHESTRATION
        )

        # Use A2A messaging to broadcast query
        broadcast_result = self.messaging_service.broadcast_resource_query(
            from_agent_id=self.agent_id,
            resource_type=session.resource_type,
            resource_subtype=session.resource_subtype,
            quantity=session.quantity
        )

        if broadcast_result.successful_responses:
            # Found resources from other hospitals
            return self._present_broadcast_results(session, broadcast_result)
        else:
            patient_message = f"""*Resource Not Available*

Unfortunately, {session.resource_subtype.replace('_', ' ').title()} is not currently available at any hospital in our network.

*What you can do:*
1. Call hospital directly
2. Try again in a few hours
3. Contact emergency services if urgent

📞 *Emergency: 1122*
📞 *Edhi: 115*

_Yeh resource abhi available nahi hai. Emergency mein 1122 call karein._"""

            return AgentResponse(
                success=False,
                data={
                    "response_type": "resource_not_available",
                    "patient_message": patient_message
                },
                reasoning="Resource not available in network",
                confidence=0.9
            )

    def _present_broadcast_results(self, session: BookingSession, broadcast_result) -> AgentResponse:
        """Present results from A2A broadcast"""
        # This would process responses from other hospital agents
        patient_message = f"""*Searching Other Hospitals...*

We're coordinating with {broadcast_result.total_recipients} hospitals to find {session.resource_subtype}.

Please wait or call emergency services if urgent.

📞 *Emergency: 1122*"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "searching",
                "broadcast_id": broadcast_result.broadcast_id,
                "patient_message": patient_message
            },
            reasoning="Broadcasting resource query to network",
            confidence=0.7
        )

    # ==================== A2A Message Handling ====================

    def _handle_a2a_message(self, message: A2AMessage) -> Dict[str, Any]:
        """Handle incoming A2A messages"""
        action = message.action

        if action == "check_resource_availability":
            return self._handle_availability_query(message.payload)
        elif action == "emergency_alert":
            return self._handle_emergency_alert(message.payload)
        elif action == "negotiate_resource":
            return self._handle_resource_negotiation(message.payload)

        return {"status": "unhandled", "action": action}

    def _handle_availability_query(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle availability query from other agents"""
        resource_type = payload.get("resource_type")
        resource_subtype = payload.get("resource_subtype")
        quantity = payload.get("quantity", 1)

        if self.hospital_id:
            # Check specific hospital
            if resource_type == "bed":
                result = self.resource_service.get_bed_availability(self.hospital_id, resource_subtype)
            elif resource_type == "blood":
                result = self.resource_service.get_blood_availability(self.hospital_id, resource_subtype)
            elif resource_type == "equipment":
                result = self.resource_service.get_equipment_availability(self.hospital_id, resource_subtype)
            else:
                result = {"error": "Unknown resource type"}

            return {
                "hospital_id": self.hospital_id,
                "hospital_name": self.hospital_name,
                **result
            }
        else:
            # Search all hospitals
            results = self.resource_service.search_available_resources(
                resource_type=resource_type,
                resource_subtype=resource_subtype,
                min_quantity=quantity
            )
            return {"results": results}

    def _handle_emergency_alert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle emergency alert"""
        self.logger.log_reasoning(
            session_id="system",
            agent_name=self.name,
            thought=f"Emergency alert received: {payload.get('alert_type')}",
            category=LogCategory.HOSPITAL
        )

        # Reserve resources for emergency
        return {
            "status": "acknowledged",
            "hospital_id": self.hospital_id,
            "emergency_capacity_reserved": True
        }

    def _handle_resource_negotiation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resource negotiation request"""
        return {
            "status": "negotiation_supported",
            "hospital_id": self.hospital_id
        }

    # ==================== Handler Methods ====================

    def handle_book_resource(self, message: AgentMessage) -> AgentResponse:
        """Handle direct resource booking request"""
        payload = message.payload
        return self.process_message(
            phone_number=payload.get("phone", "unknown"),
            message=payload.get("message", ""),
            context=payload.get("context")
        )

    def handle_check_availability(self, message: AgentMessage) -> AgentResponse:
        """Handle availability check request"""
        payload = message.payload
        resource_type = payload.get("resource_type")
        resource_subtype = payload.get("resource_subtype")
        hospital_id = payload.get("hospital_id", self.hospital_id)

        if hospital_id:
            if resource_type == "bed":
                result = self.resource_service.get_bed_availability(hospital_id, resource_subtype)
            elif resource_type == "blood":
                result = self.resource_service.get_blood_availability(hospital_id, resource_subtype)
            else:
                result = self.resource_service.get_equipment_availability(hospital_id, resource_subtype)

            return AgentResponse(
                success=True,
                data=result,
                reasoning=f"Checked {resource_type} availability",
                confidence=1.0
            )

        return AgentResponse(
            success=False,
            reasoning="Hospital ID required",
            confidence=0.0
        )

    def handle_cancel_booking(self, message: AgentMessage) -> AgentResponse:
        """Handle booking cancellation"""
        payload = message.payload
        booking_id = payload.get("booking_id")
        reason = payload.get("reason", "User requested cancellation")

        result = self.resource_service.cancel_booking(booking_id, reason)

        return AgentResponse(
            success=result.get("success", False),
            data=result,
            reasoning=result.get("message", ""),
            confidence=1.0 if result.get("success") else 0.0
        )

    def handle_emergency_booking(self, message: AgentMessage) -> AgentResponse:
        """Handle emergency booking with priority"""
        payload = message.payload
        session = self.get_or_create_session(payload.get("phone", "emergency"))
        session.urgency = "emergency"
        session.resource_type = payload.get("resource_type", "bed")
        session.resource_subtype = payload.get("resource_subtype", "emergency")

        # Fast-track emergency booking
        return self._check_and_present_availability(session)

    # ==================== Dashboard Methods ====================

    def get_dashboard_data(self, hospital_id: Optional[int] = None) -> Dict[str, Any]:
        """Get dashboard data for hospital manager"""
        target_id = hospital_id or self.hospital_id

        if target_id:
            return self.resource_service.get_dashboard_stats(target_id)
        else:
            return {
                "hospitals": self.resource_service.get_all_hospitals_summary()
            }

    def get_bookings_summary(self, hospital_id: Optional[int] = None) -> Dict[str, Any]:
        """Get bookings summary for hospital"""
        target_id = hospital_id or self.hospital_id

        if target_id:
            bookings = self.resource_service.get_hospital_bookings(target_id)
            return {
                "total": len(bookings),
                "pending": len([b for b in bookings if b["status"] == "pending"]),
                "confirmed": len([b for b in bookings if b["status"] == "confirmed"]),
                "recent_bookings": bookings[-10:]  # Last 10
            }
        return {"error": "Hospital ID required"}
