"""Text coaches. DeepSeek is optional; script keywords always remain."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from ..dialogue import completed_goal_ids
from . import settings

MODE_ZH = {
    "script": "脚本练习",
    "deepseek": "DeepSeek 文字陪练",
}


class ChatError(Exception):
    """Provider failed. Message must not include user text or keys."""


@dataclass
class TalkReview:
    completed_ids: list[str]
    mode: str
    mode_zh: str
    reply_en: str = ""
    coach_zh: str = ""
    degraded: bool = False
    provider: str = "script"


def chat_available() -> bool:
    choice = settings.provider()
    if choice in {"off", "none", "script"}:
        return False
    if choice in {"auto", "deepseek"} and settings.deepseek_key():
        return True
    return False


def chat_status() -> dict:
    available = chat_available()
    return {
        "provider": "deepseek" if available else None,
        "available": available,
        "model": settings.deepseek_model() if available else None,
        "label_zh": "DeepSeek 文字陪练" if available else "脚本练习（未配置 DeepSeek）",
        "detail_zh": (
            "提交英文后会把本课任务和你写的句子发给 DeepSeek，用来判目标和回一句。"
            if available
            else "没配密钥时只做关键词检查，不访问外网。"
        ),
    }


def explain_grammar(item: dict) -> dict:
    if not chat_available():
        raise ChatError("unavailable")
    data = _deepseek_explain(item)
    return {
        "explain_zh": _clip(data.get("explain_zh"), 480),
        "mode": "deepseek",
        "mode_zh": "补充说明",
        "provider": "deepseek",
    }


def review_talk(lesson: dict, goals: list[dict], text: str) -> TalkReview:
    keyword_ids = completed_goal_ids(text, goals)
    if not chat_available():
        return TalkReview(
            completed_ids=keyword_ids,
            mode="script",
            mode_zh=MODE_ZH["script"],
            provider="script",
        )
    try:
        data = _deepseek_review(lesson, goals, text)
    except ChatError:
        return TalkReview(
            completed_ids=keyword_ids,
            mode="script",
            mode_zh=MODE_ZH["script"],
            coach_zh="DeepSeek 暂时不可用，已改回关键词检查。",
            degraded=True,
            provider="script",
        )
    allowed = {item["id"] for item in goals}
    extra = [item for item in data.get("goal_ids") or [] if isinstance(item, str) and item in allowed]
    done = list(dict.fromkeys([*keyword_ids, *extra]))
    return TalkReview(
        completed_ids=done,
        mode="deepseek",
        mode_zh=MODE_ZH["deepseek"],
        reply_en=_clip(data.get("reply_en"), 240),
        coach_zh=_clip(data.get("coach_zh"), 240),
        provider="deepseek",
    )


def _clip(value: object, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _message_json(body: dict) -> dict:
    try:
        message = body["choices"][0]["message"]
        raw = message.get("content")
    except (KeyError, IndexError, TypeError) as exc:
        raise ChatError("bad response") from exc
    text = str(raw or "").strip()
    if not text:
        raise ChatError("empty")
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ChatError("bad response") from exc
    if not isinstance(data, dict):
        raise ChatError("bad response")
    return data


def _deepseek_explain(item: dict) -> dict:
    teach = item.get("teach") or {}
    payload = {
        "model": settings.deepseek_model(),
        "temperature": 0.2,
        "max_tokens": 360,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You explain one A1 English word, phrase, or pattern to a solo learner. "
                    "Reply with JSON only: explain_zh (2 to 4 short Simplified Chinese sentences). "
                    "If question is present, answer that question about this item. "
                    "Stay on this item. Do not teach later grammar. "
                    "Do not claim to be a human teacher. Do not ask for personal data."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "title_zh": item.get("title_zh") or "",
                        "english": item.get("english") or "",
                        "chinese": item.get("chinese") or "",
                        "kind": item.get("kind") or "",
                        "note_zh": item.get("note_zh") or "",
                        "phonetic": item.get("phonetic") or "",
                        "example_en": item.get("example_en") or "",
                        "example_zh": item.get("example_zh") or "",
                        "why_title": teach.get("why_title") or "",
                        "why_lines": teach.get("why_lines") or [],
                        "replies": teach.get("replies") or [],
                        "question": item.get("question") or "",
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }
    url = settings.deepseek_base_url() + "/chat/completions"
    body = _post_json(
        url,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.deepseek_key()}",
        },
        payload,
        timeout=20,
    )
    return _message_json(body)


def _deepseek_review(lesson: dict, goals: list[dict], text: str) -> dict:
    task = lesson.get("task") or {}
    payload = {
        "model": settings.deepseek_model(),
        "temperature": 0.3,
        "max_tokens": 280,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You coach one English turn for a solo A1 learner. "
                    "Reply with JSON only: goal_ids (array of given ids the learner met, "
                    "including clear paraphrases), reply_en (one short partner line), "
                    "coach_zh (one short Simplified Chinese note). "
                    "Do not invent goal ids. Do not ask for personal data."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "title_zh": lesson.get("title_zh") or "",
                        "task_zh": task.get("brief_zh") or "",
                        "goals": [{"id": item["id"], "label_zh": item["label_zh"]} for item in goals],
                        "user_en": text,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }
    url = settings.deepseek_base_url() + "/chat/completions"
    body = _post_json(
        url,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.deepseek_key()}",
        },
        payload,
        timeout=12,
    )
    data = _message_json(body)
    if not isinstance(data.get("goal_ids"), list):
        data["goal_ids"] = []
    return data


def _post_json(url: str, headers: dict, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ChatError(f"http {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ChatError("unavailable") from exc
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ChatError("bad response") from exc
    if not isinstance(body, dict):
        raise ChatError("bad response")
    return body
