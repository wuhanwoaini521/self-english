"""LAN English study app: lessons plus the existing phrasebook."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import catalog, learning
STATIC = learning.ROOT / "app" / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    learning.init()
    yield


app = FastAPI(title="self-english", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/api/catalog/status")
def catalog_status() -> dict:
    return catalog.status()


@app.get("/api/stats")
def stats() -> dict:
    return catalog.stats()


@app.get("/api/feed")
def feed(
    books: str = "travel",
    q: str = "",
    offset: int = Query(0, ge=0),
) -> dict:
    return catalog.feed(books, q, offset)


@app.get("/api/words")
def words(
    q: str = "",
    spoken: int = 0,
    offset: int = Query(0, ge=0),
    limit: int = Query(40, ge=1, le=80),
) -> dict:
    return catalog.words(q, spoken, offset, limit)


@app.get("/api/sentences")
def sentences(
    pack: str = "survival",
    q: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(40, ge=1, le=80),
) -> dict:
    return catalog.sentences(pack, q, offset, limit)


@app.get("/api/today")
def today() -> dict:
    return learning.today()


@app.get("/api/lessons/{lesson_id}")
def lesson(lesson_id: str) -> dict:
    return learning.lesson_payload(lesson_id)


@app.get("/api/lessons/{lesson_id}/progress")
def get_progress(lesson_id: str) -> dict:
    payload = learning.lesson_payload(lesson_id)
    return payload["progress"]


@app.post("/api/lessons/{lesson_id}/progress")
def post_progress(lesson_id: str, body: dict) -> dict:
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="进度内容不对。")
    return learning.save_progress(lesson_id, body)


@app.post("/api/review/cards")
def post_review_card(body: dict) -> dict:
    expression_id = (body or {}).get("expression_id")
    if not expression_id or not isinstance(expression_id, str):
        raise HTTPException(status_code=400, detail="缺少表达编号。")
    return learning.add_review(expression_id)


@app.post("/api/review/cards/{expression_id}/result")
def post_review_result(expression_id: str, body: dict) -> dict:
    result = (body or {}).get("result")
    mapping = {"忘了": "forgot", "模糊": "fuzzy", "记得": "remembered"}
    if result in mapping:
        result = mapping[result]
    return learning.grade_review(expression_id, result or "")


@app.get("/api/review/due")
def review_due() -> dict:
    return {"items": learning.due_cards()}


@app.get("/api/review/log")
def review_log() -> dict:
    return {"items": learning.review_log()}


@app.get("/api/dialogue/{lesson_id}")
def dialogue(lesson_id: str) -> dict:
    return learning.dialogue_state(lesson_id)


@app.post("/api/dialogue/{lesson_id}/hint")
def dialogue_hint(lesson_id: str) -> dict:
    return learning.show_dialogue_hint(lesson_id)


@app.post("/api/dialogue/{lesson_id}/order")
def dialogue_order(lesson_id: str, body: dict) -> dict:
    return learning.submit_order(lesson_id, (body or {}).get("text") or "")


@app.get("/api/progress")
def progress() -> dict:
    return learning.progress_overview()


@app.get("/{path:path}")
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="没有这个接口。")
    return FileResponse(STATIC / "index.html")
