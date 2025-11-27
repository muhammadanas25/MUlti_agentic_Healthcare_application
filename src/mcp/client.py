"""MCP Client - Helper for agents to communicate with MCP server"""
from typing import Dict, List, Optional, Any
from ..core.agent import Agent, AgentMessage, AgentResponse
from .server import get_mcp_server, MCPServer


class MCPClient:
    """
    MCP Client - Convenience wrapper for agents to communicate via MCP
    """

    def __init__(self, agent: Agent, server: Optional[MCPServer] = None):
        self.agent = agent
        self.server = server or get_mcp_server()

        # Register agent with server
        self.registration = self.server.register_agent(agent)

    async def send_to(
        self,
        target_agent_id: str,
        action: str,
        payload: Dict[str, Any],
        priority: str = "normal"
    ) -> Optional[AgentResponse]:
        """Send message to specific agent"""
        message = self.agent.send_message(
            to_agent={"id": target_agent_id},
            action=action,
            payload=payload,
            priority=priority,
        )

        return await self.server.send_message(message)

    async def broadcast(
        self,
        action: str,
        payload: Dict[str, Any],
        filter_criteria: Optional[Dict[str, Any]] = None,
        priority: str = "normal"
    ) -> List[AgentResponse]:
        """Broadcast message to multiple agents"""
        message = AgentMessage(
            from_agent={
                "id": self.agent.agent_id,
                "name": self.agent.name,
                "role": self.agent.role,
                "organization": self.agent.organization,
            },
            to_agent={},  # Broadcast
            action=action,
            payload=payload,
            priority=priority,
            message_type="broadcast",
        )

        return await self.server.broadcast(message, filter_criteria)

    async def negotiate_with(
        self,
        target_agent_ids: List[str],
        proposal: Dict[str, Any],
        max_rounds: int = 3
    ) -> Dict[str, Any]:
        """Negotiate with other agents"""
        return await self.server.negotiate(
            self.agent.agent_id,
            target_agent_ids,
            proposal,
            max_rounds
        )

    def discover_agents(
        self,
        organization: Optional[str] = None,
        role: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Discover other agents"""
        registrations = self.server.list_agents(organization=organization, role=role)

        return [
            {
                "id": reg.agent_id,
                "name": reg.name,
                "role": reg.role,
                "organization": reg.organization,
            }
            for reg in registrations
            if reg.agent_id != self.agent.agent_id  # Exclude self
        ]

    def get_agent_by_role(self, role: str) -> Optional[Dict[str, str]]:
        """Get first agent with specific role"""
        agents = self.discover_agents(role=role)
        return agents[0] if agents else None
