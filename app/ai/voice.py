"""Realtime voice slot. No audio is sent until a provider is wired in."""

from __future__ import annotations

from . import settings


def voice_available() -> bool:
    return False


def voice_status() -> dict:
    provider = settings.voice_provider() or None
    return {
        "provider": provider,
        "available": False,
        "ready": False,
        "label_zh": "实时语音口子已留，还没接入",
        "detail_zh": "接好语音 API 后这里会打开。现在不会发送录音。",
    }


def start_message() -> str:
    return "实时语音还没接入。现在不会发送录音。"
