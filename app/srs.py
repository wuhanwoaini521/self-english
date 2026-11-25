"""Explicit interval rules for review cards."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

FORGOT = "forgot"
FUZZY = "fuzzy"
REMEMBERED = "remembered"
RESULTS = (FORGOT, FUZZY, REMEMBERED)
RESULT_ZH = {FORGOT: "忘了", FUZZY: "模糊", REMEMBERED: "记得"}

# After "remembered", the new box maps to these waiting days.
REMEMBERED_DAYS = {1: 1, 2: 3, 3: 7, 4: 14}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(moment: datetime | None = None) -> str:
    moment = moment or utcnow()
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def schedule(box: int, result: str, now: datetime | None = None) -> tuple[int, int, str]:
    """Return (box, interval_days, due_at).

    忘了: back to box 1, due in 1 day.
    模糊: keep the box, due in 2 days.
    记得: box moves up one (max 4); wait 1 / 3 / 7 / 14 days.
    """
    now = now or utcnow()
    if result not in RESULTS:
        raise ValueError(f"unknown result: {result}")
    if result == FORGOT:
        box = 1
        days = 1
    elif result == FUZZY:
        box = min(4, max(1, box))
        days = 2
    else:
        box = min(4, max(1, box) + 1)
        days = REMEMBERED_DAYS[box]
    return box, days, iso(now + timedelta(days=days))
