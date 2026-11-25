"""Original A1 cafe-order lesson. Idempotent inserts."""

from __future__ import annotations

LESSON_ID = "cafe-order-a1"

LESSON = {
    "id": LESSON_ID,
    "title": "Ordering coffee",
    "title_zh": "咖啡店点餐",
    "level": "A1",
    "source": "original",
    "source_note": "本课为 self-english 原创种子，供个人学习。无真人录音，朗读使用设备系统语音。",
}

EXPRESSIONS = [
    {
        "id": f"{LESSON_ID}.coffee",
        "english": "coffee",
        "chinese": "咖啡",
        "kind": "word",
        "sort_order": 1,
    },
    {
        "id": f"{LESSON_ID}.a-cup-of",
        "english": "a cup of",
        "chinese": "一杯",
        "kind": "phrase",
        "sort_order": 2,
    },
    {
        "id": f"{LESSON_ID}.i-would-like",
        "english": "I would like",
        "chinese": "我想要",
        "kind": "phrase",
        "sort_order": 3,
    },
    {
        "id": f"{LESSON_ID}.please",
        "english": "please",
        "chinese": "请",
        "kind": "word",
        "sort_order": 4,
    },
    {
        "id": f"{LESSON_ID}.thank-you",
        "english": "Thank you.",
        "chinese": "谢谢。",
        "kind": "phrase",
        "sort_order": 5,
    },
]

DIALOGUE = [
    {
        "id": f"{LESSON_ID}.line-1",
        "speaker": "clerk",
        "speaker_zh": "店员",
        "english": "Hello. What would you like?",
        "chinese": "你好。你想要什么？",
        "sort_order": 1,
    },
    {
        "id": f"{LESSON_ID}.line-2",
        "speaker": "you",
        "speaker_zh": "你",
        "english": "I would like a cup of coffee, please.",
        "chinese": "我想要一杯咖啡。",
        "sort_order": 2,
    },
    {
        "id": f"{LESSON_ID}.line-3",
        "speaker": "clerk",
        "speaker_zh": "店员",
        "english": "Sure. Here you are.",
        "chinese": "好的。给你。",
        "sort_order": 3,
    },
    {
        "id": f"{LESSON_ID}.line-4",
        "speaker": "you",
        "speaker_zh": "你",
        "english": "Thank you.",
        "chinese": "谢谢。",
        "sort_order": 4,
    },
]

QUESTIONS = [
    {
        "id": f"{LESSON_ID}.q1",
        "prompt_en": "What does the customer want?",
        "prompt_zh": "客人想要什么？",
        "options": [
            {"id": "coffee", "en": "coffee", "zh": "咖啡"},
            {"id": "tea", "en": "tea", "zh": "茶"},
            {"id": "water", "en": "water", "zh": "水"},
        ],
        "answer_id": "coffee",
        "sort_order": 1,
    },
    {
        "id": f"{LESSON_ID}.q2",
        "prompt_en": "What does “please” do in this order?",
        "prompt_zh": "这句话里的 please 是什么意思？",
        "options": [
            {"id": "please", "en": "please", "zh": "请"},
            {"id": "sorry", "en": "sorry", "zh": "对不起"},
            {"id": "goodbye", "en": "goodbye", "zh": "再见"},
        ],
        "answer_id": "please",
        "sort_order": 2,
    },
]

GOALS = [
    {
        "id": f"{LESSON_ID}.goal-drink",
        "label_zh": "点咖啡",
        "keys": ["coffee"],
        "sort_order": 1,
    },
    {
        "id": f"{LESSON_ID}.goal-please",
        "label_zh": "用上 please",
        "keys": ["please"],
        "sort_order": 2,
    },
    {
        "id": f"{LESSON_ID}.goal-thanks",
        "label_zh": "说谢谢",
        "keys": ["thank you"],
        "sort_order": 3,
    },
]

STEPS = ("vocab", "listen", "talk", "recap", "done")
STEP_ZH = {
    "vocab": "词汇",
    "listen": "听读",
    "talk": "对话",
    "recap": "复盘",
    "done": "已完成",
}

ROADMAP = [
    {"id": "m1", "month": 1, "title_zh": "点餐、问候、请对方再说一次", "status": "in_progress"},
    {"id": "m2", "month": 2, "title_zh": "问路、坐车", "status": "pending"},
    {"id": "m3", "month": 3, "title_zh": "酒店入住", "status": "pending"},
    {"id": "m4", "month": 4, "title_zh": "日常闲聊", "status": "pending"},
    {"id": "m5", "month": 5, "title_zh": "简单工作问答", "status": "pending"},
    {"id": "m6", "month": 6, "title_zh": "把一天串起来", "status": "pending"},
]
