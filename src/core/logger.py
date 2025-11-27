"""
Agent Logging System - Structured logs for agent reasoning and tool usage

Features:
- Structured JSON logs for UI display
- Agent reasoning chain tracking
- Tool usage logging with inputs/outputs
- Session-based log aggregation
- Real-time log streaming support
"""
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from collections import defaultdict
import threading


class LogLevel(Enum):
    """Log levels with semantic meaning for agents"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    REASONING = "REASONING"      # Agent thinking/reasoning
    TOOL_CALL = "TOOL_CALL"      # Tool invocation
    TOOL_RESULT = "TOOL_RESULT"  # Tool response
    HANDOFF = "HANDOFF"          # Agent-to-agent handoff
    USER_INPUT = "USER_INPUT"    # User message received
    AGENT_OUTPUT = "AGENT_OUTPUT"  # Agent response to user
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogCategory(Enum):
    """Categories for filtering logs"""
    AGENT = "agent"
    TOOL = "tool"
    ROUTING = "routing"
    LOCATION = "location"
    HOSPITAL = "hospital"
    ASSESSMENT = "assessment"
    EMERGENCY = "emergency"
    HANDOFF = "handoff"
    ORCHESTRATION = "orchestration"
    SYSTEM = "system"


@dataclass
class AgentLogEntry:
    """Structured log entry for agent activities"""
    timestamp: str
    session_id: str
    agent_name: str
    level: str
    category: str
    action: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    parent_id: Optional[str] = None  # For nested operations
    log_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class AgentLogger:
    """
    Centralized logger for multi-agent system.

    Captures:
    - Agent reasoning chains
    - Tool invocations and results
    - User interactions
    - Agent handoffs
    - Performance metrics
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: str = "logs"):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Session-based log storage (in-memory for UI)
        self.session_logs: Dict[str, List[AgentLogEntry]] = defaultdict(list)

        # Subscribers for real-time log streaming
        self.subscribers: List[Callable[[AgentLogEntry], None]] = []

        # Setup Python logger for file output
        self._setup_file_logger()

        # Performance tracking
        self.operation_timers: Dict[str, datetime] = {}

        print("✓ Agent Logger initialized")

    def _setup_file_logger(self):
        """Setup file-based logging"""
        self.file_logger = logging.getLogger("sehat_saathi")
        self.file_logger.setLevel(logging.DEBUG)

        # File handler for JSON logs
        json_handler = logging.FileHandler(
            self.log_dir / "agent_logs.jsonl",
            encoding="utf-8"
        )
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(logging.Formatter("%(message)s"))
        self.file_logger.addHandler(json_handler)

        # Console handler for readable output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        self.file_logger.addHandler(console_handler)

    def log(
        self,
        session_id: str,
        agent_name: str,
        level: LogLevel,
        category: LogCategory,
        action: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        parent_id: Optional[str] = None
    ) -> AgentLogEntry:
        """
        Create and store a log entry.

        Args:
            session_id: Phone number or session identifier
            agent_name: Name of the agent (Dr. Sameer, Guide, etc.)
            level: Log level (REASONING, TOOL_CALL, etc.)
            category: Log category for filtering
            action: Specific action being performed
            message: Human-readable message
            data: Additional structured data
            duration_ms: Operation duration in milliseconds
            parent_id: Parent log ID for nested operations
        """
        entry = AgentLogEntry(
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            agent_name=agent_name,
            level=level.value,
            category=category.value,
            action=action,
            message=message,
            data=data or {},
            duration_ms=duration_ms,
            parent_id=parent_id
        )

        # Store in memory
        self.session_logs[session_id].append(entry)

        # Write to file
        self.file_logger.info(entry.to_json())

        # Notify subscribers
        for subscriber in self.subscribers:
            try:
                subscriber(entry)
            except Exception as e:
                print(f"Log subscriber error: {e}")

        # Console output with formatting
        self._print_formatted(entry)

        return entry

    def _print_formatted(self, entry: AgentLogEntry):
        """Print formatted log to console"""
        level_colors = {
            "DEBUG": "\033[90m",      # Gray
            "INFO": "\033[94m",       # Blue
            "REASONING": "\033[95m",  # Magenta
            "TOOL_CALL": "\033[93m",  # Yellow
            "TOOL_RESULT": "\033[92m",  # Green
            "HANDOFF": "\033[96m",    # Cyan
            "USER_INPUT": "\033[97m", # White
            "AGENT_OUTPUT": "\033[92m",  # Green
            "WARNING": "\033[33m",    # Orange
            "ERROR": "\033[91m",      # Red
        }
        reset = "\033[0m"
        color = level_colors.get(entry.level, "")

        # Format based on level
        if entry.level == "REASONING":
            print(f"{color}💭 [{entry.agent_name}] {entry.message}{reset}")
            if entry.data:
                for key, value in entry.data.items():
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    print(f"   └─ {key}: {value}")

        elif entry.level == "TOOL_CALL":
            print(f"{color}🔧 [{entry.agent_name}] TOOL: {entry.action}{reset}")
            if entry.data.get("inputs"):
                inputs = entry.data["inputs"]
                if isinstance(inputs, dict):
                    for k, v in list(inputs.items())[:3]:
                        print(f"   └─ {k}: {v}")

        elif entry.level == "TOOL_RESULT":
            duration = f" ({entry.duration_ms:.0f}ms)" if entry.duration_ms else ""
            print(f"{color}✓ [{entry.agent_name}] {entry.action} completed{duration}{reset}")
            if entry.data.get("result_summary"):
                print(f"   └─ {entry.data['result_summary']}")

        elif entry.level == "HANDOFF":
            print(f"{color}🔄 [{entry.agent_name}] → {entry.data.get('to_agent', 'Unknown')}{reset}")
            print(f"   └─ {entry.message}")

        elif entry.level == "USER_INPUT":
            msg_preview = entry.message[:50] + "..." if len(entry.message) > 50 else entry.message
            print(f"{color}👤 [{entry.session_id[-4:]}] {msg_preview}{reset}")

        elif entry.level == "AGENT_OUTPUT":
            msg_preview = entry.message[:80] + "..." if len(entry.message) > 80 else entry.message
            print(f"{color}🤖 [{entry.agent_name}] {msg_preview}{reset}")

        elif entry.level == "ERROR":
            print(f"{color}❌ [{entry.agent_name}] {entry.message}{reset}")

        elif entry.level == "WARNING":
            print(f"{color}⚠️  [{entry.agent_name}] {entry.message}{reset}")

    # Convenience methods

    def log_user_input(self, session_id: str, message: str, agent_name: str = "Router"):
        """Log user input"""
        return self.log(
            session_id=session_id,
            agent_name=agent_name,
            level=LogLevel.USER_INPUT,
            category=LogCategory.ROUTING,
            action="user_message",
            message=message
        )

    def log_reasoning(
        self,
        session_id: str,
        agent_name: str,
        thought: str,
        category: LogCategory = LogCategory.AGENT,
        data: Optional[Dict] = None
    ):
        """Log agent reasoning"""
        return self.log(
            session_id=session_id,
            agent_name=agent_name,
            level=LogLevel.REASONING,
            category=category,
            action="reasoning",
            message=thought,
            data=data
        )

    def log_tool_call(
        self,
        session_id: str,
        agent_name: str,
        tool_name: str,
        inputs: Dict[str, Any],
        category: LogCategory = LogCategory.TOOL
    ) -> str:
        """Log tool invocation, returns log_id for timing"""
        entry = self.log(
            session_id=session_id,
            agent_name=agent_name,
            level=LogLevel.TOOL_CALL,
            category=category,
            action=tool_name,
            message=f"Calling {tool_name}",
            data={"inputs": inputs}
        )
        # Start timer
        self.operation_timers[entry.log_id] = datetime.now()
        return entry.log_id

    def log_tool_result(
        self,
        session_id: str,
        agent_name: str,
        tool_name: str,
        result_summary: str,
        success: bool = True,
        log_id: Optional[str] = None,
        category: LogCategory = LogCategory.TOOL,
        data: Optional[Dict] = None
    ):
        """Log tool result"""
        duration_ms = None
        if log_id and log_id in self.operation_timers:
            start = self.operation_timers.pop(log_id)
            duration_ms = (datetime.now() - start).total_seconds() * 1000

        return self.log(
            session_id=session_id,
            agent_name=agent_name,
            level=LogLevel.TOOL_RESULT,
            category=category,
            action=tool_name,
            message=f"{'✓' if success else '✗'} {tool_name}",
            data={"result_summary": result_summary, "success": success, **(data or {})},
            duration_ms=duration_ms,
            parent_id=log_id
        )

    def log_handoff(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str,
        reason: str,
        context: Optional[Dict] = None
    ):
        """Log agent-to-agent handoff"""
        return self.log(
            session_id=session_id,
            agent_name=from_agent,
            level=LogLevel.HANDOFF,
            category=LogCategory.HANDOFF,
            action="handoff",
            message=reason,
            data={"to_agent": to_agent, "context": context or {}}
        )

    def log_agent_output(
        self,
        session_id: str,
        agent_name: str,
        message: str,
        response_type: str = "text"
    ):
        """Log agent response to user"""
        return self.log(
            session_id=session_id,
            agent_name=agent_name,
            level=LogLevel.AGENT_OUTPUT,
            category=LogCategory.AGENT,
            action="response",
            message=message,
            data={"response_type": response_type}
        )

    def log_error(
        self,
        session_id: str,
        agent_name: str,
        error: str,
        category: LogCategory = LogCategory.SYSTEM,
        data: Optional[Dict] = None
    ):
        """Log error"""
        return self.log(
            session_id=session_id,
            agent_name=agent_name,
            level=LogLevel.ERROR,
            category=category,
            action="error",
            message=error,
            data=data
        )

    # Query methods for UI

    def get_session_logs(
        self,
        session_id: str,
        limit: int = 100,
        level_filter: Optional[List[str]] = None,
        category_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get logs for a session (for UI display)"""
        logs = self.session_logs.get(session_id, [])

        if level_filter:
            logs = [l for l in logs if l.level in level_filter]

        if category_filter:
            logs = [l for l in logs if l.category in category_filter]

        return [l.to_dict() for l in logs[-limit:]]

    def get_reasoning_chain(self, session_id: str) -> List[Dict[str, Any]]:
        """Get reasoning chain for a session"""
        logs = self.session_logs.get(session_id, [])
        reasoning_logs = [
            l for l in logs
            if l.level in ["REASONING", "TOOL_CALL", "TOOL_RESULT", "HANDOFF"]
        ]
        return [l.to_dict() for l in reasoning_logs]

    def subscribe(self, callback: Callable[[AgentLogEntry], None]):
        """Subscribe to real-time log updates"""
        self.subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[AgentLogEntry], None]):
        """Unsubscribe from log updates"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def clear_session(self, session_id: str):
        """Clear logs for a session"""
        if session_id in self.session_logs:
            del self.session_logs[session_id]


# Global logger instance
_logger: Optional[AgentLogger] = None


def get_agent_logger() -> AgentLogger:
    """Get or create the agent logger"""
    global _logger
    if _logger is None:
        _logger = AgentLogger()
    return _logger
