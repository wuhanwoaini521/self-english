"""Scripted cafe-order practice. Voice and AI can replace this later."""

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


def hint_for(lines: list[dict], shown: int) -> dict | None:
    if shown < 0 or shown >= len(lines):
        return None
    line = lines[shown]
    return {
        "id": line["id"],
        "speaker": line["speaker"],
        "english": line["english"],
        "chinese": line["chinese"],
        "mode": MODE,
        "mode_zh": MODE_ZH,
    }
