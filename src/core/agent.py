"""Base Agent class with reasoning capabilities"""
import json
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
import google.generativeai as genai
from .config import settings


# Configure Gemini
genai.configure(api_key=settings.gemini_api_key)


@dataclass
class AgentMessage:
    """Message structure for agent communication"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    from_agent: Dict[str, str] = field(default_factory=dict)
    to_agent: Dict[str, str] = field(default_factory=dict)
    conversation_id: Optional[str] = None
    message_type: str = "request"  # request, response, broadcast
    priority: str = "normal"  # normal, high, critical
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    requires_response: bool = True
    response_deadline: Optional[str] = None
    encryption: str = "end-to-end"
    audit_trail: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AgentResponse:
    """Response structure from agent"""
    success: bool = True
    data: Any = None
    reasoning: str = ""
    confidence: float = 0.0
    alternatives: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)


class Agent:
    """Base Agent class with autonomous reasoning capabilities"""

    def __init__(
        self,
        agent_id: str,
        name: str,
        role: str,
        organization: str,
        system_prompt: str,
        tools: Optional[List[str]] = None,
        temperature: Optional[float] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.organization = organization
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.temperature = temperature or settings.agent_reasoning_temperature

        # Conversation history
        self.conversation_history: List[Dict[str, str]] = []

        # Message handlers
        self.message_handlers: Dict[str, Callable] = {}

        # Decision log
        self.decision_log: List[Dict[str, Any]] = []

        # Initialize Gemini model
        self.model = genai.GenerativeModel(
            model_name=settings.gemini_model,
        )

        # Build system instruction
        self.system_instruction = self._build_system_instruction()

        # Initialize chat session with system instruction in history
        self.chat = self.model.start_chat(history=[
            {
                "role": "user",
                "parts": [f"SYSTEM INSTRUCTION:\n{self.system_instruction}\n\nAcknowledge that you understand your role."]
            },
            {
                "role": "model",
                "parts": ["I understand my role and responsibilities. I am ready to assist as instructed."]
            }
        ])

    def _build_system_instruction(self) -> str:
        """Build comprehensive system instruction for the agent"""
        return f"""You are {self.name}, an AI agent in the Sehat Saathi healthcare system.

ROLE: {self.role}
ORGANIZATION: {self.organization}
AGENT ID: {self.agent_id}

{self.system_prompt}

IMPORTANT INSTRUCTIONS:
1. You make autonomous decisions based on available information
2. When communicating with other agents, be clear and structured
3. Always explain your reasoning process
4. Consider multiple options and select the best one
5. You can negotiate with other agents to reach optimal outcomes
6. Prioritize patient safety and wellbeing above all else
7. Provide responses in JSON format when structured data is required
8. For patient-facing communication, use simple Urdu/English that common people understand

COMMUNICATION STYLE:
- Be empathetic and supportive for patient interactions
- Be professional and efficient for agent-to-agent communication
- Use medical terminology accurately but explain it simply to patients
- Respect cultural context of Pakistan (gender preferences, family involvement)

DECISION MAKING:
- Always weigh multiple factors before deciding
- Document your reasoning process
- Consider urgency, cost, quality, and accessibility
- Seek consensus when possible, but act decisively when needed

Remember: You are part of an autonomous multi-agent system. Make decisions that benefit the overall healthcare ecosystem while prioritizing individual patient needs.
"""

    def reason(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """
        Core reasoning method using Gemini

        Args:
            prompt: The reasoning prompt
            context: Additional context for reasoning

        Returns:
            AgentResponse with reasoning and decision
        """
        try:
            # Build full prompt with context
            full_prompt = self._build_prompt_with_context(prompt, context)

            # Get response from Gemini
            response = self.chat.send_message(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=settings.gemini_max_tokens,
                )
            )

            # Parse response
            response_text = response.text

            # Try to extract JSON if present
            try:
                # Look for JSON in response
                if "```json" in response_text:
                    json_start = response_text.index("```json") + 7
                    json_end = response_text.index("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                    data = json.loads(json_text)
                    reasoning = response_text.replace(f"```json{json_text}```", "").strip()
                elif response_text.strip().startswith("{"):
                    data = json.loads(response_text)
                    reasoning = "Structured response"
                else:
                    data = {"response": response_text}
                    reasoning = response_text
            except (json.JSONDecodeError, ValueError):
                data = {"response": response_text}
                reasoning = response_text

            # Log decision
            self._log_decision(prompt, data, reasoning, context)

            return AgentResponse(
                success=True,
                data=data,
                reasoning=reasoning,
                confidence=0.8,  # Can be extracted from response if model provides it
                metadata={"agent_id": self.agent_id, "timestamp": datetime.utcnow().isoformat()}
            )

        except Exception as e:
            print(f"Error in reasoning: {e}")
            return AgentResponse(
                success=False,
                data=None,
                reasoning=f"Error occurred: {str(e)}",
                confidence=0.0,
            )

    def _build_prompt_with_context(self, prompt: str, context: Optional[Dict[str, Any]]) -> str:
        """Build prompt with context"""
        if not context:
            return prompt

        context_str = "CONTEXT:\n"
        for key, value in context.items():
            context_str += f"{key}: {json.dumps(value, indent=2)}\n"

        return f"{context_str}\n\nTASK:\n{prompt}"

    def process_message(self, message: AgentMessage) -> AgentResponse:
        """
        Process incoming message from another agent

        Args:
            message: AgentMessage from another agent

        Returns:
            AgentResponse
        """
        # Check if there's a specific handler for this action
        if message.action in self.message_handlers:
            return self.message_handlers[message.action](message)

        # Default: use reasoning to process message
        prompt = f"""You received a message from another agent:

FROM: {message.from_agent.get('name')} ({message.from_agent.get('id')})
ACTION: {message.action}
PRIORITY: {message.priority}
PAYLOAD: {json.dumps(message.payload, indent=2)}

Based on your role as {self.name}, how should you respond to this message?

Provide your response in JSON format with the following structure:
{{
    "decision": "your decision",
    "reasoning": "your reasoning",
    "response_payload": {{
        // structured response data
    }}
}}
"""

        return self.reason(prompt, context={"incoming_message": message.to_dict()})

    def send_message(
        self,
        to_agent: Dict[str, str],
        action: str,
        payload: Dict[str, Any],
        priority: str = "normal",
        requires_response: bool = True
    ) -> AgentMessage:
        """
        Create a message to send to another agent

        Args:
            to_agent: Destination agent info
            action: Action type
            payload: Message payload
            priority: Message priority
            requires_response: Whether response is required

        Returns:
            AgentMessage
        """
        message = AgentMessage(
            from_agent={
                "id": self.agent_id,
                "name": self.name,
                "role": self.role,
                "organization": self.organization,
            },
            to_agent=to_agent,
            action=action,
            payload=payload,
            priority=priority,
            requires_response=requires_response,
        )

        return message

    def register_message_handler(self, action: str, handler: Callable):
        """Register a handler for a specific message action"""
        self.message_handlers[action] = handler

    def _log_decision(
        self,
        prompt: str,
        decision: Any,
        reasoning: str,
        context: Optional[Dict[str, Any]]
    ):
        """Log decision for audit trail"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
            "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "decision": str(decision)[:200] + "..." if len(str(decision)) > 200 else str(decision),
            "reasoning": reasoning[:200] + "..." if len(reasoning) > 200 else reasoning,
            "context": context,
        }
        self.decision_log.append(log_entry)

    def get_decision_log(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent decision log"""
        return self.decision_log[-limit:]

    def negotiate(
        self,
        other_agents: List[Dict[str, str]],
        proposal: Dict[str, Any],
        max_rounds: int = 3
    ) -> AgentResponse:
        """
        Negotiate with other agents

        Args:
            other_agents: List of agents to negotiate with
            proposal: Initial proposal
            max_rounds: Maximum negotiation rounds

        Returns:
            AgentResponse with negotiation result
        """
        prompt = f"""You need to negotiate with {len(other_agents)} other agents.

YOUR PROPOSAL:
{json.dumps(proposal, indent=2)}

OTHER AGENTS:
{json.dumps(other_agents, indent=2)}

Based on your role, create a negotiation strategy. Consider:
1. What are your priorities?
2. What are you willing to compromise on?
3. What is your best alternative (BATNA)?
4. How can you create win-win outcomes?

Provide your negotiation approach in JSON format:
{{
    "strategy": "your negotiation strategy",
    "priorities": ["priority 1", "priority 2"],
    "compromises": ["what you can compromise on"],
    "target_outcome": "desired outcome"
}}
"""

        return self.reason(prompt, context={"proposal": proposal, "other_agents": other_agents})

    def explain_decision(self, decision: Any) -> str:
        """Generate human-readable explanation of a decision"""
        prompt = f"""Explain this decision in simple terms that a patient can understand:

DECISION: {json.dumps(decision, indent=2)}

Provide a clear, empathetic explanation in 2-3 sentences. Use simple language.
If appropriate, include next steps or what the patient should do.
"""

        response = self.reason(prompt)
        return response.data.get("response", "Decision made based on best available options.")

    def __repr__(self) -> str:
        return f"Agent(id={self.agent_id}, name={self.name}, role={self.role})"
