import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


class AiSettingsTest(unittest.TestCase):
    def setUp(self):
        self._saved = {
            key: os.environ.get(key)
            for key in (
                "SELF_ENGLISH_AI_PROVIDER",
                "SELF_ENGLISH_DEEPSEEK_API_KEY",
                "DEEPSEEK_API_KEY",
                "SELF_ENGLISH_VOICE_PROVIDER",
                "SELF_ENGLISH_VOICE_API_KEY",
            )
        }

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_status_hides_keys_and_voice_stays_closed(self):
        os.environ["SELF_ENGLISH_AI_PROVIDER"] = "deepseek"
        os.environ["SELF_ENGLISH_DEEPSEEK_API_KEY"] = "sk-test-secret"
        from app import ai

        payload = ai.status()
        blob = json.dumps(payload)
        self.assertNotIn("sk-test-secret", blob)
        self.assertTrue(payload["chat"]["available"])
        self.assertEqual(payload["chat"]["provider"], "deepseek")
        self.assertFalse(payload["voice"]["available"])
        self.assertIn("录音", payload["voice"]["detail_zh"])

    def test_off_provider_stays_script(self):
        os.environ["SELF_ENGLISH_AI_PROVIDER"] = "off"
        os.environ["SELF_ENGLISH_DEEPSEEK_API_KEY"] = "sk-test-secret"
        from app.ai.chat import chat_available

        self.assertFalse(chat_available())


class DeepSeekTalkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SELF_ENGLISH_LEARNING_DB"] = str(Path(self.tmp.name) / "learning.db")
        os.environ["SELF_ENGLISH_AI_PROVIDER"] = "deepseek"
        os.environ["SELF_ENGLISH_DEEPSEEK_API_KEY"] = "sk-test-secret"
        from app import learning, seed

        self.learning = learning
        self.seed = seed
        self.learning.init()

    def tearDown(self):
        os.environ["SELF_ENGLISH_AI_PROVIDER"] = "off"
        os.environ.pop("SELF_ENGLISH_DEEPSEEK_API_KEY", None)
        try:
            self.tmp.cleanup()
        except OSError:
            pass

    def test_deepseek_can_accept_paraphrase_and_reply(self):
        fake = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "goal_ids": [
                                    f"{self.seed.FIRST_LESSON_ID}.goal-drop",
                                    f"{self.seed.FIRST_LESSON_ID}.goal-deadline",
                                    f"{self.seed.FIRST_LESSON_ID}.goal-reason",
                                ],
                                "reply_en": "Yes, it is. Thank you.",
                                "coach_zh": "问法对了。",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        with patch("app.ai.chat._post_json", return_value=fake) as posted:
            state = self.learning.submit_order(
                self.seed.FIRST_LESSON_ID,
                "I would rather drop the elective before the deadline. The workload is too heavy.",
            )
        self.assertEqual(posted.call_count, 1)
        headers = posted.call_args.args[1]
        self.assertTrue(headers["Authorization"].startswith("Bearer "))
        self.assertEqual(len(state["completed_goals"]), 3)
        self.assertEqual(state["mode"], "deepseek")
        self.assertEqual(state["reply_en"], "Yes, it is. Thank you.")
        self.assertEqual(state["coach_zh"], "问法对了。")
        self.assertFalse(state["degraded"])

    def test_deepseek_failure_falls_back_to_keywords(self):
        from app.ai.chat import ChatError

        with patch("app.ai.chat._post_json", side_effect=ChatError("unavailable")):
            state = self.learning.submit_order(
                self.seed.FIRST_LESSON_ID,
                "I would rather drop the elective before the deadline. The workload is too heavy.",
            )
        self.assertEqual(len(state["completed_goals"]), 3)
        self.assertEqual(state["mode"], "script")
        self.assertTrue(state["degraded"])
        self.assertIn("关键词", state["coach_zh"])

    def test_grammar_explain_returns_chinese_note(self):
        expression_id = "hw.would-rather"
        fake = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"explain_zh": "提问时把 is 放到句首，句尾用问号。"},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        with patch("app.ai.chat._post_json", return_value=fake) as posted:
            result = self.learning.explain_expression(self.seed.FIRST_LESSON_ID, expression_id)
        self.assertEqual(result["explain_zh"], "提问时把 is 放到句首，句尾用问号。")
        self.assertEqual(result["mode"], "deepseek")
        payload = posted.call_args.args[2]
        blob = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertIn("would rather", blob)
        self.assertNotIn("sk-test-secret", blob)
        self.assertNotIn("review", blob.lower())
        self.assertNotIn("dialogue", blob.lower())

    def test_grammar_explain_without_key(self):
        os.environ["SELF_ENGLISH_AI_PROVIDER"] = "off"
        with self.assertRaises(HTTPException) as raised:
            self.learning.explain_expression(
                self.seed.FIRST_LESSON_ID,
                "hw.would-rather",
            )
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("DeepSeek", raised.exception.detail)

    def test_grammar_explain_unknown_expression(self):
        with self.assertRaises(HTTPException) as raised:
            self.learning.explain_expression(self.seed.FIRST_LESSON_ID, "nope.missing")
        self.assertEqual(raised.exception.status_code, 404)

    def test_grammar_explain_failure_has_retry_message(self):
        from app.ai.chat import ChatError

        with patch("app.ai.chat._post_json", side_effect=ChatError("unavailable")):
            with self.assertRaises(HTTPException) as raised:
                self.learning.explain_expression(
                    self.seed.FIRST_LESSON_ID,
                    "hw.would-rather",
                )
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("不可用", raised.exception.detail)
        self.assertNotIn("sk-test-secret", raised.exception.detail)

    def test_grammar_explain_empty_content(self):
        fake = {"choices": [{"finish_reason": "length", "message": {"content": "", "reasoning_content": "..."}}]}
        with patch("app.ai.chat._post_json", return_value=fake):
            with self.assertRaises(HTTPException) as raised:
                self.learning.explain_expression(
                    self.seed.FIRST_LESSON_ID,
                    "hw.would-rather",
                )
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("没有返回", raised.exception.detail)

    def test_grammar_explain_forwards_question(self):
        fake = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({"explain_zh": "简短回答要用 Yes, I am."}, ensure_ascii=False)
                    }
                }
            ]
        }
        with patch("app.ai.chat._post_json", return_value=fake) as posted:
            result = self.learning.explain_expression(
                self.seed.FIRST_LESSON_ID,
                "hw.would-rather",
                "为什么不能说 Yes, I'm?",
            )
        self.assertEqual(result["explain_zh"], "简短回答要用 Yes, I am.")
        payload = json.dumps(posted.call_args.args[2], ensure_ascii=False)
        self.assertIn("Yes, I'm?", payload)
        self.assertNotIn("sk-test-secret", payload)

    def test_phrase_explain_forwards_note(self):
        fake = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"explain_zh": "Excuse me 用来引起陌生人注意，借过或提问前先说。"},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        with patch("app.ai.chat._post_json", return_value=fake) as posted:
            result = self.learning.explain_expression(
                self.seed.FIRST_LESSON_ID,
                "hw.deadline",
            )
        self.assertEqual(result["explain_zh"], "Excuse me 用来引起陌生人注意，借过或提问前先说。")
        payload = json.dumps(posted.call_args.args[2], ensure_ascii=False)
        self.assertIn("deadline", payload)
        self.assertIn("截止", payload)
        self.assertIn("word", payload)
        self.assertIn("word, phrase, or pattern", payload)
        self.assertNotIn("sk-test-secret", payload)

    def test_grammar_explain_rejects_long_question(self):
        with self.assertRaises(HTTPException) as raised:
            self.learning.explain_expression(
                self.seed.FIRST_LESSON_ID,
                "hw.would-rather",
                "问" * 201,
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_voice_session_does_not_open(self):
        from app.main import voice_session

        with self.assertRaises(HTTPException) as raised:
            voice_session()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("录音", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
