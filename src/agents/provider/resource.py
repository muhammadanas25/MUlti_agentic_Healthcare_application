"""Resource Agent - Hospital Resource Management"""
from typing import Dict, Any, List
import random
from ...core.agent import Agent, AgentMessage, AgentResponse


class ResourceAgent(Agent):
    """
    Resource Agent - Hospital Resource Management

    Responsibilities:
    - Track bed availability (ICU, general wards)
    - Monitor equipment status (ventilators, oxygen, etc.)
    - Manage medicine stock
    - Track staff availability
    - Handle resource allocation requests
    - Alert when resources are low
    - Coordinate resource sharing with other hospitals
    """

    def __init__(self, hospital_id: int, hospital_name: str):
        self.hospital_id = hospital_id
        self.hospital_name = hospital_name

        super().__init__(
            agent_id=f"agent-102-resource-{hospital_id}",
            name=f"Resource ({hospital_name})",
            role="resource",
            organization="provider-hospital-side",
            system_prompt=f"""You are a Resource Management Agent for {hospital_name}.

Your mission is to optimize resource utilization and ensure availability for patients.

KEY RESPONSIBILITIES:
1. Track real-time availability of beds, equipment, medicines, staff
2. Allocate resources efficiently
3. Respond to resource queries from other agents
4. Alert when critical resources are low
5. Coordinate with other hospitals for resource sharing
6. Optimize resource distribution

RESOURCES YOU MANAGE:
- Beds: General, ICU, emergency
- Medical equipment: Ventilators, oxygen, monitors
- Medicines and supplies
- Staff: Doctors, nurses, technicians
- Diagnostic equipment: X-ray, CT, MRI, lab

DECISION MAKING:
- Emergency cases get priority
- Critical resources reserved for critical patients
- Balance current needs with future contingencies
- Coordinate overflow to other facilities when full
- Auto-reorder supplies when below threshold

COLLABORATION:
- Work with Scheduler Agent for bed allocation
- Work with Emergency Agent for critical cases
- Work with Billing Agent for insurance coverage of resources
- Negotiate with other hospital Resource Agents for sharing
""",
            tools=["resource_tracking", "inventory_management", "allocation_optimization"],
        )

        # Hospital resources (in-memory, would be in HMS in production)
        self.resources = {
            "beds": {
                "general": {"total": random.randint(30, 100), "available": random.randint(5, 30)},
                "icu": {"total": random.randint(10, 30), "available": random.randint(0, 5)},
                "emergency": {"total": random.randint(10, 20), "available": random.randint(2, 10)},
            },
            "equipment": {
                "ventilators": {"total": random.randint(5, 20), "available": random.randint(0, 5)},
                "oxygen": {"total": 100, "available": random.randint(70, 100), "unit": "cylinders"},
                "monitors": {"total": random.randint(20, 50), "available": random.randint(5, 20)},
            },
            "staff": {
                "doctors": {"on_duty": random.randint(10, 30)},
                "nurses": {"on_duty": random.randint(20, 60)},
            }
        }

        # Register handlers
        self.register_message_handler("check_bed_availability", self.handle_bed_availability)
        self.register_message_handler("reserve_bed", self.handle_bed_reservation)
        self.register_message_handler("check_medicine_stock", self.handle_medicine_stock)

    def check_resource_availability(self, resource_type: str, quantity: int = 1) -> AgentResponse:
        """Check if resource is available"""
        available = False
        details = {}

        if resource_type == "icu_bed":
            available = self.resources["beds"]["icu"]["available"] >= quantity
            details = self.resources["beds"]["icu"]
        elif resource_type == "general_bed":
            available = self.resources["beds"]["general"]["available"] >= quantity
            details = self.resources["beds"]["general"]
        elif resource_type == "ventilator":
            available = self.resources["equipment"]["ventilators"]["available"] >= quantity
            details = self.resources["equipment"]["ventilators"]

        return AgentResponse(
            success=True,
            data={
                "available": available,
                "resource_type": resource_type,
                "quantity_requested": quantity,
                "quantity_available": details.get("available", 0),
                "total": details.get("total", 0),
                "hospital": self.hospital_name
            },
            reasoning=f"{'Resource available' if available else 'Resource not available'}",
            confidence=1.0
        )

    def handle_bed_availability(self, message: AgentMessage) -> AgentResponse:
        """Handle bed availability query"""
        bed_type = message.payload.get("bed_type", "general")
        urgency = message.payload.get("urgency", "normal")

        beds = self.resources["beds"]

        prompt = f"""Bed availability query:

BED TYPE: {bed_type}
URGENCY: {urgency}

CURRENT AVAILABILITY:
- General Beds: {beds['general']['available']}/{beds['general']['total']}
- ICU Beds: {beds['icu']['available']}/{beds['icu']['total']}
- Emergency Beds: {beds['emergency']['available']}/{beds['emergency']['total']}

Provide response in JSON format:
{{
    "available": true/false,
    "bed_type": "{bed_type}",
    "quantity_available": "number",
    "estimated_wait": "if not available, wait time",
    "alternative_options": ["alternative if not available"],
    "recommendation": "what to do"
}}
"""

        response = self.reason(prompt, context={"beds": beds, "urgency": urgency})
        return response

    def handle_bed_reservation(self, message: AgentMessage) -> AgentResponse:
        """Handle bed reservation request"""
        bed_type = message.payload.get("bed_type", "general")
        patient_id = message.payload.get("patient_id")

        # Check availability
        if bed_type == "icu" and self.resources["beds"]["icu"]["available"] > 0:
            self.resources["beds"]["icu"]["available"] -= 1
            print(f"🛏️  ICU Bed reserved for patient {patient_id} at {self.hospital_name}")
            return AgentResponse(
                success=True,
                data={"reserved": True, "bed_type": "icu", "hospital": self.hospital_name},
                reasoning="ICU bed reserved successfully",
                confidence=1.0
            )
        elif self.resources["beds"]["general"]["available"] > 0:
            self.resources["beds"]["general"]["available"] -= 1
            print(f"🛏️  General bed reserved for patient {patient_id} at {self.hospital_name}")
            return AgentResponse(
                success=True,
                data={"reserved": True, "bed_type": "general", "hospital": self.hospital_name},
                reasoning="General bed reserved successfully",
                confidence=1.0
            )
        else:
            return AgentResponse(
                success=False,
                data={"reserved": False},
                reasoning="No beds available",
                confidence=1.0
            )

    def handle_medicine_stock(self, message: AgentMessage) -> AgentResponse:
        """Handle medicine stock query"""
        medicine = message.payload.get("medicine")
        location = message.payload.get("location", "")
        urgency = message.payload.get("urgency", "normal")

        # Simulate stock check
        in_stock = random.choice([True, True, False])  # 66% available
        quantity = random.randint(0, 50) if in_stock else 0
        price = random.randint(100, 5000)

        return AgentResponse(
            success=in_stock,
            data={
                "in_stock": in_stock,
                "medicine": medicine,
                "quantity": quantity,
                "price": price,
                "location": self.hospital_name,
                "delivery_available": urgency == "high"
            },
            reasoning=f"Medicine {'available' if in_stock else 'out of stock'}",
            confidence=0.9
        )
