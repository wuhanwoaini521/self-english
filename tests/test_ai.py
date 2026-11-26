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
                                    f"{self.seed.FIRST_LESSON_ID}.goal-excuse",
                                    f"{self.seed.FIRST_LESSON_ID}.goal-yours",
                                    f"{self.seed.FIRST_LESSON_ID}.goal-thanks",
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
                "Excuse me. Is this phone yours? Thanks.",
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
                "Excuse me. Is this your phone? Thank you.",
            )
        self.assertEqual(len(state["completed_goals"]), 3)
        self.assertEqual(state["mode"], "script")
        self.assertTrue(state["degraded"])
        self.assertIn("关键词", state["coach_zh"])

    def test_voice_session_does_not_open(self):
        from app.main import voice_session

        with self.assertRaises(HTTPException) as raised:
            voice_session()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("录音", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
