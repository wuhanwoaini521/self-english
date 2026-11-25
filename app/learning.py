"""Learning database: lessons, progress, review cards. Separate from app.db."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

from . import seed
from .dialogue import MODE, MODE_ZH, completed_goal_ids, hint_for, your_lines
from .srs import RESULTS, iso, schedule

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEARNING_DB = ROOT / "data" / "learning.db"
SCHEMA_VERSION = 3
STEPS = seed.STEPS
VOCAB_PHASES = seed.VOCAB_PHASES


def learning_path() -> Path:
    import os

    override = os.environ.get("SELF_ENGLISH_LEARNING_DB")
    return Path(override) if override else DEFAULT_LEARNING_DB


@contextmanager
def connect() -> sqlite3.Connection:
    path = learning_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _init_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS lessons (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            title_zh TEXT NOT NULL,
            level TEXT NOT NULL,
            source TEXT NOT NULL,
            source_note TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS expressions (
            id TEXT PRIMARY KEY,
            lesson_id TEXT NOT NULL,
            english TEXT NOT NULL,
            chinese TEXT NOT NULL,
            kind TEXT NOT NULL,
            phonetic TEXT NOT NULL DEFAULT '',
            note_zh TEXT NOT NULL DEFAULT '',
            example_en TEXT NOT NULL DEFAULT '',
            example_zh TEXT NOT NULL DEFAULT '',
            mark TEXT NOT NULL DEFAULT '',
            audio_url TEXT,
            sort_order INTEGER NOT NULL,
            FOREIGN KEY (lesson_id) REFERENCES lessons(id)
        );
        CREATE TABLE IF NOT EXISTS dialogue_lines (
            id TEXT PRIMARY KEY,
            lesson_id TEXT NOT NULL,
            speaker TEXT NOT NULL,
            speaker_zh TEXT NOT NULL,
            english TEXT NOT NULL,
            chinese TEXT NOT NULL,
            audio_url TEXT,
            sort_order INTEGER NOT NULL,
            FOREIGN KEY (lesson_id) REFERENCES lessons(id)
        );
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            lesson_id TEXT NOT NULL,
            prompt_en TEXT NOT NULL,
            prompt_zh TEXT NOT NULL,
            options_json TEXT NOT NULL,
            answer_id TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            FOREIGN KEY (lesson_id) REFERENCES lessons(id)
        );
        CREATE TABLE IF NOT EXISTS task_goals (
            id TEXT PRIMARY KEY,
            lesson_id TEXT NOT NULL,
            label_zh TEXT NOT NULL,
            keys_json TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            FOREIGN KEY (lesson_id) REFERENCES lessons(id)
        );
        CREATE TABLE IF NOT EXISTS lesson_progress (
            lesson_id TEXT PRIMARY KEY,
            step TEXT NOT NULL,
            vocab_index INTEGER NOT NULL DEFAULT 0,
            vocab_phase TEXT NOT NULL DEFAULT 'learn',
            listen_index INTEGER NOT NULL DEFAULT 0,
            hide_zh INTEGER NOT NULL DEFAULT 0,
            question_results_json TEXT NOT NULL DEFAULT '{}',
            task_results_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            FOREIGN KEY (lesson_id) REFERENCES lessons(id)
        );
        CREATE TABLE IF NOT EXISTS review_cards (
            expression_id TEXT PRIMARY KEY,
            english TEXT NOT NULL,
            chinese TEXT NOT NULL,
            box INTEGER NOT NULL,
            interval_days INTEGER NOT NULL,
            due_at TEXT NOT NULL,
            last_result TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS review_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expression_id TEXT NOT NULL,
            result TEXT NOT NULL,
            due_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS dialogue_sessions (
            lesson_id TEXT PRIMARY KEY,
            mode TEXT NOT NULL,
            order_text TEXT NOT NULL DEFAULT '',
            hints_shown INTEGER NOT NULL DEFAULT 0,
            completed_goals_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL
        );
        """
    )
    _add_column(connection, "expressions", "phonetic", "TEXT NOT NULL DEFAULT ''")
    _add_column(connection, "expressions", "note_zh", "TEXT NOT NULL DEFAULT ''")
    _add_column(connection, "expressions", "example_en", "TEXT NOT NULL DEFAULT ''")
    _add_column(connection, "expressions", "example_zh", "TEXT NOT NULL DEFAULT ''")
    _add_column(connection, "expressions", "mark", "TEXT NOT NULL DEFAULT ''")
    _add_column(connection, "lesson_progress", "vocab_phase", "TEXT NOT NULL DEFAULT 'learn'")
    row = connection.execute("SELECT version FROM schema_version").fetchone()
    current = int(row["version"]) if row is not None else 0
    if current < 3:
        connection.execute(
            """
            UPDATE lesson_progress
            SET vocab_index = 0, vocab_phase = 'learn'
            WHERE step != 'done'
            """
        )
    if row is None:
        connection.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    else:
        connection.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    connection.commit()


def _add_column(connection: sqlite3.Connection, table: str, name: str, spec: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if name not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")


def seed_lesson(connection: sqlite3.Connection) -> None:
    for lesson in seed.LESSONS:
        connection.execute(
            """
            INSERT OR IGNORE INTO lessons (id, title, title_zh, level, source, source_note)
            VALUES (:id, :title, :title_zh, :level, :source, :source_note)
            """,
            lesson,
        )
        for item in lesson["expressions"]:
            connection.execute(
                """
                INSERT INTO expressions (
                    id, lesson_id, english, chinese, kind, phonetic, note_zh,
                    example_en, example_zh, mark, audio_url, sort_order
                ) VALUES (
                    :id, :lesson_id, :english, :chinese, :kind, :phonetic, :note_zh,
                    :example_en, :example_zh, :mark, NULL, :sort_order
                )
                ON CONFLICT(id) DO UPDATE SET
                    english = excluded.english,
                    chinese = excluded.chinese,
                    kind = excluded.kind,
                    phonetic = excluded.phonetic,
                    note_zh = excluded.note_zh,
                    example_en = excluded.example_en,
                    example_zh = excluded.example_zh,
                    mark = excluded.mark,
                    sort_order = excluded.sort_order
                """,
                {**item, "lesson_id": lesson["id"]},
            )
        for item in lesson["dialogue"]:
            connection.execute(
                """
                INSERT OR IGNORE INTO dialogue_lines
                (id, lesson_id, speaker, speaker_zh, english, chinese, audio_url, sort_order)
                VALUES (:id, :lesson_id, :speaker, :speaker_zh, :english, :chinese, NULL, :sort_order)
                """,
                {**item, "lesson_id": lesson["id"]},
            )
        for item in lesson["questions"]:
            connection.execute(
                """
                INSERT OR IGNORE INTO questions
                (id, lesson_id, prompt_en, prompt_zh, options_json, answer_id, sort_order)
                VALUES (:id, :lesson_id, :prompt_en, :prompt_zh, :options_json, :answer_id, :sort_order)
                """,
                {
                    "id": item["id"],
                    "lesson_id": lesson["id"],
                    "prompt_en": item["prompt_en"],
                    "prompt_zh": item["prompt_zh"],
                    "options_json": json.dumps(item["options"], ensure_ascii=False),
                    "answer_id": item["answer_id"],
                    "sort_order": item["sort_order"],
                },
            )
        for item in lesson["goals"]:
            connection.execute(
                """
                INSERT OR IGNORE INTO task_goals
                (id, lesson_id, label_zh, keys_json, sort_order)
                VALUES (:id, :lesson_id, :label_zh, :keys_json, :sort_order)
                """,
                {
                    "id": item["id"],
                    "lesson_id": lesson["id"],
                    "label_zh": item["label_zh"],
                    "keys_json": json.dumps(item["keys"], ensure_ascii=False),
                    "sort_order": item["sort_order"],
                },
            )
    connection.commit()


def init() -> None:
    with connect() as connection:
        _init_schema(connection)
        seed_lesson(connection)


def _lesson_row(connection: sqlite3.Connection, lesson_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="没有这一课。")
    return row


def _progress_row(connection: sqlite3.Connection, lesson_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM lesson_progress WHERE lesson_id = ?", (lesson_id,)
    ).fetchone()


def _default_progress(lesson_id: str) -> dict:
    return {
        "lesson_id": lesson_id,
        "step": "vocab",
        "vocab_index": 0,
        "listen_index": 0,
        "vocab_phase": "learn",
        "hide_zh": False,
        "question_results": {},
        "task_results": {},
        "updated_at": None,
    }


def _progress_out(row: sqlite3.Row | None, lesson_id: str) -> dict:
    if row is None:
        return _default_progress(lesson_id)
    return {
        "lesson_id": row["lesson_id"],
        "step": row["step"],
        "vocab_index": row["vocab_index"],
        "vocab_phase": row["vocab_phase"] if "vocab_phase" in row.keys() else "learn",
        "listen_index": row["listen_index"],
        "hide_zh": bool(row["hide_zh"]),
        "question_results": json.loads(row["question_results_json"]),
        "task_results": json.loads(row["task_results_json"]),
        "updated_at": row["updated_at"],
    }


def _goals(connection: sqlite3.Connection, lesson_id: str) -> list[dict]:
    rows = connection.execute(
        "SELECT * FROM task_goals WHERE lesson_id = ? ORDER BY sort_order",
        (lesson_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "label_zh": row["label_zh"],
            "keys": json.loads(row["keys_json"]),
        }
        for row in rows
    ]


def _lines(connection: sqlite3.Connection, lesson_id: str) -> list[dict]:
    rows = connection.execute(
        "SELECT * FROM dialogue_lines WHERE lesson_id = ? ORDER BY sort_order",
        (lesson_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "speaker": row["speaker"],
            "speaker_zh": row["speaker_zh"],
            "english": row["english"],
            "chinese": row["chinese"],
            "audio": "system",
            "audio_label": "系统朗读",
        }
        for row in rows
    ]


def lesson_payload(lesson_id: str) -> dict:
    with connect() as connection:
        lesson = _lesson_row(connection, lesson_id)
        expressions = [
            {
                "id": row["id"],
                "english": row["english"],
                "chinese": row["chinese"],
                "kind": row["kind"],
                "phonetic": row["phonetic"] if "phonetic" in row.keys() else "",
                "note_zh": row["note_zh"] if "note_zh" in row.keys() else "",
                "example_en": row["example_en"] if "example_en" in row.keys() else "",
                "example_zh": row["example_zh"] if "example_zh" in row.keys() else "",
                "mark": row["mark"] if "mark" in row.keys() else "",
                "audio": "system" if not row["audio_url"] else "file",
                "audio_label": "系统朗读" if not row["audio_url"] else "课文音频",
            }
            for row in connection.execute(
                "SELECT * FROM expressions WHERE lesson_id = ? ORDER BY sort_order",
                (lesson_id,),
            )
        ]
        questions = [
            {
                "id": row["id"],
                "prompt_en": row["prompt_en"],
                "prompt_zh": row["prompt_zh"],
                "options": json.loads(row["options_json"]),
                "answer_id": row["answer_id"],
            }
            for row in connection.execute(
                "SELECT * FROM questions WHERE lesson_id = ? ORDER BY sort_order",
                (lesson_id,),
            )
        ]
        return {
            "id": lesson["id"],
            "title": lesson["title"],
            "title_zh": lesson["title_zh"],
            "level": lesson["level"],
            "source": lesson["source"],
            "source_note": lesson["source_note"],
            "steps": list(STEPS),
            "step_zh": seed.STEP_ZH,
            "expressions": expressions,
            "dialogue": _lines(connection, lesson_id),
            "questions": questions,
            "goals": [
                {"id": item["id"], "label_zh": item["label_zh"]}
                for item in _goals(connection, lesson_id)
            ],
            "task": lesson_meta(lesson_id)["task"],
            "progress": _progress_out(_progress_row(connection, lesson_id), lesson_id),
        }


def lesson_meta(lesson_id: str) -> dict:
    lesson = seed.lesson_by_id(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="没有这一课。")
    return lesson


def _current_lesson(connection: sqlite3.Connection) -> tuple[dict, dict, bool]:
    last = seed.LESSONS[-1]
    last_progress = _progress_out(_progress_row(connection, last["id"]), last["id"])
    for lesson in seed.LESSONS:
        progress = _progress_out(_progress_row(connection, lesson["id"]), lesson["id"])
        if progress["step"] != "done":
            return lesson, progress, False
    return last, last_progress, True


def today() -> dict:
    with connect() as connection:
        lesson, progress, all_done = _current_lesson(connection)
        due = connection.execute(
            "SELECT COUNT(*) FROM review_cards WHERE due_at <= ?",
            (iso(),),
        ).fetchone()[0]
        step = progress["step"]
        index = seed.lesson_index(lesson["id"])
        if all_done:
            action = "再看这一课"
            page = "today"
        elif progress["updated_at"] is None:
            action = "开始第一课" if index == 1 else f"开始第 {index} 课"
            page = "vocab"
        else:
            action = f"继续：{seed.STEP_ZH[step]}"
            page = {"vocab": "vocab", "listen": "reading", "talk": "talk", "recap": "today"}.get(step, "today")
        return {
            "lesson_id": lesson["id"],
            "title_zh": lesson["title_zh"],
            "level": lesson["level"],
            "lesson_no": index,
            "lesson_total": len(seed.LESSONS),
            "progress": progress,
            "due_count": due,
            "action": action,
            "page": page,
        }


def save_progress(lesson_id: str, payload: dict) -> dict:
    step = payload.get("step")
    if step not in STEPS:
        raise HTTPException(status_code=400, detail="步骤不对。")
    hide_zh = 1 if payload.get("hide_zh") else 0
    vocab_index = int(payload.get("vocab_index") or 0)
    listen_index = int(payload.get("listen_index") or 0)
    if vocab_index < 0 or listen_index < 0:
        raise HTTPException(status_code=400, detail="进度不能是负数。")
    vocab_phase = payload.get("vocab_phase")
    if vocab_phase is not None and vocab_phase not in VOCAB_PHASES:
        raise HTTPException(status_code=400, detail="词汇阶段不对。")
    question_results = payload.get("question_results") or {}
    task_results = payload.get("task_results") or {}
    if not isinstance(question_results, dict) or not isinstance(task_results, dict):
        raise HTTPException(status_code=400, detail="答题结果格式不对。")
    expected = payload.get("expected_updated_at")
    now = iso()
    with connect() as connection:
        _lesson_row(connection, lesson_id)
        current = _progress_row(connection, lesson_id)
        if vocab_phase is None:
            if current is not None and "vocab_phase" in current.keys():
                vocab_phase = current["vocab_phase"] or "learn"
            else:
                vocab_phase = "learn"
        if current is not None and current["updated_at"] != expected:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "另一端已经更新了进度。",
                    "progress": _progress_out(current, lesson_id),
                },
            )
        connection.execute(
            """
            INSERT INTO lesson_progress (
                lesson_id, step, vocab_index, vocab_phase, listen_index, hide_zh,
                question_results_json, task_results_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lesson_id) DO UPDATE SET
                step = excluded.step,
                vocab_index = excluded.vocab_index,
                vocab_phase = excluded.vocab_phase,
                listen_index = excluded.listen_index,
                hide_zh = excluded.hide_zh,
                question_results_json = excluded.question_results_json,
                task_results_json = excluded.task_results_json,
                updated_at = excluded.updated_at
            """,
            (
                lesson_id,
                step,
                vocab_index,
                vocab_phase,
                listen_index,
                hide_zh,
                json.dumps(question_results, ensure_ascii=False),
                json.dumps(task_results, ensure_ascii=False),
                now,
            ),
        )
        connection.commit()
        return _progress_out(_progress_row(connection, lesson_id), lesson_id)


def add_review(expression_id: str) -> dict:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM expressions WHERE id = ?", (expression_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="没有这个表达。")
        existing = connection.execute(
            "SELECT * FROM review_cards WHERE expression_id = ?",
            (expression_id,),
        ).fetchone()
        if existing is not None:
            return {**dict(existing), "created": False}
        now = iso()
        connection.execute(
            """
            INSERT INTO review_cards (
                expression_id, english, chinese, box, interval_days, due_at, last_result, updated_at
            ) VALUES (?, ?, ?, 1, 0, ?, NULL, ?)
            """,
            (expression_id, row["english"], row["chinese"], now, now),
        )
        connection.commit()
        saved = connection.execute(
            "SELECT * FROM review_cards WHERE expression_id = ?",
            (expression_id,),
        ).fetchone()
        return {**dict(saved), "created": True}


def grade_review(expression_id: str, result: str) -> dict:
    if result not in RESULTS:
        raise HTTPException(status_code=400, detail="只能选忘了、模糊或记得。")
    with connect() as connection:
        expression = connection.execute(
            "SELECT * FROM expressions WHERE id = ?",
            (expression_id,),
        ).fetchone()
        if expression is None:
            raise HTTPException(status_code=404, detail="没有这个表达。")
        card = connection.execute(
            "SELECT * FROM review_cards WHERE expression_id = ?",
            (expression_id,),
        ).fetchone()
        if card is None:
            now = iso()
            connection.execute(
                """
                INSERT INTO review_cards (
                    expression_id, english, chinese, box, interval_days, due_at, last_result, updated_at
                ) VALUES (?, ?, ?, 1, 0, ?, NULL, ?)
                """,
                (expression_id, expression["english"], expression["chinese"], now, now),
            )
            card = connection.execute(
                "SELECT * FROM review_cards WHERE expression_id = ?",
                (expression_id,),
            ).fetchone()
        box, days, due_at = schedule(card["box"], result)
        now = iso()
        connection.execute(
            """
            UPDATE review_cards
            SET box = ?, interval_days = ?, due_at = ?, last_result = ?, updated_at = ?
            WHERE expression_id = ?
            """,
            (box, days, due_at, result, now, expression_id),
        )
        connection.execute(
            """
            INSERT INTO review_log (expression_id, result, due_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (expression_id, result, due_at, now),
        )
        connection.commit()
        saved = connection.execute(
            "SELECT * FROM review_cards WHERE expression_id = ?",
            (expression_id,),
        ).fetchone()
        return dict(saved)


def due_cards() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM review_cards WHERE due_at <= ? ORDER BY due_at, expression_id",
            (iso(),),
        ).fetchall()
        return [dict(row) for row in rows]


def review_log(limit: int = 20) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT log.result, log.due_at, log.created_at, cards.english, cards.chinese, log.expression_id
            FROM review_log AS log
            JOIN review_cards AS cards ON cards.expression_id = log.expression_id
            ORDER BY log.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def dialogue_state(lesson_id: str) -> dict:
    with connect() as connection:
        _lesson_row(connection, lesson_id)
        session = connection.execute(
            "SELECT * FROM dialogue_sessions WHERE lesson_id = ?",
            (lesson_id,),
        ).fetchone()
        goals = _goals(connection, lesson_id)
        lines = _lines(connection, lesson_id)
        if session is None:
            return {
                "lesson_id": lesson_id,
                "mode": MODE,
                "mode_zh": MODE_ZH,
                "order_text": "",
                "hints_shown": 0,
                "completed_goals": [],
                "goals": [{"id": item["id"], "label_zh": item["label_zh"], "done": False} for item in goals],
                "hint": None,
                "updated_at": None,
            }
        completed = json.loads(session["completed_goals_json"])
        return {
            "lesson_id": lesson_id,
            "mode": session["mode"],
            "mode_zh": MODE_ZH,
            "order_text": session["order_text"],
            "hints_shown": session["hints_shown"],
            "completed_goals": completed,
            "goals": [
                {"id": item["id"], "label_zh": item["label_zh"], "done": item["id"] in completed}
                for item in goals
            ],
            "hint": hint_for(lines, session["hints_shown"] - 1) if session["hints_shown"] else None,
            "updated_at": session["updated_at"],
        }


def show_dialogue_hint(lesson_id: str) -> dict:
    with connect() as connection:
        lines = _lines(connection, lesson_id)
        session = connection.execute(
            "SELECT * FROM dialogue_sessions WHERE lesson_id = ?",
            (lesson_id,),
        ).fetchone()
        ceiling = max(len(your_lines(lines)), 1)
        shown = 1 if session is None else min(ceiling, session["hints_shown"] + 1)
        _upsert_dialogue(connection, lesson_id, session, hints_shown=shown)
        connection.commit()
    return dialogue_state(lesson_id)


def submit_order(lesson_id: str, text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail=lesson_meta(lesson_id)["task"]["empty_error"])
    if len(text) > 500:
        raise HTTPException(status_code=400, detail="这句话太长了。")
    with connect() as connection:
        goals = _goals(connection, lesson_id)
        done = completed_goal_ids(text, goals)
        session = connection.execute(
            "SELECT * FROM dialogue_sessions WHERE lesson_id = ?",
            (lesson_id,),
        ).fetchone()
        _upsert_dialogue(connection, lesson_id, session, order_text=text, completed=done)
        connection.commit()
    return dialogue_state(lesson_id)


def _upsert_dialogue(
    connection: sqlite3.Connection,
    lesson_id: str,
    session: sqlite3.Row | None,
    *,
    hints_shown: int | None = None,
    order_text: str | None = None,
    completed: list[str] | None = None,
) -> None:
    now = iso()
    if session is None:
        connection.execute(
            """
            INSERT INTO dialogue_sessions
            (lesson_id, mode, order_text, hints_shown, completed_goals_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                lesson_id,
                MODE,
                order_text or "",
                hints_shown or 0,
                json.dumps(completed or [], ensure_ascii=False),
                now,
            ),
        )
        return
    connection.execute(
        """
        UPDATE dialogue_sessions
        SET order_text = ?, hints_shown = ?, completed_goals_json = ?, updated_at = ?
        WHERE lesson_id = ?
        """,
        (
            session["order_text"] if order_text is None else order_text,
            session["hints_shown"] if hints_shown is None else hints_shown,
            session["completed_goals_json"] if completed is None else json.dumps(completed, ensure_ascii=False),
            now,
            lesson_id,
        ),
    )


def _month_done(connection: sqlite3.Connection, month: int) -> bool:
    lessons = [item for item in seed.LESSONS if item["month"] == month]
    if not lessons:
        return False
    for lesson in lessons:
        progress = _progress_out(_progress_row(connection, lesson["id"]), lesson["id"])
        if progress["step"] != "done":
            return False
    return True


def progress_overview() -> dict:
    with connect() as connection:
        due = connection.execute(
            "SELECT COUNT(*) FROM review_cards WHERE due_at <= ?",
            (iso(),),
        ).fetchone()[0]
        cards = connection.execute("SELECT COUNT(*) FROM review_cards").fetchone()[0]
        log = review_log(8)
        completed = []
        for lesson in seed.LESSONS:
            progress = _progress_out(_progress_row(connection, lesson["id"]), lesson["id"])
            if progress["step"] == "done":
                completed.append(
                    {
                        "id": lesson["id"],
                        "title_zh": lesson["title_zh"],
                        "at": progress["updated_at"],
                    }
                )
        roadmap = []
        for item in seed.ROADMAP:
            status = item["status"]
            label = "进行中" if status == "in_progress" else "待验证"
            if item["id"] == "m1" and _month_done(connection, 1):
                status = "done"
                label = "已完成"
            roadmap.append({**item, "status": status, "label": label})
        return {
            "completed_lessons": completed,
            "due_count": due,
            "card_count": cards,
            "review_log": log,
            "roadmap": roadmap,
        }
