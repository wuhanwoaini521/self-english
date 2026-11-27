"""Optional coaches. Chat is DeepSeek; voice is a reserved slot."""

from .chat import ChatError, TalkReview, chat_available, chat_status, explain_grammar, review_talk
from .voice import start_message, voice_available, voice_status


def status() -> dict:
    return {"chat": chat_status(), "voice": voice_status()}


__all__ = [
    "ChatError",
    "TalkReview",
    "chat_available",
    "chat_status",
    "explain_grammar",
    "review_talk",
    "start_message",
    "status",
    "voice_available",
    "voice_status",
]
