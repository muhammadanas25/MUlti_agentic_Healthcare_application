"""Emergency Agent - Critical Care Coordination"""
from typing import Dict, Any
import random
from ...core.agent import Agent, AgentMessage, AgentResponse


class EmergencyAgent(Agent):
    """
    Emergency Agent - Critical Care and Ambulance Coordination

    Responsibilities:
    - Handle emergency case broadcasts
    - Assess hospital capacity for emergencies
    - Coordinate ambulance dispatch
    - Reserve resources for critical patients
    - Communicate with other emergency agents
    - Triage and prioritize emergency cases
    """

    def __init__(self, hospital_id: int, hospital_name: str):
        self.hospital_id = hospital_id
        self.hospital_name = hospital_name

        super().__init__(
            agent_id=f"agent-105-emergency-{hospital_id}",
            name=f"Emergency ({hospital_name})",
            role="emergency",
            organization="provider-hospital-side",
            system_prompt=f"""You are an Emergency Coordination Agent for {hospital_name}.

Your mission is to save lives by coordinating emergency care efficiently.

KEY RESPONSIBILITIES:
1. Respond to emergency broadcasts from patient agents
2. Assess hospital capacity for emergency cases
3. Coordinate with ambulance services (1122)
4. Reserve ICU beds and equipment for critical cases
5. Alert emergency team (doctors, nurses)
6. Coordinate with other hospitals if at capacity

EMERGENCY TRIAGE:
- RED (Critical): Life-threatening, immediate care
- ORANGE (Urgent): Serious, care within minutes
- YELLOW (Semi-urgent): Can wait 30-60 minutes
- GREEN (Non-urgent): Can wait hours

DECISION CRITERIA FOR ACCEPTING EMERGENCIES:
1. Severity of case
2. ICU bed availability
3. Specialist availability (cardiology, neurology, trauma)
4. Equipment availability (ventilators, etc.)
5. Distance from patient
6. Current ER load

COLLABORATION:
- Coordinate with Resource Agent for bed/equipment
- Work with Scheduler Agent for emergency slots
- Negotiate with other Emergency Agents for overflow
- Alert Clinical Agent to prepare for admission

EMERGENCY RESPONSE PROTOCOL:
1. Receive emergency broadcast
2. Assess capacity (beds, staff, equipment)
3. Evaluate patient condition vs. capabilities
4. Respond with acceptance/referral
5. If accepting: Reserve resources immediately
6. Alert emergency team
""",
            tools=["emergency_response", "capacity_assessment", "ambulance_coordination"],
        )

        # Register handlers
        self.register_message_handler("emergency_request", self.handle_emergency_request)

    def handle_emergency_request(self, message: AgentMessage) -> AgentResponse:
        """Handle emergency case request"""
        payload = message.payload
        condition = payload.get("condition", "unknown")
        severity = payload.get("severity", "moderate")
        patient_location = payload.get("patient_location", [0, 0])

        # Assess our capacity
        can_accept = random.choice([True, True, False])  # 66% can accept
        icu_available = random.randint(0, 3)
        distance_km = random.uniform(2.0, 10.0)
        eta_minutes = int(distance_km * 3)  # Rough estimate

        prompt = f"""Emergency case request:

CONDITION: {condition}
SEVERITY: {severity}
PATIENT LOCATION: {patient_location}
DISTANCE TO OUR HOSPITAL: {distance_km:.1f} km

OUR CAPACITY:
- ICU Beds Available: {icu_available}
- Emergency Team: On duty
- Can Accept: {can_accept}

Respond to emergency request in JSON format:
{{
    "can_accept": true/false,
    "hospital_name": "{self.hospital_name}",
    "hospital_id": {self.hospital_id},
    "icu_beds_available": {icu_available},
    "distance_km": {distance_km:.1f},
    "eta_minutes": {eta_minutes},
    "resources_available": {{
        "cardiology_team": "yes/no",
        "ventilators": "available/limited/none",
        "trauma_team": "yes/no"
    }},
    "recommendation": "accept/refer_to_other",
    "reasoning": "why accepting or not"
}}

If cannot accept, suggest keeping resources on standby as backup.
"""

        response = self.reason(
            prompt,
            context={
                "condition": condition,
                "severity": severity,
                "capacity": {"icu_beds": icu_available, "can_accept": can_accept}
            }
        )

        if can_accept and response.data.get("can_accept"):
            # Reserve resources
            print(f"🚨 {self.hospital_name}: ACCEPTING emergency case - {condition}")
            print(f"   → ICU bed reserved, emergency team alerted")
        elif response.data.get("can_accept") == False:
            print(f"   {self.hospital_name}: Cannot accept (at capacity), standing by as backup")

        return response
