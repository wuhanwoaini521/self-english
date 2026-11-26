"""Original A1 month-1 and month-2 lessons. Idempotent inserts."""

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
) -> dict:
    return {
        "id": lesson_id,
        "title": title,
        "title_zh": title_zh,
        "level": "A1",
        "month": month,
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


CAFE_ORDER = _lesson(
    lesson_id="cafe-order-a1",
    title="Ordering coffee",
    title_zh="咖啡店点餐",
    task_title_zh="点一杯咖啡",
    task_placeholder="用英文写出你要点的东西。",
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
        _line(
            "clerk",
            "店员",
            "你好。你想要什么？",
            "Hello. What ",
            grammar("would you like", phonetic="/wʊd juː laɪk/", pos="动词短语", sense_zh="想要（礼貌问法）"),
            "?",
        ),
        _line(
            "you",
            "你",
            "我想要一杯咖啡。",
            grammar("I would like", phonetic="/aɪ wʊd laɪk/", pos="动词短语", sense_zh="我想要（比 I want 客气）"),
            " a cup of ",
            vocab("coffee", phonetic="/ˈkɔːfi/", pos="名词", sense_zh="咖啡"),
            ", please.",
        ),
        _line(
            "clerk",
            "店员",
            "好的。给你。",
            "Sure. ",
            vocab("Here you are", phonetic="/hɪr juː ɑːr/", pos="短语", sense_zh="给你"),
            ".",
        ),
        _line(
            "you",
            "你",
            "谢谢。",
            vocab("Thank you", phonetic="/θæŋk juː/", pos="短语", sense_zh="谢谢"),
            ".",
        ),
    ],
    passage={
        "title_zh": "短文",
        "paragraphs": [
            _para(
                "我在咖啡馆。我想要一杯拿铁。谢谢。",
                "I am at a ",
                vocab("cafe", phonetic="/kæˈfeɪ/", pos="名词", sense_zh="咖啡馆"),
                ". ",
                grammar("I'd like", phonetic="/aɪd laɪk/", pos="动词短语", sense_zh="我想要（I would like 的缩写）"),
                " a ",
                vocab("latte", phonetic="/ˈlɑː.teɪ/", pos="名词", sense_zh="拿铁咖啡"),
                ", please. ",
                vocab("Thank you", phonetic="/θæŋk juː/", pos="短语", sense_zh="谢谢"),
                ".",
            )
        ],
    },
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
    task_placeholder="用英文写出你要说的话。",
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
        _line(
            "neighbor",
            "邻居",
            "你好。",
            vocab("Hello", phonetic="/həˈloʊ/", pos="短语", sense_zh="你好"),
            ".",
        ),
        _line(
            "you",
            "你",
            "你好。你好吗？",
            "Hello. ",
            grammar("How are you", phonetic="/haʊ ɑːr juː/", pos="疑问句", sense_zh="问候近况"),
            "?",
        ),
        _line(
            "neighbor",
            "邻居",
            "我很好，谢谢。你呢？",
            grammar("I'm", phonetic="/aɪm/", pos="缩写", sense_zh="I am 的缩写"),
            " fine, thank you. And you?",
        ),
        _line(
            "you",
            "你",
            "我很好。很高兴认识你。",
            "I'm fine. ",
            vocab("Nice to meet you", phonetic="/naɪs tə miːt juː/", pos="短语", sense_zh="很高兴认识你"),
            ".",
        ),
    ],
    passage={
        "title_zh": "短文",
        "paragraphs": [
            _para(
                "我遇见邻居。你好吗？我很好。很高兴认识你。",
                "I meet my ",
                vocab("neighbor", phonetic="/ˈneɪbər/", pos="名词", sense_zh="邻居"),
                ". ",
                grammar("How are you", phonetic="/haʊ ɑːr juː/", pos="疑问句", sense_zh="问候近况"),
                "? I'm fine. ",
                vocab("Nice to meet you", phonetic="/naɪs tə miːt juː/", pos="短语", sense_zh="很高兴认识你"),
                ".",
            )
        ],
    },
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
    task_placeholder="用英文写出你要说的话。",
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
        _line(
            "clerk",
            "店员",
            "你想要什么？",
            "What ",
            grammar("would you like", phonetic="/wʊd juː laɪk/", pos="动词短语", sense_zh="想要（礼貌问法）"),
            "?",
        ),
        _line(
            "you",
            "你",
            "对不起。我听不懂。",
            vocab("Sorry", phonetic="/ˈsɑːri/", pos="短语", sense_zh="对不起"),
            ". I ",
            grammar("don't", phonetic="/doʊnt/", pos="助动词", sense_zh="不（do not 的缩写）"),
            " ",
            vocab("understand", phonetic="/ˌʌndərˈstænd/", pos="动词", sense_zh="懂、明白"),
            ".",
        ),
        _line(
            "clerk",
            "店员",
            "咖啡还是茶？",
            vocab("Coffee", phonetic="/ˈkɔːfi/", pos="名词", sense_zh="咖啡", headword="coffee"),
            " or ",
            vocab("tea", phonetic="/tiː/", pos="名词", sense_zh="茶"),
            "?",
        ),
        _line(
            "you",
            "你",
            "请再说一次，请慢一点。",
            "Please ",
            vocab("say that again", phonetic="/seɪ ðæt əˈɡen/", pos="短语", sense_zh="再说一次"),
            ", ",
            vocab("slowly", phonetic="/ˈsloʊli/", pos="副词", sense_zh="慢慢地"),
            ", please.",
        ),
    ],
    passage={
        "title_zh": "短文",
        "paragraphs": [
            _para(
                "对不起。我听不懂。请再说一次。",
                vocab("Sorry", phonetic="/ˈsɑːri/", pos="短语", sense_zh="对不起"),
                ". I ",
                grammar("don't", phonetic="/doʊnt/", pos="助动词", sense_zh="不（do not 的缩写）"),
                " ",
                vocab("understand", phonetic="/ˌʌndərˈstænd/", pos="动词", sense_zh="懂、明白"),
                ". Please ",
                vocab("say that again", phonetic="/seɪ ðæt əˈɡen/", pos="短语", sense_zh="再说一次"),
                ".",
            )
        ],
    },
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

ASK_DIRECTIONS = _lesson(
    lesson_id="asking-directions-a1",
    title="Asking for directions",
    title_zh="问路",
    month=2,
    task_title_zh="问车站怎么走",
    task_placeholder="用英文问路，例如 Excuse me. Where is the station?",
    submit_label="提交我的话",
    empty_error="先写一句英文。",
    brief_zh="你在街上，想去车站。先说 Excuse me，再问 Where is the station。能再说 thank you 更好。",
    hear_label_zh="路人刚才说",
    expressions=[
        _expr(
            "excuse-me",
            "Excuse me.",
            "打扰一下。",
            kind="phrase",
            phonetic="/ɪkˈskjuːz miː/",
            note_zh="问路、插话前先说。比直接问 Where is 更客气。",
            example_en="Excuse me. Where is the station?",
            example_zh="打扰一下。车站在哪里？",
            mark="🙋",
        ),
        _expr(
            "where-is",
            "Where is the station?",
            "车站在哪里？",
            kind="phrase",
            phonetic="/wer ɪz ðə ˈsteɪʃn/",
            note_zh="Where is + 地点。station 是车站。换地点时只改后面的词。",
            example_en="Where is the station?",
            example_zh="车站在哪里？",
            mark="📍",
        ),
        _expr(
            "go-straight",
            "Go straight.",
            "直走。",
            kind="phrase",
            phonetic="/ɡoʊ streɪt/",
            note_zh="straight 是直的。对方指路时常先说这句。",
            example_en="Go straight, then turn left.",
            example_zh="直走，然后左转。",
            mark="⬆️",
        ),
        _expr(
            "turn-left",
            "Turn left.",
            "左转。",
            kind="phrase",
            phonetic="/tɜːrn left/",
            note_zh="turn 是转，left 是左。Turn right 就是右转。",
            example_en="Go straight, then turn left.",
            example_zh="直走，然后左转。",
            mark="↩️",
        ),
        _expr(
            "over-there",
            "It's over there.",
            "就在那边。",
            kind="phrase",
            phonetic="/ɪts ˈoʊvər ðer/",
            note_zh="over there 是那边。对方用手一指时会说这句。",
            example_en="It's over there.",
            example_zh="就在那边。",
            mark="👉",
        ),
    ],
    dialogue=[
        _line(
            "local",
            "路人",
            "你好。需要帮忙吗？",
            "Hello. ",
            grammar("Can I help you", phonetic="/kæn aɪ help juː/", pos="疑问句", sense_zh="需要帮忙吗"),
            "?",
        ),
        _line(
            "you",
            "你",
            "打扰一下。车站在哪里？",
            vocab("Excuse me", phonetic="/ɪkˈskjuːz miː/", pos="短语", sense_zh="打扰一下"),
            ". ",
            grammar("Where is", phonetic="/wer ɪz/", pos="疑问句", sense_zh="在哪里"),
            " the ",
            vocab("station", phonetic="/ˈsteɪʃn/", pos="名词", sense_zh="车站"),
            "?",
        ),
        _line(
            "local",
            "路人",
            "直走，然后左转。就在那边。",
            vocab("Go straight", phonetic="/ɡoʊ streɪt/", pos="短语", sense_zh="直走"),
            ", then ",
            vocab("turn left", phonetic="/tɜːrn left/", pos="短语", sense_zh="左转"),
            ". ",
            vocab("It's over there", phonetic="/ɪts ˈoʊvər ðer/", pos="短语", sense_zh="就在那边"),
            ".",
        ),
        _line(
            "you",
            "你",
            "谢谢。",
            vocab("Thank you", phonetic="/θæŋk juː/", pos="短语", sense_zh="谢谢"),
            ".",
        ),
    ],
    passage={
        "title_zh": "短文",
        "paragraphs": [
            _para(
                "我在街上。打扰一下。车站在哪里？直走，然后左转。",
                "I am on the ",
                vocab("street", phonetic="/striːt/", pos="名词", sense_zh="街道"),
                ". ",
                vocab("Excuse me", phonetic="/ɪkˈskjuːz miː/", pos="短语", sense_zh="打扰一下"),
                ". ",
                grammar("Where is", phonetic="/wer ɪz/", pos="疑问句", sense_zh="在哪里"),
                " the ",
                vocab("station", phonetic="/ˈsteɪʃn/", pos="名词", sense_zh="车站"),
                "? ",
                vocab("Go straight", phonetic="/ɡoʊ streɪt/", pos="短语", sense_zh="直走"),
                ", then ",
                vocab("turn left", phonetic="/tɜːrn left/", pos="短语", sense_zh="左转"),
                ".",
            )
        ],
    },
    questions=[
        {
            "id": "q1",
            "prompt_en": "What are you looking for?",
            "prompt_zh": "你在找什么？",
            "options": [
                {"id": "station", "en": "the station", "zh": "车站"},
                {"id": "coffee", "en": "coffee", "zh": "咖啡"},
                {"id": "ticket", "en": "a ticket", "zh": "一张票"},
            ],
            "answer_id": "station",
        },
        {
            "id": "q2",
            "prompt_en": "What does “turn left” mean?",
            "prompt_zh": "turn left 是什么意思？",
            "options": [
                {"id": "left", "en": "turn left", "zh": "左转"},
                {"id": "straight", "en": "go straight", "zh": "直走"},
                {"id": "right", "en": "turn right", "zh": "右转"},
            ],
            "answer_id": "left",
        },
    ],
    goals=[
        ("goal-excuse", "先说 Excuse me", ["excuse me"]),
        ("goal-where", "问车站在哪", ["where is"]),
        ("goal-thanks", "说谢谢", ["thank you"]),
    ],
)

TAKE_BUS = _lesson(
    lesson_id="taking-bus-a1",
    title="Taking the bus",
    title_zh="坐车",
    month=2,
    task_title_zh="买票坐车去车站",
    task_placeholder="用英文买票，例如 I want to go to the station. A ticket, please. How much is it?",
    submit_label="提交我的话",
    empty_error="先写一句英文。",
    brief_zh="你要坐公交车去车站。说出 I want to go to the station，买 a ticket，再问 How much is it。",
    hear_label_zh="售票员刚才说",
    expressions=[
        _expr(
            "a-ticket",
            "a ticket",
            "一张票",
            kind="phrase",
            phonetic="/ə ˈtɪkɪt/",
            note_zh="ticket 是票。上车或窗口可以说 A ticket, please.",
            example_en="A ticket, please.",
            example_zh="请给我一张票。",
            mark="🎫",
        ),
        _expr(
            "how-much",
            "How much is it?",
            "多少钱？",
            kind="phrase",
            phonetic="/haʊ mʌtʃ ɪz ɪt/",
            note_zh="问价格。it 指这张票。买东西、买票都能用。",
            example_en="How much is it?",
            example_zh="多少钱？",
            mark="💵",
        ),
        _expr(
            "want-to-go",
            "I want to go to",
            "我想去",
            kind="phrase",
            phonetic="/aɪ wɑːnt tə ɡoʊ tuː/",
            note_zh="后面加地点：I want to go to the station。说清目的地。",
            example_en="I want to go to the station.",
            example_zh="我想去车站。",
            mark="🚌",
        ),
        _expr(
            "this-bus",
            "this bus",
            "这班公交车",
            kind="phrase",
            phonetic="/ðɪs bʌs/",
            note_zh="bus 是公交车。确认是不是要坐的那辆：Is this bus going to the station?",
            example_en="This bus goes to the station.",
            example_zh="这班车去车站。",
            mark="🚍",
        ),
        _expr(
            "next-stop",
            "the next stop",
            "下一站",
            kind="phrase",
            phonetic="/ðə nekst stɑːp/",
            note_zh="stop 在这里是站点。听报站时常听到 The next stop is …",
            example_en="The next stop is the station.",
            example_zh="下一站是车站。",
            mark="🛑",
        ),
    ],
    dialogue=[
        _line(
            "clerk",
            "售票员",
            "你好。你想去哪里？",
            "Hello. Where do you ",
            grammar("want to go", phonetic="/wɑːnt tə ɡoʊ/", pos="动词短语", sense_zh="想去"),
            "?",
        ),
        _line(
            "you",
            "你",
            "我想去车站。请给我一张票。多少钱？",
            grammar("I want to go to", phonetic="/aɪ wɑːnt tə ɡoʊ tuː/", pos="动词短语", sense_zh="我想去"),
            " the station. A ",
            vocab("ticket", phonetic="/ˈtɪkɪt/", pos="名词", sense_zh="票"),
            ", please. ",
            grammar("How much is it", phonetic="/haʊ mʌtʃ ɪz ɪt/", pos="疑问句", sense_zh="多少钱"),
            "?",
        ),
        _line(
            "clerk",
            "售票员",
            "两美元。这班车去车站。下一站就是车站。",
            "Two dollars. ",
            vocab("This bus", phonetic="/ðɪs bʌs/", pos="短语", sense_zh="这班公交车"),
            " goes there. ",
            vocab("The next stop", phonetic="/ðə nekst stɑːp/", pos="短语", sense_zh="下一站"),
            " is the station.",
        ),
        _line(
            "you",
            "你",
            "谢谢。",
            vocab("Thank you", phonetic="/θæŋk juː/", pos="短语", sense_zh="谢谢"),
            ".",
        ),
    ],
    passage={
        "title_zh": "短文",
        "paragraphs": [
            _para(
                "我坐公交车。我想去车站。一张票多少钱？下一站是车站。",
                "I take a ",
                vocab("bus", phonetic="/bʌs/", pos="名词", sense_zh="公交车"),
                ". ",
                grammar("I want to go to", phonetic="/aɪ wɑːnt tə ɡoʊ tuː/", pos="动词短语", sense_zh="我想去"),
                " the station. How much is a ",
                vocab("ticket", phonetic="/ˈtɪkɪt/", pos="名词", sense_zh="票"),
                "? ",
                vocab("The next stop", phonetic="/ðə nekst stɑːp/", pos="短语", sense_zh="下一站"),
                " is the station.",
            )
        ],
    },
    questions=[
        {
            "id": "q1",
            "prompt_en": "Where does the passenger want to go?",
            "prompt_zh": "乘客想去哪里？",
            "options": [
                {"id": "station", "en": "the station", "zh": "车站"},
                {"id": "cafe", "en": "a cafe", "zh": "咖啡馆"},
                {"id": "home", "en": "home", "zh": "家"},
            ],
            "answer_id": "station",
        },
        {
            "id": "q2",
            "prompt_en": "What does “How much is it?” ask?",
            "prompt_zh": "How much is it? 在问什么？",
            "options": [
                {"id": "price", "en": "the price", "zh": "多少钱"},
                {"id": "time", "en": "the time", "zh": "几点"},
                {"id": "name", "en": "the name", "zh": "叫什么"},
            ],
            "answer_id": "price",
        },
    ],
    goals=[
        ("goal-go", "说想去车站", ["i want to go"]),
        ("goal-ticket", "买票", ["ticket"]),
        ("goal-price", "问多少钱", ["how much"]),
    ],
)

LESSONS = [CAFE_ORDER, GREETINGS, SAY_AGAIN, ASK_DIRECTIONS, TAKE_BUS]
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
