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
            expressions = connection.execute("SELECT COUNT(*) FROM expressions").fetchone()[0]
            coffee = connection.execute(
                "SELECT phonetic, note_zh, example_en FROM expressions WHERE id = ?",
                (f"{self.seed.LESSON_ID}.coffee",),
            ).fetchone()
        self.assertEqual(lessons, len(self.seed.LESSONS))
        self.assertEqual(
            expressions,
            sum(len(lesson["expressions"]) for lesson in self.seed.LESSONS),
        )
        self.assertEqual(coffee["phonetic"], "/ˈkɔːfi/")
        self.assertIn("咖啡", coffee["note_zh"])
        self.assertTrue(coffee["example_en"])
        first_book = self.learning.lesson_payload(self.seed.FIRST_LESSON_ID)
        self.assertEqual(first_book["id"], "book1-01-excuse-me")
        self.assertEqual(first_book["expressions"][0]["kind"], "grammar")
        self.assertIn("句型", first_book["expressions"][0]["note_zh"])
        self.assertGreaterEqual(len(first_book["questions"]), 4)
        self.assertEqual(len([item for item in self.seed.LESSONS if item["month"] == 1]), 12)

        payload = self.learning.lesson_payload(self.seed.LESSON_ID)
        first = payload["dialogue"][0]
        self.assertEqual(first["english"], "Hello. What would you like?")
        self.assertEqual(first["marks"][0]["kind"], "grammar")
        self.assertEqual(first["marks"][0]["headword"], "would you like")
        latte = payload["passage"]["paragraphs"][0]
        self.assertIn("latte", latte["english"])
        kinds = {item["headword"]: item["kind"] for item in latte["marks"]}
        self.assertEqual(kinds["latte"], "vocab")
        self.assertEqual(kinds["I'd like"], "grammar")
        self.assertEqual(
            next(item for item in latte["marks"] if item["headword"] == "latte")["sense_zh"],
            "拿铁咖啡",
        )

    def test_vocab_phase_done_stays_on_vocab(self):
        saved = self.learning.save_progress(
            self.seed.FIRST_LESSON_ID,
            {"step": "vocab", "vocab_index": 4, "vocab_phase": "done"},
        )
        self.assertEqual(saved["step"], "vocab")
        self.assertEqual(saved["vocab_phase"], "done")
        today = self.learning.today()
        self.assertEqual(today["page"], "vocab")
        self.assertEqual(today["action"], "继续：词汇")
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as raised:
            self.learning.save_progress(self.seed.FIRST_LESSON_ID, {"step": "vocab", "vocab_phase": "nope"})
        self.assertEqual(raised.exception.status_code, 400)

    def test_vocab_starts_in_learn_phase(self):
        today = self.learning.today()
        self.assertEqual(today["progress"]["vocab_phase"], "learn")
        payload = self.learning.lesson_payload(self.seed.LESSON_ID)
        coffee = payload["expressions"][0]
        self.assertEqual(coffee["english"], "coffee")
        self.assertEqual(coffee["mark"], "☕")
        self.assertTrue(coffee["note_zh"])
        task = payload["task"]
        self.assertTrue(task["brief_zh"])
        self.assertTrue(task["hear_label_zh"])
        self.assertEqual(task["submit_label"], "提交我的话")

    def test_duplicate_review_card(self):
        first = self.learning.add_review(f"{self.seed.LESSON_ID}.coffee")
        second = self.learning.add_review(f"{self.seed.LESSON_ID}.coffee")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["due_at"], second["due_at"])
        with self.learning.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM review_cards").fetchone()[0]
        self.assertEqual(count, 1)

    def test_grade_sets_due_date(self):
        self.learning.add_review(f"{self.seed.LESSON_ID}.please")
        card = self.learning.grade_review(f"{self.seed.LESSON_ID}.please", "remembered")
        self.assertEqual(card["box"], 2)
        self.assertEqual(card["interval_days"], 3)
        self.assertTrue(card["due_at"] > card["updated_at"] or card["due_at"] >= card["updated_at"])

    def test_grade_creates_missing_card(self):
        card = self.learning.grade_review(f"{self.seed.LESSON_ID}.coffee", "forgot")
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
        self.learning.add_review(f"{self.seed.LESSON_ID}.thank-you")
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
        self.assertEqual(lesson, "咖啡店点餐")

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
        expression = lesson + ".coffee"
        payload = {"expected_revision": 0, "vocab_index": 1, "vocab_phase": "recall"}
        for _ in range(2):
            saved = self.learning.grade_review(expression, "remembered", "same-action", payload)
            self.assertEqual((saved["interval_days"], saved["progress"]["revision"]), (3, 1))
        with self.assertRaises(HTTPException):
            self.learning.grade_review(expression, "remembered", "stale", payload)
        self.assertEqual(len(self.learning.review_log()), 1)
        self.assertEqual(self.learning.lesson_payload(lesson)["progress"]["vocab_index"], 1)

    def test_due_card_retry_across_devices(self):
        expression = self.seed.LESSON_ID + ".coffee"
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
        original = "A coffee, please. Thank you."
        self.learning.submit_order(lesson, original, 0)
        with self.assertRaises(HTTPException) as stale:
            self.learning.submit_order(lesson, "Water.", 0)
        self.assertEqual(stale.exception.status_code, 409)
        self.assertEqual(self.learning.dialogue_state(lesson)["order_text"], original)

    def test_staged_catalog_failure_and_success(self):
        from scripts import build_catalog as build
        target = Path(self.tmp.name) / "app.db"
        self.learning.add_review(self.seed.LESSON_ID + ".coffee")
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
        self.assertEqual(today["action"], "开始第一课")
        self.assertTrue(today["has_next"])
        self.assertEqual(today["lessons"][0]["status"], "current")
        self.assertTrue(all(item["status"] == "upcoming" for item in today["lessons"][1:]))

    def test_today_recap_action_finishes_lesson(self):
        self.learning.save_progress(self.seed.FIRST_LESSON_ID, {"step": "recap"})
        today = self.learning.today()
        self.assertEqual(today["action"], "去复盘")
        self.assertEqual(today["page"], "today")
        self.assertTrue(today["has_next"])

    def test_today_advances_after_cafe_done(self):
        first, second = self.seed.LESSONS[0], self.seed.LESSONS[1]
        self.learning.save_progress(first["id"], {"step": "done"})
        today = self.learning.today()
        self.assertEqual(today["lesson_id"], second["id"])
        self.assertEqual(today["title_zh"], second["title_zh"])
        self.assertEqual(today["action"], "开始第 2 课")
        self.assertTrue(today["has_next"])
        self.assertEqual(today["lessons"][0]["status"], "done")
        self.assertEqual(today["lessons"][1]["status"], "current")
        overview = self.learning.progress_overview()
        self.assertEqual([item["id"] for item in overview["completed_lessons"]], [first["id"]])
        month1 = next(item for item in overview["roadmap"] if item["id"] == "m1")
        self.assertEqual(month1["status"], "in_progress")

    def test_month1_done_after_three_lessons(self):
        month1_lessons = [lesson for lesson in self.seed.LESSONS if lesson["month"] == 1]
        for lesson in month1_lessons:
            self.learning.save_progress(lesson["id"], {"step": "done"})
        today = self.learning.today()
        self.assertEqual(today["lesson_id"], "cafe-order-a1")
        self.assertEqual(today["title_zh"], "咖啡店点餐")
        self.assertEqual(today["action"], f"开始第 {len(month1_lessons) + 1} 课")
        self.assertTrue(today["has_next"])
        self.assertEqual(today["lessons"][len(month1_lessons)]["status"], "current")
        overview = self.learning.progress_overview()
        self.assertEqual(len(overview["completed_lessons"]), len(month1_lessons))
        month1 = next(item for item in overview["roadmap"] if item["id"] == "m1")
        month2 = next(item for item in overview["roadmap"] if item["id"] == "m2")
        self.assertEqual(month1["status"], "done")
        self.assertEqual(month1["label"], "已完成")
        self.assertEqual(month2["status"], "in_progress")
        self.assertEqual(overview["month_done"], 1)
        self.assertEqual(overview["lesson_total"], len(self.seed.LESSONS))
        self.assertEqual(len(overview["lessons"]), len(self.seed.LESSONS))

    def test_month2_done_after_five_lessons(self):
        for lesson in self.seed.LESSONS:
            if lesson["month"] <= 2:
                self.learning.save_progress(lesson["id"], {"step": "done"})
        today = self.learning.today()
        self.assertEqual(today["lesson_id"], "asking-directions-a1")
        self.assertEqual(today["title_zh"], "问路")
        self.assertTrue(today["has_next"])
        overview = self.learning.progress_overview()
        month2 = next(item for item in overview["roadmap"] if item["id"] == "m2")
        month3 = next(item for item in overview["roadmap"] if item["id"] == "m3")
        self.assertEqual(month2["status"], "done")
        self.assertEqual(month3["status"], "in_progress")
        self.assertEqual(overview["month_done"], 2)

    def test_all_lessons_done(self):
        for lesson in self.seed.LESSONS:
            self.learning.save_progress(lesson["id"], {"step": "done"})
        today = self.learning.today()
        self.assertEqual(today["lesson_id"], "taking-bus-a1")
        self.assertEqual(today["action"], "再看这一课")
        self.assertFalse(today["has_next"])
        self.assertTrue(all(item["status"] == "done" for item in today["lessons"]))
        overview = self.learning.progress_overview()
        self.assertEqual(len(overview["completed_lessons"]), len(self.seed.LESSONS))
        month3 = next(item for item in overview["roadmap"] if item["id"] == "m3")
        month4 = next(item for item in overview["roadmap"] if item["id"] == "m4")
        self.assertEqual(month3["status"], "done")
        self.assertEqual(month4["status"], "pending")
        self.assertEqual(overview["month_done"], 3)

    def test_overview_charts_follow_reviews(self):
        empty = self.learning.progress_overview()
        self.assertEqual([item["count"] for item in empty["boxes"]], [0, 0, 0, 0])
        self.assertEqual([item["count"] for item in empty["results"]], [0, 0, 0])
        self.learning.grade_review(f"{self.seed.LESSON_ID}.coffee", "remembered")
        self.learning.grade_review(f"{self.seed.LESSON_ID}.please", "forgot")
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

        done = completed_goal_ids("I would like a cup of coffee, please. Thank you.", GOALS)
        self.assertEqual(len(done), 3)

    def test_missing_coffee(self):
        from app.dialogue import completed_goal_ids
        from app.seed import GOALS

        done = completed_goal_ids("Water, please. Thank you.", GOALS)
        self.assertNotIn("cafe-order-a1.goal-drink", done)

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
            "Excuse me. Is this your phone? Thank you.",
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


if __name__ == "__main__":
    unittest.main()
