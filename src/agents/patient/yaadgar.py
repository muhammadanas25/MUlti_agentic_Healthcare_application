"""Yaadgar - Medication Management Agent"""
from typing import Dict, Any, List, Optional
from ...core.agent import Agent, AgentMessage, AgentResponse
from ...database.manager import get_db_manager


class YaadgarAgent(Agent):
    """
    Yaadgar - Medication Reminders & Pharmacy Coordination Agent

    Responsibilities:
    - Send medication reminders
    - Find medicines at nearby pharmacies
    - Compare prices across pharmacies
    - Coordinate with pharmacy resource agents
    - Suggest generic alternatives
    - Track medication adherence
    - Provide drug interaction warnings
    """

    def __init__(self):
        super().__init__(
            agent_id="agent-004-yaadgar",
            name="Yaadgar",
            role="medication",
            organization="sehat-saathi-patient-side",
            system_prompt="""You are Yaadgar, a medication management specialist for Sehat Saathi.

Your mission is to help patients take their medicines correctly and find affordable options.

KEY RESPONSIBILITIES:
1. Remind patients to take medications on time
2. Find medicines at nearby pharmacies
3. Compare prices and suggest cheaper alternatives
4. Coordinate with pharmacy agents for stock availability
5. Warn about drug interactions
6. Help with medication adherence

MEDICATION ADHERENCE CHALLENGES IN PAKISTAN:
- Cost is a major barrier
- Forgetfulness (especially for elderly)
- Complex regimens
- Language barriers on medicine labels
- Confusion about generic vs brand names
- Lack of understanding about importance

YOUR APPROACH:
1. Set up simple reminder schedules
2. Explain medicine purpose in simple language
3. Always look for generic alternatives (cheaper)
4. Negotiate with pharmacies for best prices
5. Suggest pill boxes for complex regimens
6. Involve family members for elderly patients

IMPORTANT CONSIDERATIONS:
- Many chronic disease patients (diabetes, hypertension, heart disease)
- Cost-sensitive population
- Generic medicines are safe and DRAP-approved
- Some medicines require prescription
- Stock-outs are common for certain medicines

COMMUNICATION STYLE:
- Be patient and understanding
- Use simple medicine names (not just chemical names)
- Explain dosage clearly (morning/evening, with/without food)
- Provide reminders in Urdu if preferred
- Encourage adherence with positive reinforcement
""",
            tools=["medication_reminders", "pharmacy_search", "price_comparison", "drug_interaction_check"],
        )

        self.db = get_db_manager()

        # Register message handlers
        self.register_message_handler("find_medicine", self.handle_find_medicine)
        self.register_message_handler("check_interactions", self.handle_check_interactions)

    def find_medicine(
        self,
        medicine_name: str,
        patient_location: str,
        budget: Optional[float] = None
    ) -> AgentResponse:
        """
        Find medicine at pharmacies

        Args:
            medicine_name: Name of medicine
            patient_location: Patient's location
            budget: Maximum budget in PKR

        Returns:
            AgentResponse with pharmacy options
        """
        # Search in database
        medicines = self.db.search_medicines(
            name=medicine_name,
            max_price=budget,
            limit=10
        )

        if not medicines:
            return AgentResponse(
                success=False,
                data=None,
                reasoning=f"Medicine '{medicine_name}' not found in database",
                confidence=0.0
            )

        # Analyze options
        prompt = f"""Patient is looking for {medicine_name} in {patient_location}.
Budget: Rs. {budget if budget else 'No limit specified'}

AVAILABLE OPTIONS:
{self._format_medicines_for_prompt(medicines)}

Analyze and provide recommendation in JSON format:
{{
    "recommended_option": {{
        "medicine_name": "name",
        "company": "manufacturer",
        "price": "PKR",
        "reason": "why this is best choice"
    }},
    "generic_alternatives": [
        {{
            "name": "generic option",
            "price": "PKR",
            "savings": "how much cheaper"
        }}
    ],
    "price_comparison": {{
        "cheapest": "medicine and price",
        "most_expensive": "medicine and price",
        "average_price": "PKR"
    }},
    "availability": "stock status",
    "patient_message": "clear, helpful message"
}}
"""

        response = self.reason(
            prompt,
            context={
                "medicine": medicine_name,
                "location": patient_location,
                "options": [m.to_dict() for m in medicines]
            }
        )

        # Add full medicine data
        response.data["medicine_details"] = [m.to_dict() for m in medicines]

        return response

    def _format_medicines_for_prompt(self, medicines: List) -> str:
        """Format medicines for prompt"""
        formatted = []
        for m in medicines:
            formatted.append(f"""
Medicine: {m.name}
Company: {m.company}
Pack Size: {m.pack_size}
Sale Price: Rs. {m.sale_price}
MRP: Rs. {m.mrp}
Stock: {m.stock_available} units
""")
        return "\n".join(formatted)

    async def coordinate_with_pharmacies(
        self,
        medicine_name: str,
        patient_location: str,
        urgency: str,
        mcp_client: Any
    ) -> AgentResponse:
        """
        Coordinate with pharmacy resource agents to find medicine

        Args:
            medicine_name: Medicine to find
            patient_location: Patient location
            urgency: high/medium/low
            mcp_client: MCP client

        Returns:
            AgentResponse with pharmacy coordination result
        """
        # Find pharmacy resource agents
        pharmacy_agents = mcp_client.discover_agents(role="resource")

        if not pharmacy_agents:
            # Fallback to local search
            return self.find_medicine(medicine_name, patient_location)

        # Broadcast request to pharmacies
        request = {
            "medicine": medicine_name,
            "location": patient_location,
            "urgency": urgency,
            "delivery_needed": urgency == "high",
        }

        responses = await mcp_client.broadcast(
            action="check_medicine_stock",
            payload=request,
            filter_criteria={"role": "resource"}
        )

        if not responses:
            return self.find_medicine(medicine_name, patient_location)

        # Select best option
        return self._select_best_pharmacy_option(responses, urgency)

    def _select_best_pharmacy_option(
        self,
        responses: List[AgentResponse],
        urgency: str
    ) -> AgentResponse:
        """Select best pharmacy option from responses"""
        available_responses = [r for r in responses if r.success and r.data.get("in_stock")]

        if not available_responses:
            return AgentResponse(
                success=False,
                reasoning="Medicine not available at any pharmacy",
                confidence=0.0
            )

        # If urgent, prioritize closest pharmacy
        if urgency == "high":
            # In production, would sort by distance
            return available_responses[0]

        # Otherwise, prioritize lowest price
        return min(available_responses, key=lambda r: r.data.get("price", float('inf')))

    def check_drug_interactions(
        self,
        current_medications: List[str],
        new_medication: str
    ) -> AgentResponse:
        """
        Check for potential drug interactions

        Args:
            current_medications: List of medicines patient is taking
            new_medication: New medicine to add

        Returns:
            AgentResponse with interaction warnings
        """
        prompt = f"""Check for drug interactions:

CURRENT MEDICATIONS:
{chr(10).join(f'- {med}' for med in current_medications)}

NEW MEDICATION:
{new_medication}

Analyze potential interactions and provide assessment in JSON format:
{{
    "has_interactions": true/false,
    "severity": "severe/moderate/minor/none",
    "interactions": [
        {{
            "drug_combination": "drug A + drug B",
            "risk_level": "high/medium/low",
            "description": "what happens",
            "recommendation": "what to do"
        }}
    ],
    "safe_to_take": true/false,
    "precautions": ["precaution 1", "precaution 2"],
    "consult_doctor": true/false,
    "patient_message": "clear warning/reassurance message"
}}

Note: For common medications in Pakistan:
- Metformin (diabetes) + certain antibiotics
- Warfarin (blood thinner) + NSAIDs (pain relievers)
- Insulin + alcohol
- Hypertension medicines + NSAIDs
"""

        response = self.reason(
            prompt,
            context={
                "current": current_medications,
                "new": new_medication
            }
        )

        return response

    def create_medication_schedule(
        self,
        medications: List[Dict[str, Any]],
        patient_age: int,
        patient_conditions: List[str]
    ) -> AgentResponse:
        """
        Create medication schedule for patient

        Args:
            medications: List of medicines with dosage info
            patient_age: Patient age
            patient_conditions: Medical conditions

        Returns:
            AgentResponse with medication schedule
        """
        prompt = f"""Create a medication schedule for patient:

AGE: {patient_age}
CONDITIONS: {', '.join(patient_conditions)}

MEDICATIONS:
{chr(10).join(f"- {med.get('name')}: {med.get('dosage')}, {med.get('frequency')}" for med in medications)}

Create a simple, easy-to-follow schedule in JSON format:
{{
    "morning": [
        {{
            "medicine": "name",
            "dosage": "amount",
            "timing": "before/after food",
            "special_instructions": "any special notes"
        }}
    ],
    "afternoon": [...],
    "evening": [...],
    "night": [...],
    "adherence_tips": ["tip 1", "tip 2"],
    "warning_signs": ["what to watch for"],
    "patient_message": "simple, encouraging message with schedule"
}}

Consider:
- Avoid too many medicines at once (spread them out)
- Some medicines need empty stomach, others with food
- Elderly patients need simpler schedules
- Provide memory aids (morning tea time, before dinner, etc.)
"""

        response = self.reason(
            prompt,
            context={
                "medications": medications,
                "age": patient_age,
                "conditions": patient_conditions
            }
        )

        return response

    def suggest_generic_alternatives(
        self,
        brand_medicine: str,
        patient_budget: float
    ) -> AgentResponse:
        """Suggest cheaper generic alternatives"""
        prompt = f"""Patient is prescribed {brand_medicine} but budget is Rs. {patient_budget}.

Suggest generic alternatives:
1. Check database for same chemical composition
2. Ensure DRAP (Drug Regulatory Authority Pakistan) approval
3. Compare prices
4. Verify quality and reliability

Provide suggestions in JSON format:
{{
    "brand_medicine": "{{
        "name": "brand name",
        "price": "PKR",
        "company": "manufacturer"
    }}",
    "generic_alternatives": [
        {{
            "name": "generic name",
            "price": "PKR",
            "company": "manufacturer",
            "savings": "PKR and percentage",
            "quality_note": "DRAP approved, same effectiveness"
        }}
    ],
    "recommendation": "which one to choose",
    "patient_message": "reassuring message that generics are safe and effective"
}}
"""

        # Search for alternatives
        medicines = self.db.search_medicines(name=brand_medicine, limit=10)

        response = self.reason(
            prompt,
            context={
                "brand": brand_medicine,
                "budget": patient_budget,
                "alternatives": [m.to_dict() for m in medicines]
            }
        )

        return response

    def handle_find_medicine(self, message: AgentMessage) -> AgentResponse:
        """Handle find medicine request"""
        return self.find_medicine(
            medicine_name=message.payload.get("medicine"),
            patient_location=message.payload.get("location", ""),
            budget=message.payload.get("budget")
        )

    def handle_check_interactions(self, message: AgentMessage) -> AgentResponse:
        """Handle drug interaction check"""
        return self.check_drug_interactions(
            current_medications=message.payload.get("current_medications", []),
            new_medication=message.payload.get("new_medication", "")
        )
