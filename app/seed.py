"""Original A1 month-1 lessons. Idempotent inserts."""

from __future__ import annotations

SOURCE_NOTE = "本课为 self-english 原创种子，供个人学习。无真人录音，朗读使用设备系统语音。"


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
    dialogue: list[tuple[str, str, str, str]],
    questions: list[dict],
    goals: list[tuple[str, str, list[str]]],
) -> dict:
    return {
        "id": lesson_id,
        "title": title,
        "title_zh": title_zh,
        "level": "A1",
        "month": 1,
        "source": "original",
        "source_note": SOURCE_NOTE,
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
                "speaker": speaker,
                "speaker_zh": speaker_zh,
                "english": english,
                "chinese": chinese,
                "sort_order": index,
            }
            for index, (speaker, speaker_zh, english, chinese) in enumerate(dialogue, start=1)
        ],
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


CAFE_ORDER = _lesson(
    lesson_id="cafe-order-a1",
    title="Ordering coffee",
    title_zh="咖啡店点餐",
    task_title_zh="点一杯咖啡",
    task_placeholder="在这里写你要说的英文，例如 I would like a cup of coffee, please. Thank you.",
    submit_label="提交我的话",
    empty_error="先写你要点的东西。",
    brief_zh="你是客人。店员已经问你想喝什么。不要抄整段剧本，自己用英文把点单写出来：要有 coffee，用上 please，再说 thank you。",
    hear_label_zh="店员刚才说",
    expressions=[
        _expr(
            "coffee",
            "coffee",
            "咖啡",
            kind="word",
            phonetic="/ˈkɔːfi/",
            note_zh="读音接近「咖啡」。点饮料时直接说这个词。cup 是杯子，a cup of coffee 就是一杯咖啡。",
            example_en="I would like a cup of coffee, please.",
            example_zh="我想要一杯咖啡。",
            mark="☕",
        ),
        _expr(
            "a-cup-of",
            "a cup of",
            "一杯",
            kind="phrase",
            phonetic="/ə kʌp əv/",
            note_zh="a cup of + 饮料。先说杯子，再说里面的东西：a cup of coffee / tea / water。",
            example_en="a cup of coffee",
            example_zh="一杯咖啡",
            mark="🥤",
        ),
        _expr(
            "i-would-like",
            "I would like",
            "我想要",
            kind="phrase",
            phonetic="/aɪ wʊd laɪk/",
            note_zh="点餐时比 I want 更客气。整句常常这样开头：I would like …, please.",
            example_en="I would like a cup of coffee, please.",
            example_zh="我想要一杯咖啡。",
            mark="🙋",
        ),
        _expr(
            "please",
            "please",
            "请",
            kind="word",
            phonetic="/pliːz/",
            note_zh="放在句尾，让请求更礼貌。中文语感接近句末的「请」。",
            example_en="I would like a cup of coffee, please.",
            example_zh="我想要一杯咖啡。",
            mark="🙏",
        ),
        _expr(
            "thank-you",
            "Thank you.",
            "谢谢。",
            kind="phrase",
            phonetic="/θæŋk juː/",
            note_zh="thank 是感谢，you 是你。店员把东西给你之后说。比 Thanks 稍完整一点。",
            example_en="Thank you.",
            example_zh="谢谢。",
            mark="🙇",
        ),
    ],
    dialogue=[
        ("clerk", "店员", "Hello. What would you like?", "你好。你想要什么？"),
        ("you", "你", "I would like a cup of coffee, please.", "我想要一杯咖啡。"),
        ("clerk", "店员", "Sure. Here you are.", "好的。给你。"),
        ("you", "你", "Thank you.", "谢谢。"),
    ],
    questions=[
        {
            "id": "q1",
            "prompt_en": "What does the customer want?",
            "prompt_zh": "客人想要什么？",
            "options": [
                {"id": "coffee", "en": "coffee", "zh": "咖啡"},
                {"id": "tea", "en": "tea", "zh": "茶"},
                {"id": "water", "en": "water", "zh": "水"},
            ],
            "answer_id": "coffee",
        },
        {
            "id": "q2",
            "prompt_en": "What does “please” do in this order?",
            "prompt_zh": "这句话里的 please 是什么意思？",
            "options": [
                {"id": "please", "en": "please", "zh": "请"},
                {"id": "sorry", "en": "sorry", "zh": "对不起"},
                {"id": "goodbye", "en": "goodbye", "zh": "再见"},
            ],
            "answer_id": "please",
        },
    ],
    goals=[
        ("goal-drink", "点咖啡", ["coffee"]),
        ("goal-please", "用上 please", ["please"]),
        ("goal-thanks", "说谢谢", ["thank you"]),
    ],
)

GREETINGS = _lesson(
    lesson_id="greetings-a1",
    title="Saying hello",
    title_zh="问候",
    task_title_zh="用英文打招呼",
    task_placeholder="在这里写你要说的英文，例如 Hello. How are you? I'm fine. Nice to meet you.",
    submit_label="提交我的话",
    empty_error="先写一句英文。",
    brief_zh="邻居在跟你打招呼。用英文回应：先打招呼，问好，再说很高兴认识你。",
    hear_label_zh="邻居刚才说",
    expressions=[
        _expr(
            "hello",
            "Hello.",
            "你好。",
            kind="phrase",
            phonetic="/həˈloʊ/",
            note_zh="见面先说。比 Hi 稍正式一点，店里、路上都能用。",
            example_en="Hello. How are you?",
            example_zh="你好。你好吗？",
            mark="👋",
        ),
        _expr(
            "how-are-you",
            "How are you?",
            "你好吗？",
            kind="phrase",
            phonetic="/haʊ ɑːr juː/",
            note_zh="问对方近况。不一定要报告身体，回 I'm fine 就可以。",
            example_en="Hello. How are you?",
            example_zh="你好。你好吗？",
            mark="🙂",
        ),
        _expr(
            "im-fine",
            "I'm fine.",
            "我很好。",
            kind="phrase",
            phonetic="/aɪm faɪn/",
            note_zh="I'm = I am。回答 How are you 的常用短句。",
            example_en="I'm fine, thank you.",
            example_zh="我很好，谢谢。",
            mark="👌",
        ),
        _expr(
            "and-you",
            "And you?",
            "你呢？",
            kind="phrase",
            phonetic="/ænd juː/",
            note_zh="把同样的问题抛回去。常接在 I'm fine, thank you. 后面。",
            example_en="I'm fine, thank you. And you?",
            example_zh="我很好，谢谢。你呢？",
            mark="🔄",
        ),
        _expr(
            "nice-to-meet-you",
            "Nice to meet you.",
            "很高兴认识你。",
            kind="phrase",
            phonetic="/naɪs tə miːt juː/",
            note_zh="第一次见面时说。meet 是遇见，不是 eat。",
            example_en="I'm fine. Nice to meet you.",
            example_zh="我很好。很高兴认识你。",
            mark="🤝",
        ),
    ],
    dialogue=[
        ("neighbor", "邻居", "Hello.", "你好。"),
        ("you", "你", "Hello. How are you?", "你好。你好吗？"),
        ("neighbor", "邻居", "I'm fine, thank you. And you?", "我很好，谢谢。你呢？"),
        ("you", "你", "I'm fine. Nice to meet you.", "我很好。很高兴认识你。"),
    ],
    questions=[
        {
            "id": "q1",
            "prompt_en": "What do you say first?",
            "prompt_zh": "开头先说什么？",
            "options": [
                {"id": "hello", "en": "Hello.", "zh": "你好。"},
                {"id": "coffee", "en": "coffee", "zh": "咖啡"},
                {"id": "goodbye", "en": "Goodbye.", "zh": "再见。"},
            ],
            "answer_id": "hello",
        },
        {
            "id": "q2",
            "prompt_en": "What does “How are you?” ask?",
            "prompt_zh": "How are you? 在问什么？",
            "options": [
                {"id": "feeling", "en": "how you are", "zh": "你好不好"},
                {"id": "name", "en": "your name", "zh": "你叫什么"},
                {"id": "drink", "en": "what you want to drink", "zh": "你想喝什么"},
            ],
            "answer_id": "feeling",
        },
    ],
    goals=[
        ("goal-hello", "打招呼", ["hello"]),
        ("goal-how-are-you", "问好", ["how are you"]),
        ("goal-nice", "说见面高兴", ["nice to meet you"]),
    ],
)

SAY_AGAIN = _lesson(
    lesson_id="say-again-a1",
    title="Please say that again",
    title_zh="请对方再说一次",
    task_title_zh="请对方再说一次",
    task_placeholder="在这里写你要说的英文，例如 Sorry. I don't understand. Please say that again.",
    submit_label="提交我的话",
    empty_error="先写一句英文。",
    brief_zh="你没听清店员的话。用英文请对方再说一次：先说 sorry，说听不懂，再请对方 repeat。",
    hear_label_zh="店员刚才说",
    expressions=[
        _expr(
            "sorry",
            "Sorry.",
            "对不起。",
            kind="phrase",
            phonetic="/ˈsɑːri/",
            note_zh="听不懂时先说 Sorry，再解释。比直接打断更客气。",
            example_en="Sorry. I don't understand.",
            example_zh="对不起。我听不懂。",
            mark="😔",
        ),
        _expr(
            "dont-understand",
            "I don't understand.",
            "我听不懂。",
            kind="phrase",
            phonetic="/aɪ doʊnt ˌʌndərˈstænd/",
            note_zh="don't = do not。直接说没听懂，对方才会换一种说法。",
            example_en="Sorry. I don't understand.",
            example_zh="对不起。我听不懂。",
            mark="❓",
        ),
        _expr(
            "say-again",
            "Please say that again.",
            "请再说一次。",
            kind="phrase",
            phonetic="/pliːz seɪ ðæt əˈɡen/",
            note_zh="that 指刚才那句。again 是再一次。请对方重复，不是请对方说快。",
            example_en="Please say that again, slowly, please.",
            example_zh="请再说一次，请慢一点。",
            mark="🔁",
        ),
        _expr(
            "slowly-please",
            "Slowly, please.",
            "请慢一点。",
            kind="phrase",
            phonetic="/ˈsloʊli pliːz/",
            note_zh="slow 是慢，slowly 是慢慢地。听不清语速时加上这句。",
            example_en="Please say that again, slowly, please.",
            example_zh="请再说一次，请慢一点。",
            mark="🐢",
        ),
        _expr(
            "thank-you",
            "Thank you.",
            "谢谢。",
            kind="phrase",
            phonetic="/θæŋk juː/",
            note_zh="对方放慢或再说一遍之后，用这句收尾。",
            example_en="Thank you.",
            example_zh="谢谢。",
            mark="🙇",
        ),
    ],
    dialogue=[
        ("clerk", "店员", "What would you like?", "你想要什么？"),
        ("you", "你", "Sorry. I don't understand.", "对不起。我听不懂。"),
        ("clerk", "店员", "Coffee or tea?", "咖啡还是茶？"),
        ("you", "你", "Please say that again, slowly, please.", "请再说一次，请慢一点。"),
    ],
    questions=[
        {
            "id": "q1",
            "prompt_en": "What can you say if you do not understand?",
            "prompt_zh": "听不懂时可以说什么？",
            "options": [
                {"id": "sorry", "en": "Sorry. I don't understand.", "zh": "对不起。我听不懂。"},
                {"id": "hello", "en": "Hello.", "zh": "你好。"},
                {"id": "coffee", "en": "coffee", "zh": "咖啡"},
            ],
            "answer_id": "sorry",
        },
        {
            "id": "q2",
            "prompt_en": "What does “Please say that again” ask for?",
            "prompt_zh": "Please say that again 是在请对方做什么？",
            "options": [
                {"id": "repeat", "en": "say it again", "zh": "再说一次"},
                {"id": "faster", "en": "speak faster", "zh": "说快一点"},
                {"id": "leave", "en": "go away", "zh": "离开"},
            ],
            "answer_id": "repeat",
        },
    ],
    goals=[
        ("goal-sorry", "先说 sorry", ["sorry"]),
        ("goal-understand", "说听不懂", ["i don't understand"]),
        ("goal-again", "请再说一次", ["say that again"]),
    ],
)

LESSONS = [CAFE_ORDER, GREETINGS, SAY_AGAIN]
LESSON = CAFE_ORDER
LESSON_ID = CAFE_ORDER["id"]
EXPRESSIONS = CAFE_ORDER["expressions"]
DIALOGUE = CAFE_ORDER["dialogue"]
QUESTIONS = CAFE_ORDER["questions"]
GOALS = CAFE_ORDER["goals"]

STEPS = ("vocab", "listen", "talk", "recap", "done")
STEP_ZH = {
    "vocab": "词汇",
    "listen": "听读",
    "talk": "对话",
    "recap": "复盘",
    "done": "已完成",
}
VOCAB_PHASES = ("learn", "recall", "done")

ROADMAP = [
    {"id": "m1", "month": 1, "title_zh": "点餐、问候、请对方再说一次", "status": "in_progress"},
    {"id": "m2", "month": 2, "title_zh": "问路、坐车", "status": "pending"},
    {"id": "m3", "month": 3, "title_zh": "酒店入住", "status": "pending"},
    {"id": "m4", "month": 4, "title_zh": "日常闲聊", "status": "pending"},
    {"id": "m5", "month": 5, "title_zh": "简单工作问答", "status": "pending"},
    {"id": "m6", "month": 6, "title_zh": "把一天串起来", "status": "pending"},
]


def lesson_by_id(lesson_id: str) -> dict | None:
    for lesson in LESSONS:
        if lesson["id"] == lesson_id:
            return lesson
    return None


def lesson_index(lesson_id: str) -> int:
    for index, lesson in enumerate(LESSONS, start=1):
        if lesson["id"] == lesson_id:
            return index
    return 0
