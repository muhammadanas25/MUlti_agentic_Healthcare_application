"""Main orchestrator for Sehat Saathi multi-agent system"""
import asyncio
from typing import List, Optional
from ..core.config import settings
from ..mcp.server import get_mcp_server
from ..mcp.client import MCPClient
from ..database.manager import get_db_manager

# Patient-side agents
from ..agents.patient import (
    DrSameerAgent,
    GuideAgent,
    HaqdarAgent,
    YaadgarAgent,
    KhandanAgent,
    MuhafizAgent
)

# Provider-side agents
from ..agents.provider import (
    SchedulerAgent,
    ResourceAgent,
    BillingAgent,
    ClinicalAgent,
    EmergencyAgent
)


class SehatSaathiOrchestrator:
    """
    Main orchestrator for Sehat Saathi multi-agent system

    Responsibilities:
    - Initialize all agents
    - Register agents with MCP server
    - Coordinate complex multi-agent workflows
    - Provide high-level API for scenarios
    """

    def __init__(self):
        print("\n" + "="*60)
        print("🏥 SEHAT SAATHI - MULTI-AGENT HEALTHCARE SYSTEM")
        print("="*60 + "\n")

        # Initialize core services
        self.db = get_db_manager()
        self.mcp = get_mcp_server()

        # Agent instances
        self.patient_agents = {}
        self.provider_agents = {}

        # MCP clients for each agent
        self.mcp_clients = {}

        print("✓ Core services initialized\n")

    def initialize_patient_agents(self):
        """Initialize all patient-side agents"""
        print("📱 Initializing Patient-Side Agents...")

        # Create patient agents
        self.patient_agents = {
            "dr_sameer": DrSameerAgent(),
            "guide": GuideAgent(),
            "haqdar": HaqdarAgent(),
            "yaadgar": YaadgarAgent(),
            "khandan": KhandanAgent(),
            "muhafiz": MuhafizAgent()
        }

        # Register with MCP and create clients
        for name, agent in self.patient_agents.items():
            self.mcp_clients[name] = MCPClient(agent, self.mcp)

        print(f"✓ {len(self.patient_agents)} patient agents registered\n")

    def initialize_provider_agents(self, num_hospitals: int = 3):
        """Initialize provider-side agents for multiple hospitals"""
        print(f"🏥 Initializing Provider-Side Agents for {num_hospitals} hospitals...")

        # Get some hospitals from database
        hospitals = self.db.search_hospitals(city="Karachi", limit=num_hospitals)

        for hospital in hospitals:
            hospital_key = f"hospital_{hospital.id}"

            # Create provider agents for this hospital
            self.provider_agents[hospital_key] = {
                "scheduler": SchedulerAgent(hospital.id, hospital.name),
                "resource": ResourceAgent(hospital.id, hospital.name),
                "billing": BillingAgent(hospital.id, hospital.name),
                "clinical": ClinicalAgent(hospital.id, hospital.name),
                "emergency": EmergencyAgent(hospital.id, hospital.name)
            }

            # Register with MCP
            for agent_name, agent in self.provider_agents[hospital_key].items():
                client_key = f"{hospital_key}_{agent_name}"
                self.mcp_clients[client_key] = MCPClient(agent, self.mcp)

        print(f"✓ {num_hospitals * 5} provider agents registered across {num_hospitals} hospitals\n")

    def initialize_all_agents(self, num_hospitals: int = 3):
        """Initialize all agents (patient + provider)"""
        self.initialize_patient_agents()
        self.initialize_provider_agents(num_hospitals)

        print("="*60)
        print(f"✅ SYSTEM READY - {len(self.mcp.agent_registry)} agents online")
        print("="*60 + "\n")

    # ==================== HIGH-LEVEL SCENARIO APIs ====================

    async def scenario_appointment_booking(
        self,
        patient_id: str,
        symptoms: List[str],
        location: str,
        preferences: dict = None
    ):
        """
        Complete appointment booking scenario

        Flow:
        1. Dr. Sameer assesses symptoms
        2. Guide finds nearby hospitals and doctors
        3. Guide negotiates with Scheduler agents
        4. Haqdar verifies insurance
        5. Billing pre-authorizes
        6. Appointment confirmed
        """
        print("\n" + "="*60)
        print("📋 SCENARIO: APPOINTMENT BOOKING WITH NEGOTIATION")
        print("="*60 + "\n")

        # Step 1: Triage
        print("Step 1: Dr. Sameer assessing symptoms...")
        dr_sameer = self.patient_agents["dr_sameer"]
        triage = dr_sameer.assess_symptoms(
            symptoms=symptoms,
            patient_info={
                "age": 35,
                "gender": "female",
                "location": location,
                "duration": "2 days",
                "severity": 7
            }
        )
        print(f"   Triage Result: {triage.data.get('urgency')} urgency")
        print(f"   Recommended Care: {triage.data.get('care_level')}\n")

        # Step 2: Find hospital
        print("Step 2: Guide finding nearby hospitals...")
        guide = self.patient_agents["guide"]
        hospitals = guide.find_nearby_hospitals(
            patient_location=location,
            specialty="general_physician",
            patient_preferences=preferences or {"gender_preference": "female"}
        )
        print(f"   Found {len(hospitals.data.get('hospital_details', []))} hospitals")
        if hospitals.data.get("recommended_hospital"):
            print(f"   Recommended: {hospitals.data['recommended_hospital']['name']}\n")

        # Step 3: Find doctor
        print("Step 3: Finding suitable doctor...")
        doctors = guide.find_doctors(
            city="Karachi",
            specialization="General Physician",
            patient_preferences=preferences
        )
        if doctors.data.get("recommended_doctor"):
            print(f"   Recommended: Dr. {doctors.data['recommended_doctor']['name']}\n")

        # Step 4: Book appointment (negotiate with schedulers)
        print("Step 4: Negotiating appointment with hospital schedulers...")
        guide_client = self.mcp_clients["guide"]

        # Broadcast appointment request to all schedulers
        appointment_request = {
            "patient_id": patient_id,
            "urgency": triage.data.get("urgency", "moderate"),
            "specialty": "general_physician",
            "preferred_time": "today_afternoon",
            "gender_preference": preferences.get("gender_preference") if preferences else None
        }

        scheduler_responses = await guide_client.broadcast(
            action="request_appointment_slot",
            payload=appointment_request,
            filter_criteria={"role": "scheduler"}
        )

        print(f"   Received {len(scheduler_responses)} responses from hospitals")
        for i, response in enumerate(scheduler_responses[:3], 1):
            if response.success and response.data.get("options"):
                print(f"   Option {i}: {response.data.get('hospital_name')}")
                for option in response.data["options"][:1]:
                    print(f"      → {option.get('time')}, Wait: {option.get('wait_estimate')}")

        # Step 5: Verify insurance
        print("\nStep 5: Haqdar verifying Sehat Sahulat card...")
        haqdar = self.patient_agents["haqdar"]
        insurance = haqdar.verify_sehat_card(
            cnic="12345-1234567-1",
            patient_name="Ayesha Khan"
        )
        print(f"   Card Status: {insurance.data.get('card_status')}")
        if insurance.data.get("is_eligible"):
            print(f"   Coverage: Rs. {insurance.data.get('coverage_amount'):,.0f}\n")

        print("✅ Appointment booking flow completed!\n")
        return {
            "triage": triage.data,
            "hospitals": hospitals.data,
            "doctors": doctors.data,
            "scheduler_responses": [r.data for r in scheduler_responses if r.success],
            "insurance": insurance.data
        }

    async def scenario_emergency_response(
        self,
        patient_id: str,
        emergency_symptoms: List[str],
        location: tuple
    ):
        """
        Emergency response scenario

        Flow:
        1. Dr. Sameer detects critical condition
        2. Broadcasts to all Emergency agents
        3. Hospitals respond with capacity
        4. Best hospital selected
        5. Resources reserved
        6. Family notified
        7. Ambulance coordinated
        """
        print("\n" + "="*60)
        print("🚨 SCENARIO: EMERGENCY RESPONSE & HOSPITAL NEGOTIATION")
        print("="*60 + "\n")

        # Step 1: Critical triage
        print("Step 1: Dr. Sameer detecting emergency...")
        dr_sameer = self.patient_agents["dr_sameer"]
        triage = dr_sameer.assess_symptoms(
            symptoms=emergency_symptoms,
            patient_info={
                "age": 52,
                "gender": "male",
                "location": "Karachi, Gulberg",
                "duration": "15 minutes"
            }
        )
        print(f"   🚨 CRITICAL: {triage.data.get('urgency')}")
        print(f"   Condition: {', '.join(triage.data.get('possible_conditions', []))}\n")

        # Step 2: Broadcast emergency to all hospitals
        print("Step 2: Broadcasting emergency to all hospitals...")
        guide_client = self.mcp_clients["guide"]

        emergency_broadcast = {
            "priority": "CRITICAL",
            "condition": "cardiac_emergency",
            "patient_location": location,
            "symptoms": emergency_symptoms,
            "age": 52,
            "gender": "male"
        }

        emergency_responses = await guide_client.broadcast(
            action="emergency_request",
            payload=emergency_broadcast,
            filter_criteria={"role": "emergency"},
            priority="critical"
        )

        print(f"   Received {len(emergency_responses)} responses from emergency departments\n")

        # Step 3: Evaluate responses
        print("Step 3: Evaluating hospital responses...")
        accepting_hospitals = []
        for response in emergency_responses:
            if response.success and response.data.get("can_accept"):
                hospital = response.data
                accepting_hospitals.append(hospital)
                print(f"   ✅ {hospital.get('hospital_name')}: CAN ACCEPT")
                print(f"      → ICU Beds: {hospital.get('icu_beds_available')}")
                print(f"      → Distance: {hospital.get('distance_km', 0):.1f} km")
                print(f"      → ETA: {hospital.get('eta_minutes', 0)} min")
            elif response.success:
                print(f"   ⏸  {response.data.get('hospital_name', 'Unknown')}: Standby (at capacity)")

        if accepting_hospitals:
            best_hospital = min(accepting_hospitals, key=lambda h: h.get('distance_km', 999))
            print(f"\n   🎯 SELECTED: {best_hospital.get('hospital_name')}")
            print(f"      → Closest hospital with capacity")
            print(f"      → ETA: {best_hospital.get('eta_minutes')} minutes\n")

        # Step 4: Notify family
        print("Step 4: Khandan notifying family members...")
        khandan = self.patient_agents["khandan"]
        family_contacts = [
            {"name": "Fatima (Wife)", "relationship": "wife", "phone": "+92-300-1234567"},
            {"name": "Ahmed (Son)", "relationship": "son", "phone": "+92-301-7654321"}
        ]

        await khandan.emergency_notify_family(
            patient_id=patient_id,
            emergency_type="Cardiac Emergency",
            hospital_location={
                "name": best_hospital.get("hospital_name") if accepting_hospitals else "Nearest Hospital",
                "address": "Emergency Department"
            },
            family_contacts=family_contacts,
            mcp_client=self.mcp_clients["khandan"]
        )
        print(f"   ✓ {len(family_contacts)} family members notified\n")

        # Step 5: Log for community monitoring
        print("Step 5: Muhafiz logging for community health monitoring...")
        muhafiz = self.patient_agents["muhafiz"]
        muhafiz.report_disease_case(
            disease="cardiac_event",
            location="Karachi, Gulberg",
            severity="critical",
            patient_id=patient_id
        )
        print("   ✓ Case logged for public health surveillance\n")

        print("✅ Emergency response completed!\n")
        return {
            "triage": triage.data,
            "hospitals_responded": len(emergency_responses),
            "hospitals_accepting": len(accepting_hospitals),
            "selected_hospital": best_hospital if accepting_hospitals else None
        }

    async def scenario_medicine_coordination(
        self,
        patient_id: str,
        medicine_name: str,
        location: str,
        urgency: str = "high"
    ):
        """
        Medicine shortage scenario - coordination across pharmacies

        Flow:
        1. Yaadgar receives medicine request
        2. Broadcasts to pharmacy Resource agents
        3. Compares prices and availability
        4. Negotiates best option
        5. Arranges delivery if urgent
        """
        print("\n" + "="*60)
        print("💊 SCENARIO: MEDICINE COORDINATION ACROSS PHARMACIES")
        print("="*60 + "\n")

        # Step 1: Find medicine
        print(f"Step 1: Yaadgar searching for {medicine_name}...")
        yaadgar = self.patient_agents["yaadgar"]
        medicine_search = yaadgar.find_medicine(
            medicine_name=medicine_name,
            patient_location=location,
            budget=5000
        )

        if medicine_search.success:
            medicines = medicine_search.data.get("medicine_details", [])
            print(f"   Found {len(medicines)} options")
            if medicines:
                cheapest = min(medicines, key=lambda m: m.get("sale_price", 9999))
                print(f"   Cheapest: {cheapest.get('name')} - Rs. {cheapest.get('sale_price')}\n")

        # Step 2: Coordinate with hospital pharmacies
        print("Step 2: Coordinating with hospital pharmacies...")
        yaadgar_client = self.mcp_clients["yaadgar"]

        pharmacy_request = {
            "medicine": medicine_name,
            "location": location,
            "urgency": urgency,
            "delivery_needed": urgency == "high"
        }

        pharmacy_responses = await yaadgar_client.broadcast(
            action="check_medicine_stock",
            payload=pharmacy_request,
            filter_criteria={"role": "resource"}
        )

        print(f"   Received {len(pharmacy_responses)} responses from pharmacies")
        available_count = sum(1 for r in pharmacy_responses if r.success and r.data.get("in_stock"))
        print(f"   Available at {available_count} locations\n")

        # Step 3: Check for generic alternatives
        print("Step 3: Checking for generic alternatives...")
        generics = yaadgar.suggest_generic_alternatives(
            brand_medicine=medicine_name,
            patient_budget=3000
        )
        if generics.data.get("generic_alternatives"):
            print(f"   Found {len(generics.data['generic_alternatives'])} generic options")
            for alt in generics.data["generic_alternatives"][:2]:
                print(f"   → {alt.get('name')}: Rs. {alt.get('price')} (Save Rs. {alt.get('savings')})")

        print("\n✅ Medicine coordination completed!\n")
        return {
            "medicine_search": medicine_search.data,
            "pharmacy_responses": [r.data for r in pharmacy_responses if r.success],
            "generics": generics.data
        }

    def print_agent_statistics(self):
        """Print statistics about agent interactions"""
        print("\n" + "="*60)
        print("📊 AGENT COMMUNICATION STATISTICS")
        print("="*60 + "\n")

        stats = self.mcp.get_stats()
        print(f"Total Agents Registered: {stats['registered_agents']}")
        print(f"Active Agents: {stats['active_agents']}")
        print(f"Messages Sent: {stats['messages_sent']}")
        print(f"Messages Received: {stats['messages_received']}")
        print(f"Broadcasts: {stats['broadcasts']}")
        print(f"Negotiations: {stats['negotiations']}")

        print("\n" + "="*60 + "\n")

    def export_communication_trace(self, filename: str = "logs/agent_trace.json"):
        """Export communication trace for visualization"""
        self.mcp.export_trace(filename)


# Global orchestrator instance
_orchestrator: Optional[SehatSaathiOrchestrator] = None


def get_orchestrator() -> SehatSaathiOrchestrator:
    """Get or create global orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SehatSaathiOrchestrator()
    return _orchestrator
