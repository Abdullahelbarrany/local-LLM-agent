from pydantic import BaseModel
from typing import Literal


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
