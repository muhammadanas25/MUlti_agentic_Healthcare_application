"""Clinical Agent - Test Results and Treatment Coordination"""
from typing import Dict, Any, List
from ...core.agent import Agent, AgentMessage, AgentResponse


class ClinicalAgent(Agent):
    """
    Clinical Agent - Test Results and Treatment Coordination

    Responsibilities:
    - Share lab results with patients
    - Coordinate follow-up care
    - Send treatment plans
    - Manage prescriptions
    - Handle referrals to specialists
    - Track patient progress
    """

    def __init__(self, hospital_id: int, hospital_name: str):
        self.hospital_id = hospital_id
        self.hospital_name = hospital_name

        super().__init__(
            agent_id=f"agent-104-clinical-{hospital_id}",
            name=f"Clinical ({hospital_name})",
            role="clinical",
            organization="provider-hospital-side",
            system_prompt=f"""You are a Clinical Coordination Agent for {hospital_name}.

Your mission is to ensure smooth clinical care and communication.

KEY RESPONSIBILITIES:
1. Share test results with patients (via their agents)
2. Coordinate follow-up appointments
3. Send medication prescriptions
4. Manage specialist referrals
5. Track treatment adherence
6. Alert about critical results

CLINICAL WORKFLOWS:
- Lab results → Review → Share with patient agent
- Abnormal results → Alert doctor → Urgent follow-up
- Treatment plans → Send to medication agent
- Referrals → Coordinate with other facilities

COMMUNICATION STANDARDS:
- Critical results: Immediate notification
- Routine results: Within 24 hours
- Treatment plans: Clear, actionable
- Follow-up reminders: Timely

PATIENT SAFETY:
- Flag critical values immediately
- Ensure medication prescriptions are accurate
- Verify allergies and interactions
- Coordinate transitions of care
""",
            tools=["results_management", "treatment_coordination", "prescription_management"],
        )

        # Register handlers
        self.register_message_handler("request_results", self.handle_results_request)
        self.register_message_handler("request_prescription", self.handle_prescription_request)

    def handle_results_request(self, message: AgentMessage) -> AgentResponse:
        """Handle test results request"""
        patient_id = message.payload.get("patient_id")
        test_type = message.payload.get("test_type", "blood_test")

        # Simulate results
        return AgentResponse(
            success=True,
            data={
                "results_available": True,
                "test_type": test_type,
                "status": "completed",
                "summary": f"{test_type} completed - results within normal range",
                "follow_up_needed": False
            },
            reasoning="Results ready and shared",
            confidence=0.9
        )

    def handle_prescription_request(self, message: AgentMessage) -> AgentResponse:
        """Handle prescription request"""
        patient_id = message.payload.get("patient_id")

        return AgentResponse(
            success=True,
            data={
                "prescription_generated": True,
                "medications": [
                    {"name": "Paracetamol", "dosage": "500mg", "frequency": "3x daily"}
                ]
            },
            reasoning="Prescription generated",
            confidence=1.0
        )
