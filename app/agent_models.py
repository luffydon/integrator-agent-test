from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

Visibility = Literal["public", "unlisted", "private"]
AgentStatus = Literal["active", "disabled", "archived"]
Scope = Literal["per_user", "shared"]

class AgentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    description: Optional[str] = None
    emoji: Optional[str] = None
    visibility: Visibility = "private"
    teachable: bool = True
    tools_allowed: List[str] = Field(default_factory=list)

class AgentCreateRequest(AgentBase):
    pass

class AgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=64)
    description: Optional[str] = None
    emoji: Optional[str] = None
    visibility: Optional[Visibility] = None
    teachable: Optional[bool] = None
    tools_allowed: Optional[List[str]] = None
    status: Optional[AgentStatus] = None

class Agent(AgentBase):
    id: str
    status: AgentStatus = "active"
    created_at: datetime
    updated_at: datetime

class TeachRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8192)
    scope: Scope = "shared"
    user_id: Optional[str] = None
    tags: Optional[List[str]] = None

class MemoryRecord(BaseModel):
    memory_id: str
    scope: Scope
    user_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    content: str
    created_at: datetime

class ToolExecRequest(BaseModel):
    tool: str
    params: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None

class ToolExecResult(BaseModel):
    ok: bool
    output: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
