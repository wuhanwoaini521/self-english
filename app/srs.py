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

KNOWN = "known"
UNKNOWN = "unknown"
MARK_RESULTS = (KNOWN, UNKNOWN)
MARK_RESULT_ZH = {KNOWN: "会", UNKNOWN: "不会"}
# After 「会」, wait these days (Ebbinghaus-style, weeks not days).
KNOWN_DAYS = {1: 14, 2: 30, 3: 60, 4: 60}


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


def schedule_mark(box: int, result: str, *, prior: str | None = None, now: datetime | None = None) -> tuple[int, int, str]:
    """Return (box, interval_days, due_at) for 会 / 不会.

    不会: box 1, due in 1 day, stay in teaching.
    会 from unmarked/unknown: box 1, due in 14 days.
    会 from already-known: box up one, wait 14 / 30 / 60 / 60 days.
    """
    now = now or utcnow()
    if result not in MARK_RESULTS:
        raise ValueError(f"unknown mark result: {result}")
    if result == UNKNOWN:
        return 1, 1, iso(now + timedelta(days=1))
    if prior != KNOWN:
        box = 1
        days = KNOWN_DAYS[1]
    else:
        box = min(4, max(1, box) + 1)
        days = KNOWN_DAYS[box]
    return box, days, iso(now + timedelta(days=days))
