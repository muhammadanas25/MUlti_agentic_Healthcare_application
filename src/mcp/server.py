"""MCP Server - Central communication hub for agents"""
import asyncio
import json
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import uuid

from ..core.agent import Agent, AgentMessage, AgentResponse
from ..core.config import settings


@dataclass
class AgentRegistration:
    """Agent registration information"""
    agent_id: str
    name: str
    role: str
    organization: str
    capabilities: List[str]
    public_key: Optional[str] = None
    status: str = "active"
    registered_at: str = ""

    def __post_init__(self):
        if not self.registered_at:
            self.registered_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


class MCPServer:
    """
    MCP (Model Context Protocol) Server
    Central hub for agent-to-agent communication, discovery, and coordination
    """

    def __init__(self):
        self.agent_registry: Dict[str, AgentRegistration] = {}
        self.message_queue: Dict[str, List[AgentMessage]] = {}
        self.communication_log: List[Dict[str, Any]] = []

        # Agent instances (for direct communication)
        self.agents: Dict[str, Agent] = {}

        # Message handlers for broadcast
        self.broadcast_handlers: Dict[str, List[Callable]] = {}

        # Statistics
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "broadcasts": 0,
            "negotiations": 0,
        }

        print(f"✓ MCP Server initialized")

    def register_agent(
        self,
        agent: Agent,
        capabilities: Optional[List[str]] = None
    ) -> AgentRegistration:
        """
        Register an agent with the MCP server

        Args:
            agent: Agent instance
            capabilities: List of capabilities/tools

        Returns:
            AgentRegistration
        """
        registration = AgentRegistration(
            agent_id=agent.agent_id,
            name=agent.name,
            role=agent.role,
            organization=agent.organization,
            capabilities=capabilities or agent.tools,
        )

        self.agent_registry[agent.agent_id] = registration
        self.agents[agent.agent_id] = agent
        self.message_queue[agent.agent_id] = []

        print(f"✓ Agent registered: {agent.name} ({agent.agent_id})")

        return registration

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent"""
        if agent_id in self.agent_registry:
            self.agent_registry[agent_id].status = "inactive"
            if agent_id in self.agents:
                del self.agents[agent_id]
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID"""
        return self.agents.get(agent_id)

    def list_agents(
        self,
        organization: Optional[str] = None,
        role: Optional[str] = None,
        status: str = "active"
    ) -> List[AgentRegistration]:
        """
        List registered agents with optional filters

        Args:
            organization: Filter by organization
            role: Filter by role
            status: Filter by status

        Returns:
            List of AgentRegistration
        """
        agents = []
        for registration in self.agent_registry.values():
            if status and registration.status != status:
                continue
            if organization and registration.organization != organization:
                continue
            if role and registration.role != role:
                continue
            agents.append(registration)
        return agents

    async def send_message(
        self,
        message: AgentMessage,
        wait_for_response: bool = True
    ) -> Optional[AgentResponse]:
        """
        Send message from one agent to another

        Args:
            message: AgentMessage to send
            wait_for_response: Whether to wait for response

        Returns:
            AgentResponse if wait_for_response is True
        """
        # Log communication
        self._log_communication(message)

        # Validate agents exist
        from_agent_id = message.from_agent.get("id")
        to_agent_id = message.to_agent.get("id")

        if to_agent_id not in self.agents:
            print(f"✗ Target agent {to_agent_id} not found")
            return AgentResponse(
                success=False,
                data=None,
                reasoning=f"Agent {to_agent_id} not found",
                confidence=0.0,
            )

        # Deliver message to target agent
        target_agent = self.agents[to_agent_id]

        print(f"📨 {message.from_agent.get('name')} → {message.to_agent.get('name')}: {message.action}")

        self.stats["messages_sent"] += 1

        if wait_for_response and message.requires_response:
            # Get response from target agent
            response = target_agent.process_message(message)
            self.stats["messages_received"] += 1
            return response
        else:
            # Fire and forget
            self.message_queue[to_agent_id].append(message)
            return None

    async def broadcast(
        self,
        message: AgentMessage,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[AgentResponse]:
        """
        Broadcast message to multiple agents

        Args:
            message: AgentMessage to broadcast
            filter_criteria: Criteria to filter recipient agents

        Returns:
            List of AgentResponse from all recipients
        """
        print(f"📢 Broadcasting from {message.from_agent.get('name')}: {message.action}")

        # Find matching agents
        recipients = []
        for agent_id, registration in self.agent_registry.items():
            # Skip sender
            if agent_id == message.from_agent.get("id"):
                continue

            # Skip inactive agents
            if registration.status != "active":
                continue

            # Apply filters
            if filter_criteria:
                match = True
                for key, value in filter_criteria.items():
                    if key == "organization" and registration.organization != value:
                        match = False
                    elif key == "role" and registration.role != value:
                        match = False
                    elif key == "capability" and value not in registration.capabilities:
                        match = False

                if not match:
                    continue

            recipients.append(agent_id)

        print(f"  → Broadcasting to {len(recipients)} agents")

        # Send to all recipients
        responses = []
        for agent_id in recipients:
            msg = AgentMessage(
                from_agent=message.from_agent,
                to_agent={"id": agent_id},
                action=message.action,
                payload=message.payload,
                priority=message.priority,
                message_type="broadcast",
            )

            response = await self.send_message(msg, wait_for_response=True)
            if response:
                responses.append(response)

        self.stats["broadcasts"] += 1

        return responses

    async def negotiate(
        self,
        initiator_agent_id: str,
        target_agent_ids: List[str],
        proposal: Dict[str, Any],
        max_rounds: int = 3
    ) -> Dict[str, Any]:
        """
        Facilitate negotiation between agents

        Args:
            initiator_agent_id: Agent initiating negotiation
            target_agent_ids: Agents to negotiate with
            proposal: Initial proposal
            max_rounds: Maximum negotiation rounds

        Returns:
            Negotiation result
        """
        initiator = self.agents.get(initiator_agent_id)
        if not initiator:
            return {"success": False, "error": "Initiator not found"}

        print(f"🤝 Negotiation started: {initiator.name} with {len(target_agent_ids)} agents")

        # Get negotiation strategy from initiator
        strategy_response = initiator.negotiate(
            [{"id": aid} for aid in target_agent_ids],
            proposal,
            max_rounds
        )

        print(f"  Strategy: {strategy_response.data.get('strategy', 'Unknown')}")

        # Collect responses from target agents
        responses = []
        for target_id in target_agent_ids:
            target = self.agents.get(target_id)
            if not target:
                continue

            # Ask target agent to evaluate proposal
            eval_response = target.reason(
                f"""You received a negotiation proposal from {initiator.name}:

PROPOSAL: {json.dumps(proposal, indent=2)}

Evaluate this proposal from your perspective as {target.name}.
Provide your response in JSON format:
{{
    "accept": true/false,
    "reasoning": "your reasoning",
    "counter_proposal": {{}} // optional
}}
""",
                context={"proposal": proposal}
            )

            responses.append({
                "agent_id": target_id,
                "agent_name": target.name,
                "response": eval_response.data
            })

        self.stats["negotiations"] += 1

        # Analyze responses
        acceptances = sum(1 for r in responses if r.get("response", {}).get("accept"))
        rejections = len(responses) - acceptances

        result = {
            "success": acceptances > rejections,
            "proposal": proposal,
            "strategy": strategy_response.data,
            "responses": responses,
            "summary": {
                "acceptances": acceptances,
                "rejections": rejections,
                "total_agents": len(responses)
            }
        }

        print(f"  Result: {acceptances} accepts, {rejections} rejects")

        return result

    def _log_communication(self, message: AgentMessage):
        """Log communication for audit trail"""
        if message.audit_trail:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "message_id": message.message_id,
                "from_agent": message.from_agent.get("name"),
                "to_agent": message.to_agent.get("name"),
                "action": message.action,
                "priority": message.priority,
                "message_type": message.message_type,
            }
            self.communication_log.append(log_entry)

    def get_communication_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent communication log"""
        return self.communication_log[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics"""
        return {
            **self.stats,
            "registered_agents": len(self.agent_registry),
            "active_agents": len([a for a in self.agent_registry.values() if a.status == "active"]),
        }

    def export_trace(self, filename: str):
        """Export communication trace for visualization"""
        trace = {
            "agents": [reg.to_dict() for reg in self.agent_registry.values()],
            "communications": self.communication_log,
            "stats": self.get_stats(),
        }

        with open(filename, 'w') as f:
            json.dump(trace, f, indent=2)

        print(f"✓ Trace exported to {filename}")


# Global MCP server instance
_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """Get or create global MCP server instance"""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer()
    return _mcp_server
