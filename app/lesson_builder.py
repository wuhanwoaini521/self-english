"""Helpers for original lesson seed data."""

from __future__ import annotations

SOURCE_NOTE = "本课为 self-english 原创种子，供个人学习。无真人录音，朗读使用设备系统语音。"
MARK_KINDS = ("vocab", "grammar")


def _mark(text: str, *, kind: str, phonetic: str, pos: str, sense_zh: str, headword: str = "") -> dict:
    if kind not in MARK_KINDS:
        raise ValueError(f"unknown mark kind: {kind}")
    return {
        "text": text,
        "kind": kind,
        "headword": headword or text,
        "phonetic": phonetic,
        "pos": pos,
        "sense_zh": sense_zh,
    }


def vocab(text: str, *, phonetic: str, pos: str, sense_zh: str, headword: str = "") -> dict:
    return _mark(text, kind="vocab", phonetic=phonetic, pos=pos, sense_zh=sense_zh, headword=headword)


def grammar(text: str, *, sense_zh: str, phonetic: str = "", pos: str = "语法", headword: str = "") -> dict:
    return _mark(text, kind="grammar", phonetic=phonetic, pos=pos, sense_zh=sense_zh, headword=headword)


def join_parts(parts: tuple[object, ...]) -> tuple[str, list[dict]]:
    chunks: list[str] = []
    marks: list[dict] = []
    for part in parts:
        if isinstance(part, str):
            chunks.append(part)
            continue
        start = sum(len(chunk) for chunk in chunks)
        text = part["text"]
        chunks.append(text)
        marks.append(
            {
                "start": start,
                "end": start + len(text),
                "kind": part["kind"],
                "headword": part["headword"],
                "phonetic": part["phonetic"],
                "pos": part["pos"],
                "sense_zh": part["sense_zh"],
            }
        )
    return "".join(chunks), marks


def _line(speaker: str, speaker_zh: str, chinese: str, *parts: object) -> dict:
    english, marks = join_parts(parts)
    return {
        "speaker": speaker,
        "speaker_zh": speaker_zh,
        "english": english,
        "chinese": chinese,
        "marks": marks,
    }


def _para(chinese: str, *parts: object) -> dict:
    english, marks = join_parts(parts)
    return {"english": english, "chinese": chinese, "marks": marks}


def _expr(
    slug: str,
    english: str,
    chinese: str,
    *,
    kind: str,
    phonetic: str,
    note_zh: str,
    example_en: str,
    example_zh: str,
    mark: str,
) -> dict:
    return {
        "slug": slug,
        "english": english,
        "chinese": chinese,
        "kind": kind,
        "phonetic": phonetic,
        "note_zh": note_zh,
        "example_en": example_en,
        "example_zh": example_zh,
        "mark": mark,
    }


def _lesson(
    *,
    lesson_id: str,
    title: str,
    title_zh: str,
    task_title_zh: str,
    task_placeholder: str,
    submit_label: str,
    empty_error: str,
    brief_zh: str,
    hear_label_zh: str,
    expressions: list[dict],
    dialogue: list[dict],
    questions: list[dict],
    goals: list[tuple[str, str, list[str]]],
    passage: dict,
    month: int = 1,
    source_note: str | None = None,
) -> dict:
    return {
        "id": lesson_id,
        "title": title,
        "title_zh": title_zh,
        "level": "A1",
        "month": month,
        "source": "original",
        "source_note": source_note or SOURCE_NOTE,
        "task": {
            "title_zh": task_title_zh,
            "placeholder": task_placeholder,
            "submit_label": submit_label,
            "empty_error": empty_error,
            "brief_zh": brief_zh,
            "hear_label_zh": hear_label_zh,
        },
        "expressions": [
            {
                "id": f"{lesson_id}.{item['slug']}",
                "english": item["english"],
                "chinese": item["chinese"],
                "kind": item["kind"],
                "phonetic": item["phonetic"],
                "note_zh": item["note_zh"],
                "example_en": item["example_en"],
                "example_zh": item["example_zh"],
                "mark": item["mark"],
                "sort_order": index,
            }
            for index, item in enumerate(expressions, start=1)
        ],
        "dialogue": [
            {
                "id": f"{lesson_id}.line-{index}",
                "speaker": item["speaker"],
                "speaker_zh": item["speaker_zh"],
                "english": item["english"],
                "chinese": item["chinese"],
                "marks": item["marks"],
                "sort_order": index,
            }
            for index, item in enumerate(dialogue, start=1)
        ],
        "passage": {
            "title_zh": passage.get("title_zh") or "短文",
            "paragraphs": list(passage.get("paragraphs") or []),
        },
        "questions": [
            {**item, "id": f"{lesson_id}.{item['id']}", "sort_order": index}
            for index, item in enumerate(questions, start=1)
        ],
        "goals": [
            {
                "id": f"{lesson_id}.{slug}",
                "label_zh": label_zh,
                "keys": keys,
                "sort_order": index,
            }
            for index, (slug, label_zh, keys) in enumerate(goals, start=1)
        ],
    }
