from pydantic import BaseModel
from typing import Any, Literal


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    system_prompt: str | None = None


class ChatResponse(BaseModel):
    reply: str
    tools_called: list[str]
    message_count: int


class JobSearchRequest(BaseModel):
    query: str
    location: str = ""
    sources: list[str] = []


class RankRequest(BaseModel):
    jobs: list[dict[str, Any]]
    cv_keywords: list[str]


class PatchStatusRequest(BaseModel):
    status: Literal["new", "saved", "applied", "interview", "offer", "rejected"]


class PatchNotesRequest(BaseModel):
    notes: str
