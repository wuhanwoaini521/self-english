import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException

os.environ.setdefault("SELF_ENGLISH_LEARNING_DB", "")


class LearningDbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SELF_ENGLISH_LEARNING_DB"] = str(Path(self.tmp.name) / "learning.db")
        os.environ["SELF_ENGLISH_AI_PROVIDER"] = "off"
        from app import learning, seed

        self.learning = learning
        self.seed = seed
        self.learning.init()

    def tearDown(self):
        try:
            self.tmp.cleanup()
        except OSError:
            pass

    def test_seed_is_idempotent(self):
        self.learning.init()
        with self.learning.connect() as connection:
            lessons = connection.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
            deadline = connection.execute(
                "SELECT phonetic, note_zh, example_en FROM expressions WHERE id = ?",
                ("hw.deadline",),
            ).fetchone()
        self.assertEqual(lessons, len(self.seed.LESSONS))
        self.assertEqual(deadline["phonetic"], "/ˈdedlaɪn/")
        self.assertIn("截止", deadline["note_zh"])
        self.assertTrue(deadline["example_en"])
        first_book = self.learning.lesson_payload(self.seed.FIRST_LESSON_ID)
        self.assertEqual(first_book["id"], "cet4-01-drop-course")
        grammar = next(item for item in first_book["expressions"] if item["id"] == "hw.would-rather")
        self.assertEqual(grammar["kind"], "grammar")
        self.assertEqual(grammar["teach"]["ask"], "怎么说「宁可」")
        self.assertGreaterEqual(len(first_book["questions"]), 4)
        self.assertEqual(len([item for item in self.seed.LESSONS if item["month"] == 1]), 6)

        payload = self.learning.lesson_payload(self.seed.LESSON_ID)
        first = payload["dialogue"][0]
        self.assertIn("syllabus", first["english"])
        kinds = {item["headword"]: item["kind"] for para in payload["passage"]["paragraphs"] for item in para["marks"]}
        self.assertEqual(kinds["deadline"], "vocab")
        self.assertEqual(kinds["would rather"], "grammar")

    def test_known_mark_hides_until_due(self):
        first, second = self.seed.LESSONS[0], self.seed.LESSONS[1]
        marks = [
            mark["headword"]
            for para in self.learning.reading_payload(first["id"])["passage"]["paragraphs"]
            for mark in para["marks"]
        ]
        self.assertIn("deadline", marks)
        saved = self.learning.mark_headword("deadline", "会")
        self.assertEqual(saved["interval_days"], 14)
        hidden = [
            mark["headword"]
            for para in self.learning.reading_payload(second["id"])["passage"]["paragraphs"]
            for mark in para["marks"]
        ]
        self.assertNotIn("deadline", hidden)
        queue = {item["headword_id"] for item in self.learning.vocab_queue()["items"]}
        self.assertNotIn("deadline", queue)
        with self.learning.connect() as db:
            db.execute("UPDATE headword_state SET due_at = ? WHERE headword_id = ?", ("2020-01-01T00:00:00Z", "deadline"))
            db.execute("UPDATE review_cards SET due_at = ? WHERE expression_id = ?", ("2020-01-01T00:00:00Z", "hw.deadline"))
        leaked = [
            mark["headword"]
            for para in self.learning.reading_payload(second["id"])["passage"]["paragraphs"]
            for mark in para["marks"]
        ]
        self.assertIn("deadline", leaked)
        self.assertIn("deadline", {item["headword_id"] for item in self.learning.vocab_queue()["items"]})

    def test_cet4_readings_are_long_articles(self):
        first = self.learning.reading_payload(self.seed.FIRST_LESSON_ID)
        self.assertEqual(first["level"], "CET-4")
        self.assertGreaterEqual(len(self.seed.LESSONS), 6)
        total_marks = 0
        for lesson in self.seed.LESSONS:
            payload = self.learning.reading_payload(lesson["id"])
            passage = payload["passage"]
            words = sum(len(para["english"].split()) for para in passage["paragraphs"])
            self.assertGreaterEqual(words, 160, lesson["id"])
            marks = [mark for para in passage["paragraphs"] for mark in para["marks"]]
            total_marks += len(marks)
            kinds = {mark["kind"] for mark in marks}
            self.assertTrue({"vocab", "grammar", "phrase"} <= kinds, lesson["id"])
        first_marks = [
            mark
            for para in first["passage"]["paragraphs"]
            for mark in para["marks"]
        ]
        self.assertGreaterEqual(len(first_marks), 50)
        self.assertIn("phrase", {mark["kind"] for mark in first_marks})
        heads = {mark["headword"] for mark in first_marks}
        self.assertTrue({"term", "neat", "timetable"} <= heads)
        listed = self.learning.readings_list()["items"]
        self.assertEqual(len(listed), len(self.seed.LESSONS))
        self.assertEqual(listed[0]["id"], self.seed.FIRST_LESSON_ID)
        self.assertGreater(listed[0]["word_count"], 0)
        self.assertEqual(len(self.learning.talk_topics()["items"]), len(self.seed.LESSONS))
        queue = self.learning.vocab_queue()["items"]
        self.assertGreater(len(queue), 20)
        self.assertIn("deadline", {item["headword_id"] for item in queue})
        self.assertTrue(all(item["status"] == "unknown" for item in queue))

    def test_grammar_teach_is_structured(self):
        first_book = self.learning.lesson_payload(self.seed.FIRST_LESSON_ID)
        grammar = next(item for item in first_book["expressions"] if item["id"] == "hw.would-rather")
        teach = grammar["teach"]
        self.assertEqual(grammar["kind"], "grammar")
        self.assertEqual(teach["ask"], "怎么说「宁可」")
        self.assertIn("would rather", teach["ask_en"])
        self.assertTrue(teach["replies"])
        self.assertTrue(teach["swaps"])
        self.assertTrue(teach["why_title"])
        self.assertTrue(teach["why_lines"])
        word = next(item for item in first_book["expressions"] if item["kind"] == "word")
        self.assertEqual(word["teach"], {})

    def test_teach_json_upgrade_keeps_progress(self):
        lesson = self.seed.FIRST_LESSON_ID
        self.learning.save_progress(lesson, {"step": "vocab", "vocab_index": 1})
        with self.learning.connect() as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(expressions)")}
            if "teach_json" in columns:
                db.execute("ALTER TABLE expressions DROP COLUMN teach_json")
            db.execute("UPDATE schema_version SET version = 6")
        self.learning.init()
        payload = self.learning.lesson_payload(lesson)
        self.assertEqual(payload["progress"]["step"], "vocab")
        self.assertEqual(payload["progress"]["vocab_index"], 1)
        grammar = next(item for item in payload["expressions"] if item["id"] == "hw.would-rather")
        self.assertEqual(grammar["teach"]["ask"], "怎么说「宁可」")

    def test_vocab_phase_done_stays_on_vocab(self):
        saved = self.learning.save_progress(
            self.seed.FIRST_LESSON_ID,
            {"step": "vocab", "vocab_index": 4, "vocab_phase": "done"},
        )
        self.assertEqual(saved["step"], "vocab")
        self.assertEqual(saved["vocab_phase"], "done")
        today = self.learning.today()
        self.assertEqual(today["page"], "reading")
        self.assertEqual(today["action"], "继续阅读")
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as raised:
            self.learning.save_progress(self.seed.FIRST_LESSON_ID, {"step": "vocab", "vocab_phase": "nope"})
        self.assertEqual(raised.exception.status_code, 400)

    def test_vocab_starts_in_learn_phase(self):
        today = self.learning.today()
        self.assertEqual(today["progress"]["vocab_phase"], "learn")
        payload = self.learning.lesson_payload(self.seed.LESSON_ID)
        first = next(item for item in payload["expressions"] if item["id"] == "hw.would-rather")
        self.assertEqual(first["english"], "would rather")
        self.assertTrue(first["note_zh"])
        task = payload["task"]
        self.assertTrue(task["brief_zh"])
        self.assertTrue(task["hear_label_zh"])
        self.assertEqual(task["submit_label"], "提交我的话")

    def test_duplicate_review_card(self):
        first = self.learning.add_review("hw.deadline")
        second = self.learning.add_review("hw.deadline")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["due_at"], second["due_at"])
        with self.learning.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM review_cards").fetchone()[0]
        self.assertEqual(count, 1)

    def test_grade_sets_due_date(self):
        self.learning.add_review("hw.elective")
        card = self.learning.grade_review("hw.elective", "remembered")
        self.assertEqual(card["box"], 2)
        self.assertEqual(card["interval_days"], 3)
        self.assertTrue(card["due_at"] > card["updated_at"] or card["due_at"] >= card["updated_at"])

    def test_grade_creates_missing_card(self):
        card = self.learning.grade_review("hw.deadline", "forgot")
        self.assertEqual(card["box"], 1)
        self.assertEqual(card["interval_days"], 1)
        self.assertEqual(card["last_result"], "forgot")
        with self.learning.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM review_cards").fetchone()[0]
        self.assertEqual(count, 1)

    def test_grade_unknown_expression(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as raised:
            self.learning.grade_review("missing-expression", "remembered")
        self.assertEqual(raised.exception.status_code, 404)

    def test_progress_conflict(self):
        saved = self.learning.save_progress(self.seed.LESSON_ID, {"step": "vocab", "vocab_index": 1})
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as raised:
            self.learning.save_progress(
                self.seed.LESSON_ID,
                {"step": "listen", "expected_updated_at": "1999-01-01T00:00:00Z"},
            )
        self.assertEqual(raised.exception.status_code, 409)
        with self.assertRaises(HTTPException) as stale:
            self.learning.save_progress(self.seed.LESSON_ID, {"step": "talk"})
        self.assertEqual(stale.exception.status_code, 409)
        again = self.learning.save_progress(
            self.seed.LESSON_ID,
            {"step": "listen", "expected_updated_at": saved["updated_at"]},
        )
        self.assertEqual(again["step"], "listen")

    def test_catalog_rebuild_does_not_touch_learning(self):
        self.learning.add_review("hw.syllabus")
        catalog = Path(self.tmp.name) / "app.db"
        connection = sqlite3.connect(catalog)
        connection.execute("CREATE TABLE words (headword TEXT)")
        connection.execute("INSERT INTO words VALUES ('gone')")
        connection.commit()
        connection.close()
        catalog.unlink()
        with self.learning.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM review_cards").fetchone()[0]
            lesson = db.execute(
                "SELECT title_zh FROM lessons WHERE id = ?",
                (self.seed.LESSON_ID,),
            ).fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(lesson, "这门选修该不该退")

    def test_parallel_revision_and_revisit(self):
        lesson = self.seed.LESSON_ID
        def save(_):
            try:
                return self.learning.save_progress(lesson, {"expected_revision": 0, "step": "done"})["revision"]
            except HTTPException as exc:
                return exc.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save, range(2))), [1, 409])
        saved = self.learning.save_progress(lesson, {"expected_revision": 1, "step": "listen", "question_results": {"q": 1}})
        self.assertEqual((saved["revision"], saved["step"], saved["question_results"]), (2, "done", {"q": 1}))
        self.assertNotEqual(self.learning.today()["lesson_id"], lesson)

    def test_v4_upgrade_preserves_progress(self):
        lesson = self.seed.LESSON_ID
        self.learning.save_progress(lesson, {"step": "talk", "vocab_index": 2})
        with self.learning.connect() as db:
            db.execute("ALTER TABLE lesson_progress DROP COLUMN revision")
            db.execute("DROP INDEX review_operation")
            db.execute("ALTER TABLE review_log DROP COLUMN operation_id")
            db.execute("UPDATE schema_version SET version = 4")
        self.learning.init()
        saved = self.learning.lesson_payload(lesson)["progress"]
        self.assertEqual((saved["step"], saved["vocab_index"], saved["revision"]), ("talk", 2, 1))

    def test_retry_grade_and_progress_are_atomic(self):
        lesson = self.seed.LESSON_ID
        expression = "hw.deadline"
        payload = {"expected_revision": 0, "vocab_index": 1, "vocab_phase": "recall"}
        for _ in range(2):
            saved = self.learning.grade_review(expression, "remembered", "same-action", payload)
            self.assertEqual((saved["interval_days"], saved["progress"]["revision"]), (3, 1))
        with self.assertRaises(HTTPException):
            self.learning.grade_review(expression, "remembered", "stale", payload)
        self.assertEqual(len(self.learning.review_log()), 1)
        self.assertEqual(self.learning.lesson_payload(lesson)["progress"]["vocab_index"], 1)

    def test_due_card_retry_across_devices(self):
        expression = "hw.deadline"
        due = self.learning.add_review(expression)["due_at"]
        for _ in range(2):
            saved = self.learning.grade_review(expression, "remembered", "phone", expected_due=due)
            self.assertEqual(saved["interval_days"], 3)
        with self.assertRaises(HTTPException) as stale:
            self.learning.grade_review(expression, "remembered", "desktop", expected_due=due)
        self.assertEqual(stale.exception.status_code, 409)
        self.assertEqual(len(self.learning.review_log()), 1)

    def test_stale_dialogue_preserves_answer(self):
        lesson = self.seed.LESSON_ID
        original = "I would rather drop the elective before the deadline."
        self.learning.submit_order(lesson, original, 0)
        with self.assertRaises(HTTPException) as stale:
            self.learning.submit_order(lesson, "Water.", 0)
        self.assertEqual(stale.exception.status_code, 409)
        self.assertEqual(self.learning.dialogue_state(lesson)["order_text"], original)

    def test_staged_catalog_failure_and_success(self):
        from scripts import build_catalog as build
        target = Path(self.tmp.name) / "app.db"
        self.learning.add_review("hw.deadline")
        with patch.object(build, "DB", target), patch.object(build, "load_spoken", return_value={}), \
             patch.object(build, "load_cards", return_value=[]), patch.object(build, "load_gloss", return_value={}), \
             patch.object(build, "load_tatoeba", return_value=[]):
            build.main()
            before = target.read_bytes()
            with patch.object(build, "write_catalog", side_effect=RuntimeError("interrupted")), self.assertRaises(RuntimeError):
                build.main()
            self.assertEqual(target.read_bytes(), before)
            build.main()
        with closing(sqlite3.connect(target)) as db:
            self.assertGreater(db.execute("SELECT count(*) FROM sentences").fetchone()[0], 0)
        self.assertEqual(self.learning.progress_overview()["card_count"], 1)

    def test_today_starts_with_cafe(self):
        today = self.learning.today()
        first = self.seed.LESSONS[0]
        self.assertEqual(today["lesson_id"], first["id"])
        self.assertEqual(today["title_zh"], first["title_zh"])
        self.assertEqual(today["lesson_no"], 1)
        self.assertEqual(today["lesson_total"], len(self.seed.LESSONS))
        self.assertEqual(today["action"], "去阅读")
        self.assertTrue(today["has_next"])
        self.assertEqual(today["lessons"][0]["status"], "current")
        self.assertTrue(all(item["status"] == "unread" for item in today["lessons"][1:]))

    def test_today_recap_action_finishes_lesson(self):
        self.learning.save_progress(self.seed.FIRST_LESSON_ID, {"step": "recap"})
        today = self.learning.today()
        self.assertEqual(today["action"], "继续阅读")
        self.assertEqual(today["page"], "reading")
        self.assertTrue(today["has_next"])

    def test_today_advances_after_cafe_done(self):
        first, second = self.seed.LESSONS[0], self.seed.LESSONS[1]
        self.learning.save_progress(first["id"], {"step": "done"})
        today = self.learning.today()
        self.assertEqual(today["lesson_id"], second["id"])
        self.assertEqual(today["title_zh"], second["title_zh"])
        self.assertEqual(today["action"], "去阅读")
        self.assertTrue(today["has_next"])
        self.assertEqual(today["lessons"][0]["status"], "done")
        self.assertEqual(today["lessons"][1]["status"], "current")
        overview = self.learning.progress_overview()
        self.assertEqual([item["id"] for item in overview["completed_lessons"]], [first["id"]])
        month1 = next(item for item in overview["roadmap"] if item["id"] == "m1")
        self.assertEqual(month1["status"], "in_progress")

    def test_month1_done_after_all_cet4_lessons(self):
        month1_lessons = [lesson for lesson in self.seed.LESSONS if lesson["month"] == 1]
        for lesson in month1_lessons:
            self.learning.save_progress(lesson["id"], {"step": "done"})
        today = self.learning.today()
        self.assertEqual(today["action"], "再看阅读")
        self.assertFalse(today["has_next"])
        overview = self.learning.progress_overview()
        self.assertEqual(len(overview["completed_lessons"]), len(month1_lessons))
        month1 = next(item for item in overview["roadmap"] if item["id"] == "m1")
        month2 = next(item for item in overview["roadmap"] if item["id"] == "m2")
        self.assertEqual(month1["status"], "done")
        self.assertEqual(month1["label"], "已完成")
        self.assertEqual(month2["status"], "pending")
        self.assertEqual(overview["month_done"], 1)
        self.assertEqual(overview["lesson_total"], len(self.seed.LESSONS))
        self.assertEqual(len(overview["lessons"]), len(self.seed.LESSONS))

    def test_all_lessons_done(self):
        for lesson in self.seed.LESSONS:
            self.learning.save_progress(lesson["id"], {"step": "done"})
        today = self.learning.today()
        self.assertEqual(today["lesson_id"], self.seed.LESSONS[-1]["id"])
        self.assertEqual(today["action"], "再看阅读")
        self.assertFalse(today["has_next"])
        self.assertTrue(all(item["status"] == "done" for item in today["lessons"]))
        overview = self.learning.progress_overview()
        self.assertEqual(len(overview["completed_lessons"]), len(self.seed.LESSONS))
        month1 = next(item for item in overview["roadmap"] if item["id"] == "m1")
        month2 = next(item for item in overview["roadmap"] if item["id"] == "m2")
        self.assertEqual(month1["status"], "done")
        self.assertEqual(month2["status"], "pending")
        self.assertEqual(overview["month_done"], 1)

    def test_overview_charts_follow_reviews(self):
        empty = self.learning.progress_overview()
        self.assertEqual([item["count"] for item in empty["boxes"]], [0, 0, 0, 0])
        self.assertEqual([item["count"] for item in empty["results"]], [0, 0, 0])
        self.learning.grade_review("hw.deadline", "remembered")
        self.learning.grade_review("hw.elective", "forgot")
        overview = self.learning.progress_overview()
        boxes = {item["box"]: item["count"] for item in overview["boxes"]}
        results = {item["id"]: item["count"] for item in overview["results"]}
        self.assertEqual(boxes[1], 1)
        self.assertEqual(boxes[2], 1)
        self.assertEqual(results["remembered"], 1)
        self.assertEqual(results["forgot"], 1)


class MarkTest(unittest.TestCase):
    def test_join_parts_keeps_sentence(self):
        from app.seed import grammar, join_parts, vocab

        english, marks = join_parts(
            (
                grammar("I'd like", phonetic="/aɪd laɪk/", pos="动词短语", sense_zh="我想要"),
                " a ",
                vocab("latte", phonetic="/ˈlɑː.teɪ/", pos="名词", sense_zh="拿铁咖啡"),
                ", please.",
            )
        )
        self.assertEqual(english, "I'd like a latte, please.")
        self.assertEqual(marks[0]["kind"], "grammar")
        self.assertEqual(marks[1]["kind"], "vocab")
        self.assertEqual(english[marks[1]["start"] : marks[1]["end"]], "latte")


class DialogueTest(unittest.TestCase):
    def test_order_completes_goals(self):
        from app.dialogue import completed_goal_ids
        from app.seed import GOALS

        done = completed_goal_ids(
            "I would rather drop the elective before the deadline. The workload is too heavy.",
            GOALS,
        )
        self.assertEqual(len(done), 3)

    def test_missing_coffee(self):
        from app.dialogue import completed_goal_ids
        from app.seed import GOALS

        done = completed_goal_ids("Water, please. Thank you.", GOALS)
        self.assertEqual(done, [])

    def test_greetings_goals(self):
        from app.dialogue import completed_goal_ids
        from app.seed import GREETINGS

        done = completed_goal_ids(
            "Hello. How are you? I'm fine. Nice to meet you.",
            GREETINGS["goals"],
        )
        self.assertEqual(len(done), 3)

    def test_hint_is_your_line(self):
        from app.dialogue import hint_for
        from app.seed import CAFE_ORDER

        first = hint_for(CAFE_ORDER["dialogue"], 0)
        self.assertEqual(first["english"], "I would like a cup of coffee, please.")
        second = hint_for(CAFE_ORDER["dialogue"], 1)
        self.assertEqual(second["english"], "Thank you.")
        self.assertIsNone(hint_for(CAFE_ORDER["dialogue"], 2))

    def test_say_again_goals(self):
        from app.dialogue import completed_goal_ids
        from app.seed import SAY_AGAIN

        done = completed_goal_ids(
            "Sorry. I don't understand. Please say that again.",
            SAY_AGAIN["goals"],
        )
        self.assertEqual(len(done), 3)

    def test_directions_goals(self):
        from app.dialogue import completed_goal_ids
        from app.seed import ASK_DIRECTIONS

        done = completed_goal_ids(
            "Excuse me. Where is the station? Thank you.",
            ASK_DIRECTIONS["goals"],
        )
        self.assertEqual(len(done), 3)

    def test_book1_first_lesson_goals(self):
        from app.dialogue import completed_goal_ids
        from app.seed import FIRST_LESSON

        done = completed_goal_ids(
            "I will drop the elective before the deadline. The workload is too heavy.",
            FIRST_LESSON["goals"],
        )
        self.assertEqual(len(done), 3)

    def test_bus_goals(self):
        from app.dialogue import completed_goal_ids
        from app.seed import TAKE_BUS

        done = completed_goal_ids(
            "I want to go to the station. A ticket, please. How much is it?",
            TAKE_BUS["goals"],
        )
        self.assertEqual(len(done), 3)


class SrsTest(unittest.TestCase):
    def test_rules(self):
        from datetime import datetime, timezone

        from app.srs import schedule

        now = datetime(2026, 11, 25, 8, 0, tzinfo=timezone.utc)
        box, days, due = schedule(1, "forgot", now)
        self.assertEqual((box, days), (1, 1))
        box, days, due = schedule(2, "fuzzy", now)
        self.assertEqual((box, days), (2, 2))
        box, days, due = schedule(1, "remembered", now)
        self.assertEqual((box, days), (2, 3))
        self.assertEqual(due, "2026-11-28T08:00:00Z")

    def test_known_mark_waits_weeks(self):
        from datetime import datetime, timezone

        from app.srs import schedule_mark

        now = datetime(2026, 11, 25, 8, 0, tzinfo=timezone.utc)
        box, days, due = schedule_mark(0, "known", prior=None, now=now)
        self.assertEqual((box, days), (1, 14))
        self.assertEqual(due, "2026-12-09T08:00:00Z")
        box, days, due = schedule_mark(1, "known", prior="known", now=now)
        self.assertEqual((box, days), (2, 30))
        box, days, due = schedule_mark(2, "known", prior="known", now=now)
        self.assertEqual((box, days), (3, 60))
        box, days, due = schedule_mark(1, "unknown", prior="known", now=now)
        self.assertEqual((box, days), (1, 1))
        box, days, due = schedule_mark(3, "known", prior="unknown", now=now)
        self.assertEqual((box, days), (1, 14))


if __name__ == "__main__":
    unittest.main()
