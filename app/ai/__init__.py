"""Optional coaches. Chat is DeepSeek; voice is a reserved slot."""

from .chat import TalkReview, chat_available, chat_status, review_talk
from .voice import start_message, voice_available, voice_status


def status() -> dict:
    return {"chat": chat_status(), "voice": voice_status()}


__all__ = [
    "TalkReview",
    "chat_available",
    "chat_status",
    "review_talk",
    "start_message",
    "status",
    "voice_available",
    "voice_status",
]
