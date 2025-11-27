"""
Shared Context Store for Multi-Agent Conversations

Provides:
- Centralized conversation context accessible by all agents
- Session state tracking (which agent is active, what state)
- Patient snapshot (key facts for quick context loading)
- Timeline of events and decisions
- Memory summarization to keep context windows small
"""
import json
import sqlite3
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import hashlib


class SessionStatus(Enum):
    """Status of a conversation session"""
    ACTIVE = "active"
    AWAITING_INPUT = "awaiting_input"
    COMPLETED = "completed"
    EXPIRED = "expired"


@dataclass
class PatientSnapshot:
    """Quick-load patient context"""
    patient_id: str
    phone_number: str
    name: str = ""
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    location_coords: Optional[Tuple[float, float]] = None
    chief_complaint: str = ""
    urgency: str = "low"  # low, medium, high, emergency
    sehat_card: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'PatientSnapshot':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AgentState:
    """State of an active agent session"""
    agent_type: str
    agent_name: str
    state: str  # Agent-specific state (e.g., "awaiting_location", "showing_results")
    awaiting_input: bool = False
    awaiting_input_type: str = ""  # "selection", "confirmation", "location", "details"
    valid_inputs: List[str] = field(default_factory=list)  # e.g., ["1", "2", "3", "4", "5", "book"]
    context_data: Dict[str, Any] = field(default_factory=dict)  # Agent-specific data
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'AgentState':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ConversationContext:
    """Full conversation context"""
    conversation_id: str
    phone_number: str
    patient: PatientSnapshot
    current_agent: Optional[AgentState] = None
    previous_agents: List[str] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    facts: Dict[str, Any] = field(default_factory=dict)  # Extracted facts
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    pending_actions: List[Dict[str, Any]] = field(default_factory=list)
    short_summary: str = ""  # Auto-generated summary
    turn_count: int = 0
    status: str = SessionStatus.ACTIVE.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = ""  # Session expiry

    def __post_init__(self):
        if not self.expires_at:
            # Default 30 min session
            self.expires_at = (datetime.now() + timedelta(minutes=30)).isoformat()

    def to_dict(self) -> dict:
        result = {
            "conversation_id": self.conversation_id,
            "phone_number": self.phone_number,
            "patient": self.patient.to_dict(),
            "current_agent": self.current_agent.to_dict() if self.current_agent else None,
            "previous_agents": self.previous_agents,
            "decisions": self.decisions,
            "facts": self.facts,
            "timeline": self.timeline,
            "pending_actions": self.pending_actions,
            "short_summary": self.short_summary,
            "turn_count": self.turn_count,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at
        }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'ConversationContext':
        patient = PatientSnapshot.from_dict(data.get("patient", {}))
        current_agent = None
        if data.get("current_agent"):
            current_agent = AgentState.from_dict(data["current_agent"])

        return cls(
            conversation_id=data["conversation_id"],
            phone_number=data["phone_number"],
            patient=patient,
            current_agent=current_agent,
            previous_agents=data.get("previous_agents", []),
            decisions=data.get("decisions", []),
            facts=data.get("facts", {}),
            timeline=data.get("timeline", []),
            pending_actions=data.get("pending_actions", []),
            short_summary=data.get("short_summary", ""),
            turn_count=data.get("turn_count", 0),
            status=data.get("status", SessionStatus.ACTIVE.value),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            expires_at=data.get("expires_at", "")
        )

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now()

    def has_active_agent_session(self) -> bool:
        """Check if there's an active agent awaiting input"""
        if not self.current_agent:
            return False
        if self.is_expired():
            return False
        return self.current_agent.awaiting_input


@dataclass
class ContextPacket:
    """Lightweight context packet attached to messages"""
    conversation_id: str
    patient_snapshot: Dict[str, Any]
    current_agent: Optional[str] = None
    current_state: Optional[str] = None
    awaiting_input: bool = False
    valid_inputs: List[str] = field(default_factory=list)
    last_decision: Optional[Dict[str, Any]] = None
    context_version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


class ContextStore:
    """
    SQLite-backed shared context store for multi-agent conversations.

    Features:
    - Persistent storage across sessions
    - Fast lookups by phone number or conversation ID
    - Auto-expiry of stale sessions
    - Context summarization
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "context_store.db"

        self.db_path = str(db_path)
        self._init_db()

        print(f"Context Store initialized at {self.db_path}")

    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                phone_number TEXT NOT NULL,
                context_json TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_phone ON conversations(phone_number)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON conversations(status)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timeline_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                agent_name TEXT,
                event_data TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
            )
        """)

        conn.commit()
        conn.close()

    # ==================== Core Operations ====================

    def create_context(
        self,
        phone_number: str,
        patient_name: str = "",
        conversation_id: Optional[str] = None
    ) -> ConversationContext:
        """Create a new conversation context"""
        if not conversation_id:
            conversation_id = f"conv-{phone_number}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        patient = PatientSnapshot(
            patient_id=phone_number,
            phone_number=phone_number,
            name=patient_name
        )

        context = ConversationContext(
            conversation_id=conversation_id,
            phone_number=phone_number,
            patient=patient
        )

        self._save_context(context)
        return context

    def get_context(
        self,
        phone_number: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Optional[ConversationContext]:
        """Get conversation context by phone or conversation ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if conversation_id:
            cursor.execute(
                "SELECT context_json FROM conversations WHERE conversation_id = ?",
                (conversation_id,)
            )
        elif phone_number:
            # Get most recent active context for phone
            cursor.execute("""
                SELECT context_json FROM conversations
                WHERE phone_number = ? AND status = 'active'
                ORDER BY updated_at DESC LIMIT 1
            """, (phone_number,))
        else:
            conn.close()
            return None

        row = cursor.fetchone()
        conn.close()

        if row:
            data = json.loads(row[0])
            context = ConversationContext.from_dict(data)

            # Check expiry
            if context.is_expired():
                self.expire_context(context.conversation_id)
                return None

            return context

        return None

    def get_or_create_context(self, phone_number: str) -> ConversationContext:
        """Get existing context or create new one"""
        context = self.get_context(phone_number=phone_number)
        if context:
            return context
        return self.create_context(phone_number)

    def update_context(
        self,
        conversation_id: str,
        updates: Dict[str, Any]
    ) -> Optional[ConversationContext]:
        """Update context with delta changes"""
        context = self.get_context(conversation_id=conversation_id)
        if not context:
            return None

        # Apply updates
        if "patient" in updates:
            for key, value in updates["patient"].items():
                if hasattr(context.patient, key):
                    setattr(context.patient, key, value)

        if "facts" in updates:
            context.facts.update(updates["facts"])

        if "current_agent" in updates:
            agent_data = updates["current_agent"]
            if agent_data:
                context.current_agent = AgentState.from_dict(agent_data)
            else:
                context.current_agent = None

        if "decision" in updates:
            context.decisions.append(updates["decision"])

        if "timeline_event" in updates:
            context.timeline.append(updates["timeline_event"])

        if "pending_action" in updates:
            context.pending_actions.append(updates["pending_action"])

        if "short_summary" in updates:
            context.short_summary = updates["short_summary"]

        context.turn_count += 1
        context.updated_at = datetime.now().isoformat()

        self._save_context(context)
        return context

    def _save_context(self, context: ConversationContext):
        """Save context to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO conversations
            (conversation_id, phone_number, context_json, status, created_at, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            context.conversation_id,
            context.phone_number,
            json.dumps(context.to_dict()),
            context.status,
            context.created_at,
            context.updated_at,
            context.expires_at
        ))

        conn.commit()
        conn.close()

    # ==================== Agent State Management ====================

    def set_agent_state(
        self,
        phone_number: str,
        agent_type: str,
        agent_name: str,
        state: str,
        awaiting_input: bool = False,
        awaiting_input_type: str = "",
        valid_inputs: List[str] = None,
        context_data: Dict[str, Any] = None
    ) -> Optional[ConversationContext]:
        """Set the current active agent state"""
        context = self.get_or_create_context(phone_number)

        agent_state = AgentState(
            agent_type=agent_type,
            agent_name=agent_name,
            state=state,
            awaiting_input=awaiting_input,
            awaiting_input_type=awaiting_input_type,
            valid_inputs=valid_inputs or [],
            context_data=context_data or {}
        )

        context.current_agent = agent_state
        context.updated_at = datetime.now().isoformat()

        # Track agent transitions
        if agent_type not in context.previous_agents:
            context.previous_agents.append(agent_type)

        self._save_context(context)
        return context

    def clear_agent_state(self, phone_number: str) -> Optional[ConversationContext]:
        """Clear current agent state (conversation completed)"""
        context = self.get_context(phone_number=phone_number)
        if not context:
            return None

        if context.current_agent:
            context.previous_agents.append(context.current_agent.agent_type)

        context.current_agent = None
        context.updated_at = datetime.now().isoformat()

        self._save_context(context)
        return context

    def is_awaiting_input(self, phone_number: str) -> Tuple[bool, Optional[AgentState]]:
        """Check if we're awaiting input from user for an active agent"""
        context = self.get_context(phone_number=phone_number)

        if not context or not context.current_agent:
            return False, None

        if context.is_expired():
            return False, None

        if context.current_agent.awaiting_input:
            return True, context.current_agent

        return False, None

    def validate_input(self, phone_number: str, user_input: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if user input matches expected inputs for current agent state.
        Returns (is_valid, expected_type)
        """
        is_awaiting, agent_state = self.is_awaiting_input(phone_number)

        if not is_awaiting or not agent_state:
            return True, None  # Not awaiting specific input, any input is valid

        # Check if input matches valid inputs
        user_input_lower = user_input.lower().strip()

        if agent_state.valid_inputs:
            # Check exact match
            if user_input_lower in [v.lower() for v in agent_state.valid_inputs]:
                return True, agent_state.awaiting_input_type

            # Check if it's a number selection
            if user_input.isdigit():
                num = int(user_input)
                max_num = max([int(v) for v in agent_state.valid_inputs if v.isdigit()], default=0)
                if 1 <= num <= max_num:
                    return True, agent_state.awaiting_input_type

        return False, agent_state.awaiting_input_type

    # ==================== Context Packet ====================

    def get_context_packet(self, phone_number: str) -> Optional[ContextPacket]:
        """Get lightweight context packet for message injection"""
        context = self.get_context(phone_number=phone_number)
        if not context:
            return None

        return ContextPacket(
            conversation_id=context.conversation_id,
            patient_snapshot=context.patient.to_dict(),
            current_agent=context.current_agent.agent_type if context.current_agent else None,
            current_state=context.current_agent.state if context.current_agent else None,
            awaiting_input=context.current_agent.awaiting_input if context.current_agent else False,
            valid_inputs=context.current_agent.valid_inputs if context.current_agent else [],
            last_decision=context.decisions[-1] if context.decisions else None,
            context_version=context.turn_count
        )

    # ==================== Timeline ====================

    def add_timeline_event(
        self,
        phone_number: str,
        event_type: str,
        agent_name: str,
        event_data: Dict[str, Any]
    ):
        """Add event to timeline"""
        context = self.get_context(phone_number=phone_number)
        if not context:
            return

        event = {
            "type": event_type,
            "agent": agent_name,
            "data": event_data,
            "timestamp": datetime.now().isoformat()
        }

        context.timeline.append(event)
        context.updated_at = datetime.now().isoformat()

        self._save_context(context)

        # Also save to timeline_events table for queries
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO timeline_events (conversation_id, event_type, agent_name, event_data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            context.conversation_id,
            event_type,
            agent_name,
            json.dumps(event_data),
            event["timestamp"]
        ))
        conn.commit()
        conn.close()

    # ==================== Session Management ====================

    def expire_context(self, conversation_id: str):
        """Mark a context as expired"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE conversations SET status = 'expired' WHERE conversation_id = ?",
            (conversation_id,)
        )
        conn.commit()
        conn.close()

    def complete_context(self, phone_number: str):
        """Mark conversation as completed"""
        context = self.get_context(phone_number=phone_number)
        if context:
            context.status = SessionStatus.COMPLETED.value
            context.current_agent = None
            self._save_context(context)

    def cleanup_expired(self):
        """Cleanup expired sessions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE conversations SET status = 'expired' WHERE expires_at < ? AND status = 'active'",
            (now,)
        )
        conn.commit()
        conn.close()

    # ==================== Summarization ====================

    def should_summarize(self, phone_number: str, threshold: int = 10) -> bool:
        """Check if context needs summarization"""
        context = self.get_context(phone_number=phone_number)
        if not context:
            return False
        return context.turn_count >= threshold and not context.short_summary

    def set_summary(self, phone_number: str, summary: str):
        """Set conversation summary"""
        context = self.get_context(phone_number=phone_number)
        if context:
            context.short_summary = summary
            self._save_context(context)


# Global instance
_context_store: Optional[ContextStore] = None


def get_context_store() -> ContextStore:
    """Get or create the context store instance"""
    global _context_store
    if _context_store is None:
        _context_store = ContextStore()
    return _context_store
