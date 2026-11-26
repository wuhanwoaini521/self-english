"""Keyword checks for lesson talk. DeepSeek and voice sit in app.ai."""

from __future__ import annotations

import re

MODE = "script"
MODE_ZH = "脚本练习"


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def completed_goal_ids(text: str, goals: list[dict]) -> list[str]:
    blob = f" {normalize(text)} "
    done: list[str] = []
    for goal in goals:
        keys = [normalize(key) for key in goal.get("keys", []) if key]
        if keys and all(f" {key} " in blob or blob.startswith(f"{key} ") or blob.endswith(f" {key}") or blob == key for key in keys):
            done.append(goal["id"])
    return done


def your_lines(lines: list[dict]) -> list[dict]:
    return [line for line in lines if line.get("speaker") == "you"]


def hint_for(lines: list[dict], shown: int) -> dict | None:
    yours = your_lines(lines)
    if shown < 0 or shown >= len(yours):
        return None
    line = yours[shown]
    return {
        "id": line["id"],
        "speaker": line["speaker"],
        "english": line["english"],
        "chinese": line["chinese"],
        "mode": MODE,
        "mode_zh": MODE_ZH,
    }
