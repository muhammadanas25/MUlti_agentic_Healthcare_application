"""
Sehat Saathi - Main Demo Script
Showcases multi-agent autonomy and cross-system communication
"""
import asyncio
import sys
from src.demo.orchestrator import get_orchestrator


async def run_demo_1_appointment():
    """Demo 1: Appointment Booking with Multi-Agent Negotiation"""
    orchestrator = get_orchestrator()
    orchestrator.initialize_all_agents(num_hospitals=3)

    await orchestrator.scenario_appointment_booking(
        patient_id="PAT-001",
        symptoms=[
            "fever for 3 days",
            "body aches",
            "headache",
            "suspected dengue"
        ],
        location="Karachi, Gulberg",
        preferences={"gender_preference": "female", "budget_conscious": True}
    )

    orchestrator.print_agent_statistics()
    orchestrator.export_communication_trace("logs/demo1_appointment_trace.json")


async def run_demo_2_emergency():
    """Demo 2: Emergency Response & Hospital Negotiation"""
    orchestrator = get_orchestrator()
    orchestrator.initialize_all_agents(num_hospitals=3)

    await orchestrator.scenario_emergency_response(
        patient_id="PAT-002",
        emergency_symptoms=[
            "severe chest pain",
            "difficulty breathing",
            "sweating",
            "nausea"
        ],
        location=(24.8607, 67.0011)  # Karachi coordinates
    )

    orchestrator.print_agent_statistics()
    orchestrator.export_communication_trace("logs/demo2_emergency_trace.json")


async def run_demo_3_medicine():
    """Demo 3: Medicine Coordination Across Pharmacies"""
    orchestrator = get_orchestrator()
    orchestrator.initialize_all_agents(num_hospitals=3)

    await orchestrator.scenario_medicine_coordination(
        patient_id="PAT-003",
        medicine_name="Insulin",
        location="Karachi, Gulberg",
        urgency="high"
    )

    orchestrator.print_agent_statistics()
    orchestrator.export_communication_trace("logs/demo3_medicine_trace.json")


async def run_all_demos():
    """Run all demo scenarios"""
    print("\n" + "="*60)
    print("🚀 RUNNING ALL DEMO SCENARIOS")
    print("="*60 + "\n")

    await run_demo_1_appointment()
    print("\n\n" + "⏸ "*30 + "\n\n")

    await run_demo_2_emergency()
    print("\n\n" + "⏸ "*30 + "\n\n")

    await run_demo_3_medicine()

    print("\n" + "="*60)
    print("✅ ALL DEMOS COMPLETED!")
    print("="*60 + "\n")


def interactive_menu():
    """Interactive menu for demo selection"""
    print("\n" + "="*60)
    print("🏥 SEHAT SAATHI - MULTI-AGENT HEALTHCARE DEMO")
    print("="*60 + "\n")

    print("Select a demo scenario:\n")
    print("1. Appointment Booking with Negotiation")
    print("   → Patient agents negotiate with hospital schedulers")
    print("   → Gender preferences, insurance verification, slot optimization\n")

    print("2. Emergency Response & Hospital Coordination")
    print("   → Critical patient broadcast to all hospitals")
    print("   → Hospitals negotiate capacity and resources")
    print("   → Family notification and ambulance coordination\n")

    print("3. Medicine Coordination Across Pharmacies")
    print("   → Search medicines across multiple pharmacies")
    print("   → Price comparison and generic alternatives")
    print("   → Urgent delivery coordination\n")

    print("4. Run All Demos")
    print("5. Exit\n")

    choice = input("Enter your choice (1-5): ").strip()
    return choice


async def main():
    """Main entry point"""
    while True:
        choice = interactive_menu()

        if choice == "1":
            await run_demo_1_appointment()
        elif choice == "2":
            await run_demo_2_emergency()
        elif choice == "3":
            await run_demo_3_medicine()
        elif choice == "4":
            await run_all_demos()
        elif choice == "5":
            print("\n👋 Thank you for using Sehat Saathi!\n")
            break
        else:
            print("\n❌ Invalid choice. Please select 1-5.\n")

        if choice in ["1", "2", "3", "4"]:
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted. Goodbye!\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
