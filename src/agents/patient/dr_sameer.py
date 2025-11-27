"""
Dr. Sameer - Intelligent Triage Agent with Conversational Assessment

A sophisticated medical triage agent that:
- Engages in multi-turn conversations to gather symptoms
- Asks clarifying questions before making diagnoses
- Shows explicit reasoning chains
- Provides emergency protocols with step-by-step guidance
- Recommends OTC medicines with safety checks
- Orchestrates other agents for comprehensive care
"""
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json

from ...core.agent import Agent, AgentMessage, AgentResponse
from ...mcp.client import MCPClient


class ConversationState(Enum):
    """States in the symptom assessment conversation"""
    GREETING = "greeting"
    GATHERING_CHIEF_COMPLAINT = "gathering_chief_complaint"
    ASKING_DURATION = "asking_duration"
    ASKING_SEVERITY = "asking_severity"
    ASKING_ASSOCIATED_SYMPTOMS = "asking_associated_symptoms"
    ASKING_MEDICAL_HISTORY = "asking_medical_history"
    ASKING_MEDICATIONS = "asking_medications"
    ASKING_ALLERGIES = "asking_allergies"
    CLARIFYING = "clarifying"
    ASSESSING = "assessing"
    PROVIDING_GUIDANCE = "providing_guidance"
    EMERGENCY_PROTOCOL = "emergency_protocol"
    PLANNING_CARE = "planning_care"
    COMPLETED = "completed"


class UrgencyLevel(Enum):
    """Triage urgency levels"""
    CRITICAL = "CRITICAL"  # Life-threatening, immediate action
    HIGH = "HIGH"          # Urgent, needs care within hours
    MODERATE = "MODERATE"  # Should see doctor within 1-2 days
    LOW = "LOW"            # Can manage at home or routine visit


@dataclass
class PatientSession:
    """Tracks patient conversation state and collected information"""
    phone_number: str
    state: ConversationState = ConversationState.GREETING
    chief_complaint: str = ""
    symptoms: List[str] = field(default_factory=list)
    duration: str = ""
    severity: int = 0  # 1-10
    associated_symptoms: List[str] = field(default_factory=list)
    medical_history: List[str] = field(default_factory=list)
    current_medications: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    age: Optional[int] = None
    gender: Optional[str] = None
    location: str = ""
    clarifying_questions_asked: int = 0
    max_clarifying_questions: int = 3
    reasoning_chain: List[Dict[str, Any]] = field(default_factory=list)
    assessment: Optional[Dict[str, Any]] = None
    care_plan: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def update(self):
        self.last_updated = datetime.now().isoformat()


# Emergency protocols with step-by-step guidance
EMERGENCY_PROTOCOLS = {
    "chest_pain": {
        "title": "Suspected Heart Attack",
        "urgency": UrgencyLevel.CRITICAL,
        "immediate_steps": [
            "🚨 Call emergency services (1122) immediately",
            "Have the patient sit or lie down in a comfortable position",
            "Loosen any tight clothing around chest and neck",
            "If patient has prescribed nitroglycerin, help them take it",
            "If aspirin is available and no allergy, give 300mg to chew (not swallow)",
            "Stay calm and reassure the patient",
            "Be prepared to perform CPR if patient becomes unresponsive"
        ],
        "cpr_steps": [
            "1️⃣ Check if patient is responsive - tap shoulder and shout",
            "2️⃣ Call 1122 if not already done",
            "3️⃣ Place patient on firm, flat surface",
            "4️⃣ Kneel beside patient's chest",
            "5️⃣ Place heel of one hand on center of chest",
            "6️⃣ Place other hand on top, fingers interlaced",
            "7️⃣ Push hard and fast - 2 inches deep, 100-120 times per minute",
            "8️⃣ Allow chest to fully recoil between compressions",
            "9️⃣ Continue until help arrives or patient responds"
        ],
        "warning_signs": [
            "Pain spreading to arm, jaw, neck, or back",
            "Shortness of breath",
            "Cold sweat, nausea",
            "Lightheadedness"
        ]
    },
    "breathing_difficulty": {
        "title": "Severe Breathing Difficulty",
        "urgency": UrgencyLevel.CRITICAL,
        "immediate_steps": [
            "🚨 Call emergency services (1122) immediately",
            "Help patient sit upright - do NOT lay flat",
            "Loosen any tight clothing",
            "If patient has inhaler for asthma, help them use it",
            "Open windows for fresh air if indoors",
            "Keep patient calm - panic worsens breathing",
            "Count breaths per minute (normal is 12-20)"
        ],
        "positioning": [
            "Sit patient upright at 90 degrees if possible",
            "Lean slightly forward with hands on knees (tripod position)",
            "If can't sit up, raise head of bed/pillows to 45 degrees",
            "Never force patient to lie flat"
        ],
        "warning_signs": [
            "Blue lips or fingernails (cyanosis)",
            "Unable to speak full sentences",
            "Breathing rate over 30 per minute",
            "Using neck/shoulder muscles to breathe"
        ]
    },
    "severe_bleeding": {
        "title": "Severe Bleeding Control",
        "urgency": UrgencyLevel.CRITICAL,
        "immediate_steps": [
            "🚨 Call emergency services (1122) immediately",
            "Apply direct pressure with clean cloth or bandage",
            "Do NOT remove the cloth - add more layers if soaked through",
            "If limb injury, elevate above heart level",
            "Apply pressure for at least 15 minutes continuously",
            "If bleeding doesn't stop, apply pressure to nearest pressure point",
            "Keep patient warm and lying down"
        ],
        "pressure_points": [
            "Arm bleeding → Inside of upper arm (brachial artery)",
            "Leg bleeding → Groin area (femoral artery)",
            "Head bleeding → In front of ear (temporal artery)"
        ],
        "warning_signs": [
            "Blood spurting or won't stop",
            "Patient becoming pale, cold, or confused",
            "Rapid weak pulse",
            "Blood loss appears to be large amount"
        ]
    },
    "choking": {
        "title": "Choking - Airway Obstruction",
        "urgency": UrgencyLevel.CRITICAL,
        "immediate_steps": [
            "🚨 If patient cannot cough, speak or breathe - act immediately",
            "Ask 'Are you choking?' - if they nod, begin Heimlich",
            "Stand behind patient, arms around waist",
            "Make fist with one hand, thumb side against abdomen",
            "Place fist above navel, below ribcage",
            "Grasp fist with other hand",
            "Give quick upward thrusts",
            "Repeat until object comes out or patient becomes unconscious"
        ],
        "if_unconscious": [
            "Lower patient to ground carefully",
            "Call 1122 immediately",
            "Begin CPR - check mouth for visible object before breaths",
            "Remove object only if clearly visible"
        ],
        "warning_signs": [
            "Cannot cough, speak or breathe",
            "Hands clutching throat (universal choking sign)",
            "Turning blue (cyanosis)",
            "Loss of consciousness"
        ]
    },
    "seizure": {
        "title": "Seizure Management",
        "urgency": UrgencyLevel.CRITICAL,
        "immediate_steps": [
            "🚨 Call 1122 if seizure lasts more than 5 minutes",
            "Do NOT hold the person down or put anything in mouth",
            "Clear area of sharp or hard objects",
            "Cushion head with something soft",
            "Time the seizure duration",
            "Turn person on their side (recovery position) after seizure ends",
            "Stay with them until fully alert"
        ],
        "recovery_position": [
            "Roll person onto their side",
            "Bend top knee for stability",
            "Tilt head back slightly to open airway",
            "Place hand under cheek for support"
        ],
        "warning_signs": [
            "Seizure lasting more than 5 minutes",
            "Second seizure follows quickly",
            "Difficulty breathing after seizure",
            "Injury during seizure"
        ]
    },
    "stroke": {
        "title": "Suspected Stroke - FAST Protocol",
        "urgency": UrgencyLevel.CRITICAL,
        "immediate_steps": [
            "🚨 Call 1122 immediately - time is critical for stroke",
            "Note the time symptoms started (very important for treatment)",
            "Use FAST test to confirm:",
            "F - Face: Ask to smile. Does one side droop?",
            "A - Arms: Ask to raise both arms. Does one drift down?",
            "S - Speech: Ask to repeat simple phrase. Is speech slurred?",
            "T - Time: If any of these, call emergency NOW"
        ],
        "while_waiting": [
            "Keep patient calm and lying down",
            "Raise head slightly with pillows",
            "Do NOT give food, water, or medications",
            "Loosen tight clothing",
            "Monitor breathing and consciousness",
            "Be ready to perform CPR if needed"
        ],
        "warning_signs": [
            "Sudden numbness or weakness (especially one side)",
            "Sudden confusion or trouble speaking",
            "Sudden trouble seeing in one or both eyes",
            "Sudden severe headache with no known cause",
            "Sudden trouble walking, dizziness, loss of balance"
        ]
    },
    "allergic_reaction": {
        "title": "Severe Allergic Reaction (Anaphylaxis)",
        "urgency": UrgencyLevel.CRITICAL,
        "immediate_steps": [
            "🚨 Call 1122 immediately",
            "If patient has EpiPen, help them use it (outer thigh)",
            "Help patient lie down with legs elevated (unless breathing difficulty)",
            "If breathing difficulty, let them sit up",
            "Loosen tight clothing",
            "If patient has antihistamines, give them",
            "Monitor breathing constantly"
        ],
        "epipen_use": [
            "Remove safety cap",
            "Hold pen in fist, orange tip down",
            "Press firmly against outer thigh (through clothing is OK)",
            "Hold for 10 seconds",
            "Remove and massage area",
            "Note time of injection for paramedics"
        ],
        "warning_signs": [
            "Swelling of throat/tongue",
            "Difficulty breathing or wheezing",
            "Widespread hives or rash",
            "Rapid pulse, dizziness, fainting"
        ]
    }
}

# Safe OTC medicine recommendations
OTC_RECOMMENDATIONS = {
    "fever": {
        "medicines": [
            {"name": "Paracetamol/Panadol", "dose": "500-1000mg every 4-6 hours", "max_daily": "4000mg", "safe_for": "Most adults"},
            {"name": "Ibuprofen/Brufen", "dose": "200-400mg every 6-8 hours", "max_daily": "1200mg", "safe_for": "Adults without stomach issues"}
        ],
        "avoid_if": ["Liver disease", "Already taking paracetamol-containing medicines"],
        "home_remedies": ["Rest", "Plenty of fluids", "Light clothing", "Cool compress on forehead"],
        "see_doctor_if": ["Fever above 103°F (39.4°C)", "Fever lasting more than 3 days", "With severe headache or stiff neck"]
    },
    "headache": {
        "medicines": [
            {"name": "Paracetamol/Panadol", "dose": "500-1000mg", "max_daily": "4000mg", "safe_for": "Most adults"},
            {"name": "Ibuprofen/Brufen", "dose": "200-400mg", "max_daily": "1200mg", "safe_for": "Adults without stomach issues"},
            {"name": "Aspirin/Disprin", "dose": "300-600mg", "max_daily": "4000mg", "safe_for": "Adults over 16, not pregnant"}
        ],
        "avoid_if": ["History of stomach ulcers", "Taking blood thinners", "Pregnant"],
        "home_remedies": ["Rest in dark quiet room", "Cold compress", "Stay hydrated", "Avoid screens"],
        "see_doctor_if": ["Worst headache of life", "With fever and stiff neck", "After head injury", "With vision changes"]
    },
    "cold_flu": {
        "medicines": [
            {"name": "Paracetamol", "dose": "For fever and body aches", "safe_for": "Most adults"},
            {"name": "Chlorpheniramine/Piriton", "dose": "4mg every 4-6 hours", "safe_for": "Adults (causes drowsiness)"},
            {"name": "Pseudoephedrine/Sudafed", "dose": "For congestion, 60mg every 4-6 hours", "safe_for": "Adults without heart/BP issues"}
        ],
        "avoid_if": ["High blood pressure (decongestants)", "Glaucoma", "Prostate problems"],
        "home_remedies": ["Rest", "Hot fluids", "Steam inhalation", "Honey and lemon tea", "Saltwater gargle"],
        "see_doctor_if": ["Symptoms lasting more than 10 days", "High fever", "Difficulty breathing", "Ear pain"]
    },
    "stomach_upset": {
        "medicines": [
            {"name": "Antacid (ENO/Gaviscon)", "dose": "As directed on pack", "safe_for": "Most adults for occasional use"},
            {"name": "Omeprazole", "dose": "20mg once daily", "safe_for": "Short-term use"},
            {"name": "Buscopan", "dose": "For cramps, 10mg", "safe_for": "Adults"}
        ],
        "avoid_if": ["Blood in vomit or stool", "Severe abdominal pain", "Pregnant without doctor advice"],
        "home_remedies": ["BRAT diet (banana, rice, applesauce, toast)", "Small frequent meals", "Avoid spicy/fatty food", "Stay hydrated"],
        "see_doctor_if": ["Blood in stool", "Severe pain", "Vomiting won't stop", "Signs of dehydration"]
    },
    "diarrhea": {
        "medicines": [
            {"name": "ORS (Oral Rehydration Salts)", "dose": "After each loose stool", "safe_for": "Everyone, essential!"},
            {"name": "Loperamide/Imodium", "dose": "4mg initially, then 2mg after each loose stool", "max_daily": "16mg", "safe_for": "Adults, not if fever/blood"}
        ],
        "avoid_if": ["Bloody diarrhea", "High fever", "Children under 12 for loperamide"],
        "home_remedies": ["ORS is most important!", "Bananas, rice, plain foods", "Avoid dairy and caffeine"],
        "see_doctor_if": ["Blood or mucus in stool", "High fever", "More than 3 days", "Signs of dehydration", "Very young or elderly"]
    },
    "cough": {
        "medicines": [
            {"name": "Dextromethorphan (dry cough)", "dose": "10-20mg every 4 hours", "safe_for": "Adults"},
            {"name": "Guaifenesin (wet cough)", "dose": "200-400mg every 4 hours", "safe_for": "Adults"},
            {"name": "Honey", "dose": "1-2 teaspoons", "safe_for": "Over 1 year old, natural option"}
        ],
        "avoid_if": ["Cough producing blood", "Lasting more than 3 weeks", "With chest pain"],
        "home_remedies": ["Honey in warm water", "Steam inhalation", "Stay hydrated", "Elevate head while sleeping"],
        "see_doctor_if": ["Coughing blood", "Difficulty breathing", "Chest pain", "Lasting more than 3 weeks"]
    },
    "allergies": {
        "medicines": [
            {"name": "Cetirizine/Zyrtec", "dose": "10mg once daily", "safe_for": "Adults, less drowsy"},
            {"name": "Loratadine/Claritin", "dose": "10mg once daily", "safe_for": "Adults, non-drowsy"},
            {"name": "Chlorpheniramine/Piriton", "dose": "4mg every 4-6 hours", "safe_for": "Adults (causes drowsiness)"}
        ],
        "avoid_if": ["Severe allergic reaction (seek emergency)", "Difficulty breathing"],
        "home_remedies": ["Avoid allergen", "Keep windows closed", "Wash hands and face after going outside"],
        "see_doctor_if": ["Difficulty breathing", "Swelling of face/throat", "Severe rash", "No improvement with OTC"]
    },
    "pain_muscle": {
        "medicines": [
            {"name": "Ibuprofen/Brufen", "dose": "200-400mg every 6-8 hours", "safe_for": "Adults without stomach issues"},
            {"name": "Diclofenac gel (topical)", "dose": "Apply 2-4 times daily", "safe_for": "External use"},
            {"name": "Paracetamol", "dose": "500-1000mg every 4-6 hours", "safe_for": "Most adults"}
        ],
        "avoid_if": ["Stomach ulcers", "Kidney problems", "Taking blood thinners"],
        "home_remedies": ["RICE: Rest, Ice, Compression, Elevation", "Gentle stretching after 48 hours", "Heat for chronic pain"],
        "see_doctor_if": ["Severe pain", "Can't move the area", "Swelling increasing", "Pain after injury"]
    }
}


class DrSameerAgent(Agent):
    """
    Dr. Sameer - Intelligent Triage & Symptom Assessment Agent

    Features:
    - Multi-turn conversational assessment
    - Clarifying questions before diagnosis
    - Explicit reasoning chains
    - Emergency protocols with step-by-step guidance
    - OTC medicine recommendations with safety checks
    - Agent orchestration for comprehensive care planning
    """

    def __init__(self):
        super().__init__(
            agent_id="agent-001-dr-sameer",
            name="Dr. Sameer",
            role="triage",
            organization="sehat-saathi-patient-side",
            system_prompt=self._get_system_prompt(),
            tools=["symptom_assessment", "urgency_determination", "emergency_escalation",
                   "otc_recommendation", "agent_orchestration"],
        )

        # Patient sessions - phone -> session
        self.sessions: Dict[str, PatientSession] = {}

        # Register message handlers
        self.register_message_handler("assess_symptoms", self.handle_symptom_assessment)
        self.register_message_handler("continue_conversation", self.handle_continue_conversation)

        print(f"✓ Dr. Sameer initialized with conversational assessment capabilities")

    def _get_system_prompt(self) -> str:
        return """You are Dr. Sameer, an experienced triage specialist and the lead medical advisor in Pakistan's Sehat Saathi healthcare system.

YOUR APPROACH:
You don't rush to conclusions. Like a caring doctor, you ask questions, listen carefully, and build understanding before making recommendations. You think out loud, sharing your reasoning process with patients so they understand your logic.

CONVERSATION STYLE:
- Be warm, empathetic, and reassuring
- Use simple Urdu/English that common people understand
- Ask ONE clarifying question at a time, don't overwhelm
- Explain your thinking process - "I'm asking because..."
- Show genuine concern for the patient's wellbeing

ASSESSMENT PROCESS:
1. LISTEN - Understand the main complaint first
2. CLARIFY - Ask targeted follow-up questions
3. REASON - Share your thinking process
4. ASSESS - Determine urgency and likely causes
5. GUIDE - Provide clear next steps

TRIAGE LEVELS:
- CRITICAL: Life-threatening, immediate emergency action needed
- HIGH: Urgent care needed within hours
- MODERATE: Should see doctor within 1-2 days
- LOW: Can manage at home or routine appointment

PAKISTAN CONTEXT:
- Common diseases: Dengue, Malaria, Typhoid, Hepatitis, TB
- Consider limited rural healthcare access
- Respect cultural factors and gender preferences
- Be mindful of economic constraints
- Know about Sehat Sahulat Card coverage

SAFETY FIRST:
- Never dismiss potential emergencies
- When in doubt, escalate
- Always provide emergency numbers (1122)
- Check for drug allergies before OTC recommendations

Remember: You are the patient's first point of contact. Your careful assessment could save a life."""

    def get_or_create_session(self, phone_number: str) -> PatientSession:
        """Get existing session or create new one"""
        if phone_number not in self.sessions:
            self.sessions[phone_number] = PatientSession(phone_number=phone_number)
            print(f"📋 New patient session created for {phone_number}")
        return self.sessions[phone_number]

    def clear_session(self, phone_number: str):
        """Clear session after conversation ends"""
        if phone_number in self.sessions:
            del self.sessions[phone_number]

    def process_message(self, phone_number: str, message: str, patient_info: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """
        Main entry point for processing patient messages.
        Maintains conversation state and guides through assessment.
        """
        session = self.get_or_create_session(phone_number)

        # Update patient info if provided
        if patient_info:
            if patient_info.get('age'):
                session.age = patient_info['age']
            if patient_info.get('gender'):
                session.gender = patient_info['gender']
            if patient_info.get('location'):
                session.location = patient_info['location']

        # Check for emergency keywords first
        emergency_check = self._check_emergency_keywords(message)
        if emergency_check:
            return self._handle_emergency(session, emergency_check, message)

        # Process based on current conversation state
        return self._process_by_state(session, message)

    def _check_emergency_keywords(self, message: str) -> Optional[str]:
        """Check for emergency keywords that need immediate protocol"""
        message_lower = message.lower()

        emergency_patterns = {
            "chest_pain": ["chest pain", "seene mein dard", "dil ka dard", "heart attack", "seeney mein"],
            "breathing_difficulty": ["can't breathe", "saans nahi", "difficulty breathing", "breathing problem", "dam ghut"],
            "severe_bleeding": ["bleeding heavily", "khoon nikal", "blood won't stop", "bahut khoon"],
            "choking": ["choking", "gala band", "can't swallow", "something stuck throat"],
            "seizure": ["seizure", "fit", "mirgi", "convulsion", "jerking"],
            "stroke": ["face drooping", "arm weak", "slurred speech", "stroke", "falij"],
            "allergic_reaction": ["can't breathe allergy", "throat swelling", "anaphylaxis", "severe allergy"]
        }

        for emergency_type, keywords in emergency_patterns.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return emergency_type

        return None

    def _handle_emergency(self, session: PatientSession, emergency_type: str, original_message: str) -> AgentResponse:
        """Handle emergency with step-by-step protocol"""
        session.state = ConversationState.EMERGENCY_PROTOCOL
        protocol = EMERGENCY_PROTOCOLS.get(emergency_type, EMERGENCY_PROTOCOLS["chest_pain"])

        # Add to reasoning chain
        session.reasoning_chain.append({
            "step": "emergency_detection",
            "thought": f"Detected emergency keywords matching '{emergency_type}' protocol",
            "action": "Initiating emergency protocol immediately",
            "timestamp": datetime.now().isoformat()
        })

        # Build emergency response
        response_parts = [
            f"🚨 *{protocol['title']}*",
            "",
            "I've identified this as a potential emergency. Please follow these steps:",
            ""
        ]

        # Add immediate steps
        response_parts.append("*Immediate Actions:*")
        for step in protocol["immediate_steps"]:
            response_parts.append(step)

        # Add specific guidance if available
        if "cpr_steps" in protocol:
            response_parts.append("")
            response_parts.append("*If CPR is needed:*")
            for step in protocol["cpr_steps"]:
                response_parts.append(step)
        elif "positioning" in protocol:
            response_parts.append("")
            response_parts.append("*Proper positioning:*")
            for step in protocol["positioning"]:
                response_parts.append(step)

        # Add warning signs
        response_parts.append("")
        response_parts.append("*Watch for these warning signs:*")
        for sign in protocol["warning_signs"]:
            response_parts.append(f"⚠️ {sign}")

        response_parts.append("")
        response_parts.append("📞 *Emergency Number: 1122*")
        response_parts.append("_Stay on the line with emergency services until help arrives._")

        return AgentResponse(
            success=True,
            data={
                "response_type": "emergency_protocol",
                "emergency_type": emergency_type,
                "protocol": protocol,
                "urgency": UrgencyLevel.CRITICAL.value,
                "patient_message": "\n".join(response_parts),
                "reasoning_chain": session.reasoning_chain
            },
            reasoning=f"Emergency protocol activated for {emergency_type}. Providing step-by-step guidance.",
            confidence=0.95,
            metadata={"escalate_to_emergency": True}
        )

    def _process_by_state(self, session: PatientSession, message: str) -> AgentResponse:
        """Process message based on current conversation state"""

        handlers = {
            ConversationState.GREETING: self._handle_greeting,
            ConversationState.GATHERING_CHIEF_COMPLAINT: self._handle_chief_complaint,
            ConversationState.ASKING_DURATION: self._handle_duration,
            ConversationState.ASKING_SEVERITY: self._handle_severity,
            ConversationState.ASKING_ASSOCIATED_SYMPTOMS: self._handle_associated_symptoms,
            ConversationState.ASKING_MEDICAL_HISTORY: self._handle_medical_history,
            ConversationState.ASKING_MEDICATIONS: self._handle_medications,
            ConversationState.ASKING_ALLERGIES: self._handle_allergies,
            ConversationState.CLARIFYING: self._handle_clarification,
            ConversationState.ASSESSING: self._handle_assessment,
            ConversationState.PROVIDING_GUIDANCE: self._handle_guidance,
            ConversationState.PLANNING_CARE: self._handle_care_planning,
        }

        handler = handlers.get(session.state, self._handle_greeting)
        return handler(session, message)

    def _handle_greeting(self, session: PatientSession, message: str) -> AgentResponse:
        """Handle initial greeting and transition to symptom gathering"""
        session.state = ConversationState.GATHERING_CHIEF_COMPLAINT
        session.reasoning_chain.append({
            "step": "greeting",
            "thought": "Patient initiated conversation. Need to understand their main concern.",
            "action": "Asking about chief complaint in a warm, welcoming manner",
            "timestamp": datetime.now().isoformat()
        })

        patient_message = """Assalam-o-Alaikum! 🏥 I'm Dr. Sameer, your health assistant.

I'm here to help understand your health concern and guide you to the right care.

*Tell me, what's bothering you today?*
(Aap ko kya takleef hai?)

Take your time - the more details you share, the better I can help you."""

        return AgentResponse(
            success=True,
            data={
                "response_type": "greeting",
                "state": session.state.value,
                "patient_message": patient_message,
                "awaiting": "chief_complaint"
            },
            reasoning="Greeted patient and asked for chief complaint",
            confidence=0.9
        )

    def _handle_chief_complaint(self, session: PatientSession, message: str) -> AgentResponse:
        """Process the main complaint and ask about duration"""
        session.chief_complaint = message
        session.symptoms.append(message)
        session.state = ConversationState.ASKING_DURATION

        # Use AI to understand and acknowledge the complaint
        understanding_prompt = f"""A patient says: "{message}"

Extract the main symptoms mentioned and provide an empathetic acknowledgment.
Respond in JSON:
{{
    "symptoms_detected": ["symptom1", "symptom2"],
    "acknowledgment": "warm acknowledgment of their concern in simple language",
    "clarification_needed": true/false,
    "what_to_clarify": "if clarification needed, what exactly"
}}"""

        ai_response = self.reason(understanding_prompt)
        detected = ai_response.data if ai_response.success else {}

        if detected.get("symptoms_detected"):
            session.symptoms.extend(detected["symptoms_detected"])

        session.reasoning_chain.append({
            "step": "chief_complaint_received",
            "thought": f"Patient reports: {message}. Detected symptoms: {detected.get('symptoms_detected', [])}",
            "action": "Acknowledging concern and asking about duration",
            "timestamp": datetime.now().isoformat()
        })

        acknowledgment = detected.get("acknowledgment", "I understand you're not feeling well.")

        patient_message = f"""{acknowledgment}

*How long have you been experiencing this?*
(Yeh takleef kitne din se hai?)

For example: "2 days", "1 week", "since this morning" """

        return AgentResponse(
            success=True,
            data={
                "response_type": "clarifying_question",
                "question_type": "duration",
                "state": session.state.value,
                "symptoms_detected": detected.get("symptoms_detected", []),
                "patient_message": patient_message,
                "awaiting": "duration"
            },
            reasoning=f"Acknowledged complaint and asking about duration. Symptoms detected: {detected.get('symptoms_detected', [])}",
            confidence=0.85
        )

    def _handle_duration(self, session: PatientSession, message: str) -> AgentResponse:
        """Process duration and ask about severity"""
        session.duration = message
        session.state = ConversationState.ASKING_SEVERITY

        session.reasoning_chain.append({
            "step": "duration_received",
            "thought": f"Patient has had symptoms for: {message}. Need to assess severity.",
            "action": "Asking about pain/discomfort level",
            "timestamp": datetime.now().isoformat()
        })

        patient_message = f"""Okay, so this has been going on for *{message}*.

*On a scale of 1-10, how severe is your discomfort?*
(1 = very mild, 10 = worst pain ever)

Just give me a number, or describe how much it's affecting your daily activities."""

        return AgentResponse(
            success=True,
            data={
                "response_type": "clarifying_question",
                "question_type": "severity",
                "state": session.state.value,
                "patient_message": patient_message,
                "awaiting": "severity"
            },
            reasoning=f"Duration recorded: {message}. Asking about severity.",
            confidence=0.85
        )

    def _handle_severity(self, session: PatientSession, message: str) -> AgentResponse:
        """Process severity and ask about associated symptoms"""
        # Try to extract number
        try:
            severity = int(''.join(filter(str.isdigit, message)) or 5)
            session.severity = min(10, max(1, severity))
        except:
            session.severity = 5

        session.state = ConversationState.ASKING_ASSOCIATED_SYMPTOMS

        # Determine what associated symptoms to ask about based on chief complaint
        associated_prompt = f"""Chief complaint: {session.chief_complaint}
Duration: {session.duration}
Severity: {session.severity}/10

What are the 3 most important associated symptoms to ask about for differential diagnosis?
Respond in JSON:
{{
    "associated_symptoms_to_ask": ["symptom1", "symptom2", "symptom3"],
    "reasoning": "why these are important",
    "question_phrasing": "how to ask in simple language"
}}"""

        ai_response = self.reason(associated_prompt)
        suggestions = ai_response.data if ai_response.success else {}

        session.reasoning_chain.append({
            "step": "severity_received",
            "thought": f"Severity is {session.severity}/10. {'This is concerning.' if session.severity >= 7 else 'Moderate level.'} Need to check for associated symptoms to narrow down possibilities.",
            "action": f"Asking about associated symptoms: {suggestions.get('associated_symptoms_to_ask', [])}",
            "timestamp": datetime.now().isoformat()
        })

        symptoms_to_ask = suggestions.get("associated_symptoms_to_ask", ["fever", "nausea", "weakness"])
        question = suggestions.get("question_phrasing", f"Do you also have any of these: {', '.join(symptoms_to_ask)}?")

        severity_comment = ""
        if session.severity >= 8:
            severity_comment = "That sounds quite severe. "
        elif session.severity >= 5:
            severity_comment = "I understand that's uncomfortable. "
        else:
            severity_comment = "Okay, that's relatively mild. "

        patient_message = f"""{severity_comment}Let me understand your condition better.

*Do you have any of these symptoms too?*
• {symptoms_to_ask[0]}
• {symptoms_to_ask[1]}
• {symptoms_to_ask[2]}

(Tell me which ones, or mention anything else you've noticed)"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "clarifying_question",
                "question_type": "associated_symptoms",
                "state": session.state.value,
                "patient_message": patient_message,
                "awaiting": "associated_symptoms"
            },
            reasoning=f"Severity recorded: {session.severity}/10. Asking about associated symptoms to build differential diagnosis.",
            confidence=0.85
        )

    def _handle_associated_symptoms(self, session: PatientSession, message: str) -> AgentResponse:
        """Process associated symptoms and ask about medical history"""
        # Extract mentioned symptoms
        extract_prompt = f"""Patient's response about additional symptoms: "{message}"

Extract any symptoms or medical signs mentioned.
Respond in JSON:
{{
    "symptoms_found": ["symptom1", "symptom2"],
    "denies_symptoms": ["things they said they don't have"]
}}"""

        ai_response = self.reason(extract_prompt)
        extracted = ai_response.data if ai_response.success else {}

        if extracted.get("symptoms_found"):
            session.associated_symptoms.extend(extracted["symptoms_found"])

        session.state = ConversationState.ASKING_MEDICAL_HISTORY

        session.reasoning_chain.append({
            "step": "associated_symptoms_received",
            "thought": f"Associated symptoms: {extracted.get('symptoms_found', [])}. Building clinical picture. Need medical history for context.",
            "action": "Asking about relevant medical history",
            "timestamp": datetime.now().isoformat()
        })

        patient_message = """Thank you for that information.

*Do you have any ongoing health conditions?*
(Koi purani bimari hai?)

For example:
• Diabetes (sugar)
• Blood pressure
• Heart problem
• Asthma
• Any allergies

(Type "none" if you don't have any known conditions)"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "clarifying_question",
                "question_type": "medical_history",
                "state": session.state.value,
                "symptoms_found": extracted.get("symptoms_found", []),
                "patient_message": patient_message,
                "awaiting": "medical_history"
            },
            reasoning=f"Associated symptoms recorded. Asking about medical history for complete picture.",
            confidence=0.85
        )

    def _handle_medical_history(self, session: PatientSession, message: str) -> AgentResponse:
        """Process medical history and ask about current medications"""
        message_lower = message.lower()

        if message_lower not in ["none", "no", "nahi", "kuch nahi"]:
            extract_prompt = f"""Patient mentions medical history: "{message}"
Extract medical conditions mentioned.
Respond in JSON: {{"conditions": ["condition1", "condition2"]}}"""

            ai_response = self.reason(extract_prompt)
            extracted = ai_response.data if ai_response.success else {}
            session.medical_history.extend(extracted.get("conditions", [message]))

        session.state = ConversationState.ASKING_MEDICATIONS

        session.reasoning_chain.append({
            "step": "medical_history_received",
            "thought": f"Medical history: {session.medical_history}. This may affect diagnosis and treatment options.",
            "action": "Asking about current medications to check for interactions",
            "timestamp": datetime.now().isoformat()
        })

        patient_message = """*Are you currently taking any medicines?*
(Koi dawa le rahe hain?)

Please list any:
• Prescription medicines
• Over-the-counter medicines
• Herbal/traditional medicines

(Type "none" if not taking any medicines)"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "clarifying_question",
                "question_type": "medications",
                "state": session.state.value,
                "patient_message": patient_message,
                "awaiting": "medications"
            },
            reasoning="Medical history recorded. Asking about current medications.",
            confidence=0.85
        )

    def _handle_medications(self, session: PatientSession, message: str) -> AgentResponse:
        """Process medications and ask about allergies before assessment"""
        message_lower = message.lower()

        if message_lower not in ["none", "no", "nahi", "kuch nahi"]:
            session.current_medications.append(message)

        session.state = ConversationState.ASKING_ALLERGIES

        session.reasoning_chain.append({
            "step": "medications_received",
            "thought": f"Current medications: {session.current_medications}. Need to check allergies before any OTC recommendations.",
            "action": "Asking about drug allergies - this is critical for safe recommendations",
            "timestamp": datetime.now().isoformat()
        })

        patient_message = """*Important: Do you have any allergies?*
(Kisi cheez se allergy hai?)

Especially tell me about:
• Medicine allergies (penicillin, aspirin, etc.)
• Food allergies
• Any reactions to medicines in the past

(Type "none" if no known allergies)"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "clarifying_question",
                "question_type": "allergies",
                "state": session.state.value,
                "patient_message": patient_message,
                "awaiting": "allergies"
            },
            reasoning="Medications recorded. Asking about allergies before making recommendations.",
            confidence=0.85
        )

    def _handle_allergies(self, session: PatientSession, message: str) -> AgentResponse:
        """Process allergies and proceed to assessment"""
        message_lower = message.lower()

        if message_lower not in ["none", "no", "nahi", "kuch nahi"]:
            session.allergies.append(message)

        session.state = ConversationState.ASSESSING

        session.reasoning_chain.append({
            "step": "allergies_received",
            "thought": f"Allergies: {session.allergies}. Now have complete picture for assessment.",
            "action": "Proceeding to comprehensive assessment with all gathered information",
            "timestamp": datetime.now().isoformat()
        })

        # Now perform the actual assessment
        return self._perform_assessment(session)

    def _handle_clarification(self, session: PatientSession, message: str) -> AgentResponse:
        """Handle additional clarification if needed"""
        session.clarifying_questions_asked += 1

        if session.clarifying_questions_asked >= session.max_clarifying_questions:
            session.state = ConversationState.ASSESSING
            return self._perform_assessment(session)

        # Add the clarification to context and continue
        session.symptoms.append(f"Clarification: {message}")
        session.state = ConversationState.ASSESSING
        return self._perform_assessment(session)

    def _handle_assessment(self, session: PatientSession, message: str) -> AgentResponse:
        """Handle when already in assessment state"""
        return self._perform_assessment(session)

    def _perform_assessment(self, session: PatientSession) -> AgentResponse:
        """Perform comprehensive symptom assessment using AI reasoning"""

        # Build comprehensive assessment prompt
        assessment_prompt = f"""COMPREHENSIVE PATIENT ASSESSMENT

PATIENT INFORMATION:
- Age: {session.age or 'Not specified'}
- Gender: {session.gender or 'Not specified'}
- Location: {session.location or 'Pakistan'}

CHIEF COMPLAINT:
{session.chief_complaint}

ALL SYMPTOMS:
{', '.join(session.symptoms)}

ASSOCIATED SYMPTOMS:
{', '.join(session.associated_symptoms) if session.associated_symptoms else 'None reported'}

DURATION: {session.duration}
SEVERITY: {session.severity}/10

MEDICAL HISTORY:
{', '.join(session.medical_history) if session.medical_history else 'None reported'}

CURRENT MEDICATIONS:
{', '.join(session.current_medications) if session.current_medications else 'None'}

ALLERGIES:
{', '.join(session.allergies) if session.allergies else 'None reported'}

---

As Dr. Sameer, perform a thorough clinical assessment. Think step by step:

1. What is the most likely diagnosis (differential diagnosis)?
2. What is the urgency level?
3. Are there any red flags?
4. What immediate action should be taken?
5. Can this be managed at home or needs medical attention?
6. What OTC medicines might help (considering allergies)?

Provide response in JSON format:
{{
    "thinking_process": [
        "First, I notice...",
        "This combination suggests...",
        "However, I should also consider...",
        "Given the severity and duration..."
    ],
    "urgency": "CRITICAL/HIGH/MODERATE/LOW",
    "urgency_reasoning": "why this urgency level",
    "primary_diagnosis": "most likely condition",
    "differential_diagnoses": [
        {{"condition": "name", "likelihood": "high/medium/low", "reasoning": "why"}}
    ],
    "red_flags": ["any warning signs to watch"],
    "recommended_action": "specific recommendation",
    "care_level": "emergency/urgent_care/clinic/home_care",
    "can_use_otc": true/false,
    "otc_category": "fever/headache/cold_flu/etc if applicable",
    "needs_tests": ["list of tests if needed"],
    "home_care_advice": ["advice for home management"],
    "when_to_seek_immediate_care": ["conditions that warrant immediate medical attention"],
    "follow_up": "when to follow up",
    "patient_message": "empathetic summary for patient in simple language"
}}"""

        ai_response = self.reason(assessment_prompt)

        if not ai_response.success:
            return ai_response

        assessment = ai_response.data
        session.assessment = assessment

        # Add assessment to reasoning chain
        session.reasoning_chain.append({
            "step": "assessment_complete",
            "thought": assessment.get("thinking_process", []),
            "conclusion": {
                "urgency": assessment.get("urgency"),
                "primary_diagnosis": assessment.get("primary_diagnosis"),
                "care_level": assessment.get("care_level")
            },
            "timestamp": datetime.now().isoformat()
        })

        # Build patient-friendly response
        response_parts = []

        # Add thinking process (abbreviated)
        thinking = assessment.get("thinking_process", [])
        if thinking:
            response_parts.append("💭 *My Assessment:*")
            response_parts.append(thinking[-1] if thinking else "Based on your symptoms...")
            response_parts.append("")

        # Urgency indicator
        urgency = assessment.get("urgency", "MODERATE")
        urgency_emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MODERATE": "📋", "LOW": "✅"}.get(urgency, "📋")
        response_parts.append(f"{urgency_emoji} *Urgency Level: {urgency}*")
        response_parts.append("")

        # Main finding
        response_parts.append(f"📍 *Most likely:* {assessment.get('primary_diagnosis', 'Needs further evaluation')}")
        response_parts.append("")

        # Red flags if any
        red_flags = assessment.get("red_flags", [])
        if red_flags:
            response_parts.append("🚨 *Watch for these warning signs:*")
            for flag in red_flags[:3]:
                response_parts.append(f"  • {flag}")
            response_parts.append("")

        # Recommendation
        response_parts.append(f"✅ *My Recommendation:*")
        response_parts.append(assessment.get("recommended_action", "Please consult a doctor"))
        response_parts.append("")

        # OTC recommendations if applicable
        if assessment.get("can_use_otc") and assessment.get("otc_category"):
            otc_response = self._get_otc_recommendations(
                assessment["otc_category"],
                session.allergies,
                session.medical_history
            )
            if otc_response:
                response_parts.append("💊 *Medicine Suggestions:*")
                response_parts.append(otc_response)
                response_parts.append("")

        # Home care if applicable
        home_care = assessment.get("home_care_advice", [])
        if home_care and assessment.get("care_level") in ["home_care", "clinic"]:
            response_parts.append("🏠 *Home Care Tips:*")
            for tip in home_care[:4]:
                response_parts.append(f"  • {tip}")
            response_parts.append("")

        # When to seek immediate care
        when_to_seek = assessment.get("when_to_seek_immediate_care", [])
        if when_to_seek:
            response_parts.append("🏥 *Go to hospital immediately if:*")
            for condition in when_to_seek[:3]:
                response_parts.append(f"  • {condition}")
            response_parts.append("")

        # Emergency contact
        if urgency in ["CRITICAL", "HIGH"]:
            response_parts.append("📞 *Emergency: 1122*")

        # Transition to care planning
        session.state = ConversationState.PLANNING_CARE

        return AgentResponse(
            success=True,
            data={
                "response_type": "assessment",
                "assessment": assessment,
                "urgency": urgency,
                "reasoning_chain": session.reasoning_chain,
                "patient_message": "\n".join(response_parts),
                "care_level": assessment.get("care_level"),
                "needs_followup": True
            },
            reasoning=f"Assessment complete. Urgency: {urgency}. Primary diagnosis: {assessment.get('primary_diagnosis')}",
            confidence=0.85,
            metadata={
                "escalate_to_emergency": urgency == "CRITICAL",
                "suggested_agents": self._get_suggested_agents(assessment)
            }
        )

    def _get_otc_recommendations(self, category: str, allergies: List[str], medical_history: List[str]) -> str:
        """Get OTC recommendations with safety checks"""
        otc_info = OTC_RECOMMENDATIONS.get(category.lower(), None)
        if not otc_info:
            return ""

        # Filter medicines based on allergies and conditions
        safe_medicines = []
        allergies_lower = [a.lower() for a in allergies]
        history_lower = [h.lower() for h in medical_history]

        for med in otc_info.get("medicines", [])[:2]:
            # Check if medicine or its components are in allergies
            med_name_lower = med["name"].lower()
            is_safe = True

            for allergy in allergies_lower:
                if allergy in med_name_lower or med_name_lower in allergy:
                    is_safe = False
                    break

            # Check avoid_if conditions
            for condition in otc_info.get("avoid_if", []):
                condition_lower = condition.lower()
                for hist in history_lower:
                    if hist in condition_lower or condition_lower in hist:
                        is_safe = False
                        break

            if is_safe:
                safe_medicines.append(f"• {med['name']}: {med['dose']}")

        if not safe_medicines:
            return "⚠️ Due to your medical history/allergies, please consult a pharmacist before taking any medicine."

        result = "\n".join(safe_medicines)

        # Add see doctor if conditions
        see_doctor = otc_info.get("see_doctor_if", [])
        if see_doctor:
            result += f"\n\n⚠️ Stop and see doctor if: {see_doctor[0]}"

        return result

    def _get_suggested_agents(self, assessment: Dict[str, Any]) -> List[str]:
        """Determine which other agents should be involved"""
        agents = []

        care_level = assessment.get("care_level", "")
        urgency = assessment.get("urgency", "")

        if urgency == "CRITICAL" or care_level == "emergency":
            agents.extend(["emergency_agent", "guide_agent"])
        elif care_level in ["urgent_care", "clinic"]:
            agents.extend(["guide_agent", "scheduler_agent"])

        # Always suggest insurance check
        agents.append("haqdar_agent")

        return agents

    def _handle_guidance(self, session: PatientSession, message: str) -> AgentResponse:
        """Handle follow-up after providing guidance"""
        # Check if patient has more questions
        return self._continue_or_conclude(session, message)

    def _handle_care_planning(self, session: PatientSession, message: str) -> AgentResponse:
        """Handle care planning phase - orchestrate other agents"""
        message_lower = message.lower()

        # Check what the patient wants to do next
        if any(word in message_lower for word in ["hospital", "doctor", "clinic", "dawaakhana"]):
            return self._plan_hospital_visit(session)
        elif any(word in message_lower for word in ["medicine", "dawa", "pharmacy", "dawai"]):
            return self._plan_medicine_search(session)
        elif any(word in message_lower for word in ["insurance", "sehat card", "sehat sahulat"]):
            return self._plan_insurance_check(session)
        elif any(word in message_lower for word in ["thank", "shukriya", "okay", "theek"]):
            return self._conclude_session(session)
        else:
            return self._offer_next_steps(session)

    def _plan_hospital_visit(self, session: PatientSession) -> AgentResponse:
        """Create plan to hand off to Guide agent for hospital search"""
        session.reasoning_chain.append({
            "step": "care_planning",
            "thought": "Patient wants to find a hospital/doctor. Need to coordinate with Guide agent.",
            "action": "Preparing handoff to Guide agent with medical context",
            "timestamp": datetime.now().isoformat()
        })

        care_plan = {
            "next_agent": "guide_agent",
            "action": "find_hospital",
            "context": {
                "symptoms": session.symptoms,
                "diagnosis": session.assessment.get("primary_diagnosis") if session.assessment else None,
                "urgency": session.assessment.get("urgency") if session.assessment else "MODERATE",
                "recommended_specialty": self._infer_specialty(session),
                "location": session.location
            }
        }
        session.care_plan = care_plan

        specialty = care_plan["context"]["recommended_specialty"]

        patient_message = f"""I'll help you find the right care! 🏥

Based on your symptoms, you should see a *{specialty}*.

Let me connect you with our Guide agent who will:
• Find hospitals near you
• Show available doctors
• Help book an appointment

*What area/city are you in?*
(Aap kis sheher mein hain?)"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "care_planning",
                "care_plan": care_plan,
                "handoff_to": "guide_agent",
                "patient_message": patient_message,
                "reasoning_chain": session.reasoning_chain
            },
            reasoning=f"Planning hospital visit. Recommending {specialty}. Preparing handoff to Guide agent.",
            confidence=0.85
        )

    def _plan_medicine_search(self, session: PatientSession) -> AgentResponse:
        """Create plan to hand off to Yaadgar agent for medicine search"""
        session.reasoning_chain.append({
            "step": "care_planning",
            "thought": "Patient wants medicine information. Need to coordinate with Yaadgar agent.",
            "action": "Preparing handoff to Yaadgar agent with prescription context",
            "timestamp": datetime.now().isoformat()
        })

        care_plan = {
            "next_agent": "yaadgar_agent",
            "action": "find_medicine",
            "context": {
                "diagnosis": session.assessment.get("primary_diagnosis") if session.assessment else None,
                "otc_category": session.assessment.get("otc_category") if session.assessment else None,
                "allergies": session.allergies,
                "location": session.location
            }
        }
        session.care_plan = care_plan

        patient_message = """I'll help you find medicines! 💊

Let me connect you with our Yaadgar agent who will:
• Find pharmacies near you
• Compare medicine prices
• Suggest generic alternatives to save money

*Which medicine are you looking for?*
(Aap ko konsi dawa chahiye?)"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "care_planning",
                "care_plan": care_plan,
                "handoff_to": "yaadgar_agent",
                "patient_message": patient_message,
                "reasoning_chain": session.reasoning_chain
            },
            reasoning="Planning medicine search. Preparing handoff to Yaadgar agent.",
            confidence=0.85
        )

    def _plan_insurance_check(self, session: PatientSession) -> AgentResponse:
        """Create plan to hand off to Haqdar agent for insurance verification"""
        session.reasoning_chain.append({
            "step": "care_planning",
            "thought": "Patient wants to check Sehat Card eligibility. Need to coordinate with Haqdar agent.",
            "action": "Preparing handoff to Haqdar agent",
            "timestamp": datetime.now().isoformat()
        })

        care_plan = {
            "next_agent": "haqdar_agent",
            "action": "check_eligibility",
            "context": {
                "diagnosis": session.assessment.get("primary_diagnosis") if session.assessment else None,
                "care_level": session.assessment.get("care_level") if session.assessment else None
            }
        }
        session.care_plan = care_plan

        patient_message = """I'll help you check your Sehat Sahulat Card! 💳

Let me connect you with our Haqdar agent who will:
• Verify your card status
• Check your coverage amount
• Find empaneled hospitals

*Please provide your CNIC number:*
(Apna CNIC number batayein)

Format: XXXXX-XXXXXXX-X"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "care_planning",
                "care_plan": care_plan,
                "handoff_to": "haqdar_agent",
                "patient_message": patient_message,
                "reasoning_chain": session.reasoning_chain
            },
            reasoning="Planning insurance check. Preparing handoff to Haqdar agent.",
            confidence=0.85
        )

    def _offer_next_steps(self, session: PatientSession) -> AgentResponse:
        """Offer next steps to the patient"""
        urgency = session.assessment.get("urgency", "MODERATE") if session.assessment else "MODERATE"

        if urgency == "CRITICAL":
            patient_message = """🚨 Given the urgency of your situation:

*Please go to the nearest hospital immediately or call 1122*

I can also help you:
1️⃣ Find nearest hospital
2️⃣ Check Sehat Card coverage

*What would you like?*"""
        else:
            patient_message = """Now that we've assessed your condition, I can help you with:

1️⃣ *Find Hospital/Doctor* - Locate healthcare near you
2️⃣ *Find Medicines* - Search pharmacies and compare prices
3️⃣ *Check Sehat Card* - Verify your insurance coverage

*What would you like to do next?*
(Aagey kya karna chahein ge?)"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "offering_next_steps",
                "patient_message": patient_message,
                "reasoning_chain": session.reasoning_chain
            },
            reasoning="Offering next steps for patient care journey.",
            confidence=0.85
        )

    def _conclude_session(self, session: PatientSession) -> AgentResponse:
        """Conclude the session with summary"""
        session.state = ConversationState.COMPLETED

        session.reasoning_chain.append({
            "step": "session_concluded",
            "thought": "Patient is satisfied with the consultation.",
            "summary": {
                "chief_complaint": session.chief_complaint,
                "assessment": session.assessment.get("primary_diagnosis") if session.assessment else "Not assessed",
                "urgency": session.assessment.get("urgency") if session.assessment else "Unknown"
            },
            "timestamp": datetime.now().isoformat()
        })

        patient_message = """Thank you for consulting with me! 🙏

*Remember:*
• Follow the advice given
• Watch for warning signs mentioned
• Don't hesitate to seek medical help if symptoms worsen

*Take care of yourself!*
(Apna khayal rakhein!)

📞 Emergency: 1122

_Type "hi" anytime to start a new consultation._"""

        return AgentResponse(
            success=True,
            data={
                "response_type": "session_concluded",
                "session_summary": {
                    "chief_complaint": session.chief_complaint,
                    "symptoms": session.symptoms,
                    "assessment": session.assessment,
                    "care_plan": session.care_plan,
                    "reasoning_chain": session.reasoning_chain
                },
                "patient_message": patient_message
            },
            reasoning="Session concluded. Provided summary and farewell.",
            confidence=0.9
        )

    def _continue_or_conclude(self, session: PatientSession, message: str) -> AgentResponse:
        """Determine if session should continue or conclude"""
        message_lower = message.lower()

        if any(word in message_lower for word in ["thank", "shukriya", "okay", "bye", "khuda hafiz"]):
            return self._conclude_session(session)
        else:
            return self._offer_next_steps(session)

    def _infer_specialty(self, session: PatientSession) -> str:
        """Infer medical specialty based on symptoms and assessment"""
        symptoms_text = " ".join(session.symptoms + session.associated_symptoms).lower()
        diagnosis = (session.assessment.get("primary_diagnosis", "") if session.assessment else "").lower()

        specialty_map = {
            "general physician": ["fever", "cold", "flu", "bukhar", "general"],
            "cardiologist": ["heart", "chest pain", "dil", "blood pressure"],
            "pulmonologist": ["breathing", "lungs", "asthma", "saans", "cough"],
            "gastroenterologist": ["stomach", "digestion", "pait", "vomit", "diarrhea"],
            "neurologist": ["headache", "sar dard", "migraine", "seizure", "nerves"],
            "orthopedic": ["bone", "joint", "haddi", "fracture", "pain leg", "pain arm"],
            "dermatologist": ["skin", "rash", "jild", "allergy skin"],
            "ENT specialist": ["ear", "nose", "throat", "kaan", "naak", "gala"],
            "pediatrician": ["child", "bacha", "baby"],
            "gynecologist": ["pregnancy", "women", "period", "menstrual"]
        }

        for specialty, keywords in specialty_map.items():
            for keyword in keywords:
                if keyword in symptoms_text or keyword in diagnosis:
                    return specialty

        return "general physician"

    # Legacy methods for backward compatibility
    def assess_symptoms(self, symptoms: List[str], patient_info: Dict[str, Any]) -> AgentResponse:
        """Legacy method - now routes through conversation"""
        phone = patient_info.get("phone", "unknown")
        message = ", ".join(symptoms)
        return self.process_message(phone, message, patient_info)

    def handle_symptom_assessment(self, message: AgentMessage) -> AgentResponse:
        """Handle symptom assessment request from other agents"""
        symptoms = message.payload.get("symptoms", [])
        patient_info = message.payload.get("patient_info", {})
        return self.assess_symptoms(symptoms, patient_info)

    def handle_continue_conversation(self, message: AgentMessage) -> AgentResponse:
        """Handle continuation of existing conversation"""
        phone = message.payload.get("phone", "unknown")
        text = message.payload.get("message", "")
        return self.process_message(phone, text)

    def get_emergency_protocol(self, emergency_type: str) -> Dict[str, Any]:
        """Get emergency protocol by type"""
        return EMERGENCY_PROTOCOLS.get(emergency_type, EMERGENCY_PROTOCOLS["chest_pain"])

    def get_otc_info(self, category: str) -> Dict[str, Any]:
        """Get OTC medicine information by category"""
        return OTC_RECOMMENDATIONS.get(category.lower(), {})
