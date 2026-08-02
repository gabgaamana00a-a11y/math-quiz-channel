"""
generate_uk_titles.py  —  add a unique UK-targeted, high-CTR YouTube title to
every row of uk_trivia.csv (deterministic per question, so re-runs are stable).

Recipe:
  • UK-targeted hooks (🇬🇧, "Brits", "Britain", "UK", "British")
  • High-CTR triggers: numbers, "only 1%", "fail/get wrong", "test", "can you",
    "how well do you know", curiosity gaps
  • Each title embeds a per-question entity keyword {k} and/or subject noun {s}
    so the unique-title space is huge; a collision-resolver guarantees 100%
    uniqueness across all rows.
"""
import csv
import hashlib
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "uk_trivia.csv")
TITLE_COL = "title"

# ── Templates ────────────────────────────────────────────────────────────────
# {k} = entity keyword, {c} = category label, {s} = subject noun.
TEMPLATES = [
    # Static UK high-CTR ────────────────────────────────────────────────────
    "Only 1% of Brits get this right 🇬🇧",
    "99% of Brits fail this — will you? 🇬🇧",
    "Are you smarter than the average Brit? 🇬🇧",
    "How British are you really? 🇬🇧",
    "Only true Brits know this one 🇬🇧",
    "The UK quiz that stumps everyone 🇬🇧",
    "Test your British knowledge! 🇬🇧",
    "Can you pass this UK test? 🇬🇧",
    "Most Brits get this WRONG 🇬🇧",
    "Think you know the UK? Prove it 🇬🇧",
    "This UK question fools 9 out of 10 Brits 🤯",
    "How well do you really know Britain? 🇬🇧",
    "The British question everyone argues about 🇬🇧",
    "Do you know your own country? 🇬🇧",
    "The UK trivia trap that fools everyone 🇬🇧",
    "Can you beat the average Brit? 🇬🇧",
    "This British fact will surprise you 🇬🇧",
    "What every Brit should know 🇬🇧",
    "The UK test 90% fail 🇬🇧",
    "Is your British knowledge up to scratch? 🇬🇧",
    "The British trivia nobody agrees on 🇬🇧",
    "99% can't answer this British question 🇬🇧",
    "Are you a true Brit? Prove it 🇬🇧",
    "The UK quiz that divides the internet 🇬🇧",
    "Only a real Brit knows the answer 🇬🇧",
    "How sharp is your UK knowledge? 🇬🇧",
    "This British question has people arguing 🇬🇧",
    "Test how British you really are 🇬🇧",
    "The UK fact everyone gets wrong 🇬🇧",
    "Can you outsmart the average Brit? 🇬🇧",
    "Your British IQ is about to be tested 🇬🇧",
    "This UK question breaks brains 🇬🇧",
    "Be honest — would YOU pass this? 🇬🇧",
    "The British quiz making the internet talk 🇬🇧",
    "One question every Brit gets wrong 🇬🇧",
    "You're not as British as you think 🇬🇧",
    "The UK trivia 95% miss 🇬🇧",
    "Britain's hardest question? 🇬🇧",
    "This UK question stumps geniuses 🇬🇧",
    "How British is your brain? 🇬🇧",
    "Only sharp minds pass this UK quiz 🇬🇧",
    "The UK question that stops people mid-scroll 🇬🇧",
    "Could you pass this British test? 🇬🇧",
    "Britain vs you — who wins? 🇬🇧",
    "The British question everyone thinks they know 🇬🇧",
    "Be proud if you get this one 🇬🇧",
    "The UK quiz tripping up grown adults 🇬🇧",
    "How quickly can you solve this UK quiz? 🇬🇧",
    # Category-based ────────────────────────────────────────────────────────
    "{c} quiz — only Brits pass 🇬🇧",
    "How well do you know {c}? 🇬🇧",
    "The {c} question that fools everyone 🇬🇧",
    "Test your {c} knowledge 🇬🇧",
    "{c} trivia — most Brits fail 🇬🇧",
    "The {c} quiz stumping the internet 🇬🇧",
    "What do you really know about {c}? 🇬🇧",
    # Keyword-based (embed the per-question entity) ─────────────────────────
    "How well do you know {k}? 🇬🇧",
    "The {k} question everyone gets wrong 🇬🇧",
    "Only 1% of Brits know {k} 🇬🇧",
    "Can you pass the {k} test? 🇬🇧",
    "Do you really know {k}? 🇬🇧",
    "The {k} trivia trap 🇬🇧",
    "Britain's {k} question — can you answer? 🇬🇧",
    "Most Brits don't know {k} 🇬🇧",
    "Think you know {k}? Prove it 🇬🇧",
    "The {k} quiz that stumps everyone 🇬🇧",
    "Only true Brits know {k} 🇬🇧",
    "The {k} question 90% miss 🇬🇧",
    "How well do you remember {k}? 🇬🇧",
    "The truth about {k} most Brits miss 🇬🇧",
    "{k} — do you really know it? 🇬🇧",
    "The {k} test only 1 in 100 pass 🇬🇧",
    "What's the deal with {k}? 🇬🇧",
    "Brits argue about {k} all the time 🇬🇧",
    "The {k} quiz that went viral 🇬🇧",
    "Only sharp Brits know {k} 🇬🇧",
    # Subject-based (embed the thing the question asks about) ───────────────
    "The {s} question that fools everyone 🇬🇧",
    "Only 1% of Brits know this {s} 🇬🇧",
    "The UK {s} test — can you pass? 🇬🇧",
    "Most Brits get this {s} wrong 🇬🇧",
    "The {s} quiz that stumps everyone 🇬🇧",
    "Think you know this {s}? 🇬🇧",
    "The British {s} question everyone argues about 🇬🇧",
    "{s} trivia — most Brits fail 🇬🇧",
    "How well do you know the {s}? 🇬🇧",
    "The {s} everyone gets wrong 🇬🇧",
]

_BAD_KEYWORDS = {"king", "queen", "day", "times", "area", "city", "island",
                 "country", "question", "answer", "year", "it", "them"}

_ENTITY_ALIASES = {
    "united kingdom":   "the UK",
    "great britain":    "Britain",
    "northern ireland": "Northern Ireland",
    "republic of ireland": "Ireland",
    "uk":               "the UK",
}

# Nationality/descriptive adjectives never picked as the primary entity.
_NAT_ADJ = {"british", "english", "scottish", "welsh", "irish", "celtic",
            "southern", "northern", "eastern", "western", "roman", "victorian",
            "tudor", "georgian", "edwardian"}

_LEADING = re.compile(
    r"^(in which|which of these|which one|which of|which|what is|what are|"
    r"what|who is|who are|who|where|when|how many|how much|how well|how old|"
    r"how|whose|what's)\s+", re.I)

_PREP = re.compile(
    r"\s+(?:of|in|on|at|for|from|by|with|about|between|during|against|"
    r"through|along|across|past|inside|outside|called|named|nicknamed|"
    r"known\s+as|belongs\s+to)\s+", re.I)

_STOP = {"the", "a", "an", "is", "are", "was", "were", "of", "in", "on", "at",
         "for", "from", "to", "by", "with", "about", "and", "or", "known",
         "called", "named", "also", "as", "its", "it", "this", "that", "has",
         "have", "be", "been", "did", "does", "do", "not", "no", "all", "most",
         "which", "what", "who", "into", "onto", "around", "after", "before",
         "under", "over", "up", "down", "out"}


# Words that are verbs/adjectives/superlatives — never part of a subject noun.
_VERBS_ADJ = {"released", "sang", "wrote", "played", "starred", "hosted",
              "founded", "became", "known", "called", "named", "nicknamed",
              "located", "flows", "runs", "built", "carried", "carries",
              "crosses", "connects", "borders", "lies", "sits", "stands",
              "won", "held", "took", "made", "created", "discovered",
              "invented", "used", "lives", "owned", "largest", "biggest",
              "highest", "oldest", "longest", "smallest", "deepest",
              "tallest", "most", "first", "last", "second", "next",
              "famous", "current", "official", "traditional", "only",
              "few", "many", "much", "between", "during", "against",
              "flows"}


def _extract_keyword(question: str) -> str:
    q = question.rstrip("?").strip()
    q = _LEADING.sub("", q, count=1)

    # Longest proper-noun run, skipping single nationality adjectives.
    caps = re.findall(r"\b[A-Z][a-zA-Z'\-]*(?:\s+[A-Z][a-zA-Z'\-]*){0,3}\b", q)
    caps = [c for c in caps if not (len(c.split()) == 1 and c.lower() in _NAT_ADJ)]
    if caps:
        kw = max(caps, key=lambda s: (len(s.split()), len(s)))
        kw = re.sub(r"['’]s$", "", kw)
    else:
        # Last segment after a preposition.
        entity = _PREP.split(q)[-1].strip().rstrip(".")
        words = [w for w in entity.split() if w.lower() not in _STOP and not w.isdigit()]
        kw = " ".join(words[:2]).strip() if words else ""
        if not kw:
            tail = [w for w in q.split() if w.lower() not in _STOP and not w.isdigit()]
            kw = " ".join(tail[-2:]).strip()
    kw = kw.strip()
    key = kw.lower()
    if key in _ENTITY_ALIASES:
        kw = _ENTITY_ALIASES[key]
    return kw or "Britain"


def _extract_subject(question: str) -> str:
    """First 1-2 lowercase common nouns — the thing the question asks about."""
    q = question.rstrip("?").strip()
    q = _LEADING.sub("", q, count=1)
    out = []
    for w in q.split():
        wc = w.rstrip(".,;!?").lower()
        if (wc in _NAT_ADJ or wc in _STOP or wc in _VERBS_ADJ
                or w[0].isupper() or wc.isdigit()):
            continue
        out.append(w.rstrip(".,;!?"))
        if len(out) >= 2:
            break
    return " ".join(out).strip()


def _usable_keyword(kw: str) -> bool:
    if not kw or kw.lower() in _BAD_KEYWORDS:
        return False
    if kw.lower() == "the uk":
        return True
    first = kw.split()[0]
    return first[0].isupper() or first[0].isdigit()


def _pretty_category(cat: str) -> str:
    words = []
    for w in cat.split():
        if w.upper() in {"UK", "TV"}:
            words.append(w.upper())
        elif w == "&":
            words.append(w)
        else:
            words.append(w.capitalize())
    return " ".join(words)


def _title_for(row: dict, used: set) -> str:
    q = row["question"]
    h = int(hashlib.md5(q.encode()).hexdigest(), 16)
    kw = _extract_keyword(q)
    s = _extract_subject(q)
    ok_kw = _usable_keyword(kw)
    ok_s = bool(s)
    cat = _pretty_category(row.get("category", "UK TRIVIA"))

    def _build(t):
        try:
            title = re.sub(r"\bthe\s+the\b", "the",
                           " ".join(t.format(k=kw, c=cat, s=s).split()), flags=re.I)
            return title[:1].upper() + title[1:] if title else ""
        except (KeyError, IndexError):
            return ""

    for off in range(len(TEMPLATES)):
        t = TEMPLATES[(h + off) % len(TEMPLATES)]
        if "{k}" in t and not ok_kw:
            continue
        if "{s}" in t and not ok_s:
            continue
        title = _build(t)[:70].rstrip()
        if title and title not in used:
            used.add(title)
            return title
    # Absolute last resort: combine entity + subject for a natural unique title.
    kk = kw if ok_kw else "Britain"
    ss = s if ok_s else "quiz"
    base = TEMPLATES[h % len(TEMPLATES)]
    base = _build(base)
    title = f"{base} — {kk} {ss} 🇬🇧" if base else f"The {ss} — {kk} 🇬🇧"
    title = re.sub(r"\s+", " ", title).strip()
    title = title[:1].upper() + title[1:] if title else title
    title = title[:70].rstrip()
    n = 0
    while title in used:
        n += 1
        title = f"{title[:-1]}" if len(title) > 1 else f"UK trivia {n} 🇬🇧"
    used.add(title)
    return title


def main():
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0].keys()) if rows else []
    if TITLE_COL not in fields:
        fields.append(TITLE_COL)

    used = set()
    for row in rows:
        row[TITLE_COL] = _title_for(row, used)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    kw_used = sum(1 for r in rows if _usable_keyword(_extract_keyword(r["question"])))
    s_used = sum(1 for r in rows if _extract_subject(r["question"]))
    print(f"Rows: {len(rows)} | Unique titles: {len(used)}")
    print(f"Keyword-usable: {kw_used} | Subject-usable: {s_used}")
    print(f"Max title length: {max(len(r[TITLE_COL]) for r in rows)} chars")
    print("\nSamples:")
    for r in rows[:16]:
        print(f"  [{r['category']:12s}] {r['title']}")


if __name__ == "__main__":
    main()
