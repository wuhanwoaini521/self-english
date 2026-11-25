"""Phrasebook catalog backed by data/app.db. Rebuilding it must not touch learning.db."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "app.db"
BOOKS = ("travel", "business", "reading")
PAGE = 7
BUILD_HINT = "还没有词库。在项目目录运行 uv run python scripts/build_catalog.py"


def ready() -> bool:
    return DB_PATH.exists()


def status() -> dict:
    if not ready():
        return {"ready": False, "hint": BUILD_HINT}
    with connect() as connection:
        words = connection.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        survival = connection.execute("SELECT COUNT(*) FROM sentences WHERE pack = 'survival'").fetchone()[0]
        tatoeba = connection.execute("SELECT COUNT(*) FROM sentences WHERE pack = 'tatoeba'").fetchone()[0]
    return {"ready": True, "hint": "", "words": words, "survival": survival, "tatoeba": tatoeba}


@contextmanager
def connect():
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail=BUILD_HINT)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def chosen_books(raw: str) -> list[str]:
    selected = [part for part in raw.split(",") if part in BOOKS]
    return selected or ["travel"]


def searchable(q: str, *fields: str) -> bool:
    needle = q.strip().casefold()
    if not needle:
        return True
    return any(needle in (field or "").casefold() for field in fields)


def stats() -> dict:
    info = status()
    if not info["ready"]:
        raise HTTPException(status_code=503, detail=BUILD_HINT)
    with connect() as connection:
        words = connection.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        spoken = connection.execute("SELECT COUNT(*) FROM words WHERE spoken_rank IS NOT NULL").fetchone()[0]
        survival = connection.execute("SELECT COUNT(*) FROM sentences WHERE pack = 'survival'").fetchone()[0]
        tatoeba = connection.execute("SELECT COUNT(*) FROM sentences WHERE pack = 'tatoeba'").fetchone()[0]
    return {"words": words, "spoken": spoken, "survival": survival, "tatoeba": tatoeba}


def feed(books: str = "travel", q: str = "", offset: int = 0) -> dict:
    selected = chosen_books(books)
    word_books = [book for book in selected if book != "reading"]
    with connect() as connection:
        sentence_rows = connection.execute(
            "SELECT english, chinese, book FROM sentences ORDER BY id"
        ).fetchall()
        word_rows = connection.execute(
            """
            SELECT headword, pos, phonetic, translation, spoken_rank, books
            FROM words
            ORDER BY spoken_rank IS NULL, spoken_rank, headword
            """
        ).fetchall()
    grouped: dict[str, list[dict]] = {book: [] for book in selected}
    for row in sentence_rows:
        if row["book"] not in grouped:
            continue
        if not searchable(q, row["english"], row["chinese"]):
            continue
        grouped[row["book"]].append(
            {
                "kind": "sentence",
                "english": row["english"],
                "chinese": row["chinese"],
                "phonetic": "",
                "pos": "",
            }
        )
    sentences: list[dict] = []
    pending = [grouped[book] for book in selected if grouped[book]]
    while pending:
        next_round = []
        for bucket in pending:
            sentences.append(bucket.pop(0))
            if bucket:
                next_round.append(bucket)
        pending = next_round
    words = []
    for row in word_rows:
        tags = set((row["books"] or "").split())
        if word_books and not tags.intersection(word_books):
            continue
        if not word_books:
            continue
        if not searchable(q, row["headword"], row["translation"]):
            continue
        words.append(
            {
                "kind": "word",
                "english": row["headword"],
                "chinese": row["translation"],
                "phonetic": row["phonetic"],
                "pos": row["pos"],
            }
        )
    items = sentences + words
    page = items[offset : offset + PAGE]
    return {"total": len(items), "books": selected, "items": page}


def words(
    q: str = "",
    spoken: int = 0,
    offset: int = 0,
    limit: int = 40,
) -> dict:
    clauses = []
    params: list[object] = []
    if q.strip():
        pattern = like_pattern(q.strip())
        clauses.append("(headword LIKE ? ESCAPE '\\' OR translation LIKE ? ESCAPE '\\')")
        params.extend([pattern, pattern])
    if spoken:
        clauses.append("spoken_rank IS NOT NULL")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM words {where}", params).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT headword, pos, phonetic, translation, spoken_rank, topics
            FROM words
            {where}
            ORDER BY spoken_rank IS NULL, spoken_rank, headword
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    return {"total": total, "items": [dict(row) for row in rows]}


def sentences(
    pack: str = "survival",
    q: str = "",
    offset: int = 0,
    limit: int = 40,
) -> dict:
    if pack not in {"survival", "tatoeba"}:
        raise HTTPException(status_code=400, detail="pack 只能是 survival 或 tatoeba")
    clauses = ["pack = ?"]
    params: list[object] = [pack]
    if q.strip():
        pattern = like_pattern(q.strip())
        clauses.append("(english LIKE ? ESCAPE '\\' OR chinese LIKE ? ESCAPE '\\')")
        params.extend([pattern, pattern])
    where = "WHERE " + " AND ".join(clauses)
    order = "id" if pack == "survival" else "length(english), id"
    with connect() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM sentences {where}", params).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT english, chinese, pack, attribution
            FROM sentences
            {where}
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    return {"total": total, "items": [dict(row) for row in rows]}
