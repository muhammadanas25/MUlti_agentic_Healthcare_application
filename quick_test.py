"""Quick test script to verify system works"""
import asyncio
from src.demo.orchestrator import get_orchestrator


async def quick_test():
    """Quick test of the multi-agent system"""
    print("\n" + "="*60)
    print("🧪 QUICK SYSTEM TEST")
    print("="*60 + "\n")

    # Initialize orchestrator
    orchestrator = get_orchestrator()

    # Initialize agents (just 2 hospitals for quick test)
    orchestrator.initialize_all_agents(num_hospitals=2)

    print("✅ System initialized successfully!")
    print(f"   → {len(orchestrator.patient_agents)} patient-side agents")
    print(f"   → {len(orchestrator.provider_agents)} hospitals with 5 agents each")
    print(f"   → Total: {len(orchestrator.mcp.agent_registry)} agents registered\n")

    # Test 1: Simple symptom assessment
    print("Test 1: Symptom Assessment...")
    dr_sameer = orchestrator.patient_agents["dr_sameer"]
    result = dr_sameer.assess_symptoms(
        symptoms=["fever", "cough"],
        patient_info={"age": 30, "gender": "male", "location": "Karachi"}
    )
    print(f"   ✓ Dr. Sameer assessed symptoms: {result.data.get('urgency')} urgency\n")

    # Test 2: Find hospitals
    print("Test 2: Finding Hospitals...")
    guide = orchestrator.patient_agents["guide"]
    hospitals = guide.find_nearby_hospitals(
        patient_location="Karachi",
        specialty="general_physician"
    )
    print(f"   ✓ Guide found {len(hospitals.data.get('hospital_details', []))} hospitals\n")

    # Test 3: Medicine search
    print("Test 3: Medicine Search...")
    yaadgar = orchestrator.patient_agents["yaadgar"]
    medicine = yaadgar.find_medicine(
        medicine_name="Paracetamol",
        patient_location="Karachi"
    )
    print(f"   ✓ Yaadgar found {len(medicine.data.get('medicine_details', []))} medicine options\n")

    # Test 4: Agent communication
    print("Test 4: Agent-to-Agent Communication...")
    guide_client = orchestrator.mcp_clients["guide"]

    # Test broadcast
    responses = await guide_client.broadcast(
        action="check_availability",
        payload={"date": "2024-11-25"},
        filter_criteria={"role": "scheduler"}
    )
    print(f"   ✓ Broadcast sent, received {len(responses)} responses from schedulers\n")

    # Show statistics
    orchestrator.print_agent_statistics()

    print("="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60 + "\n")

    print("System is ready for full demos. Run: python main_demo.py\n")


if __name__ == "__main__":
    asyncio.run(quick_test())
