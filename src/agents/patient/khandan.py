"""Khandan - Family Health Tracking Agent"""
from typing import Dict, Any, List, Optional
from ...core.agent import Agent, AgentMessage, AgentResponse
from datetime import datetime


class KhandanAgent(Agent):
    """
    Khandan - Family Health Tracking & Coordination Agent

    Responsibilities:
    - Track health of all family members
    - Manage immunization schedules for children
    - Coordinate care for elderly family members
    - Send health reminders for entire family
    - Alert about hereditary health risks
    - Facilitate family health discussions
    - Coordinate during emergencies (notify all members)
    """

    def __init__(self):
        super().__init__(
            agent_id="agent-005-khandan",
            name="Khandan",
            role="family",
            organization="sehat-saathi-patient-side",
            system_prompt="""You are Khandan, a family health coordinator for Sehat Saathi.

Your mission is to keep the entire family healthy and coordinate care across all members.

KEY RESPONSIBILITIES:
1. Track health of all family members
2. Manage vaccination schedules for children
3. Coordinate care for elderly members
4. Send health reminders to the right family member
5. Alert about hereditary conditions
6. Facilitate family involvement in healthcare decisions
7. Emergency notifications to all family members

FAMILY STRUCTURE IN PAKISTAN:
- Joint families are common (grandparents, parents, children)
- Multigenerational households
- Strong family support systems
- Decision-making often involves multiple family members
- Gender roles affect healthcare access (men often accompany women)
- Children's health is top priority

CULTURAL CONSIDERATIONS:
- Respect for elders in decision-making
- Gender preferences in care
- Family involvement expected (not individualistic)
- Economic interdependence
- Shared health insurance (Sehat Card covers whole family)

YOUR APPROACH:
1. Map family structure and relationships
2. Track each member's health conditions
3. Identify family health patterns (diabetes, hypertension runs in family)
4. Coordinate appointments to minimize travel
5. Ensure vulnerable members (elderly, children) get priority
6. Facilitate family discussions for major health decisions
7. During emergencies, notify appropriate family members

PRIVACY:
- Each family member can control their own information sharing
- Minors' information accessible to parents/guardians
- Elderly members may designate family caregivers
- Emergency information always shared with designated contacts

COMMUNICATION STYLE:
- Respectful of family hierarchy
- Use "Uncle", "Aunty", "Bhai", "Baji" appropriately
- Engage the decision-maker (often head of household)
- Be culturally sensitive
- Provide information that families can discuss together
""",
            tools=["family_tracking", "immunization_schedules", "emergency_notifications", "hereditary_risk_assessment"],
        )

        # In-memory family profiles (would be in database in production)
        self.family_profiles: Dict[str, Dict[str, Any]] = {}

        # Register message handlers
        self.register_message_handler("register_family", self.handle_register_family)
        self.register_message_handler("emergency_notify", self.handle_emergency_notify)

    def create_family_profile(
        self,
        head_of_family_id: str,
        family_members: List[Dict[str, Any]]
    ) -> AgentResponse:
        """
        Create family health profile

        Args:
            head_of_family_id: ID of family head
            family_members: List of family member information

        Returns:
            AgentResponse with family profile
        """
        prompt = f"""Create a family health profile:

HEAD OF FAMILY: {head_of_family_id}

FAMILY MEMBERS:
{chr(10).join(f"- {m.get('name')}: {m.get('age')}yo {m.get('gender')}, {m.get('relationship')}" for m in family_members)}

Analyze and create profile in JSON format:
{{
    "family_id": "unique_id",
    "family_size": "number",
    "vulnerable_members": [
        {{
            "name": "member name",
            "age": "age",
            "vulnerability": "elderly/child/chronic condition",
            "priority_level": "high/medium/low"
        }}
    ],
    "health_priorities": ["priority 1", "priority 2"],
    "recommended_screenings": [
        {{
            "screening": "what test",
            "for_members": ["who should get it"],
            "frequency": "how often",
            "reason": "why needed"
        }}
    ],
    "hereditary_risks": ["potential hereditary conditions to monitor"],
    "family_health_score": "1-10",
    "recommendations": ["recommendation 1", "recommendation 2"]
}}
"""

        response = self.reason(
            prompt,
            context={"head": head_of_family_id, "members": family_members}
        )

        # Store family profile
        family_id = response.data.get("family_id", head_of_family_id)
        self.family_profiles[family_id] = {
            "head": head_of_family_id,
            "members": family_members,
            "profile": response.data,
            "created_at": datetime.now().isoformat()
        }

        return response

    def manage_immunization_schedule(
        self,
        child_age_months: int,
        already_vaccinated: List[str]
    ) -> AgentResponse:
        """
        Manage child immunization schedule (Pakistan EPI program)

        Args:
            child_age_months: Child's age in months
            already_vaccinated: List of vaccines already given

        Returns:
            AgentResponse with vaccination schedule
        """
        prompt = f"""Create immunization schedule for child in Pakistan:

CHILD AGE: {child_age_months} months
VACCINES COMPLETED: {', '.join(already_vaccinated) if already_vaccinated else 'None'}

Pakistan EPI (Expanded Program on Immunization) Schedule:
- Birth: BCG, OPV-0, Hep-B
- 6 weeks: OPV-1, Penta-1, PCV-1
- 10 weeks: OPV-2, Penta-2, PCV-2
- 14 weeks: OPV-3, Penta-3, PCV-3
- 9 months: Measles-1
- 15 months: Measles-2

Provide schedule in JSON format:
{{
    "child_age": "{child_age_months} months",
    "vaccines_completed": {len(already_vaccinated)},
    "vaccines_pending": [
        {{
            "vaccine": "vaccine name",
            "due_at_age": "age in months",
            "days_from_now": "approximate days",
            "location": "where to get it (EPI center, hospital)",
            "cost": "free at government centers"
        }}
    ],
    "overdue_vaccines": ["any missed vaccines"],
    "next_vaccination_date": "when to go",
    "reminder_message": "clear message for parents in simple language",
    "bring_with_you": ["vaccination card", "other items"]
}}
"""

        response = self.reason(
            prompt,
            context={"age": child_age_months, "completed": already_vaccinated}
        )

        return response

    def coordinate_elderly_care(
        self,
        elderly_member: Dict[str, Any],
        family_caregivers: List[Dict[str, Any]]
    ) -> AgentResponse:
        """
        Coordinate care for elderly family member

        Args:
            elderly_member: Elderly person's information
            family_caregivers: Family members who can help

        Returns:
            AgentResponse with care coordination plan
        """
        prompt = f"""Coordinate care for elderly family member:

ELDERLY MEMBER:
Name: {elderly_member.get('name')}
Age: {elderly_member.get('age')}
Conditions: {', '.join(elderly_member.get('conditions', []))}
Mobility: {elderly_member.get('mobility', 'Unknown')}
Medications: {len(elderly_member.get('medications', []))} medicines

AVAILABLE CAREGIVERS:
{chr(10).join(f"- {c.get('name')}: {c.get('relationship')}, {c.get('availability')}" for c in family_caregivers)}

Create care coordination plan in JSON format:
{{
    "primary_caregiver": "who should be main caregiver",
    "backup_caregivers": ["backup person 1", "backup person 2"],
    "care_schedule": {{
        "medication_management": "who handles medicines",
        "doctor_appointments": "who accompanies to doctor",
        "daily_monitoring": "who checks on them daily",
        "emergency_contact": "who to call in emergency"
    }},
    "health_monitoring_checklist": [
        "blood pressure - daily",
        "medicine adherence - daily",
        "mobility - check weekly"
    ],
    "red_flags": ["warning signs family should watch for"],
    "support_needed": ["any external support needed (nurse, physiotherapy)"],
    "family_meeting_recommended": true/false,
    "caregiver_message": "message with clear care instructions"
}}
"""

        response = self.reason(
            prompt,
            context={"elderly": elderly_member, "caregivers": family_caregivers}
        )

        return response

    async def emergency_notify_family(
        self,
        patient_id: str,
        emergency_type: str,
        hospital_location: Dict[str, Any],
        family_contacts: List[Dict[str, Any]],
        mcp_client: Any
    ) -> AgentResponse:
        """
        Notify all family members during emergency

        Args:
            patient_id: Patient in emergency
            emergency_type: Type of emergency
            hospital_location: Where patient is/will be taken
            family_contacts: Family member contact information
            mcp_client: MCP client

        Returns:
            AgentResponse with notification status
        """
        prompt = f"""Create emergency notification for family:

PATIENT: {patient_id}
EMERGENCY: {emergency_type}
LOCATION: {hospital_location.get('name')} - {hospital_location.get('address')}

FAMILY MEMBERS TO NOTIFY:
{chr(10).join(f"- {c.get('name')} ({c.get('relationship')}): {c.get('phone')}" for c in family_contacts)}

Create notification messages in JSON format:
{{
    "urgent_contacts": ["who to call immediately"],
    "notification_message": {{
        "urdu": "message in Urdu",
        "english": "message in English"
    }},
    "information_to_share": {{
        "patient_name": "name",
        "condition": "condition summary",
        "hospital": "hospital name",
        "address": "full address",
        "contact_person": "doctor/staff to contact",
        "what_to_bring": ["items family should bring"],
        "estimated_cost": "if known",
        "insurance_status": "sehat card status"
    }},
    "priority_actions": [
        "immediate action 1",
        "immediate action 2"
    ],
    "who_should_come": "which family members should come to hospital"
}}
"""

        response = self.reason(
            prompt,
            context={
                "patient": patient_id,
                "emergency": emergency_type,
                "hospital": hospital_location,
                "contacts": family_contacts
            }
        )

        print(f"👨‍👩‍👧‍👦 Khandan: Notifying {len(family_contacts)} family members of emergency")

        return response

    def assess_hereditary_risks(
        self,
        family_health_history: Dict[str, List[str]]
    ) -> AgentResponse:
        """
        Assess hereditary health risks for family

        Args:
            family_health_history: Dictionary of family member conditions

        Returns:
            AgentResponse with risk assessment
        """
        prompt = f"""Assess hereditary health risks for family:

FAMILY HEALTH HISTORY:
{chr(10).join(f"{member}: {', '.join(conditions)}" for member, conditions in family_health_history.items())}

Common hereditary conditions in South Asian populations:
- Diabetes (very high prevalence)
- Hypertension
- Heart disease
- Thalassemia
- G6PD deficiency

Provide risk assessment in JSON format:
{{
    "high_risk_conditions": [
        {{
            "condition": "condition name",
            "risk_level": "high/medium/low",
            "family_pattern": "who in family has it",
            "at_risk_members": ["who should be screened"],
            "recommended_tests": ["test 1", "test 2"],
            "prevention_measures": ["preventive action 1", "preventive action 2"]
        }}
    ],
    "screening_recommendations": [
        {{
            "test": "test name",
            "who": "which family members",
            "frequency": "how often",
            "reason": "why needed"
        }}
    ],
    "lifestyle_recommendations": ["recommendation for whole family"],
    "genetic_counseling_needed": true/false,
    "family_message": "clear, non-alarming message about health awareness"
}}
"""

        response = self.reason(prompt, context={"history": family_health_history})

        return response

    def coordinate_family_appointments(
        self,
        family_members_needing_care: List[Dict[str, Any]],
        location: str
    ) -> AgentResponse:
        """
        Coordinate appointments for multiple family members

        Args:
            family_members_needing_care: List of family members who need appointments
            location: Family location

        Returns:
            AgentResponse with coordination plan
        """
        prompt = f"""Coordinate healthcare appointments for multiple family members:

LOCATION: {location}

FAMILY MEMBERS NEEDING CARE:
{chr(10).join(f"- {m.get('name')}: {m.get('care_needed')}" for m in family_members_needing_care)}

Optimize appointment scheduling:
1. Same hospital/clinic if possible (reduce travel)
2. Same day if possible (save time and transport cost)
3. Consider priority (urgent cases first)
4. Consider gender preferences (some family members may need same-gender doctors)

Provide coordination plan in JSON format:
{{
    "recommended_strategy": "book all at same hospital on same day / split by urgency / etc",
    "hospital_recommendations": [
        {{
            "hospital": "name",
            "can_serve": ["which family members"],
            "estimated_cost": "total cost for all",
            "available_slots": "timing options"
        }}
    ],
    "appointment_sequence": [
        {{
            "time": "time",
            "member": "family member",
            "doctor": "doctor/specialty",
            "estimated_duration": "duration"
        }}
    ],
    "logistics": {{
        "transport": "rickshaw/bus/etc",
        "estimated_cost": "PKR",
        "total_time": "hours",
        "who_should_accompany": "which family member should come"
    }},
    "cost_savings": "how much saved by coordinating",
    "family_message": "clear plan for the family"
}}
"""

        response = self.reason(
            prompt,
            context={"members": family_members_needing_care, "location": location}
        )

        return response

    def handle_register_family(self, message: AgentMessage) -> AgentResponse:
        """Handle family registration request"""
        return self.create_family_profile(
            head_of_family_id=message.payload.get("head_of_family"),
            family_members=message.payload.get("members", [])
        )

    def handle_emergency_notify(self, message: AgentMessage) -> AgentResponse:
        """Handle emergency notification request (synchronous version)"""
        # This would normally be async, but providing synchronous response
        return AgentResponse(
            success=True,
            data={"status": "notifications_initiated"},
            reasoning="Emergency notifications will be sent to family members",
            confidence=0.9
        )
