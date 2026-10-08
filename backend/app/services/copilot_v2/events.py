"""Ephemeral progress events for Copilot V2.

Emits live status transitions (STARTED, TOOL_RUNNING, ESCALATING, REASONING, COMPLETED, FAILED)
to keep users informed during multi-second reasoning or tool runs.

INVARIANT:
Progress events are strictly ephemeral and are NEVER persisted as chat messages
in the database (copilot_messages table).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import inspect
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ProgressEventType(str, Enum):
    """Lifecycle progress event types."""

    STARTED = "STARTED"
    TOOL_RUNNING = "TOOL_RUNNING"
    ESCALATING = "ESCALATING"
    REASONING = "REASONING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


TOOL_DISPLAY_NAMES: Dict[str, str] = {
    "get_portfolio_summary": "Portföy özeti",
    "get_holdings": "Varlık dağılımı ve pozisyonlar",
    "get_asset_context": "Varlık ve piyasa detayları",
    "get_briefing": "Piyasa ve istihbarat briefingi",
    "search_news": "Son haberler ve gelişmeler",
    "search_web": "Web kaynakları ve duyurular",
    "fetch_web_page": "Haber ve kaynak içeriği",
}


@dataclass
class ProgressEvent:
    """An individual progress status event."""

    event_type: ProgressEventType
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to serializable dictionary."""
        return {
            "event_type": self.event_type.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": dict(self.details),
        }

    @classmethod
    def started(cls, message: str = "Talebiniz inceleniyor...") -> "ProgressEvent":
        return cls(event_type=ProgressEventType.STARTED, message=message)

    @classmethod
    def tool_running(
        cls,
        tool_name: str,
        message: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
    ) -> "ProgressEvent":
        display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        if tool_name in {"search_news", "search_web"}:
            msg = message or f"Güncel piyasa ve haberler taranıyor: {display_name}..."
        elif tool_name == "fetch_web_page":
            msg = message or f"Detaylı kaynak inceleniyor: {display_name}..."
        else:
            msg = message or f"Portföy verileri alınıyor: {display_name}..."
        return cls(
            event_type=ProgressEventType.TOOL_RUNNING,
            message=msg,
            details={"tool": tool_name, "args": tool_args or {}},
        )

    @classmethod
    def escalating(
        cls,
        target_profile: str,
        reason: Optional[str] = None,
        effort: Optional[str] = None,
        message: Optional[str] = None,
    ) -> "ProgressEvent":
        msg = message or f"Derin analiz modeline aktarılıyor ({target_profile})..."
        return cls(
            event_type=ProgressEventType.ESCALATING,
            message=msg,
            details={"target_profile": target_profile, "reason": reason, "effort": effort},
        )

    @classmethod
    def reasoning(
        cls,
        profile: str,
        effort: str,
        message: Optional[str] = None,
    ) -> "ProgressEvent":
        msg = message or f"Kapsamlı analiz sentezleniyor ({profile} / {effort})..."
        return cls(
            event_type=ProgressEventType.REASONING,
            message=msg,
            details={"profile": profile, "effort": effort},
        )

    @classmethod
    def completed(cls, message: str = "Yanıt hazır.") -> "ProgressEvent":
        return cls(event_type=ProgressEventType.COMPLETED, message=message)

    @classmethod
    def failed(
        cls,
        error: Optional[str] = None,
        message: str = "İşlem tamamlanamadı.",
    ) -> "ProgressEvent":
        return cls(
            event_type=ProgressEventType.FAILED,
            message=message,
            details={"error": error} if error else {},
        )


ProgressCallback = Callable[[ProgressEvent], Union[Awaitable[None], None]]


class EventEmitter:
    """Safe dispatcher for progress callbacks."""

    def __init__(
        self,
        callback: Optional[ProgressCallback] = None,
        trace: Optional[Any] = None,
    ):
        self.callback = callback
        self.trace = trace
        self.events: List[ProgressEvent] = []

    async def emit(self, event: ProgressEvent) -> None:
        """Emit an event to the registered callback, trace, and history."""
        self.events.append(event)
        logger.debug("Progress event [%s]: %s", event.event_type.value, event.message)

        if self.trace is not None and hasattr(self.trace, "record_progress_event"):
            self.trace.record_progress_event(
                event.event_type.value,
                event.message,
                event.details,
            )

        if not self.callback:
            return

        try:
            res = self.callback(event)
            if inspect.isawaitable(res):
                await res
        except Exception as exc:
            # Progress emission errors must NEVER fail the core model execution
            logger.warning("Error in progress event callback: %s", exc)
