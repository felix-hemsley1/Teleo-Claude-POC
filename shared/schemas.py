from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Literal
from enum import Enum
import uuid


class EventType(str, Enum):
    FOCUS_CHANGED = "focus_changed"
    VALUE_CHANGED = "value_changed"
    INVOKE = "invoke"
    SELECTION_CHANGED = "selection_changed"
    NAVIGATION = "navigation"
    PASTE = "paste"
    TYPING_BURST = "typing_burst"
    WINDOW_OPENED = "window_opened"
    WINDOW_CLOSED = "window_closed"


class AppContext(BaseModel):
    process_name: str
    window_title: str = ""
    url: Optional[str] = None
    document_path: Optional[str] = None


class ControlInfo(BaseModel):
    control_type: Optional[str] = None
    label: Optional[str] = None
    automation_id: Optional[str] = None
    value: Optional[str] = None
    is_password: bool = False


class ActionEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    device_id: str
    ts_utc: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType
    app_context: AppContext
    control: Optional[ControlInfo] = None
    semantic_label: Optional[str] = None
    redacted: bool = False
    pii_flags: List[str] = []


class WorkflowStep(BaseModel):
    step_number: int
    action_type: Literal["navigate", "read", "write", "decide", "wait", "approve"]
    target_app: str
    description: str
    automatable: bool = True
    requires_approval: bool = False


class DiscoveredWorkflow(BaseModel):
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_name: str
    description: str
    frequency: str
    occurrences: List[str]
    steps: List[WorkflowStep]
    inputs: str
    outputs: str
    automation_confidence: float
    estimated_minutes_per_run: int
    trigger_condition: str


class AgentRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: Literal["running", "success", "failed", "awaiting_approval", "rejected"]
    log_text: str = ""
    error_message: Optional[str] = None
    minutes_saved: int = 0
