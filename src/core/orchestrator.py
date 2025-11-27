"""
Multi-Agent Orchestration Framework

A LangGraph-inspired orchestration system for Sehat Saathi that:
1. Routes user requests to appropriate agent(s)
2. Manages agent handoffs and parallel execution
3. Maintains conversation state across agents
4. Provides planning and decision-making capabilities
"""
import json
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import google.generativeai as genai

from .config import settings
from .logger import get_agent_logger, LogCategory, LogLevel
from .context_store import get_context_store, ContextStore, AgentState


class AgentType(Enum):
    """Available agent types in the system"""
    GUIDE = "guide"                    # Hospital search & navigation
    DR_SAMEER = "dr_sameer"           # Health assessment & triage
    HAQDAR = "haqdar"                 # Eligibility verification
    YAADGAR = "yaadgar"               # Medical history tracker
    KHANDAN = "khandan"               # Family health manager
    MUHAFIZ = "muhafiz"               # Health protector/emergency
    SCHEDULER = "scheduler"            # Appointment scheduling
    BILLING = "billing"               # Cost & insurance
    CLINICAL = "clinical"             # Clinical decision support
    HOSPITAL_BOOKING = "hospital_booking"  # Hospital resource booking (beds, blood, equipment)
    DOCTOR_APPOINTMENT = "doctor_appointment"  # Doctor search & appointment booking


class ExecutionMode(Enum):
    """How to execute multiple agents"""
    SEQUENTIAL = "sequential"          # One after another
    PARALLEL = "parallel"              # All at once
    CONDITIONAL = "conditional"        # Based on conditions


@dataclass
class AgentCapability:
    """Describes what an agent can do"""
    agent_type: AgentType
    name: str
    description: str
    keywords: List[str]                # Keywords that trigger this agent
    can_handoff_to: List[AgentType]   # Agents this one can hand off to
    priority: int = 5                  # Higher = more important (1-10)

    def matches_intent(self, intent: str) -> float:
        """Score how well this agent matches the intent (0-1)"""
        intent_lower = intent.lower()
        score = 0.0

        for keyword in self.keywords:
            if keyword.lower() in intent_lower:
                score += 0.2

        return min(score, 1.0)


@dataclass
class ConversationState:
    """Shared state that flows between agents"""
    session_id: str
    phone_number: str
    user_message: str
    intent: Optional[str] = None
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    agent_responses: Dict[str, Any] = field(default_factory=dict)
    handoff_context: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    current_agent: Optional[AgentType] = None
    completed_agents: List[AgentType] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowEdge:
    """An edge in the workflow graph (handoff between agents)"""
    from_agent: AgentType
    to_agent: AgentType
    condition: Optional[Callable[[ConversationState], bool]] = None
    priority: int = 5


@dataclass
class WorkflowNode:
    """A node in the workflow graph (an agent)"""
    agent_type: AgentType
    execute: Callable[[ConversationState], ConversationState]
    edges: List[WorkflowEdge] = field(default_factory=list)


class AgentRegistry:
    """Central registry of all available agents"""

    def __init__(self):
        self.agents: Dict[AgentType, AgentCapability] = {}
        self._agent_instances: Dict[AgentType, Any] = {}
        self._register_default_agents()

    def _register_default_agents(self):
        """Register the default Sehat Saathi agents"""
        self.register(AgentCapability(
            agent_type=AgentType.DR_SAMEER,
            name="Dr. Sameer",
            description="Health assessment and symptom analysis. Provides initial triage and care recommendations.",
            keywords=[
                "health", "symptom", "pain", "sick", "feeling", "illness", "disease",
                "fever", "headache", "stomach", "chest", "breathing", "cough",
                "tabiyat", "dard", "bimar", "bukhar", "dard", "seena", "sans"
            ],
            can_handoff_to=[AgentType.GUIDE, AgentType.MUHAFIZ],
            priority=8
        ))

        self.register(AgentCapability(
            agent_type=AgentType.GUIDE,
            name="Guide",
            description="Hospital search, navigation, and appointment booking. Finds nearby healthcare facilities.",
            keywords=[
                "hospital", "clinic", "doctor", "nearby", "near", "location", "find",
                "appointment", "book", "direction", "map", "where", "closest",
                "qareeb", "hospital", "doctor", "appointment", "kahan"
            ],
            can_handoff_to=[AgentType.SCHEDULER, AgentType.BILLING],
            priority=7
        ))

        self.register(AgentCapability(
            agent_type=AgentType.MUHAFIZ,
            name="Muhafiz",
            description="Emergency health protector. Handles urgent medical situations.",
            keywords=[
                "emergency", "urgent", "critical", "accident", "serious", "ambulance",
                "emergency", "fori", "hadsaa", "ambulance"
            ],
            can_handoff_to=[AgentType.GUIDE],
            priority=10
        ))

        self.register(AgentCapability(
            agent_type=AgentType.HAQDAR,
            name="Haqdar",
            description="Eligibility verification for health programs and insurance.",
            keywords=[
                "eligibility", "eligible", "program", "sehat sahulat", "insurance",
                "card", "scheme", "benefit", "coverage",
                "sehat card", "eligibility", "scheme"
            ],
            can_handoff_to=[AgentType.GUIDE, AgentType.BILLING],
            priority=5
        ))

        self.register(AgentCapability(
            agent_type=AgentType.YAADGAR,
            name="Yaadgar",
            description="Medical history tracker. Maintains and retrieves patient health records.",
            keywords=[
                "history", "record", "past", "previous", "medication", "allergy",
                "treatment", "prescription", "report", "test",
                "history", "record", "dawai", "allergy"
            ],
            can_handoff_to=[AgentType.DR_SAMEER],
            priority=4
        ))

        self.register(AgentCapability(
            agent_type=AgentType.KHANDAN,
            name="Khandan",
            description="Family health manager. Manages health records for family members.",
            keywords=[
                "family", "member", "child", "parent", "spouse", "dependent",
                "khandan", "bachay", "family", "member"
            ],
            can_handoff_to=[AgentType.DR_SAMEER, AgentType.GUIDE],
            priority=3
        ))

        self.register(AgentCapability(
            agent_type=AgentType.SCHEDULER,
            name="Scheduler",
            description="Appointment scheduling and management.",
            keywords=[
                "schedule", "appointment", "slot", "time", "available", "book",
                "cancel", "reschedule", "calendar",
                "appointment", "time", "slot"
            ],
            can_handoff_to=[AgentType.GUIDE],
            priority=6
        ))

        self.register(AgentCapability(
            agent_type=AgentType.BILLING,
            name="Billing",
            description="Cost estimation and insurance processing.",
            keywords=[
                "cost", "price", "fee", "pay", "insurance", "bill", "charge",
                "expensive", "cheap", "afford",
                "qeemat", "paisa", "insurance"
            ],
            can_handoff_to=[AgentType.HAQDAR],
            priority=4
        ))

        self.register(AgentCapability(
            agent_type=AgentType.HOSPITAL_BOOKING,
            name="Hospital Booking",
            description="Hospital resource booking for beds, blood bank, and equipment like ventilators.",
            keywords=[
                "bed", "icu", "icu bed", "ventilator", "blood", "blood bank",
                "oxygen", "dialysis", "ambulance", "admit", "admission",
                "book bed", "reserve", "emergency bed", "general ward",
                "khoon", "bistar", "admit", "dakhil"
            ],
            can_handoff_to=[AgentType.GUIDE, AgentType.BILLING],
            priority=8
        ))

        self.register(AgentCapability(
            agent_type=AgentType.DOCTOR_APPOINTMENT,
            name="Doctor Appointment",
            description="Find and book appointments with doctors by specialization, city, and availability.",
            keywords=[
                "doctor", "appointment", "specialist", "cardiologist", "dermatologist",
                "gynecologist", "orthopedic", "neurologist", "pediatrician",
                "find doctor", "book doctor", "doctor appointment", "opd",
                "skin doctor", "heart doctor", "bone doctor", "child doctor",
                "doctor dhundein", "appointment lein", "doctor milna"
            ],
            can_handoff_to=[AgentType.GUIDE, AgentType.BILLING],
            priority=7
        ))

    def register(self, capability: AgentCapability):
        """Register an agent capability"""
        self.agents[capability.agent_type] = capability

    def register_instance(self, agent_type: AgentType, instance: Any):
        """Register an agent instance"""
        self._agent_instances[agent_type] = instance

    def get_instance(self, agent_type: AgentType) -> Optional[Any]:
        """Get agent instance"""
        return self._agent_instances.get(agent_type)

    def get_capability(self, agent_type: AgentType) -> Optional[AgentCapability]:
        """Get agent capability"""
        return self.agents.get(agent_type)

    def find_matching_agents(self, intent: str, limit: int = 3) -> List[Tuple[AgentType, float]]:
        """Find agents that match the given intent, sorted by score"""
        scores = []
        for agent_type, capability in self.agents.items():
            score = capability.matches_intent(intent)
            if score > 0:
                # Adjust score by priority
                adjusted_score = score * (capability.priority / 10)
                scores.append((agent_type, adjusted_score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:limit]

    def get_all_agents(self) -> List[AgentCapability]:
        """Get all registered agents"""
        return list(self.agents.values())


class PlanningAgent:
    """
    The orchestrator that decides which agent(s) to use.

    Uses LLM to:
    1. Understand user intent
    2. Select appropriate agent(s)
    3. Plan the execution order
    4. Handle multi-agent coordination
    """

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.logger = get_agent_logger()

        # Configure Gemini for planning
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(model_name=settings.gemini_model)

        # Planning prompt
        self.planning_prompt = self._build_planning_prompt()

    def _build_planning_prompt(self) -> str:
        """Build the planning system prompt"""
        agent_descriptions = []
        for capability in self.registry.get_all_agents():
            agent_descriptions.append(
                f"- **{capability.name}** ({capability.agent_type.value}): {capability.description}"
            )

        return f"""You are a healthcare assistant orchestrator for Sehat Saathi in Pakistan.

AVAILABLE AGENTS:
{chr(10).join(agent_descriptions)}

YOUR TASK:
Analyze the user's message and determine the best course of action:
1. Does the request need clarification before proceeding?
2. What is the primary intent?
3. Which agent(s) should handle this request?
4. Should agents work sequentially (one after another) or can the primary handle alone?
5. Extract relevant entities (location, symptoms, urgency)

RESPONSE FORMAT (JSON):
{{
    "needs_clarification": true/false,
    "clarification_question": "question to ask user (only if needs_clarification is true)",
    "intent": "brief description of user intent",
    "primary_agent": "agent_type (e.g., dr_sameer, guide)",
    "secondary_agents": ["list of additional agents if needed"],
    "execution_mode": "single/sequential/parallel",
    "workflow_description": "how agents should work together (if multiple)",
    "extracted_entities": {{
        "location": "if mentioned or null",
        "symptoms": ["list if health-related"],
        "urgency": "low/medium/high/emergency"
    }},
    "reasoning": "brief explanation of your decision"
}}

WHEN TO ASK FOR CLARIFICATION:
- User mentions symptoms but no severity/duration → Ask about severity
- User wants hospital but no location mentioned → Ask for location
- Ambiguous request that could go multiple ways → Ask to clarify
- Missing critical information for proper routing

MULTI-AGENT WORKFLOWS (execution_mode="sequential"):
- "I have fever and need a hospital nearby" → dr_sameer (assess) → guide (find hospital)
- "Check my eligibility and book appointment" → haqdar (eligibility) → guide (booking)
- "Emergency chest pain, need ambulance" → muhafiz (emergency) → guide (navigation)
- "Book an ICU bed" → hospital_booking (book resource)
- "Find cardiologist in Karachi" → doctor_appointment (search and book)
- "I have chest pain, find a heart doctor" → dr_sameer (assess) → doctor_appointment (find specialist)

SINGLE AGENT (execution_mode="single"):
- Simple symptom query → dr_sameer only
- Just find hospital → guide only
- Just check eligibility → haqdar only
- Book bed/blood/ventilator → hospital_booking only
- Find/book doctor appointment → doctor_appointment only

RULES:
1. For health symptoms → Start with Dr. Sameer (dr_sameer)
2. For hospital/location queries → Use Guide (guide)
3. For emergencies → Use Muhafiz (muhafiz) first, then Guide
4. For eligibility → Use Haqdar (haqdar)
5. If symptoms + hospital needed → Sequential: dr_sameer → guide
6. For hospital resource booking (beds, blood, ventilators, equipment) → Use Hospital Booking (hospital_booking)
7. For doctor search/appointment booking → Use Doctor Appointment (doctor_appointment)
8. If symptoms + doctor needed → Sequential: dr_sameer → doctor_appointment
9. ALWAYS ask for location if hospital is needed but location not provided
10. ALWAYS ask about symptom severity for vague health complaints

IMPORTANT: Respond ONLY with valid JSON, no additional text."""

    def plan(self, user_message: str, conversation_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Analyze user message and create execution plan.

        Returns:
            Plan with selected agents and execution order
        """
        try:
            # Build context from history
            history_context = ""
            if conversation_history:
                history_context = "\n\nCONVERSATION HISTORY:\n"
                for msg in conversation_history[-5:]:  # Last 5 messages
                    role = msg.get("role", "user")
                    content = msg.get("content", "")[:100]
                    history_context += f"{role}: {content}\n"

            # Create planning request
            prompt = f"""{self.planning_prompt}

USER MESSAGE: {user_message}
{history_context}

Analyze and provide your plan:"""

            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent planning
                    max_output_tokens=500,
                )
            )

            # Parse JSON response
            response_text = response.text.strip()

            # Handle markdown code blocks
            if "```json" in response_text:
                json_start = response_text.index("```json") + 7
                json_end = response_text.index("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.index("```") + 3
                json_end = response_text.index("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            plan = json.loads(response_text)

            # Log the plan
            self.logger.log_reasoning(
                session_id="planner",
                agent_name="PlanningAgent",
                thought=f"Plan: {plan.get('primary_agent')} for intent: {plan.get('intent')[:50]}",
                category=LogCategory.ORCHESTRATION,
                data=plan
            )

            return plan

        except json.JSONDecodeError as e:
            # Fallback to keyword-based routing
            self.logger.log_error(
                session_id="planner",
                agent_name="PlanningAgent",
                error=f"JSON parse error: {e}. Using fallback routing.",
                category=LogCategory.ORCHESTRATION
            )
            return self._fallback_plan(user_message)
        except Exception as e:
            self.logger.log_error(
                session_id="planner",
                agent_name="PlanningAgent",
                error=f"Planning error: {e}",
                category=LogCategory.ORCHESTRATION
            )
            return self._fallback_plan(user_message)

    def _fallback_plan(self, user_message: str) -> Dict[str, Any]:
        """Fallback keyword-based planning"""
        # Find matching agents
        matches = self.registry.find_matching_agents(user_message)

        if matches:
            primary_agent = matches[0][0].value
            secondary = [m[0].value for m in matches[1:]]
        else:
            # Default to Dr. Sameer for health queries, Guide for others
            if any(word in user_message.lower() for word in ["hospital", "clinic", "near", "find", "where"]):
                primary_agent = AgentType.GUIDE.value
            else:
                primary_agent = AgentType.DR_SAMEER.value
            secondary = []

        return {
            "intent": "user request",
            "primary_agent": primary_agent,
            "secondary_agents": secondary,
            "execution_mode": "sequential",
            "extracted_entities": {},
            "reasoning": "Fallback keyword-based routing"
        }


class Orchestrator:
    """
    Main orchestrator that coordinates multi-agent execution.

    Features:
    - Automatic agent selection via PlanningAgent
    - Sequential and parallel execution
    - State management across agents
    - Handoff handling
    """

    def __init__(self):
        self.registry = AgentRegistry()
        self.planner = PlanningAgent(self.registry)
        self.logger = get_agent_logger()
        self.context_store = get_context_store()

        # Active sessions
        self.sessions: Dict[str, ConversationState] = {}

        print("✓ Orchestrator initialized with planning capabilities")

    def register_agent(self, agent_type: AgentType, instance: Any):
        """Register an agent instance with the orchestrator"""
        self.registry.register_instance(agent_type, instance)

    def get_or_create_session(self, phone_number: str) -> ConversationState:
        """Get existing session or create new one"""
        if phone_number not in self.sessions:
            self.sessions[phone_number] = ConversationState(
                session_id=f"session-{phone_number}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                phone_number=phone_number,
                user_message=""
            )
        return self.sessions[phone_number]

    def process(
        self,
        phone_number: str,
        user_message: str,
        location_coords: Optional[Tuple[float, float]] = None
    ) -> Dict[str, Any]:
        """
        Process user message through the orchestration pipeline.

        Args:
            phone_number: User's phone number
            user_message: The user's message
            location_coords: Optional (lat, long) from WhatsApp location share

        Returns:
            Response with patient_message and metadata
        """
        # Get/create session
        state = self.get_or_create_session(phone_number)
        state.user_message = user_message

        # Add location if provided
        if location_coords:
            state.extracted_entities["location_coords"] = location_coords

        # Log incoming message
        self.logger.log(
            session_id=state.session_id,
            agent_name="Orchestrator",
            level=LogLevel.USER_INPUT,
            category=LogCategory.ORCHESTRATION,
            action="receive_message",
            message=user_message[:100]
        )

        # ========== CHECK FOR ACTIVE AGENT SESSION ==========
        # If an agent is awaiting input (e.g., user selecting 1-5), route directly to that agent
        is_awaiting, agent_state = self.context_store.is_awaiting_input(phone_number)

        if is_awaiting and agent_state:
            self.logger.log_reasoning(
                session_id=state.session_id,
                agent_name="Orchestrator",
                thought=f"Active session: {agent_state.agent_name} awaiting {agent_state.awaiting_input_type}",
                category=LogCategory.ORCHESTRATION,
                data={"agent_state": agent_state.to_dict()}
            )

            # Route directly to the active agent without re-planning
            return self._route_to_active_agent(
                state, agent_state, phone_number, user_message, location_coords
            )

        # ========== NO ACTIVE SESSION - PLAN EXECUTION ==========
        # Plan the execution
        plan = self.planner.plan(user_message, state.conversation_history)
        state.intent = plan.get("intent")
        state.extracted_entities.update(plan.get("extracted_entities", {}))

        # Store plan in state for reference
        state.metadata["current_plan"] = plan

        # Check if clarification is needed
        if plan.get("needs_clarification", False):
            clarification_question = plan.get("clarification_question", "Could you please provide more details?")

            # Log clarification request
            self.logger.log_reasoning(
                session_id=state.session_id,
                agent_name="Orchestrator",
                thought=f"Needs clarification: {clarification_question[:50]}",
                category=LogCategory.ORCHESTRATION,
                data={"reason": plan.get("reasoning", "")}
            )

            # Update conversation history
            state.conversation_history.append({"role": "user", "content": user_message})
            state.conversation_history.append({"role": "assistant", "content": clarification_question})

            return {
                "success": True,
                "patient_message": clarification_question,
                "metadata": {
                    "action": "clarification_needed",
                    "intent": state.intent,
                    "session_id": state.session_id,
                    "plan": plan
                }
            }

        # Get the primary agent
        primary_agent_type = AgentType(plan.get("primary_agent", "guide"))
        agent_instance = self.registry.get_instance(primary_agent_type)

        if not agent_instance:
            return {
                "success": False,
                "patient_message": "I'm sorry, the requested service is not available right now. Please try again.",
                "metadata": {"error": f"Agent {primary_agent_type} not registered"}
            }

        # Execute based on execution mode
        execution_mode = plan.get("execution_mode", "single")
        secondary_agents = plan.get("secondary_agents", [])

        # Execute the primary agent
        state.current_agent = primary_agent_type

        try:
            # Call the agent's process_message method
            response = self._execute_agent(
                agent_instance,
                primary_agent_type,
                phone_number,
                user_message,
                location_coords,
                state
            )

            # Store response
            state.agent_responses[primary_agent_type.value] = response
            state.completed_agents.append(primary_agent_type)

            # Update conversation history
            state.conversation_history.append({
                "role": "user",
                "content": user_message
            })

            if response.success and response.data:
                patient_message = response.data.get("patient_message", "")
                state.conversation_history.append({
                    "role": "assistant",
                    "content": patient_message
                })

            # Log completion
            self.logger.log_tool_result(
                session_id=state.session_id,
                agent_name="Orchestrator",
                tool_name="execute_agent",
                result_summary=f"Completed {primary_agent_type.value}",
                success=response.success,
                category=LogCategory.ORCHESTRATION,
                data={"agent": primary_agent_type.value}
            )

            # Handle sequential multi-agent workflow
            if execution_mode == "sequential" and secondary_agents and response.success:
                return self._execute_sequential_workflow(
                    state, response, secondary_agents, phone_number, location_coords
                )

            # Check for handoffs from agent response
            if response.data and response.data.get("handoff_to"):
                return self._handle_handoff(state, response)

            return {
                "success": response.success,
                "patient_message": response.data.get("patient_message", "") if response.data else response.reasoning,
                "metadata": {
                    "agent": primary_agent_type.value,
                    "intent": state.intent,
                    "session_id": state.session_id,
                    "execution_mode": execution_mode
                }
            }

        except Exception as e:
            self.logger.log_error(
                session_id=state.session_id,
                agent_name="Orchestrator",
                error=str(e),
                category=LogCategory.ORCHESTRATION
            )
            return {
                "success": False,
                "patient_message": "An error occurred while processing your request. Please try again.",
                "metadata": {"error": str(e)}
            }

    def _route_to_active_agent(
        self,
        state: ConversationState,
        agent_state: AgentState,
        phone_number: str,
        user_message: str,
        location_coords: Optional[Tuple[float, float]]
    ) -> Dict[str, Any]:
        """
        Route message directly to an active agent that's awaiting input.

        This bypasses the planning phase when we know an agent is waiting
        for user response (e.g., selection from numbered list).
        """
        try:
            agent_type = AgentType(agent_state.agent_type)
            agent_instance = self.registry.get_instance(agent_type)

            if not agent_instance:
                # Agent not registered, clear the state and re-plan
                self.context_store.clear_agent_state(phone_number)
                return self.process(phone_number, user_message, location_coords)

            state.current_agent = agent_type

            # Execute the agent
            response = self._execute_agent(
                agent_instance,
                agent_type,
                phone_number,
                user_message,
                location_coords,
                state
            )

            # Store response
            state.agent_responses[agent_type.value] = response

            # Update conversation history
            state.conversation_history.append({
                "role": "user",
                "content": user_message
            })

            if response.success and response.data:
                patient_message = response.data.get("patient_message", "")
                state.conversation_history.append({
                    "role": "assistant",
                    "content": patient_message
                })

            # Log completion
            self.logger.log_tool_result(
                session_id=state.session_id,
                agent_name="Orchestrator",
                tool_name="route_to_active_agent",
                result_summary=f"Routed to active {agent_type.value}",
                success=response.success,
                category=LogCategory.ORCHESTRATION,
                data={"agent": agent_type.value, "input_type": agent_state.awaiting_input_type}
            )

            return {
                "success": response.success,
                "patient_message": response.data.get("patient_message", "") if response.data else response.reasoning,
                "metadata": {
                    "agent": agent_type.value,
                    "routed_directly": True,
                    "awaiting_input_type": agent_state.awaiting_input_type,
                    "session_id": state.session_id
                }
            }

        except Exception as e:
            self.logger.log_error(
                session_id=state.session_id,
                agent_name="Orchestrator",
                error=f"Error routing to active agent: {e}",
                category=LogCategory.ORCHESTRATION
            )
            # Clear state and fall back to re-planning
            self.context_store.clear_agent_state(phone_number)
            return {
                "success": False,
                "patient_message": "I'm sorry, there was an issue. Please try again.",
                "metadata": {"error": str(e)}
            }

    def _handle_handoff(self, state: ConversationState, response) -> Dict[str, Any]:
        """Handle handoff to another agent"""
        handoff_to = response.data.get("handoff_to")
        handoff_context = response.data.get("handoff_context", {})

        try:
            target_agent_type = AgentType(handoff_to)
            target_agent = self.registry.get_instance(target_agent_type)

            if not target_agent:
                return {
                    "success": True,
                    "patient_message": response.data.get("patient_message", ""),
                    "metadata": {"handoff_pending": handoff_to}
                }

            # Store handoff context
            state.handoff_context = handoff_context
            state.current_agent = target_agent_type

            # Log handoff
            self.logger.log_handoff(
                session_id=state.session_id,
                from_agent=state.completed_agents[-1].value if state.completed_agents else "unknown",
                to_agent=target_agent_type.value,
                context=handoff_context,
                category=LogCategory.ORCHESTRATION
            )

            # Execute target agent with handoff context
            if hasattr(target_agent, 'handle_handoff'):
                target_response = target_agent.handle_handoff(
                    state.phone_number,
                    handoff_context
                )
            else:
                # Use process_message with context in message
                target_response = target_agent.process_message(
                    state.phone_number,
                    f"[Handoff from {state.completed_agents[-1].value}] {state.user_message}"
                )

            return {
                "success": target_response.success,
                "patient_message": target_response.data.get("patient_message", "") if target_response.data else "",
                "metadata": {
                    "agent": target_agent_type.value,
                    "handoff_from": state.completed_agents[-1].value if state.completed_agents else None,
                    "session_id": state.session_id
                }
            }

        except Exception as e:
            self.logger.log_error(
                session_id=state.session_id,
                agent_name="Orchestrator",
                error=f"Handoff error: {e}",
                category=LogCategory.ORCHESTRATION
            )
            return {
                "success": True,
                "patient_message": response.data.get("patient_message", ""),
                "metadata": {"handoff_error": str(e)}
            }

    def _execute_agent(
        self,
        agent_instance,
        agent_type: AgentType,
        phone_number: str,
        message: str,
        location_coords: Optional[Tuple[float, float]],
        state: ConversationState
    ):
        """Execute a single agent with appropriate parameters"""
        if hasattr(agent_instance, 'process_message'):
            # Only pass location_coords to agents that support it (Guide)
            if agent_type == AgentType.GUIDE and location_coords:
                return agent_instance.process_message(
                    phone_number,
                    message,
                    location_coords=location_coords
                )
            else:
                return agent_instance.process_message(
                    phone_number,
                    message
                )
        else:
            from ..core.agent import AgentResponse
            return AgentResponse(
                success=False,
                reasoning="Agent does not have process_message method"
            )

    def _execute_sequential_workflow(
        self,
        state: ConversationState,
        primary_response,
        secondary_agents: List[str],
        phone_number: str,
        location_coords: Optional[Tuple[float, float]]
    ) -> Dict[str, Any]:
        """
        Execute multiple agents in sequence, passing context between them.

        For example: dr_sameer (assess symptoms) → guide (find hospital)
        """
        combined_messages = []
        last_response = primary_response

        # Collect primary agent's response
        if primary_response.success and primary_response.data:
            combined_messages.append(primary_response.data.get("patient_message", ""))

        # Execute secondary agents in sequence
        for agent_name in secondary_agents:
            try:
                agent_type = AgentType(agent_name)
                agent_instance = self.registry.get_instance(agent_type)

                if not agent_instance:
                    continue

                # Build context message from previous agent
                context_message = state.user_message
                if last_response.data:
                    # Pass relevant context to next agent
                    handoff_context = last_response.data.get("handoff_context", {})
                    if handoff_context:
                        # Guide needs location for hospital search
                        if agent_type == AgentType.GUIDE:
                            location = state.extracted_entities.get("location")
                            if location:
                                context_message = f"Find hospital near {location}"
                            else:
                                context_message = f"Find nearby hospital for patient"

                # Log the sequential execution
                self.logger.log_reasoning(
                    session_id=state.session_id,
                    agent_name="Orchestrator",
                    thought=f"Sequential workflow: executing {agent_name}",
                    category=LogCategory.ORCHESTRATION,
                    data={"previous_agent": state.completed_agents[-1].value if state.completed_agents else None}
                )

                # Execute the agent
                response = self._execute_agent(
                    agent_instance,
                    agent_type,
                    phone_number,
                    context_message,
                    location_coords,
                    state
                )

                # Store response
                state.agent_responses[agent_name] = response
                state.completed_agents.append(agent_type)
                last_response = response

                if response.success and response.data:
                    combined_messages.append(response.data.get("patient_message", ""))

            except Exception as e:
                self.logger.log_error(
                    session_id=state.session_id,
                    agent_name="Orchestrator",
                    error=f"Sequential workflow error for {agent_name}: {e}",
                    category=LogCategory.ORCHESTRATION
                )

        # Combine all messages
        final_message = "\n\n---\n\n".join(filter(None, combined_messages))

        return {
            "success": True,
            "patient_message": final_message,
            "metadata": {
                "agents_executed": [a.value for a in state.completed_agents],
                "execution_mode": "sequential",
                "intent": state.intent,
                "session_id": state.session_id
            }
        }

    def clear_session(self, phone_number: str):
        """Clear a user's session"""
        if phone_number in self.sessions:
            del self.sessions[phone_number]


# Global instance
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Get or create the orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
