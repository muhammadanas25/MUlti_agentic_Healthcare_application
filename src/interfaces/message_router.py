"""
Message Router - Routes incoming messages to appropriate agents

Analyzes user messages and determines which agent(s) should handle them.
Supports multi-turn conversations with stateful agents like Dr. Sameer.
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import asyncio

from ..core.agent import AgentResponse
from ..agents.patient import (
    DrSameerAgent,
    GuideAgent,
    HaqdarAgent,
    YaadgarAgent,
    KhandanAgent,
    MuhafizAgent
)
from ..agents.patient.guide import GuideState
from ..mcp.server import get_mcp_server
from ..mcp.client import MCPClient


class MessageRouter:
    """
    Routes user messages to appropriate agents based on intent.

    Flow:
    1. Analyze message to determine intent
    2. Route to appropriate agent(s)
    3. Coordinate multi-agent responses if needed
    4. Return formatted response
    """

    # Intent patterns (keyword matching + AI fallback)
    INTENT_PATTERNS = {
        "symptoms": {
            "keywords": [
                "bukhar", "fever", "dard", "pain", "cough", "khansi", "sar dard",
                "headache", "stomach", "pet", "saans", "breathing", "chest",
                "seena", "vomit", "ulti", "diarrhea", "dast", "blood", "khoon",
                "weak", "kamzor", "dizzy", "chakkar", "emergency", "urgent",
                "jaldi", "bimar", "sick", "tabiyet", "health", "feeling"
            ],
            "agent": "dr_sameer",
            "priority": 1
        },
        "hospital": {
            "keywords": [
                "hospital", "clinic", "hospatal", "medical", "center", "centre",
                "bhu", "dispensary", "emergency room", "er", "ward", "admission",
                "nearby", "closest", "qareeb", "nazdeek", "kahan", "where"
            ],
            "agent": "guide",
            "priority": 2
        },
        "doctor": {
            "keywords": [
                "doctor", "daktar", "specialist", "physician", "surgeon",
                "dermatologist", "cardiologist", "eye", "skin", "bone", "heart",
                "brain", "child", "woman", "lady doctor", "female doctor",
                "appointment", "milna", "checkup", "consult"
            ],
            "agent": "guide",
            "priority": 2
        },
        "medicine": {
            "keywords": [
                "medicine", "dawa", "dawai", "tablet", "syrup", "injection",
                "pharmacy", "chemist", "medical store", "price", "keemat",
                "generic", "alternative", "stock", "available", "milegi",
                "insulin", "panadol", "disprin", "antibiotic"
            ],
            "agent": "yaadgar",
            "priority": 3
        },
        "insurance": {
            "keywords": [
                "sehat", "sahulat", "card", "insurance", "coverage", "free",
                "muft", "eligibility", "check", "verify", "cnic", "nadra",
                "government", "sarkari", "scheme"
            ],
            "agent": "haqdar",
            "priority": 3
        },
        "family": {
            "keywords": [
                "family", "khandan", "child", "bacha", "baby", "mother", "maa",
                "father", "abba", "elderly", "buzurg", "pregnant", "vaccine",
                "vaccination", "teeka", "immunization"
            ],
            "agent": "khandan",
            "priority": 4
        },
        "emergency": {
            "keywords": [
                "emergency", "urgent", "critical", "ambulance", "1122",
                "heart attack", "stroke", "accident", "bleeding", "unconscious",
                "behosh", "faint", "collapse", "chest pain", "breathless",
                "saans nahi", "jaan", "khatarnak"
            ],
            "agent": "dr_sameer",  # But with emergency flag
            "priority": 0,  # Highest priority
            "is_emergency": True
        }
    }

    # Common greetings and meta commands
    META_COMMANDS = {
        "greeting": ["hi", "hello", "assalam", "salam", "aoa", "hey", "start"],
        "help": ["help", "madad", "kaise", "how", "guide", "menu", "options"],
        "cancel": ["cancel", "band", "stop", "exit", "bye", "quit"],
        "language": ["urdu", "english", "roman"],
        "agent": ["agent", "human", "insaan", "person", "talk"],
    }

    def __init__(self):
        # Initialize agents
        self.agents = {}
        self.mcp_clients = {}
        self._initialize_agents()

        print("✓ Message Router initialized")

    def _initialize_agents(self):
        """Initialize patient-side agents"""
        mcp = get_mcp_server()

        agent_classes = {
            "dr_sameer": DrSameerAgent,
            "guide": GuideAgent,
            "haqdar": HaqdarAgent,
            "yaadgar": YaadgarAgent,
            "khandan": KhandanAgent,
            "muhafiz": MuhafizAgent,
        }

        for name, AgentClass in agent_classes.items():
            try:
                agent = AgentClass()
                self.agents[name] = agent
                self.mcp_clients[name] = MCPClient(agent, mcp)
                print(f"  ✓ {agent.name} ready")
            except Exception as e:
                print(f"  ❌ Failed to initialize {name}: {e}")

    def detect_intent(self, message: str) -> Tuple[str, Dict[str, Any]]:
        """
        Detect user intent from message.

        Returns:
            Tuple of (intent_name, metadata)
        """
        message_lower = message.lower().strip()

        # Check for meta commands first
        for meta_type, keywords in self.META_COMMANDS.items():
            if any(kw in message_lower for kw in keywords):
                return meta_type, {"original_message": message}

        # Check for intent patterns
        best_match = None
        best_priority = 999
        match_metadata = {}

        for intent_name, intent_config in self.INTENT_PATTERNS.items():
            keywords = intent_config["keywords"]
            matched_keywords = [kw for kw in keywords if kw in message_lower]

            if matched_keywords:
                priority = intent_config["priority"]
                # More keyword matches = higher confidence
                if len(matched_keywords) > len(match_metadata.get("matched_keywords", [])):
                    best_match = intent_name
                    best_priority = priority
                    match_metadata = {
                        "matched_keywords": matched_keywords,
                        "agent": intent_config["agent"],
                        "is_emergency": intent_config.get("is_emergency", False),
                        "original_message": message
                    }
                elif priority < best_priority:
                    best_match = intent_name
                    best_priority = priority
                    match_metadata = {
                        "matched_keywords": matched_keywords,
                        "agent": intent_config["agent"],
                        "is_emergency": intent_config.get("is_emergency", False),
                        "original_message": message
                    }

        if best_match:
            return best_match, match_metadata

        # Default to symptoms if no clear match (let Dr. Sameer analyze)
        return "symptoms", {
            "agent": "dr_sameer",
            "original_message": message,
            "is_fallback": True
        }

    async def route_message(
        self,
        message: str,
        session: Dict[str, Any]
    ) -> Tuple[AgentResponse, str]:
        """
        Route message to appropriate agent(s).

        Args:
            message: User's message
            session: User's session data

        Returns:
            Tuple of (AgentResponse, agent_name)
        """
        phone_number = session.get("phone", "unknown")

        # Check if there's an active conversation with Guide agent
        guide: GuideAgent = self.agents.get("guide")
        if guide and phone_number in guide.sessions:
            guide_session = guide.sessions[phone_number]
            # If conversation is active (not completed or initial), continue with Guide
            if guide_session.state not in [GuideState.COMPLETED, GuideState.INITIAL]:
                print(f"📨 Continuing conversation with Guide (state: {guide_session.state.value})")
                return await self._handle_guide_conversation(message, session), "guide"

        # Check if there's an active conversation with Dr. Sameer
        dr_sameer: DrSameerAgent = self.agents.get("dr_sameer")
        if dr_sameer and phone_number in dr_sameer.sessions:
            dr_session = dr_sameer.sessions[phone_number]
            # If conversation is active (not completed), continue with Dr. Sameer
            if dr_session.state.value != "completed":
                print(f"📨 Continuing conversation with Dr. Sameer (state: {dr_session.state.value})")
                return await self._handle_dr_sameer_conversation(message, session), "dr_sameer"

        intent, metadata = self.detect_intent(message)

        print(f"📨 Intent detected: {intent}")
        print(f"   Metadata: {metadata}")

        # Handle meta commands
        if intent == "greeting":
            # Start a new conversation with Dr. Sameer
            return await self._handle_dr_sameer_conversation(message, session), "dr_sameer"

        elif intent == "help":
            return self._handle_help(), "system"

        elif intent == "cancel":
            # Clear Dr. Sameer session if exists
            if dr_sameer and phone_number in dr_sameer.sessions:
                dr_sameer.clear_session(phone_number)
            return self._handle_cancel(session), "system"

        # Handle emergency with high priority - Dr. Sameer has emergency protocols
        if metadata.get("is_emergency"):
            return await self._handle_dr_sameer_conversation(message, session), "dr_sameer"

        # Route to appropriate agent
        agent_name = metadata.get("agent", "dr_sameer")
        agent = self.agents.get(agent_name)

        if not agent:
            return AgentResponse(
                success=False,
                reasoning="Agent not available"
            ), "system"

        # Process based on intent
        if intent == "symptoms":
            # Use Dr. Sameer's conversational assessment
            return await self._handle_dr_sameer_conversation(message, session), "dr_sameer"

        elif intent in ["hospital", "doctor"]:
            return await self._handle_navigation(message, session, intent, metadata), agent_name

        elif intent == "medicine":
            return await self._handle_medicine(message, session), agent_name

        elif intent == "insurance":
            return await self._handle_insurance(message, session), agent_name

        elif intent == "family":
            return await self._handle_family(message, session), agent_name

        else:
            # Fallback to Dr. Sameer's conversational assessment
            return await self._handle_dr_sameer_conversation(message, session), "dr_sameer"

    def _handle_greeting(self, session: Dict[str, Any]) -> AgentResponse:
        """Handle greeting messages"""
        return AgentResponse(
            success=True,
            data={"template": "welcome"},
            reasoning="User greeted, showing welcome message"
        )

    def _handle_help(self) -> AgentResponse:
        """Handle help requests"""
        return AgentResponse(
            success=True,
            data={"template": "help"},
            reasoning="User requested help"
        )

    def _handle_cancel(self, session: Dict[str, Any]) -> AgentResponse:
        """Handle cancel/exit"""
        session["conversation_state"] = "ended"
        return AgentResponse(
            success=True,
            data={
                "response": """👋 Thank you for using Sehat Saathi!

Stay healthy! 🏥
_Message us anytime you need healthcare help._

Allah Hafiz! اللہ حافظ"""
            },
            reasoning="User ended conversation"
        )

    async def _handle_dr_sameer_conversation(
        self,
        message: str,
        session: Dict[str, Any]
    ) -> AgentResponse:
        """
        Handle conversation with Dr. Sameer's stateful, multi-turn assessment.

        This method supports:
        - Multi-turn symptom assessment with clarifying questions
        - Emergency detection and step-by-step protocols
        - Agent handoff planning for hospital/medicine/insurance
        - OTC medicine recommendations with safety checks
        """
        dr_sameer: DrSameerAgent = self.agents["dr_sameer"]
        phone_number = session.get("phone", "unknown")

        # Prepare patient info from session
        patient_info = session.get("patient_info", {})
        patient_info["phone"] = phone_number

        # Process message through Dr. Sameer's conversational engine
        response = dr_sameer.process_message(
            phone_number=phone_number,
            message=message,
            patient_info=patient_info
        )

        # Update session with latest state
        if phone_number in dr_sameer.sessions:
            dr_session = dr_sameer.sessions[phone_number]
            session["conversation_state"] = dr_session.state.value
            session["last_assessment"] = dr_session.assessment

        # Handle agent handoffs if Dr. Sameer is planning care
        if response.data and response.data.get("handoff_to"):
            handoff_agent = response.data["handoff_to"]
            care_plan = response.data.get("care_plan", {})

            # Store handoff context for next message
            session["pending_handoff"] = {
                "agent": handoff_agent,
                "context": care_plan.get("context", {})
            }

        # Log emergencies to community monitoring
        if response.data and response.data.get("response_type") == "emergency_protocol":
            muhafiz = self.agents.get("muhafiz")
            if muhafiz:
                muhafiz.report_disease_case(
                    disease=response.data.get("emergency_type", "emergency"),
                    location=session.get("patient_info", {}).get("location", "Unknown"),
                    severity="critical",
                    patient_id=phone_number
                )

        return response

    async def _handle_symptoms(
        self,
        message: str,
        session: Dict[str, Any],
        agent: DrSameerAgent
    ) -> AgentResponse:
        """
        Handle symptom assessment - now routes through conversational Dr. Sameer.
        Kept for backward compatibility.
        """
        return await self._handle_dr_sameer_conversation(message, session)

    async def _handle_navigation(
        self,
        message: str,
        session: Dict[str, Any],
        intent: str,
        metadata: Dict[str, Any]
    ) -> AgentResponse:
        """Handle hospital/doctor search using Guide agent's conversational flow"""
        guide: GuideAgent = self.agents["guide"]
        phone_number = session.get("phone", "unknown")

        # Check if this is a handoff from Dr. Sameer
        pending_handoff = session.get("pending_handoff")
        context = None
        if pending_handoff and pending_handoff.get("agent") == "guide_agent":
            context = pending_handoff.get("context", {})
            # Clear the handoff after using
            session.pop("pending_handoff", None)

        if intent == "hospital":
            # Use Guide's conversational process_message
            response = guide.process_message(
                phone_number=phone_number,
                message=message,
                context=context
            )

            # Update session with Guide's state
            if phone_number in guide.sessions:
                guide_session = guide.sessions[phone_number]
                session["guide_state"] = guide_session.state.value

        else:  # doctor
            specialty = self._extract_specialty(message) or "General Physician"
            city = self._extract_location(message) or session.get("patient_info", {}).get("location", "Karachi")
            response = guide.find_doctors(
                city=city.split(",")[0].strip(),
                specialization=specialty,
                patient_preferences=session.get("patient_info", {})
            )

        return response

    async def _handle_guide_conversation(
        self,
        message: str,
        session: Dict[str, Any]
    ) -> AgentResponse:
        """Handle ongoing conversation with Guide agent"""
        guide: GuideAgent = self.agents["guide"]
        phone_number = session.get("phone", "unknown")

        # Check for WhatsApp location coordinates
        location_coords = None
        if session.get("location_lat") and session.get("location_long"):
            location_coords = (session["location_lat"], session["location_long"])
            # Clear after using
            session.pop("location_lat", None)
            session.pop("location_long", None)

        response = guide.process_message(
            phone_number=phone_number,
            message=message,
            location_coords=location_coords
        )

        # Update session with Guide's state
        if phone_number in guide.sessions:
            guide_session = guide.sessions[phone_number]
            session["guide_state"] = guide_session.state.value

        return response

    async def _handle_medicine(
        self,
        message: str,
        session: Dict[str, Any]
    ) -> AgentResponse:
        """Handle medicine search"""
        yaadgar = self.agents["yaadgar"]

        medicine_name = self._extract_medicine_name(message)
        location = session.get("patient_info", {}).get("location", "Karachi")

        response = yaadgar.find_medicine(
            medicine_name=medicine_name,
            patient_location=location
        )

        return response

    async def _handle_insurance(
        self,
        message: str,
        session: Dict[str, Any]
    ) -> AgentResponse:
        """Handle insurance/Sehat Card queries"""
        haqdar = self.agents["haqdar"]

        # Try to extract CNIC from message
        cnic = self._extract_cnic(message)

        if cnic:
            response = haqdar.verify_sehat_card(
                cnic=cnic,
                patient_name=session.get("patient_info", {}).get("name", "Patient")
            )
        else:
            # Ask for CNIC
            response = AgentResponse(
                success=True,
                data={
                    "response": """💳 *Sehat Card Verification*

Please provide your CNIC number:
_Example: 12345-1234567-1_

آپ کا شناختی کارڈ نمبر درج کریں"""
                },
                reasoning="CNIC not provided, asking user"
            )
            session["conversation_state"] = "awaiting_cnic"

        return response

    async def _handle_family(
        self,
        message: str,
        session: Dict[str, Any]
    ) -> AgentResponse:
        """Handle family health queries"""
        khandan = self.agents["khandan"]

        # Check for vaccination queries
        if any(kw in message.lower() for kw in ["vaccine", "vaccination", "teeka", "immunization"]):
            # Extract child age if mentioned
            age_months = self._extract_age(message)
            response = khandan.manage_immunization_schedule(
                child_age_months=age_months or 12,
                already_vaccinated=[]
            )
        else:
            response = AgentResponse(
                success=True,
                data={
                    "response": """👨‍👩‍👧‍👦 *Family Health Services*

I can help with:
• 💉 Child vaccination schedule
• 👵 Elderly care coordination
• 📋 Family health tracking
• 🚨 Emergency family notifications

_What would you like help with?_"""
                },
                reasoning="Showing family services menu"
            )

        return response

    def _extract_symptoms(self, message: str) -> List[str]:
        """Extract symptoms from message"""
        # Common symptom keywords
        symptom_keywords = [
            "fever", "bukhar", "cough", "khansi", "cold", "zukam",
            "headache", "sar dard", "body pain", "jism dard",
            "stomach pain", "pet dard", "vomit", "ulti", "nausea",
            "diarrhea", "dast", "constipation", "qabz", "weakness", "kamzori",
            "dizziness", "chakkar", "chest pain", "seene mein dard",
            "breathing", "saans", "blood", "khoon", "skin", "jild",
            "joint pain", "joron ka dard", "back pain", "kamar dard",
            "throat pain", "gale mein dard", "eye pain", "ankh dard"
        ]

        symptoms = []
        message_lower = message.lower()

        for symptom in symptom_keywords:
            if symptom in message_lower:
                symptoms.append(symptom)

        # If no specific symptoms found, use the whole message
        if not symptoms:
            symptoms = [message]

        return symptoms

    def _extract_location(self, message: str) -> Optional[str]:
        """Extract location from message"""
        # Common Pakistan cities
        cities = [
            "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad",
            "multan", "peshawar", "quetta", "hyderabad", "sialkot",
            "gujranwala", "bahawalpur", "sargodha", "sukkur", "larkana"
        ]

        # Common areas
        areas = [
            "gulberg", "dha", "clifton", "saddar", "johar", "north nazimabad",
            "gulshan", "malir", "korangi", "model town", "cantonment"
        ]

        message_lower = message.lower()

        for city in cities:
            if city in message_lower:
                # Check for area too
                for area in areas:
                    if area in message_lower:
                        return f"{area.title()}, {city.title()}"
                return city.title()

        return None

    def _extract_specialty(self, message: str) -> Optional[str]:
        """Extract medical specialty from message"""
        specialties = {
            "heart": "Cardiologist",
            "dil": "Cardiologist",
            "cardio": "Cardiologist",
            "skin": "Dermatologist",
            "jild": "Dermatologist",
            "bone": "Orthopedic",
            "haddi": "Orthopedic",
            "eye": "Ophthalmologist",
            "ankh": "Ophthalmologist",
            "child": "Pediatrician",
            "bacha": "Pediatrician",
            "women": "Gynecologist",
            "lady": "Gynecologist",
            "brain": "Neurologist",
            "nerve": "Neurologist",
            "kidney": "Nephrologist",
            "gurda": "Nephrologist",
            "mental": "Psychiatrist",
            "general": "General Physician",
            "physician": "General Physician",
        }

        message_lower = message.lower()
        for keyword, specialty in specialties.items():
            if keyword in message_lower:
                return specialty

        return None

    def _extract_medicine_name(self, message: str) -> str:
        """Extract medicine name from message"""
        # Remove common prefixes
        message = message.lower()
        for prefix in ["medicine", "dawa", "dawai", "tablet", "find", "search", "where", "kahan"]:
            message = message.replace(prefix, "")

        return message.strip().title() or "Paracetamol"

    def _extract_cnic(self, message: str) -> Optional[str]:
        """Extract CNIC from message"""
        # CNIC pattern: XXXXX-XXXXXXX-X
        pattern = r'\d{5}-?\d{7}-?\d'
        match = re.search(pattern, message.replace(" ", ""))

        if match:
            cnic = match.group()
            # Format properly
            clean = cnic.replace("-", "")
            return f"{clean[:5]}-{clean[5:12]}-{clean[12]}"

        return None

    def _extract_age(self, message: str) -> Optional[int]:
        """Extract age (in months) from message"""
        # Look for patterns like "6 months", "2 year", "1 saal"
        patterns = [
            (r'(\d+)\s*months?', 1),  # months
            (r'(\d+)\s*mahine', 1),  # Urdu months
            (r'(\d+)\s*years?', 12),  # years -> months
            (r'(\d+)\s*saal', 12),  # Urdu years
        ]

        for pattern, multiplier in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return int(match.group(1)) * multiplier

        return None


# Global instance
_router: Optional[MessageRouter] = None


def get_message_router() -> MessageRouter:
    """Get or create message router instance"""
    global _router
    if _router is None:
        _router = MessageRouter()
    return _router
