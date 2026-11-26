"""Read AI settings from the environment. Never log secrets."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv()


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def provider() -> str:
    return env("SELF_ENGLISH_AI_PROVIDER", "auto").lower()


def deepseek_key() -> str:
    return env("SELF_ENGLISH_DEEPSEEK_API_KEY") or env("DEEPSEEK_API_KEY")


def deepseek_model() -> str:
    return env("SELF_ENGLISH_DEEPSEEK_MODEL", "deepseek-chat") or "deepseek-chat"


def deepseek_base_url() -> str:
    return (env("SELF_ENGLISH_DEEPSEEK_BASE_URL", "https://api.deepseek.com") or "https://api.deepseek.com").rstrip("/")


def voice_provider() -> str:
    return env("SELF_ENGLISH_VOICE_PROVIDER").lower()


def voice_key() -> str:
    return env("SELF_ENGLISH_VOICE_API_KEY")
