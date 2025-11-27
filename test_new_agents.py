#!/usr/bin/env python
"""
Test script for new agents and services:
- Hospital Booking Agent
- Doctor Appointment Agent
- A2A Messaging
- Dashboards
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime

def test_services():
    """Test the new services"""
    print("\n" + "="*60)
    print("TESTING SERVICES")
    print("="*60)

    # Test Hospital Resource Service
    print("\n--- Hospital Resource Service ---")
    from src.services.hospital_resources import get_hospital_resource_service
    resource_service = get_hospital_resource_service()

    # Get dashboard stats for hospital 1
    print("\nHospital 1 Dashboard Stats:")
    stats = resource_service.get_dashboard_stats(1)
    print(f"  Hospital: {stats.get('hospital_name')}")
    print(f"  Total Beds: {stats.get('summary', {}).get('total_beds')}")
    print(f"  Available Beds: {stats.get('summary', {}).get('available_beds')}")
    print(f"  ICU Available: {stats.get('summary', {}).get('icu_beds_available')}")
    print(f"  Ventilators: {stats.get('summary', {}).get('ventilators_available')}")

    # Search for ICU beds
    print("\nSearching for ICU beds across hospitals:")
    icu_results = resource_service.search_available_resources("bed", "icu")
    for r in icu_results[:3]:
        print(f"  {r['hospital_name']}: {r['available']} ICU beds available")

    # Create a booking
    print("\nCreating test booking:")
    booking = resource_service.create_booking(
        hospital_id=1,
        resource_type="bed",
        resource_subtype="general",
        patient_id="test-patient-001",
        patient_name="Test Patient"
    )
    print(f"  Booking: {booking.get('success')} - {booking.get('booking', {}).get('booking_id')}")

    # Test Doctor Availability Service
    print("\n--- Doctor Availability Service ---")
    from src.services.doctor_availability import get_doctor_availability_service
    doctor_service = get_doctor_availability_service()

    # Search for doctors
    print("\nSearching for Cardiologists:")
    cardiologists = doctor_service.search_doctors(specialization="Cardiologist", limit=3)
    for doc in cardiologists:
        print(f"  {doc['name']} - {doc['city']} - {doc['schedule']['day']} {doc['schedule']['timing']} - Rs.{int(doc['fee'])}")

    # Get specializations
    print("\nAvailable Specializations:")
    specs = doctor_service.get_specializations()[:10]
    print(f"  {', '.join(specs)}")

    # Get doctor availability
    print("\nDoctor 1 Next Available Slot:")
    next_slot = doctor_service.get_next_available_slot(1)
    print(f"  Date: {next_slot.get('next_date')}")
    print(f"  Day: {next_slot.get('day')}")
    print(f"  Slots: {next_slot.get('available_slots', [])[:5]}")

    # Test A2A Messaging
    print("\n--- A2A Messaging Service ---")
    from src.services.a2a_messaging import get_a2a_messaging_service
    messaging_service = get_a2a_messaging_service()

    print(f"\nRegistered Agents: {len(messaging_service.get_registered_agents())}")
    print(f"Messaging Stats: {messaging_service.get_stats()}")

    return True


def test_hospital_booking_agent():
    """Test the Hospital Booking Agent"""
    print("\n" + "="*60)
    print("TESTING HOSPITAL BOOKING AGENT")
    print("="*60)

    from src.agents.provider.hospital_booking import HospitalBookingAgent

    # Create global booking agent
    booking_agent = HospitalBookingAgent()

    # Test 1: Initial message asking for ICU bed
    print("\n--- Test 1: Book ICU Bed ---")
    response = booking_agent.process_message(
        phone_number="03001234567",
        message="I need an ICU bed",
        context={"patient_name": "Ali Khan"}
    )
    print(f"Response Type: {response.data.get('response_type')}")
    print(f"Message:\n{response.data.get('patient_message', '')[:500]}")

    # Test 2: Blood bank request
    print("\n--- Test 2: Blood Bank Request ---")
    response = booking_agent.process_message(
        phone_number="03001234568",
        message="Need O+ blood urgently",
        context={"patient_name": "Sara Ahmed", "urgency": "high"}
    )
    print(f"Response Type: {response.data.get('response_type')}")
    print(f"Message:\n{response.data.get('patient_message', '')[:500]}")

    # Test 3: Ventilator request
    print("\n--- Test 3: Ventilator Request ---")
    response = booking_agent.process_message(
        phone_number="03001234569",
        message="Book a ventilator for emergency",
        context={"urgency": "emergency"}
    )
    print(f"Response Type: {response.data.get('response_type')}")
    print(f"Message:\n{response.data.get('patient_message', '')[:500]}")

    return True


def test_doctor_appointment_agent():
    """Test the Doctor Appointment Agent"""
    print("\n" + "="*60)
    print("TESTING DOCTOR APPOINTMENT AGENT")
    print("="*60)

    from src.agents.patient.doctor_appointment import DoctorAppointmentAgent

    # Create agent
    appt_agent = DoctorAppointmentAgent()

    # Test 1: Find cardiologist
    print("\n--- Test 1: Find Cardiologist ---")
    response = appt_agent.process_message(
        phone_number="03001234570",
        message="Find a heart doctor in Karachi",
        context={"patient_name": "Ahmed Khan"}
    )
    print(f"Response Type: {response.data.get('response_type')}")
    print(f"Found: {response.data.get('total_found', 0)} doctors")
    print(f"Message:\n{response.data.get('patient_message', '')[:600]}")

    # Test 2: Find dermatologist
    print("\n--- Test 2: Find Dermatologist ---")
    response = appt_agent.process_message(
        phone_number="03001234571",
        message="Skin doctor in Quetta",
        context={"patient_name": "Fatima Ali"}
    )
    print(f"Response Type: {response.data.get('response_type')}")
    print(f"Found: {response.data.get('total_found', 0)} doctors")
    print(f"Message:\n{response.data.get('patient_message', '')[:600]}")

    # Test 3: Initial request
    print("\n--- Test 3: General Doctor Request ---")
    response = appt_agent.process_message(
        phone_number="03001234572",
        message="I need to see a doctor"
    )
    print(f"Response Type: {response.data.get('response_type')}")
    print(f"Message:\n{response.data.get('patient_message', '')[:500]}")

    return True


def test_dashboard_service():
    """Test the Dashboard Service"""
    print("\n" + "="*60)
    print("TESTING DASHBOARD SERVICE")
    print("="*60)

    from src.services.dashboards import get_dashboard_service

    dashboard = get_dashboard_service()

    # Test Hospital Dashboard
    print("\n--- Hospital Manager Dashboard ---")
    hosp_dash = dashboard.get_hospital_dashboard(1)
    print(f"Hospital: {hosp_dash.get('hospital_name')}")
    print(f"Bed Occupancy: {hosp_dash.get('summary', {}).get('bed_occupancy_rate')}%")
    print(f"Alerts: {len(hosp_dash.get('alerts', []))}")
    for alert in hosp_dash.get('alerts', [])[:3]:
        print(f"  - [{alert.get('alert_type')}] {alert.get('title')}")

    # Test Doctor Dashboard
    print("\n--- Doctor Dashboard ---")
    doc_dash = dashboard.get_doctor_dashboard(1)
    print(f"Doctor: {doc_dash.get('doctor_name')}")
    print(f"Working Day: {doc_dash.get('schedule', {}).get('working_day')}")
    print(f"Today's Appointments: {doc_dash.get('today', {}).get('total', 0)}")

    # Test Admin Dashboard
    print("\n--- Admin Dashboard ---")
    admin_dash = dashboard.get_admin_dashboard()
    print(f"Total Hospitals: {admin_dash.get('hospitals', {}).get('total')}")
    print(f"Total Doctors: {admin_dash.get('doctors', {}).get('total')}")
    print(f"System Bed Occupancy: {admin_dash.get('resources', {}).get('bed_occupancy_rate')}%")

    return True


def test_a2a_communication():
    """Test A2A communication between agents"""
    print("\n" + "="*60)
    print("TESTING A2A COMMUNICATION")
    print("="*60)

    from src.services.a2a_messaging import get_a2a_messaging_service

    messaging = get_a2a_messaging_service()

    # Test broadcast query
    print("\n--- Broadcast Resource Query ---")
    result = messaging.broadcast_resource_query(
        from_agent_id="test-agent",
        resource_type="bed",
        resource_subtype="icu",
        city="Karachi"
    )
    print(f"Broadcast ID: {result.broadcast_id}")
    print(f"Recipients: {result.total_recipients}")
    print(f"Responses: {result.responses_received}")

    # Test event publishing
    print("\n--- Publish Event ---")
    count = messaging.publish_event(
        from_agent_id="test-agent",
        event_type="test_event",
        event_data={"test": "data"}
    )
    print(f"Event published to {count} subscribers")

    # Get stats
    print("\n--- Messaging Stats ---")
    stats = messaging.get_stats()
    print(f"Total Messages: {stats.get('total_messages')}")
    print(f"Pending Messages: {stats.get('pending_messages')}")
    print(f"Broadcasts: {stats.get('broadcasts')}")

    return True


def test_orchestrator_routing():
    """Test orchestrator routing to new agents"""
    print("\n" + "="*60)
    print("TESTING ORCHESTRATOR ROUTING")
    print("="*60)

    from src.core.orchestrator import get_orchestrator, AgentType
    from src.agents.provider.hospital_booking import HospitalBookingAgent
    from src.agents.patient.doctor_appointment import DoctorAppointmentAgent

    orchestrator = get_orchestrator()

    # Register the new agents
    print("\nRegistering new agents...")
    booking_agent = HospitalBookingAgent()
    appt_agent = DoctorAppointmentAgent()

    orchestrator.register_agent(AgentType.HOSPITAL_BOOKING, booking_agent)
    orchestrator.register_agent(AgentType.DOCTOR_APPOINTMENT, appt_agent)
    print("  Hospital Booking Agent registered")
    print("  Doctor Appointment Agent registered")

    # Test routing queries
    test_queries = [
        "I need an ICU bed",
        "Book blood O positive",
        "Find a cardiologist in Karachi",
        "Doctor appointment for skin problem",
        "Need ventilator for my father"
    ]

    print("\n--- Testing Query Routing ---")
    for query in test_queries:
        plan = orchestrator.planner.plan(query)
        print(f"\nQuery: '{query}'")
        print(f"  Primary Agent: {plan.get('primary_agent')}")
        print(f"  Intent: {plan.get('intent', '')[:50]}")
        print(f"  Needs Clarification: {plan.get('needs_clarification', False)}")

    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("SEHAT SAATHI - NEW AGENTS TEST SUITE")
    print("="*60)
    print(f"Test Time: {datetime.now().isoformat()}")

    all_passed = True

    try:
        # Test services
        test_services()
    except Exception as e:
        print(f"\nERROR in services test: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        # Test Hospital Booking Agent
        test_hospital_booking_agent()
    except Exception as e:
        print(f"\nERROR in Hospital Booking Agent test: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        # Test Doctor Appointment Agent
        test_doctor_appointment_agent()
    except Exception as e:
        print(f"\nERROR in Doctor Appointment Agent test: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        # Test Dashboard Service
        test_dashboard_service()
    except Exception as e:
        print(f"\nERROR in Dashboard Service test: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        # Test A2A Communication
        test_a2a_communication()
    except Exception as e:
        print(f"\nERROR in A2A Communication test: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        # Test Orchestrator Routing
        test_orchestrator_routing()
    except Exception as e:
        print(f"\nERROR in Orchestrator Routing test: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED - Check errors above")
    print("="*60 + "\n")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
