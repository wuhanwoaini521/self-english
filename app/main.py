"""LAN phrasebook: A1 words and short bilingual sentences."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "app.db"
STATIC = Path(__file__).resolve().parent / "static"
BOOKS = ("travel", "business", "reading")
PAGE = 7

app = FastAPI(title="self-english")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="还没有词库。请先运行 python scripts/build_catalog.py")
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/stats")
def stats() -> dict:
    with connect() as connection:
        words = connection.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        spoken = connection.execute("SELECT COUNT(*) FROM words WHERE spoken_rank IS NOT NULL").fetchone()[0]
        survival = connection.execute("SELECT COUNT(*) FROM sentences WHERE pack = 'survival'").fetchone()[0]
        tatoeba = connection.execute("SELECT COUNT(*) FROM sentences WHERE pack = 'tatoeba'").fetchone()[0]
    return {"words": words, "spoken": spoken, "survival": survival, "tatoeba": tatoeba}


def chosen_books(raw: str) -> list[str]:
    selected = [part for part in raw.split(",") if part in BOOKS]
    return selected or ["travel"]


def searchable(q: str, *fields: str) -> bool:
    needle = q.strip().casefold()
    if not needle:
        return True
    return any(needle in (field or "").casefold() for field in fields)


@app.get("/api/feed")
def feed(books: str = "travel", q: str = "", offset: int = Query(0, ge=0)) -> dict:
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


@app.get("/api/words")
def words(
    q: str = "",
    spoken: int = 0,
    offset: int = Query(0, ge=0),
    limit: int = Query(40, ge=1, le=80),
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


@app.get("/api/sentences")
def sentences(
    pack: str = "survival",
    q: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(40, ge=1, le=80),
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
