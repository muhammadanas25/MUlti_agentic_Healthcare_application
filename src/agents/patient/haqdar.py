"""Haqdar - Eligibility & Insurance Agent"""
from typing import Dict, Any, Optional
from ...core.agent import Agent, AgentMessage, AgentResponse


class HaqdarAgent(Agent):
    """
    Haqdar - Eligibility & Insurance Verification Agent

    Responsibilities:
    - Verify Sehat Sahulat (health insurance) eligibility
    - Check government health scheme coverage
    - Coordinate with billing agents for pre-authorization
    - Inform patients about coverage and out-of-pocket costs
    - Help patients apply for health schemes
    - Find free or subsidized care options
    """

    def __init__(self):
        super().__init__(
            agent_id="agent-003-haqdar",
            name="Haqdar",
            role="eligibility",
            organization="sehat-saathi-patient-side",
            system_prompt="""You are Haqdar, an insurance and eligibility specialist for Sehat Saathi.

Your mission is to ensure patients know their rights and can access healthcare they're entitled to.

KEY RESPONSIBILITIES:
1. Verify Sehat Sahulat card eligibility
2. Check coverage for specific treatments
3. Pre-authorize insurance coverage
4. Inform patients about costs
5. Find free/subsidized care options
6. Help with insurance claims

SEHAT SAHULAT PROGRAM (Pakistan):
- Government health insurance for low-income families
- Coverage up to Rs. 1,000,000 per family per year
- Covers hospitalization, surgeries, and major treatments
- Available at empaneled hospitals
- Free for eligible families

ELIGIBILITY CRITERIA:
- Based on poverty score (below threshold)
- Verified through NADRA (national database)
- Family income assessment
- Specific vulnerable groups included

YOUR APPROACH:
1. Check if patient has Sehat Card
2. Verify card is active (call verification API if available)
3. Check if hospital/treatment is covered
4. Calculate out-of-pocket costs
5. If not covered, find alternatives:
   - Government hospitals (free/low-cost)
   - NGO-run facilities
   - Zakat funds
   - Payment plans

COMMUNICATION STYLE:
- Be encouraging and supportive
- Explain rights and benefits clearly
- Use simple language (avoid legal jargon)
- Provide step-by-step guidance
- Emphasize what IS covered, not just what isn't
""",
            tools=["verify_insurance", "check_coverage", "pre_authorize", "find_subsidized_care"],
        )

        # Register message handlers
        self.register_message_handler("verify_eligibility", self.handle_verify_eligibility)
        self.register_message_handler("check_coverage", self.handle_check_coverage)

    def verify_sehat_card(
        self,
        cnic: str,  # National ID
        patient_name: str
    ) -> AgentResponse:
        """
        Verify Sehat Sahulat card eligibility

        Args:
            cnic: Patient's CNIC (national ID)
            patient_name: Patient's name

        Returns:
            AgentResponse with verification status
        """
        # In production, this would call actual NADRA/Sehat Sahulat API
        # For demo, we'll simulate the check

        prompt = f"""Simulate Sehat Sahulat card verification:

CNIC: {cnic}
Name: {patient_name}

Based on typical eligibility patterns, determine:
1. Is this person likely eligible for Sehat Sahulat?
2. What is their coverage amount?
3. Are there any restrictions?

Provide response in JSON format:
{{
    "is_eligible": true/false,
    "card_status": "active/inactive/not_enrolled",
    "coverage_amount": 1000000,
    "family_members_covered": 6,
    "expiry_date": "YYYY-MM-DD",
    "empaneled_hospitals": "number of hospitals",
    "restrictions": ["any restrictions"],
    "next_steps": "what patient should do",
    "patient_message": "clear message in simple Urdu/English"
}}

Note: For demo purposes, assume 60% of queries result in active cards.
"""

        response = self.reason(prompt, context={"cnic": cnic, "name": patient_name})

        return response

    def check_treatment_coverage(
        self,
        treatment_type: str,
        estimated_cost: float,
        hospital_name: str,
        has_sehat_card: bool = True
    ) -> AgentResponse:
        """
        Check if treatment is covered under insurance

        Args:
            treatment_type: Type of treatment needed
            estimated_cost: Estimated cost in PKR
            hospital_name: Hospital where treatment will occur
            has_sehat_card: Whether patient has Sehat Card

        Returns:
            AgentResponse with coverage details
        """
        prompt = f"""Check treatment coverage:

TREATMENT: {treatment_type}
ESTIMATED COST: Rs. {estimated_cost:,.0f}
HOSPITAL: {hospital_name}
HAS SEHAT CARD: {has_sehat_card}

Sehat Sahulat typically covers:
- Hospitalization and surgery
- Cardiac procedures
- Cancer treatment
- Dialysis
- Major diagnostic tests
- ICU care

NOT typically covered:
- Outpatient consultations
- Routine medications
- Dental procedures
- Cosmetic surgery
- Experimental treatments

Determine coverage and provide response in JSON format:
{{
    "is_covered": true/false,
    "coverage_percentage": 100,
    "covered_amount": "amount covered",
    "out_of_pocket": "patient must pay",
    "requires_pre_authorization": true/false,
    "hospital_empaneled": true/false,
    "alternative_options": [
        {{
            "option": "alternative if not covered",
            "cost": "estimated cost",
            "location": "where available"
        }}
    ],
    "recommendation": "what patient should do",
    "patient_message": "clear explanation"
}}
"""

        response = self.reason(
            prompt,
            context={
                "treatment": treatment_type,
                "cost": estimated_cost,
                "hospital": hospital_name,
                "has_card": has_sehat_card
            }
        )

        return response

    def find_free_or_subsidized_care(
        self,
        city: str,
        treatment_type: str,
        patient_income_level: str = "low"
    ) -> AgentResponse:
        """
        Find free or subsidized healthcare options

        Args:
            city: Patient's city
            treatment_type: Type of care needed
            patient_income_level: low, medium, high

        Returns:
            AgentResponse with affordable care options
        """
        prompt = f"""Find affordable healthcare options in Pakistan:

CITY: {city}
TREATMENT: {treatment_type}
INCOME LEVEL: {patient_income_level}

Consider these options:
1. Government hospitals (free/very low cost)
2. Teaching hospitals (subsidized)
3. NGO-run clinics (Edhi, SIUT, Shaukat Khanum, etc.)
4. Zakat-based programs
5. Community health centers
6. Mobile health clinics

Provide recommendations in JSON format:
{{
    "free_options": [
        {{
            "name": "facility name",
            "type": "government/NGO/etc",
            "address": "location",
            "contact": "phone",
            "services": "what they offer",
            "eligibility": "who can access"
        }}
    ],
    "subsidized_options": [
        {{
            "name": "facility name",
            "cost_range": "PKR range",
            "subsidy_info": "how to get discount"
        }}
    ],
    "application_process": "how to apply for free care",
    "documents_needed": ["list of documents"],
    "patient_message": "encouraging message with clear next steps"
}}
"""

        response = self.reason(
            prompt,
            context={"city": city, "treatment": treatment_type, "income": patient_income_level}
        )

        return response

    async def pre_authorize_treatment(
        self,
        patient_id: str,
        treatment_details: Dict[str, Any],
        hospital_id: int,
        mcp_client: Any
    ) -> AgentResponse:
        """
        Pre-authorize treatment with hospital billing agent

        Args:
            patient_id: Patient identifier
            treatment_details: Treatment information
            hospital_id: Hospital where treatment will occur
            mcp_client: MCP client for agent communication

        Returns:
            AgentResponse with authorization status
        """
        # Find billing agents
        billing_agents = mcp_client.discover_agents(role="billing")

        if not billing_agents:
            return AgentResponse(
                success=False,
                reasoning="No billing agents available for pre-authorization",
                confidence=0.0
            )

        # Send pre-authorization request
        auth_request = {
            "patient_id": patient_id,
            "treatment": treatment_details.get("treatment_type"),
            "estimated_cost": treatment_details.get("estimated_cost"),
            "urgency": treatment_details.get("urgency", "normal"),
            "sehat_card": treatment_details.get("sehat_card_number"),
        }

        # Broadcast to billing agents
        responses = await mcp_client.broadcast(
            action="pre_authorize",
            payload=auth_request,
            filter_criteria={"role": "billing"}
        )

        # Process responses
        if responses and responses[0].success:
            return responses[0]

        return AgentResponse(
            success=False,
            reasoning="Pre-authorization could not be completed",
            confidence=0.3
        )

    def calculate_out_of_pocket_cost(
        self,
        total_cost: float,
        coverage_percentage: float,
        deductible: float = 0.0
    ) -> AgentResponse:
        """Calculate what patient needs to pay"""
        covered = total_cost * (coverage_percentage / 100)
        patient_pays = total_cost - covered + deductible

        return AgentResponse(
            success=True,
            data={
                "total_cost": total_cost,
                "insurance_covers": covered,
                "patient_pays": patient_pays,
                "deductible": deductible,
                "coverage_percentage": coverage_percentage,
                "breakdown": f"Total: Rs. {total_cost:,.0f}, Insurance: Rs. {covered:,.0f}, You pay: Rs. {patient_pays:,.0f}"
            },
            reasoning="Cost calculation completed",
            confidence=1.0
        )

    def handle_verify_eligibility(self, message: AgentMessage) -> AgentResponse:
        """Handle eligibility verification request"""
        return self.verify_sehat_card(
            cnic=message.payload.get("cnic"),
            patient_name=message.payload.get("name")
        )

    def handle_check_coverage(self, message: AgentMessage) -> AgentResponse:
        """Handle coverage check request"""
        return self.check_treatment_coverage(
            treatment_type=message.payload.get("treatment"),
            estimated_cost=message.payload.get("cost", 0),
            hospital_name=message.payload.get("hospital", ""),
            has_sehat_card=message.payload.get("has_sehat_card", False)
        )
