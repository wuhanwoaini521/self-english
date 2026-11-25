import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SELF_ENGLISH_LEARNING_DB", "")


class LearningDbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SELF_ENGLISH_LEARNING_DB"] = str(Path(self.tmp.name) / "learning.db")
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
        self.assertEqual(lessons, 3)
        self.assertEqual(expressions, 15)
        self.assertEqual(coffee["phonetic"], "/ˈkɔːfi/")
        self.assertIn("咖啡", coffee["note_zh"])
        self.assertTrue(coffee["example_en"])

    def test_vocab_phase_done_stays_on_vocab(self):
        saved = self.learning.save_progress(
            self.seed.LESSON_ID,
            {"step": "vocab", "vocab_index": 4, "vocab_phase": "done"},
        )
        self.assertEqual(saved["step"], "vocab")
        self.assertEqual(saved["vocab_phase"], "done")
        today = self.learning.today()
        self.assertEqual(today["page"], "vocab")
        self.assertEqual(today["action"], "继续：词汇")
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as raised:
            self.learning.save_progress(self.seed.LESSON_ID, {"step": "vocab", "vocab_phase": "nope"})
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
            lesson = db.execute("SELECT title_zh FROM lessons").fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(lesson, "咖啡店点餐")

    def test_today_starts_with_cafe(self):
        today = self.learning.today()
        self.assertEqual(today["lesson_id"], "cafe-order-a1")
        self.assertEqual(today["lesson_no"], 1)
        self.assertEqual(today["lesson_total"], 3)
        self.assertEqual(today["action"], "开始第一课")
        self.assertTrue(today["has_next"])
        self.assertEqual([item["status"] for item in today["lessons"]], ["current", "upcoming", "upcoming"])

    def test_today_recap_action_finishes_lesson(self):
        self.learning.save_progress(self.seed.LESSON_ID, {"step": "recap"})
        today = self.learning.today()
        self.assertEqual(today["action"], "去复盘")
        self.assertEqual(today["page"], "today")
        self.assertTrue(today["has_next"])

    def test_today_advances_after_cafe_done(self):
        self.learning.save_progress(self.seed.LESSON_ID, {"step": "done"})
        today = self.learning.today()
        self.assertEqual(today["lesson_id"], "greetings-a1")
        self.assertEqual(today["title_zh"], "问候")
        self.assertEqual(today["action"], "开始第 2 课")
        self.assertTrue(today["has_next"])
        self.assertEqual([item["status"] for item in today["lessons"]], ["done", "current", "upcoming"])
        overview = self.learning.progress_overview()
        self.assertEqual([item["id"] for item in overview["completed_lessons"]], ["cafe-order-a1"])
        month1 = next(item for item in overview["roadmap"] if item["id"] == "m1")
        self.assertEqual(month1["status"], "in_progress")

    def test_month1_done_after_three_lessons(self):
        for lesson in self.seed.LESSONS:
            self.learning.save_progress(lesson["id"], {"step": "done"})
        today = self.learning.today()
        self.assertEqual(today["lesson_id"], "say-again-a1")
        self.assertEqual(today["action"], "再看这一课")
        self.assertFalse(today["has_next"])
        self.assertTrue(all(item["status"] == "done" for item in today["lessons"]))
        overview = self.learning.progress_overview()
        self.assertEqual(len(overview["completed_lessons"]), 3)
        month1 = next(item for item in overview["roadmap"] if item["id"] == "m1")
        self.assertEqual(month1["status"], "done")
        self.assertEqual(month1["label"], "已完成")
        self.assertEqual(overview["month_done"], 1)
        self.assertEqual(overview["lesson_total"], 3)
        self.assertEqual(len(overview["lessons"]), 3)
        self.assertTrue(all(item["step"] == "done" for item in overview["lessons"]))

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
