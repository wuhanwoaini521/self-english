"""Build data/app.db: A1 words with Chinese, plus short bilingual sentences."""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import zipfile
from pathlib import Path

import zhconv

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "app.db"
SURVIVAL = ROOT / "data" / "seed" / "survival.json"
WORK = ROOT / "data" / "seed" / "work.json"
TRAVEL_TOPICS = (
    "travel",
    "travelling",
    "holiday",
    "food and drink",
    "shopping",
    "things in the town",
    "ways of travelling",
)
BUSINESS_TOPICS = ("work and jobs",)
TRAVEL_WORDS = {
    "airport", "hotel", "ticket", "taxi", "bus", "train", "plane", "station", "map",
    "street", "restaurant", "menu", "bill", "passport", "bag", "room", "key", "left",
    "right", "stop", "shop", "store", "food", "water", "money", "toilet", "luggage",
    "flight", "cash", "reservation", "breakfast", "address", "city", "bank", "doctor",
    "hospital", "car", "help",
}
BUSINESS_WORDS = {
    "work", "job", "office", "meeting", "email", "company", "customer", "manager",
    "boss", "business", "price", "pay", "buy", "sell", "computer", "phone", "message",
    "question", "answer", "report", "desk", "call", "late", "agree", "colleague",
    "project", "schedule", "document", "client", "appointment", "team", "send",
}

WORD_RE = re.compile(r"[A-Za-z']+")
POS_ZH = {
    "noun": "名词",
    "verb": "动词",
    "adjective": "形容词",
    "adverb": "副词",
    "determiner": "限定词",
    "pronoun": "代词",
    "preposition": "介词",
    "conjunction": "连词",
    "interjection": "感叹词",
    "number": "数词",
    "numeral": "数词",
    "modal": "情态动词",
    "auxiliary": "助动词",
    "article": "冠词",
    "exclamation": "感叹词",
}
CONTRACTIONS = {
    "don't",
    "i'm",
    "it's",
    "that's",
    "what's",
    "let's",
    "can't",
    "i'll",
    "you're",
    "we're",
    "they're",
    "isn't",
    "aren't",
    "didn't",
    "doesn't",
    "won't",
    "i've",
    "here's",
}


def lookup_keys(headword: str) -> list[str]:
    keys: list[str] = []
    for part in re.split(r"[/;]", headword):
        part = re.sub(r"\([^)]*\)", "", part).strip().lower()
        part = part.strip(" .")
        if part and part not in keys:
            keys.append(part)
    return keys


def display_of(headword: str) -> str:
    keys = lookup_keys(headword)
    if not keys:
        return headword.strip()
    if "/" not in headword and ";" not in headword:
        return headword.strip()
    return keys[0]


def pos_tokens(raw: str) -> list[str]:
    tokens: list[str] = []
    for chunk in raw.replace("/", " ").split(","):
        for token in chunk.split():
            token = token.strip().lower()
            if token.endswith("-verb"):
                token = "verb"
            if token and token not in tokens:
                tokens.append(token)
    return tokens


def pos_label(raw: str) -> str:
    labels = []
    for token in pos_tokens(raw):
        label = POS_ZH.get(token)
        if label and label not in labels:
            labels.append(label)
    return "、".join(labels)


ECDICT_POS = {
    "noun": {"n"},
    "verb": {"v", "vt", "vi"},
    "adjective": {"a", "adj"},
    "adverb": {"adv", "ad"},
    "pronoun": {"pron"},
    "preposition": {"prep"},
    "conjunction": {"conj"},
    "interjection": {"int", "interj"},
    "exclamation": {"int", "interj"},
    "determiner": {"art", "det"},
    "article": {"art"},
    "number": {"num"},
    "numeral": {"num"},
    "modal": {"aux", "v"},
    "auxiliary": {"aux"},
}


def clean_phonetic(raw: str) -> str:
    text = raw.strip().strip("/")
    return text.replace("\u04d9", "ə").replace("'", "ˈ").replace(":", "ː")


def gloss_lines(text: str) -> list[str]:
    text = text.replace("\\r", "").replace("\\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip() and not line.strip().startswith("[")]
    return [line for line in lines if "[计]" not in line]


def line_tag(line: str) -> str:
    match = re.match(r"^([A-Za-z]+)\.", line)
    return match.group(1).lower() if match else ""


POS_PRIORITY = [
    "interjection",
    "exclamation",
    "pronoun",
    "determiner",
    "article",
    "noun",
    "verb",
    "adjective",
    "adverb",
    "number",
    "numeral",
    "modal",
    "auxiliary",
    "preposition",
    "conjunction",
]


def gloss_usable(part: str) -> bool:
    if not re.search(r"[\u4e00-\u9fff]", part):
        return False
    if re.search(r"[A-Za-z\[\]]", part):
        return False
    if "计" in part[:2]:
        return False
    return True


def first_gloss(line: str) -> str:
    body = re.sub(r"^(?:[A-Za-z]+\.\s*)+", "", line)
    parts = [part.strip() for part in re.split(r"[;；,，]", body) if part.strip()]
    usable = [part for part in parts if gloss_usable(part)]
    if not usable:
        return ""
    return zhconv.convert(usable[0], "zh-cn")[:24]


def brief_zh(text: str, poses: list[str]) -> str:
    lines = gloss_lines(text)
    tokens = []
    for pos in poses:
        tokens.extend(pos_tokens(pos))
    ordered = sorted(tokens, key=lambda token: POS_PRIORITY.index(token) if token in POS_PRIORITY else 50)
    for token in ordered:
        tags = ECDICT_POS.get(token, set())
        for line in lines:
            if line_tag(line) in tags:
                gloss = first_gloss(line)
                if gloss:
                    return gloss
    for line in lines:
        gloss = first_gloss(line)
        if gloss:
            return gloss
    return ""


def load_spoken(path: Path) -> dict[str, int]:
    ranks: dict[str, int] = {}
    rank = 0
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        word = line.split(",")[0].split("\t")[0].strip().lower()
        if not word or word in {"word", "lemma"} or word.startswith("#"):
            continue
        rank += 1
        ranks.setdefault(word, rank)
    return ranks


def book_names(keys: list[str], topics: list[str], level: str) -> list[str]:
    blob = " ".join(topics).lower()
    keyset = set(keys)
    names: list[str] = []
    travel_topic = level in {"A1", "A2"} and any(hint in blob for hint in TRAVEL_TOPICS)
    business_topic = level in {"A1", "A2"} and any(hint in blob for hint in BUSINESS_TOPICS)
    if travel_topic or keyset & TRAVEL_WORDS:
        names.append("travel")
    if business_topic or keyset & BUSINESS_WORDS:
        names.append("business")
    return names


def load_cards(path: Path) -> list[dict]:
    grouped: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            level = (row.get("CEFR") or "").strip()
            if level not in {"A1", "A2", "B1"}:
                continue
            head = (row.get("headword") or "").strip()
            keys = lookup_keys(head)
            if not keys:
                continue
            topics = []
            for field in ("CoreInventory 1", "CoreInventory 2", "Threshold"):
                topic = (row.get(field) or "").strip()
                if topic and topic not in topics:
                    topics.append(topic)
            books = book_names(keys, topics, level)
            if level != "A1" and not books:
                continue
            display = display_of(head)
            card = grouped.get(display)
            if card is None:
                card = {
                    "headword": display,
                    "pos": [],
                    "keys": [],
                    "topics": [],
                    "books": [],
                    "cefr": level,
                }
                grouped[display] = card
            elif level == "A1":
                card["cefr"] = "A1"
            pos = (row.get("pos") or "").strip()
            if pos and pos not in card["pos"]:
                card["pos"].append(pos)
            for key in keys:
                if key not in card["keys"]:
                    card["keys"].append(key)
            for topic in topics:
                if topic not in card["topics"]:
                    card["topics"].append(topic)
            for book in books:
                if book not in card["books"]:
                    card["books"].append(book)
    return list(grouped.values())


def load_gloss(path: Path, wanted: set[str]) -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            word = (row.get("word") or "").strip().lower()
            if word not in wanted or word in found:
                continue
            raw = row.get("translation") or ""
            if not raw.strip():
                continue
            phonetic = clean_phonetic(row.get("phonetic") or "")
            found[word] = (phonetic, raw)
            if len(found) == len(wanted):
                break
    return found


def tokens(text: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(text)]


def allowed(token: str, known: set[str]) -> bool:
    if token in known or token in CONTRACTIONS:
        return True
    plain = token.replace("'", "")
    return plain in known


def has_inner_capital(text: str) -> bool:
    pieces = re.findall(r"[A-Za-z']+", text)
    for index, piece in enumerate(pieces):
        if index == 0 or piece == "I":
            continue
        if piece[0].isupper():
            return True
    return False


def load_tatoeba(path: Path, known: set[str]) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith((".txt", ".tsv", ".csv"))]
        if not names:
            raise RuntimeError(f"no text file inside {path.name}")
        name = max(names, key=lambda item: archive.getinfo(item).file_size)
        raw = archive.read(name).decode("utf-8-sig")
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        english, chinese = parts[0].strip(), parts[1].strip()
        attribution = parts[2].strip() if len(parts) > 2 else ""
        words = tokens(english)
        if not english or not chinese or not 1 <= len(words) <= 8:
            continue
        if has_inner_capital(english):
            continue
        if any(not allowed(word, known) for word in words):
            continue
        key = english.casefold()
        if key in seen:
            continue
        seen.add(key)
        rows.append((english, zhconv.convert(chinese, "zh-cn"), attribution))
    rows.sort(key=lambda item: (len(tokens(item[0])), len(item[0]), item[0].lower()))
    return rows[:240]


def main() -> None:
    spoken = load_spoken(RAW / "NGSL-Spoken_1.2.txt")
    cards = load_cards(RAW / "cefrj-vocabulary-profile-1.5.csv")
    wanted: set[str] = set()
    for card in cards:
        wanted.update(card["keys"])
    gloss = load_gloss(RAW / "ecdict.csv", wanted)

    ready = []
    missing = 0
    for card in cards:
        match = next((gloss[key] for key in card["keys"] if key in gloss), None)
        if match is None:
            missing += 1
            continue
        phonetic, raw_zh = match
        translation = brief_zh(raw_zh, card["pos"])
        if not translation:
            missing += 1
            continue
        if phonetic.lower().replace("ˈ", "").replace("ː", "") == card["headword"].lower():
            phonetic = ""
        ranks = [spoken[key] for key in card["keys"] if key in spoken]
        ready.append(
            {
                "headword": card["headword"],
                "pos": pos_label(",".join(card["pos"])),
                "phonetic": phonetic,
                "translation": translation,
                "spoken_rank": min(ranks) if ranks else None,
                "topics": " / ".join(card["topics"]),
                "books": " ".join(card["books"]),
                "cefr": card["cefr"],
            }
        )
    ready.sort(key=lambda item: (item["spoken_rank"] is None, item["spoken_rank"] or 0, item["headword"]))

    known = set(wanted)
    known.update(item["headword"].lower() for item in ready)
    sentences = load_tatoeba(RAW / "cmn-eng.zip", known)
    survival = json.loads(SURVIVAL.read_text(encoding="utf-8"))
    work = json.loads(WORK.read_text(encoding="utf-8"))

    if DB.exists():
        DB.unlink()
    connection = sqlite3.connect(DB)
    connection.executescript(
        """
        CREATE TABLE words (
            id INTEGER PRIMARY KEY,
            headword TEXT NOT NULL,
            pos TEXT NOT NULL,
            cefr TEXT NOT NULL,
            phonetic TEXT NOT NULL,
            translation TEXT NOT NULL,
            spoken_rank INTEGER,
            topics TEXT NOT NULL,
            books TEXT NOT NULL
        );
        CREATE TABLE sentences (
            id INTEGER PRIMARY KEY,
            english TEXT NOT NULL,
            chinese TEXT NOT NULL,
            pack TEXT NOT NULL,
            book TEXT NOT NULL,
            attribution TEXT NOT NULL
        );
        CREATE INDEX idx_words_head ON words(headword);
        CREATE INDEX idx_sentences_pack ON sentences(pack);
        """
    )
    connection.executemany(
        """
        INSERT INTO words (headword, pos, cefr, phonetic, translation, spoken_rank, topics, books)
        VALUES (:headword, :pos, :cefr, :phonetic, :translation, :spoken_rank, :topics, :books)
        """,
        ready,
    )
    connection.executemany(
        "INSERT INTO sentences (english, chinese, pack, book, attribution) VALUES (?, ?, 'survival', 'travel', '')",
        [(item["english"], item["chinese"]) for item in survival],
    )
    connection.executemany(
        "INSERT INTO sentences (english, chinese, pack, book, attribution) VALUES (?, ?, 'work', 'business', '')",
        [(item["english"], item["chinese"]) for item in work],
    )
    connection.executemany(
        "INSERT INTO sentences (english, chinese, pack, book, attribution) VALUES (?, ?, 'tatoeba', 'reading', ?)",
        sentences,
    )
    connection.commit()
    connection.close()
    spoken_hits = sum(1 for item in ready if item["spoken_rank"] is not None)
    travel_n = sum(1 for item in ready if "travel" in item["books"].split())
    business_n = sum(1 for item in ready if "business" in item["books"].split())
    print(f"words {len(ready)} (spoken {spoken_hits}, travel {travel_n}, business {business_n}, no Chinese {missing})")
    print(f"sentences travel {len(survival)} business {len(work)} reading {len(sentences)}")
    print(f"database {DB}")


if __name__ == "__main__":
    main()
