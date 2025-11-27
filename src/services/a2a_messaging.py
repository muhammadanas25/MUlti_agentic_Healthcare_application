"""
Agent-to-Agent (A2A) Messaging Service

Provides messaging and broadcast capabilities between agents:
- Direct agent-to-agent messaging
- Broadcasting to multiple agents
- Resource availability queries
- Coordination and negotiation
- Event notifications
"""
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import uuid
import asyncio
from collections import defaultdict


class MessageType(Enum):
    """Types of A2A messages"""
    REQUEST = "request"           # Request for action/info
    RESPONSE = "response"         # Response to request
    BROADCAST = "broadcast"       # Broadcast to multiple agents
    NOTIFICATION = "notification" # Event notification
    QUERY = "query"              # Query for information
    NEGOTIATION = "negotiation"  # Negotiation message
    ALERT = "alert"              # Urgent alert


class MessagePriority(Enum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class A2AMessage:
    """Agent-to-Agent message structure"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Sender info
    from_agent_id: str = ""
    from_agent_name: str = ""
    from_agent_type: str = ""

    # Recipient info (for direct messages)
    to_agent_id: Optional[str] = None
    to_agent_name: Optional[str] = None
    to_agent_type: Optional[str] = None

    # For broadcasts
    broadcast_to: List[str] = field(default_factory=list)  # List of agent types

    # Message details
    message_type: str = MessageType.REQUEST.value
    priority: int = MessagePriority.NORMAL.value
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    # Response handling
    requires_response: bool = True
    response_to: Optional[str] = None  # Original message_id for responses
    response_deadline: Optional[str] = None

    # Conversation tracking
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'A2AMessage':
        return cls(**data)


@dataclass
class MessageResponse:
    """Response to an A2A message"""
    success: bool
    message_id: str
    response_to: str
    from_agent_id: str
    from_agent_name: str
    data: Any = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BroadcastResult:
    """Result of a broadcast message"""
    broadcast_id: str
    from_agent: str
    action: str
    total_recipients: int
    responses_received: int
    successful_responses: List[MessageResponse] = field(default_factory=list)
    failed_responses: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        result = asdict(self)
        result["successful_responses"] = [r.to_dict() if hasattr(r, 'to_dict') else r for r in self.successful_responses]
        return result


class A2AMessagingService:
    """
    Central messaging service for agent-to-agent communication.

    Features:
    - Direct messaging between agents
    - Broadcast messaging to multiple agents
    - Message queuing and delivery
    - Response tracking
    - Event subscriptions
    """

    def __init__(self):
        # Registered agents
        self.agents: Dict[str, Dict[str, Any]] = {}

        # Message handlers by agent
        self.handlers: Dict[str, Dict[str, Callable]] = defaultdict(dict)

        # Message queues
        self.message_queue: Dict[str, List[A2AMessage]] = defaultdict(list)

        # Message history
        self.message_history: List[A2AMessage] = []

        # Broadcast results
        self.broadcast_results: Dict[str, BroadcastResult] = {}

        # Event subscriptions
        self.subscriptions: Dict[str, List[str]] = defaultdict(list)  # event -> [agent_ids]

        print("A2A Messaging Service initialized")

    # ==================== Agent Registration ====================

    def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        agent_type: str,
        capabilities: List[str] = None,
        handler: Optional[Callable] = None
    ):
        """Register an agent with the messaging service"""
        self.agents[agent_id] = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "capabilities": capabilities or [],
            "registered_at": datetime.now().isoformat(),
            "online": True
        }

        if handler:
            self.handlers[agent_id]["default"] = handler

        print(f"   Registered agent: {agent_name} ({agent_type})")

    def register_handler(
        self,
        agent_id: str,
        action: str,
        handler: Callable
    ):
        """Register a message handler for specific action"""
        self.handlers[agent_id][action] = handler

    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
        if agent_id in self.handlers:
            del self.handlers[agent_id]

    def get_agents_by_type(self, agent_type: str) -> List[Dict[str, Any]]:
        """Get all agents of a specific type"""
        return [
            agent for agent in self.agents.values()
            if agent["agent_type"] == agent_type and agent.get("online", False)
        ]

    # ==================== Direct Messaging ====================

    def send_message(
        self,
        from_agent_id: str,
        to_agent_id: str,
        action: str,
        payload: Dict[str, Any],
        message_type: str = MessageType.REQUEST.value,
        priority: int = MessagePriority.NORMAL.value,
        requires_response: bool = True,
        conversation_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> A2AMessage:
        """Send a direct message to another agent"""
        from_agent = self.agents.get(from_agent_id, {})
        to_agent = self.agents.get(to_agent_id, {})

        message = A2AMessage(
            from_agent_id=from_agent_id,
            from_agent_name=from_agent.get("agent_name", "Unknown"),
            from_agent_type=from_agent.get("agent_type", "unknown"),
            to_agent_id=to_agent_id,
            to_agent_name=to_agent.get("agent_name", "Unknown"),
            to_agent_type=to_agent.get("agent_type", "unknown"),
            message_type=message_type,
            priority=priority,
            action=action,
            payload=payload,
            requires_response=requires_response,
            conversation_id=conversation_id or str(uuid.uuid4()),
            session_id=session_id
        )

        # Add to queue and history
        self.message_queue[to_agent_id].append(message)
        self.message_history.append(message)

        return message

    def process_message(
        self,
        message: A2AMessage,
        agent_instance: Any = None
    ) -> MessageResponse:
        """Process a received message"""
        to_agent_id = message.to_agent_id

        # Find handler
        handler = None
        if to_agent_id in self.handlers:
            handler = self.handlers[to_agent_id].get(message.action)
            if not handler:
                handler = self.handlers[to_agent_id].get("default")

        if handler:
            try:
                result = handler(message)
                return MessageResponse(
                    success=True,
                    message_id=str(uuid.uuid4()),
                    response_to=message.message_id,
                    from_agent_id=to_agent_id,
                    from_agent_name=self.agents.get(to_agent_id, {}).get("agent_name", "Unknown"),
                    data=result
                )
            except Exception as e:
                return MessageResponse(
                    success=False,
                    message_id=str(uuid.uuid4()),
                    response_to=message.message_id,
                    from_agent_id=to_agent_id,
                    from_agent_name=self.agents.get(to_agent_id, {}).get("agent_name", "Unknown"),
                    error=str(e)
                )
        else:
            return MessageResponse(
                success=False,
                message_id=str(uuid.uuid4()),
                response_to=message.message_id,
                from_agent_id=to_agent_id,
                from_agent_name="Unknown",
                error="No handler registered"
            )

    def get_pending_messages(self, agent_id: str) -> List[A2AMessage]:
        """Get pending messages for an agent"""
        messages = self.message_queue.get(agent_id, [])
        # Clear queue after retrieval
        self.message_queue[agent_id] = []
        return messages

    # ==================== Broadcasting ====================

    def broadcast(
        self,
        from_agent_id: str,
        target_agent_types: List[str],
        action: str,
        payload: Dict[str, Any],
        priority: int = MessagePriority.NORMAL.value,
        collect_responses: bool = True
    ) -> BroadcastResult:
        """
        Broadcast a message to all agents of specified types.

        This is useful for:
        - Resource availability queries across hospitals
        - Emergency notifications
        - Price/availability comparisons
        """
        from_agent = self.agents.get(from_agent_id, {})
        broadcast_id = str(uuid.uuid4())

        # Find target agents
        target_agents = []
        for agent_type in target_agent_types:
            target_agents.extend(self.get_agents_by_type(agent_type))

        result = BroadcastResult(
            broadcast_id=broadcast_id,
            from_agent=from_agent.get("agent_name", "Unknown"),
            action=action,
            total_recipients=len(target_agents),
            responses_received=0
        )

        # Send to each target
        for target in target_agents:
            message = A2AMessage(
                from_agent_id=from_agent_id,
                from_agent_name=from_agent.get("agent_name", "Unknown"),
                from_agent_type=from_agent.get("agent_type", "unknown"),
                to_agent_id=target["agent_id"],
                to_agent_name=target["agent_name"],
                to_agent_type=target["agent_type"],
                broadcast_to=target_agent_types,
                message_type=MessageType.BROADCAST.value,
                priority=priority,
                action=action,
                payload=payload,
                requires_response=collect_responses,
                conversation_id=broadcast_id
            )

            # Queue message
            self.message_queue[target["agent_id"]].append(message)
            self.message_history.append(message)

            # Process immediately if handler exists
            if collect_responses:
                response = self.process_message(message)
                result.responses_received += 1
                if response.success:
                    result.successful_responses.append(response)
                else:
                    result.failed_responses.append({
                        "agent_id": target["agent_id"],
                        "error": response.error
                    })

        self.broadcast_results[broadcast_id] = result
        return result

    def broadcast_resource_query(
        self,
        from_agent_id: str,
        resource_type: str,
        resource_subtype: str,
        city: Optional[str] = None,
        quantity: int = 1
    ) -> BroadcastResult:
        """
        Broadcast a resource availability query to all hospital resource agents.

        Example: Find hospitals with available ICU beds
        """
        return self.broadcast(
            from_agent_id=from_agent_id,
            target_agent_types=["hospital_resource", "hospital_booking"],
            action="check_resource_availability",
            payload={
                "resource_type": resource_type,
                "resource_subtype": resource_subtype,
                "city": city,
                "quantity": quantity
            },
            priority=MessagePriority.HIGH.value,
            collect_responses=True
        )

    def broadcast_emergency_alert(
        self,
        from_agent_id: str,
        alert_type: str,
        patient_info: Dict[str, Any],
        location: Optional[Dict[str, float]] = None
    ) -> BroadcastResult:
        """
        Broadcast an emergency alert to relevant agents.
        """
        return self.broadcast(
            from_agent_id=from_agent_id,
            target_agent_types=["muhafiz", "hospital_resource", "hospital_booking"],
            action="emergency_alert",
            payload={
                "alert_type": alert_type,
                "patient_info": patient_info,
                "location": location,
                "timestamp": datetime.now().isoformat()
            },
            priority=MessagePriority.CRITICAL.value,
            collect_responses=True
        )

    # ==================== Event Subscriptions ====================

    def subscribe(self, agent_id: str, event_type: str):
        """Subscribe an agent to an event type"""
        if agent_id not in self.subscriptions[event_type]:
            self.subscriptions[event_type].append(agent_id)

    def unsubscribe(self, agent_id: str, event_type: str):
        """Unsubscribe an agent from an event type"""
        if agent_id in self.subscriptions[event_type]:
            self.subscriptions[event_type].remove(agent_id)

    def publish_event(
        self,
        from_agent_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> int:
        """Publish an event to all subscribers"""
        subscribers = self.subscriptions.get(event_type, [])
        from_agent = self.agents.get(from_agent_id, {})

        count = 0
        for subscriber_id in subscribers:
            if subscriber_id != from_agent_id:  # Don't send to self
                message = A2AMessage(
                    from_agent_id=from_agent_id,
                    from_agent_name=from_agent.get("agent_name", "Unknown"),
                    from_agent_type=from_agent.get("agent_type", "unknown"),
                    to_agent_id=subscriber_id,
                    message_type=MessageType.NOTIFICATION.value,
                    action=event_type,
                    payload=event_data,
                    requires_response=False
                )
                self.message_queue[subscriber_id].append(message)
                self.message_history.append(message)
                count += 1

        return count

    # ==================== Negotiation Support ====================

    def start_negotiation(
        self,
        from_agent_id: str,
        to_agent_ids: List[str],
        negotiation_type: str,
        initial_offer: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> str:
        """Start a negotiation session with multiple agents"""
        negotiation_id = str(uuid.uuid4())
        from_agent = self.agents.get(from_agent_id, {})

        for to_agent_id in to_agent_ids:
            message = A2AMessage(
                from_agent_id=from_agent_id,
                from_agent_name=from_agent.get("agent_name", "Unknown"),
                from_agent_type=from_agent.get("agent_type", "unknown"),
                to_agent_id=to_agent_id,
                message_type=MessageType.NEGOTIATION.value,
                action="negotiation_start",
                payload={
                    "negotiation_type": negotiation_type,
                    "initial_offer": initial_offer,
                    "constraints": constraints or {}
                },
                conversation_id=negotiation_id,
                requires_response=True
            )
            self.message_queue[to_agent_id].append(message)
            self.message_history.append(message)

        return negotiation_id

    # ==================== Query Methods ====================

    def get_message_history(
        self,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get message history"""
        messages = self.message_history

        if agent_id:
            messages = [
                m for m in messages
                if m.from_agent_id == agent_id or m.to_agent_id == agent_id
            ]

        if conversation_id:
            messages = [
                m for m in messages
                if m.conversation_id == conversation_id
            ]

        # Return most recent
        return [m.to_dict() for m in messages[-limit:]]

    def get_broadcast_result(self, broadcast_id: str) -> Optional[Dict[str, Any]]:
        """Get result of a broadcast"""
        result = self.broadcast_results.get(broadcast_id)
        return result.to_dict() if result else None

    def get_registered_agents(self) -> List[Dict[str, Any]]:
        """Get all registered agents"""
        return list(self.agents.values())

    def get_stats(self) -> Dict[str, Any]:
        """Get messaging stats"""
        return {
            "registered_agents": len(self.agents),
            "total_messages": len(self.message_history),
            "pending_messages": sum(len(q) for q in self.message_queue.values()),
            "active_subscriptions": sum(len(s) for s in self.subscriptions.values()),
            "broadcasts": len(self.broadcast_results)
        }


# Global instance
_a2a_messaging_service: Optional[A2AMessagingService] = None


def get_a2a_messaging_service() -> A2AMessagingService:
    """Get or create the A2A messaging service instance"""
    global _a2a_messaging_service
    if _a2a_messaging_service is None:
        _a2a_messaging_service = A2AMessagingService()
    return _a2a_messaging_service
