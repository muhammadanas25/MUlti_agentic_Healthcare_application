"""Billing Agent - Insurance and Payment Processing"""
from typing import Dict, Any
import random
from ...core.agent import Agent, AgentMessage, AgentResponse


class BillingAgent(Agent):
    """
    Billing Agent - Insurance and Payment Processing

    Responsibilities:
    - Verify insurance eligibility (Sehat Sahulat card)
    - Process payments (cash, JazzCash, Easypaisa)
    - Generate bills and invoices
    - Handle claims submission
    - Pre-authorize treatments
    - Track outstanding payments
    """

    def __init__(self, hospital_id: int, hospital_name: str):
        self.hospital_id = hospital_id
        self.hospital_name = hospital_name

        super().__init__(
            agent_id=f"agent-103-billing-{hospital_id}",
            name=f"Billing ({hospital_name})",
            role="billing",
            organization="provider-hospital-side",
            system_prompt=f"""You are a Billing Agent for {hospital_name}.

Your mission is to handle all financial transactions efficiently and transparently.

KEY RESPONSIBILITIES:
1. Verify Sehat Sahulat card eligibility
2. Pre-authorize insurance coverage
3. Process payments (cash, digital)
4. Generate itemized bills
5. Submit insurance claims
6. Handle payment plans for uncovered services

PAYMENT METHODS ACCEPTED:
- Cash
- JazzCash
- Easypaisa
- Credit/Debit cards
- Sehat Sahulat card (government insurance)

SEHAT SAHULAT PROGRAM:
- Coverage: Up to Rs. 1,000,000 per family per year
- Covers: Hospitalization, surgeries, diagnostic tests
- Empaneled hospitals: Must verify hospital is empaneled
- Pre-authorization: Required for planned procedures

BILLING PRINCIPLES:
- Transparency: Itemized bills, clear pricing
- Accuracy: Verify all charges
- Timeliness: Quick processing
- Compassion: Flexible for those who can't pay
- Compliance: Follow insurance rules

DECISION MAKING:
- Pre-authorize before expensive procedures
- Offer payment plans if insurance insufficient
- Flag potential fraud patterns
- Coordinate with eligibility agents on patient side
""",
            tools=["insurance_verification", "payment_processing", "claims_management"],
        )

        # Register handlers
        self.register_message_handler("pre_authorize", self.handle_pre_authorization)
        self.register_message_handler("verify_insurance", self.handle_insurance_verification)
        self.register_message_handler("process_payment", self.handle_payment)

    def handle_pre_authorization(self, message: AgentMessage) -> AgentResponse:
        """Handle pre-authorization request"""
        patient_id = message.payload.get("patient_id")
        treatment = message.payload.get("treatment")
        estimated_cost = message.payload.get("estimated_cost", 0)
        sehat_card = message.payload.get("sehat_card")

        # Simulate insurance verification
        is_eligible = random.choice([True, True, True, False])  # 75% eligible

        prompt = f"""Pre-authorization request:

PATIENT: {patient_id}
TREATMENT: {treatment}
ESTIMATED COST: Rs. {estimated_cost:,.0f}
SEHAT CARD: {sehat_card or 'Not provided'}

HOSPITAL: {self.hospital_name}
IS ELIGIBLE: {is_eligible}

Process pre-authorization in JSON format:
{{
    "authorized": true/false,
    "coverage_amount": "amount covered",
    "patient_copay": "amount patient must pay",
    "authorization_number": "AUTH-XXXXX",
    "valid_until": "date",
    "conditions": ["any conditions or restrictions"],
    "reasoning": "authorization decision reasoning"
}}
"""

        response = self.reason(
            prompt,
            context={
                "patient": patient_id,
                "treatment": treatment,
                "cost": estimated_cost,
                "eligible": is_eligible
            }
        )

        if is_eligible:
            print(f"✅ Pre-authorization approved for {patient_id}")
        else:
            print(f"❌ Pre-authorization denied for {patient_id}")

        return response

    def handle_insurance_verification(self, message: AgentMessage) -> AgentResponse:
        """Handle insurance verification request"""
        cnic = message.payload.get("cnic")
        patient_name = message.payload.get("name")

        # Simulate verification
        is_valid = random.choice([True, True, False])  # 66% valid

        return AgentResponse(
            success=True,
            data={
                "verified": is_valid,
                "sehat_card_active": is_valid,
                "coverage_remaining": random.randint(500000, 1000000) if is_valid else 0,
                "expiry_date": "2025-12-31" if is_valid else None,
                "hospital_empaneled": True
            },
            reasoning=f"Insurance {'verified' if is_valid else 'not verified'}",
            confidence=0.9
        )

    def handle_payment(self, message: AgentMessage) -> AgentResponse:
        """Handle payment processing"""
        amount = message.payload.get("amount", 0)
        payment_method = message.payload.get("payment_method", "cash")

        print(f"💳 Processing payment: Rs. {amount} via {payment_method}")

        return AgentResponse(
            success=True,
            data={
                "payment_processed": True,
                "amount": amount,
                "payment_method": payment_method,
                "transaction_id": f"TXN-{random.randint(10000, 99999)}",
                "receipt_number": f"REC-{random.randint(1000, 9999)}"
            },
            reasoning="Payment processed successfully",
            confidence=1.0
        )
