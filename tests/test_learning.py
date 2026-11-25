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
        self.assertEqual(lessons, 1)
        self.assertEqual(expressions, 5)

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
