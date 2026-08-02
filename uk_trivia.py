"""
uk_trivia.py  —  CSV-driven UK trivia question bank for the quiz card pipeline.

Reads questions from uk_trivia.csv (question + 4 options + correct answer +
explanation + category + unique UK-targeted YouTube title) and serves them one
at a time WITHOUT repeats using a persistent history file
(uk_trivia_history.json).

Each row is converted into the quiz_data dict expected by
quiz_renderer.create_quiz_video(), which renders a 1080x1920 short with a
question card, A-D choices, a 3-2-1 countdown, and a comment CTA card.
"""
import csv
import json
import os
import random

_HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_HERE, "uk_trivia.csv")
HISTORY_PATH = os.path.join(_HERE, "uk_trivia_history.json")

_FIELDS = ["question", "option_a", "option_b", "option_c", "option_d",
           "correct_answer", "explanation", "category", "title"]

# Pexels photo query for the centre image, per category.
CATEGORY_IMAGE_QUERY = {
    "UK GEOGRAPHY":   "london skyline landmark",
    "LONDON":         "big ben london",
    "UK HISTORY":     "ancient castle stone",
    "ROYAL FAMILY":   "royal crown palace",
    "FOOD & DRINK":   "afternoon tea cups",
    "UK SPORT":       "football stadium pitch",
    "UK TV & FILM":   "film cinema camera",
    "UK MUSIC":       "guitar stage concert",
}
_DEFAULT_IMAGE = "london city britain"

# Pexels background VIDEO query, per category.
CATEGORY_BG_QUERY = {
    "UK GEOGRAPHY":   "london aerial city",
    "LONDON":         "london night lights",
    "UK HISTORY":     "stone castle historic",
    "ROYAL FAMILY":   "elegant palace interior",
    "FOOD & DRINK":   "cozy cafe tea",
    "UK SPORT":       "stadium floodlights",
    "UK TV & FILM":   "cinema neon lights",
    "UK MUSIC":       "concert crowd lights",
}
_DEFAULT_BG = "dark city skyline night"


def load_questions() -> list[dict]:
    """Read every row of uk_trivia.csv as a dict with _FIELDS keys."""
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _load_history() -> dict:
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"questions": [], "video_ids": []}


def _save_history(history: dict):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def build_quiz_data(row: dict) -> dict:
    """Convert one CSV row into quiz_data for quiz_renderer.create_quiz_video."""
    category = (row.get("category") or "").strip()
    question = (row.get("question") or "").strip()
    return {
        "question":       question,
        "options": {
            "A": (row.get("option_a") or "").strip(),
            "B": (row.get("option_b") or "").strip(),
            "C": (row.get("option_c") or "").strip(),
            "D": (row.get("option_d") or "").strip(),
        },
        "correct_answer": (row.get("correct_answer") or "").strip().upper(),
        "explanation":    (row.get("explanation") or "").strip(),
        "category":       category or "UK TRIVIA",
        "title":          (row.get("title") or "").strip(),
        "image_query":    CATEGORY_IMAGE_QUERY.get(category, _DEFAULT_IMAGE),
        "bg_query":       CATEGORY_BG_QUERY.get(category, _DEFAULT_BG),
    }


def get_next_question(used_questions: list | None = None) -> dict:
    """Return quiz_data for a random question not yet used (no repeats).

    used_questions: list of already-posted question texts. When the bank runs
    out (never within 6 months at 3/day), it falls back to the full bank so the
    pipeline never crashes.
    """
    questions = load_questions()
    used = {q.strip() for q in (used_questions or [])}
    pool = [row for row in questions if (row.get("question") or "").strip() not in used]
    if not pool:
        pool = questions
        print("[uk_trivia] WARNING: question bank exhausted — restarting cycle.")
    row = random.choice(pool)
    return build_quiz_data(row)


def get_used_questions() -> list[str]:
    return _load_history().get("questions", [])


def mark_used(question_text: str):
    """Persist a question text so it is never picked again."""
    history = _load_history()
    if question_text and question_text not in history["questions"]:
        history["questions"].append(question_text)
        _save_history(history)


def get_used_video_ids() -> list:
    return _load_history().get("video_ids", [])


def mark_video_used(video_id):
    """Persist a Pexels video id so background clips are never reused."""
    history = _load_history()
    if video_id and video_id not in history.get("video_ids", []):
        history.setdefault("video_ids", []).append(video_id)
        _save_history(history)


# ── Viral post copy (no LLM — deterministic UK trivia templates) ──────────────
_UK_TITLES = [
    "How British are you really? 🇬🇧",
    "99% of Brits get this WRONG 🇬🇧",
    "Only true Brits know this 🤔",
    "The UK quiz that stumps everyone 🇬🇧",
    "Are you smarter than the average Brit? 🇬🇧",
    "This UK trivia question is harder than it looks 😅",
    "Test your British knowledge! 🇬🇧",
    "Can you pass this UK quiz? 🧠",
    "Most Brits fail this — do you? 🇬🇧",
    "Think you know the UK? Prove it! 🇬🇧",
    "The British question everyone argues about 😤",
    "How well do you really know Britain? 🇬🇧",
    "This UK fact will surprise you 🇬🇧",
    "Do you know your own country? 🇬🇧",
    "The UK trivia trap that fools everyone 🤯",
]

_UK_HASHTAGS = ("#UKtrivia #trivia #quiz #UK #British #britain #britishquiz "
                "#quiztime #generalknowledge #triviatime #funfacts #ukfacts "
                "#london #england #scotland #wales #northernireland #shorts "
                "#youtubeshorts #learnontiktok #brainteaser #viral")


def generate_uk_post_txt(quiz_data: dict, output_dir: str) -> str:
    """Write post.txt (title / description / hashtags) for a UK trivia video.

    Title comes from the per-question CSV `title` column (unique, UK-targeted,
    high CTR). Falls back to a rotating template if the CSV has no title.
    """
    import hashlib as _hl
    question = quiz_data.get("question", "How British are you?")
    category = quiz_data.get("category", "UK TRIVIA")
    title = quiz_data.get("title") or ""
    if not title:
        _q_hash = int(_hl.md5(question.encode()).hexdigest(), 16)
        title = _UK_TITLES[_q_hash % len(_UK_TITLES)]

    description = (
        f"{question}\n\n"
        f"🇬🇧 Test your British knowledge! Drop your answer (A, B, C or D) in the "
        f"comments below.\n\n"
        f"Category: {category}\n\n"
        f"New UK trivia every day — 3 challenges daily. Subscribe so you never miss one!"
    )
    txt = (
        f"TITLE\n{title}\n\n"
        f"DESCRIPTION\n{description}\n\n"
        f"HASHTAGS\n{_UK_HASHTAGS}\n"
    )
    out_path = os.path.join(output_dir, "post.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[uk_trivia] post.txt written → {out_path}")
    return out_path
