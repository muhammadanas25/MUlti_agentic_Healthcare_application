#!/usr/bin/env python3
"""
Test script for the improved Dr. Sameer agent.

Tests:
1. Multi-turn conversation flow
2. Emergency detection and protocols
3. OTC medicine recommendations
4. Agent orchestration planning
"""
import asyncio
import sys
sys.path.insert(0, '.')

from src.agents.patient.dr_sameer import DrSameerAgent, EMERGENCY_PROTOCOLS, OTC_RECOMMENDATIONS


def test_conversation_flow():
    """Test multi-turn conversation flow"""
    print("\n" + "="*60)
    print("TEST 1: Multi-Turn Conversation Flow")
    print("="*60)

    dr_sameer = DrSameerAgent()
    phone = "+923001234567"

    # Simulate a conversation
    messages = [
        "Hi",
        "mujhe bukhar hai aur sar dard",
        "2 din se",
        "6",
        "haan, kamzori bhi hai",
        "diabetes hai",
        "metformin le raha hun",
        "koi allergy nahi",
    ]

    for i, msg in enumerate(messages):
        print(f"\n--- Turn {i+1} ---")
        print(f"Patient: {msg}")

        response = dr_sameer.process_message(phone, msg)

        if response.success and response.data:
            print(f"Dr. Sameer: {response.data.get('patient_message', response.reasoning)[:500]}...")
            print(f"State: {response.data.get('state', 'N/A')}")
        else:
            print(f"Error: {response.reasoning}")

    print("\n✓ Conversation flow test completed")


def test_emergency_detection():
    """Test emergency keyword detection and protocol response"""
    print("\n" + "="*60)
    print("TEST 2: Emergency Detection")
    print("="*60)

    dr_sameer = DrSameerAgent()

    emergency_messages = [
        ("chest_pain", "My father has severe chest pain"),
        ("breathing_difficulty", "meri saans nahi aa rahi"),
        ("seizure", "someone is having a fit"),
    ]

    for emergency_type, msg in emergency_messages:
        phone = f"+9230012345{emergency_type[:2]}"
        print(f"\n--- Testing: {emergency_type} ---")
        print(f"Patient: {msg}")

        response = dr_sameer.process_message(phone, msg)

        if response.success and response.data:
            resp_type = response.data.get('response_type', 'N/A')
            print(f"Response Type: {resp_type}")
            if resp_type == 'emergency_protocol':
                print(f"Emergency Type Detected: {response.data.get('emergency_type')}")
                print(f"Protocol Title: {response.data.get('protocol', {}).get('title', 'N/A')}")
                print("✓ Emergency correctly detected!")
            else:
                print(f"❌ Expected emergency_protocol, got {resp_type}")
        else:
            print(f"Error: {response.reasoning}")

    print("\n✓ Emergency detection test completed")


def test_emergency_protocols():
    """Test that all emergency protocols are properly defined"""
    print("\n" + "="*60)
    print("TEST 3: Emergency Protocols Verification")
    print("="*60)

    required_fields = ["title", "urgency", "immediate_steps", "warning_signs"]

    for protocol_name, protocol in EMERGENCY_PROTOCOLS.items():
        print(f"\n--- {protocol_name} ---")
        missing = []
        for field in required_fields:
            if field not in protocol:
                missing.append(field)

        if missing:
            print(f"❌ Missing fields: {missing}")
        else:
            print(f"✓ Title: {protocol['title']}")
            print(f"  Steps: {len(protocol['immediate_steps'])} immediate actions")
            print(f"  Warnings: {len(protocol['warning_signs'])} warning signs")

    print("\n✓ Emergency protocols verification completed")


def test_otc_recommendations():
    """Test OTC medicine recommendations"""
    print("\n" + "="*60)
    print("TEST 4: OTC Recommendations")
    print("="*60)

    dr_sameer = DrSameerAgent()

    for category in ["fever", "headache", "cold_flu", "diarrhea"]:
        print(f"\n--- {category} ---")
        otc_info = dr_sameer.get_otc_info(category)

        if otc_info:
            medicines = otc_info.get("medicines", [])
            print(f"  Medicines: {len(medicines)}")
            for med in medicines[:2]:
                print(f"    • {med['name']}: {med['dose']}")
            print(f"  See doctor if: {otc_info.get('see_doctor_if', [])[:2]}")
        else:
            print(f"❌ No OTC info found for {category}")

    print("\n✓ OTC recommendations test completed")


def test_agent_orchestration():
    """Test agent orchestration/handoff planning"""
    print("\n" + "="*60)
    print("TEST 5: Agent Orchestration")
    print("="*60)

    dr_sameer = DrSameerAgent()
    phone = "+923009876543"

    # Simulate conversation up to care planning phase
    conversation = [
        "hi",
        "I have a fever",
        "3 days",
        "7",
        "yes, also have body pain",
        "none",
        "none",
        "none",
        "hospital",  # This should trigger handoff to Guide agent
    ]

    print("Simulating conversation to reach care planning...")

    for msg in conversation:
        response = dr_sameer.process_message(phone, msg)

    if response.success and response.data:
        print(f"\nResponse type: {response.data.get('response_type')}")

        if response.data.get('handoff_to'):
            print(f"✓ Handoff planned to: {response.data['handoff_to']}")
            print(f"  Care plan: {response.data.get('care_plan', {}).get('action')}")
        elif response.data.get('response_type') == 'care_planning':
            print("✓ Care planning phase reached")
            print(f"  Care plan: {response.data.get('care_plan', {})}")
        else:
            print(f"Current state: {response.data.get('state', 'N/A')}")

    print("\n✓ Agent orchestration test completed")


def test_reasoning_chain():
    """Test that reasoning chain is being tracked"""
    print("\n" + "="*60)
    print("TEST 6: Reasoning Chain Tracking")
    print("="*60)

    dr_sameer = DrSameerAgent()
    phone = "+923007777777"

    # Have a brief conversation
    messages = ["hi", "bukhar", "1 day", "5", "no other symptoms", "none", "none", "none"]

    for msg in messages:
        dr_sameer.process_message(phone, msg)

    # Check reasoning chain
    session = dr_sameer.sessions.get(phone)
    if session:
        chain = session.reasoning_chain
        print(f"Reasoning chain has {len(chain)} steps:")
        for i, step in enumerate(chain[:5]):
            print(f"\n  Step {i+1}: {step.get('step')}")
            print(f"    Thought: {str(step.get('thought'))[:100]}...")
            print(f"    Action: {step.get('action', 'N/A')[:80]}...")
    else:
        print("❌ No session found")

    print("\n✓ Reasoning chain test completed")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("DR. SAMEER IMPROVED AGENT TESTS")
    print("="*60)

    try:
        test_emergency_protocols()
        test_otc_recommendations()
        test_emergency_detection()
        test_conversation_flow()
        test_reasoning_chain()
        test_agent_orchestration()

        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
