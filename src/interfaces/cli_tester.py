#!/usr/bin/env python3
"""
CLI Testing Interface for Sehat Saathi

A command-line interface to test agent conversations without WhatsApp.
Simulates the full conversation flow with logging.

Usage:
    python -m src.interfaces.cli_tester

Commands:
    /guide    - Switch to Guide agent (hospital search)
    /sameer   - Switch to Dr. Sameer agent (health assessment)
    /logs     - Show recent logs for current session
    /chain    - Show reasoning chain
    /clear    - Clear session and start fresh
    /help     - Show help
    /quit     - Exit
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Optional
from datetime import datetime

from ..core.logger import get_agent_logger, LogCategory
from ..core.orchestrator import get_orchestrator, AgentType
from ..agents.patient.guide import GuideAgent, GuideState
from ..agents.patient.dr_sameer import DrSameerAgent
from ..agents.patient.doctor_appointment import DoctorAppointmentAgent
from ..agents.provider.hospital_booking import HospitalBookingAgent


class CLITester:
    """Interactive CLI for testing Sehat Saathi agents."""

    def __init__(self, use_orchestrator: bool = False):
        print("\n" + "="*60)
        print("  🏥 SEHAT SAATHI - CLI Testing Interface")
        print("="*60)
        print("\nInitializing agents...")

        self.logger = get_agent_logger()
        self.guide = GuideAgent()
        self.dr_sameer = DrSameerAgent()
        self.doctor_appointment = DoctorAppointmentAgent()
        self.hospital_booking = HospitalBookingAgent()

        # Initialize orchestrator
        self.orchestrator = get_orchestrator()
        # Register agents with orchestrator
        self.orchestrator.register_agent(AgentType.GUIDE, self.guide)
        self.orchestrator.register_agent(AgentType.DR_SAMEER, self.dr_sameer)
        self.orchestrator.register_agent(AgentType.DOCTOR_APPOINTMENT, self.doctor_appointment)
        self.orchestrator.register_agent(AgentType.HOSPITAL_BOOKING, self.hospital_booking)

        # Session info
        self.phone = f"+92-TEST-{datetime.now().strftime('%H%M%S')}"
        self.current_agent = "auto" if use_orchestrator else "guide"  # "guide", "sameer", or "auto"

        print(f"\n✓ Session ID: {self.phone}")
        if use_orchestrator:
            print(f"✓ Mode: Auto (Orchestrator with Planning Agent)")
        else:
            print(f"✓ Current Agent: Guide (hospital search)")
        print("\nType /help for commands, or start chatting!\n")

    def run(self):
        """Main interaction loop."""
        while True:
            try:
                # Show prompt based on current mode
                if self.current_agent == "auto":
                    agent_name = "Auto"
                elif self.current_agent == "guide":
                    agent_name = "Guide"
                else:
                    agent_name = "Dr. Sameer"

                user_input = input(f"\n👤 You ({agent_name}): ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    if self._handle_command(user_input):
                        continue
                    else:
                        break  # Exit command

                # Process message
                if self.current_agent == "auto":
                    self._process_with_orchestrator(user_input)
                else:
                    self._process_message(user_input)

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except EOFError:
                break

    def _handle_command(self, cmd: str) -> bool:
        """Handle CLI commands. Returns False to exit."""
        cmd = cmd.lower().strip()

        if cmd in ["/quit", "/exit", "/q"]:
            print("\n👋 Goodbye!")
            return False

        elif cmd == "/help":
            self._show_help()

        elif cmd == "/guide":
            self.current_agent = "guide"
            print("\n✓ Switched to Guide agent (hospital search)")
            print("  Try: 'Find hospital near DHA Karachi'")

        elif cmd == "/sameer":
            self.current_agent = "sameer"
            print("\n✓ Switched to Dr. Sameer agent (health assessment)")
            print("  Try: 'I have a headache and fever'")

        elif cmd == "/auto":
            self.current_agent = "auto"
            print("\n✓ Switched to Auto mode (Orchestrator with Planning Agent)")
            print("  The system will automatically route your request to the right agent(s)")
            print("  Try: 'I have fever and need a hospital near Gulshan Karachi'")

        elif cmd == "/logs":
            self._show_logs()

        elif cmd == "/chain":
            self._show_reasoning_chain()

        elif cmd == "/clear":
            self._clear_session()

        elif cmd == "/status":
            self._show_status()

        elif cmd.startswith("/location "):
            # Simulate location share: /location 24.9165,67.1255
            self._simulate_location(cmd[10:])

        else:
            print(f"\n❌ Unknown command: {cmd}")
            print("   Type /help for available commands")

        return True

    def _show_help(self):
        """Show help message."""
        print("""
╔═══════════════════════════════════════════════════════════╗
║                    SEHAT SAATHI CLI                       ║
╠═══════════════════════════════════════════════════════════╣
║  AGENT MODES:                                             ║
║    /auto      - Auto mode (Orchestrator routes requests)  ║
║    /guide     - Switch to Guide (hospital search)         ║
║    /sameer    - Switch to Dr. Sameer (health assessment)  ║
║                                                           ║
║  DEBUG COMMANDS:                                          ║
║    /logs      - Show recent logs for this session         ║
║    /chain     - Show reasoning chain                      ║
║    /status    - Show current session status               ║
║                                                           ║
║  SESSION COMMANDS:                                        ║
║    /clear     - Clear session and start fresh             ║
║    /location LAT,LONG - Simulate WhatsApp location share  ║
║                                                           ║
║  OTHER:                                                   ║
║    /help      - Show this help                            ║
║    /quit      - Exit the CLI                              ║
╠═══════════════════════════════════════════════════════════╣
║  EXAMPLES:                                                ║
║    Auto: "I have fever and need a hospital in Gulshan"    ║
║    Guide: "Find hospital near Gulistan-e-Jauhar Karachi"  ║
║    Dr. Sameer: "I have chest pain"                        ║
║    Location: /location 24.9165,67.1255                    ║
╚═══════════════════════════════════════════════════════════╝
""")

    def _process_message(self, message: str):
        """Process user message with current agent."""
        print("\n" + "-"*50)

        try:
            if self.current_agent == "guide":
                response = self.guide.process_message(self.phone, message)
            else:
                response = self.dr_sameer.process_message(self.phone, message)

            # Display response
            if response.success and response.data:
                patient_message = response.data.get("patient_message", "")
                if patient_message:
                    print(f"\n🤖 Agent Response:\n")
                    # Format the message nicely
                    for line in patient_message.split('\n'):
                        print(f"   {line}")
                else:
                    print(f"\n🤖 Response: {response.data}")

                # Show state if Guide
                if self.current_agent == "guide" and self.phone in self.guide.sessions:
                    state = self.guide.sessions[self.phone].state
                    print(f"\n   [State: {state.value}]")
            else:
                print(f"\n⚠️ Response: {response.reasoning}")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

        print("-"*50)

    def _process_with_orchestrator(self, message: str):
        """Process user message through the orchestrator (auto mode)."""
        print("\n" + "-"*50)
        print("🧠 Planning Agent analyzing request...")

        try:
            # First show what the planner decided
            plan = self.orchestrator.planner.plan(message)
            print(f"\n📋 Plan:")
            print(f"   Intent: {plan.get('intent', 'unknown')}")

            # Check if clarification is needed
            if plan.get('needs_clarification'):
                print(f"   ❓ Needs Clarification: Yes")
            else:
                print(f"   Primary Agent: {plan.get('primary_agent', 'unknown')}")
                if plan.get('secondary_agents'):
                    print(f"   Workflow: {plan.get('primary_agent')} → {' → '.join(plan.get('secondary_agents', []))}")
                    print(f"   Mode: {plan.get('execution_mode', 'single')}")

            if plan.get('extracted_entities'):
                entities = plan.get('extracted_entities', {})
                if entities and any(v for v in entities.values() if v):
                    print(f"   Extracted: {entities}")

            print(f"   Reasoning: {plan.get('reasoning', '')[:70]}...")

            # Execute through orchestrator
            print("\n" + "-"*30)
            if plan.get('needs_clarification'):
                print("❓ Asking for clarification...")
            elif plan.get('secondary_agents'):
                agents = [plan.get('primary_agent')] + plan.get('secondary_agents', [])
                print(f"🔄 Multi-Agent: {' → '.join(agents).upper()}")
            else:
                print(f"🔄 Routing to {plan.get('primary_agent', 'guide').upper()}...")
            print("-"*30)

            response = self.orchestrator.process(
                phone_number=self.phone,
                user_message=message
            )

            # Display response
            if response.get("success"):
                patient_message = response.get("patient_message", "")
                if patient_message:
                    print(f"\n🤖 Response:\n")
                    for line in patient_message.split('\n'):
                        print(f"   {line}")

                # Show metadata
                metadata = response.get("metadata", {})
                if metadata.get("action") == "clarification_needed":
                    print(f"\n   [Awaiting user response...]")
                elif metadata.get("agents_executed"):
                    agents = metadata.get("agents_executed", [])
                    print(f"\n   [Agents: {' → '.join(agents)}]")
                else:
                    print(f"\n   [Agent: {metadata.get('agent', 'unknown')}]")
            else:
                print(f"\n⚠️ Response: {response.get('patient_message', 'Error occurred')}")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

        print("-"*50)

    def _simulate_location(self, coords_str: str):
        """Simulate WhatsApp location share."""
        try:
            lat, long = map(float, coords_str.split(","))
            print(f"\n📍 Simulating location share: ({lat}, {long})")

            if self.current_agent == "auto":
                response = self.orchestrator.process(
                    phone_number=self.phone,
                    user_message="My location",
                    location_coords=(lat, long)
                )
                if response.get("success"):
                    patient_message = response.get("patient_message", "")
                    if patient_message:
                        print(f"\n🤖 Agent Response:\n")
                        for line in patient_message.split('\n'):
                            print(f"   {line}")
                return

            elif self.current_agent == "guide":
                response = self.guide.process_message(
                    self.phone,
                    "My location",
                    location_coords=(lat, long)
                )

                if response.success and response.data:
                    patient_message = response.data.get("patient_message", "")
                    if patient_message:
                        print(f"\n🤖 Agent Response:\n")
                        for line in patient_message.split('\n'):
                            print(f"   {line}")
            else:
                print("   Location sharing only works with Guide agent")

        except ValueError:
            print("❌ Invalid coordinates. Use format: /location 24.9165,67.1255")

    def _show_logs(self, limit: int = 15):
        """Show recent logs for current session."""
        logs = self.logger.get_session_logs(self.phone, limit=limit)

        if not logs:
            print("\n📋 No logs for this session yet.")
            return

        print(f"\n📋 Recent Logs ({len(logs)} entries):")
        print("-"*60)

        for log in logs:
            level = log['level']
            agent = log['agent_name']
            msg = log['message'][:60] + "..." if len(log['message']) > 60 else log['message']

            # Color code by level
            if level == "REASONING":
                icon = "💭"
            elif level == "TOOL_CALL":
                icon = "🔧"
            elif level == "TOOL_RESULT":
                icon = "✓"
            elif level == "USER_INPUT":
                icon = "👤"
            elif level == "AGENT_OUTPUT":
                icon = "🤖"
            elif level == "HANDOFF":
                icon = "🔄"
            elif level == "ERROR":
                icon = "❌"
            else:
                icon = "•"

            print(f"  {icon} [{agent}] {msg}")

        print("-"*60)

    def _show_reasoning_chain(self):
        """Show reasoning chain for debugging."""
        chain = self.logger.get_reasoning_chain(self.phone)

        if not chain:
            print("\n🔗 No reasoning chain for this session yet.")
            return

        print(f"\n🔗 Reasoning Chain ({len(chain)} steps):")
        print("-"*60)

        for i, entry in enumerate(chain, 1):
            level = entry['level']
            action = entry['action']
            msg = entry['message'][:50] + "..." if len(entry['message']) > 50 else entry['message']

            if level == "REASONING":
                print(f"  {i}. 💭 {msg}")
            elif level == "TOOL_CALL":
                print(f"  {i}. 🔧 CALL: {action}")
            elif level == "TOOL_RESULT":
                duration = entry.get('duration_ms')
                time_str = f" ({duration:.0f}ms)" if duration else ""
                print(f"  {i}. ✓ RESULT: {action}{time_str}")
            elif level == "HANDOFF":
                to_agent = entry.get('data', {}).get('to_agent', 'Unknown')
                print(f"  {i}. 🔄 HANDOFF → {to_agent}")

        print("-"*60)

    def _show_status(self):
        """Show current session status."""
        print(f"\n📊 Session Status:")
        print(f"   Session ID: {self.phone}")
        print(f"   Current Agent: {self.current_agent}")

        # Guide session info
        if self.phone in self.guide.sessions:
            session = self.guide.sessions[self.phone]
            print(f"\n   Guide Session:")
            print(f"   - State: {session.state.value}")
            print(f"   - Specialty: {session.specialty_needed or 'None'}")
            print(f"   - Urgency: {session.urgency}")
            if session.resolved_location:
                loc = session.resolved_location
                print(f"   - Location: {loc.city or 'Unknown'} ({loc.lat:.4f}, {loc.long:.4f})")
            print(f"   - Results: {len(session.search_results)} hospitals")

        # Dr. Sameer session info
        if hasattr(self.dr_sameer, 'sessions') and self.phone in self.dr_sameer.sessions:
            session = self.dr_sameer.sessions[self.phone]
            print(f"\n   Dr. Sameer Session:")
            print(f"   - State: {session.state.value if hasattr(session.state, 'value') else session.state}")

        # Log count
        logs = self.logger.get_session_logs(self.phone, limit=1000)
        print(f"\n   Total Logs: {len(logs)}")

    def _clear_session(self):
        """Clear current session."""
        self.guide.clear_session(self.phone)
        if hasattr(self.dr_sameer, 'clear_session'):
            self.dr_sameer.clear_session(self.phone)
        self.logger.clear_session(self.phone)

        # Generate new session ID
        self.phone = f"+92-TEST-{datetime.now().strftime('%H%M%S')}"
        print(f"\n✓ Session cleared. New session: {self.phone}")


def main():
    """Main entry point."""
    import sys

    # Check for --auto flag to start in orchestrator mode
    use_orchestrator = "--auto" in sys.argv or "-a" in sys.argv

    tester = CLITester(use_orchestrator=use_orchestrator)
    tester.run()


if __name__ == "__main__":
    main()
