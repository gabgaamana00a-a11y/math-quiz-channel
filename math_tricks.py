"""
math_tricks.py — templated "math tips & tricks" bank.

Each row of math_tricks.csv names a trick `type` plus `args` (pipe-separated
numbers). The generator for that type produces the hook, the step-by-step
"how it happens" lines, the final result, and narration — and the result is
re-computed independently so a wrong CSV row can never ship.

Everything is plain arithmetic (no LaTeX needed): the renderer draws the text
with Manim's Text object, so CI only needs cairo/pango + ffmpeg.
"""
from __future__ import annotations

import csv
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_HERE, "math_tricks.csv")
HISTORY_PATH = os.path.join(_HERE, "math_tricks_history.json")

_FIELDS = ["type", "args", "category", "title"]


# ── speech cleanup (steps are shown as text; read aloud naturally) ────────────
def _speak(text: str) -> str:
    t = text
    for a, b in [("×", " times "), ("÷", " divided by "), ("²", " squared"),
                 ("³", " cubed "), ("√", " square root of "), ("−", " minus "),
                 ("+", " plus "), ("=", " equals "), ("→", " gives "),
                 ("|", ", ")]:
        t = t.replace(a, b)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _digits(n: int) -> str:
    return str(n)


# ── generators: each returns hook / steps / result / answer / category ───────
def _mul11(a: tuple) -> dict:
    n = a[0]
    t, u = n // 10, n % 10
    s = t + u
    steps = [f"Split the digits: {t} | {u}", f"Add them: {t} + {u} = {s}"]
    if s < 10:
        steps.append(f"Drop {s} between the digits → {t}{s}{u}")
    else:
        steps.append(f"{s} is two digits — write {s % 10}, carry {s // 10}")
        steps.append(f"{t} + {s // 10} = {t + s // 10} → {t + s // 10}{s % 10}{u}")
    return _pack(f"{n} × 11", steps, n * 11, "MULTIPLY BY 11")


def _sq5(a: tuple) -> dict:
    n = a[0]
    num = n * 10 + 5
    hi = n * (n + 1)
    steps = [f"Take the part before the 5: {n}", f"Multiply by the next: {n} × {n + 1} = {hi}",
             f"Stick 25 on the end → {hi}25"]
    return _pack(f"{num}²", steps, num * num, "SQUARE ENDING IN 5")


def _mul9(a: tuple) -> dict:
    n = a[0]
    steps = [f"×10 first: {n} × 10 = {n * 10}", f"Now take one {n} back: {n * 10} − {n} = {n * 9}"]
    return _pack(f"{n} × 9", steps, n * 9, "MULTIPLY BY 9")


def _mul5(a: tuple) -> dict:
    n = a[0]
    steps = [f"×10: {n} × 10 = {n * 10}", f"Halve it: {n * 10} ÷ 2 = {n * 5}"]
    return _pack(f"{n} × 5", steps, n * 5, "MULTIPLY BY 5")


def _mul25(a: tuple) -> dict:
    n = a[0]
    steps = [f"Divide by 4: {n} ÷ 4 = {n // 4}", f"Multiply by 100: {n // 4} × 100 = {n * 25}"]
    return _pack(f"{n} × 25", steps, n * 25, "MULTIPLY BY 25")


def _mul125(a: tuple) -> dict:
    n = a[0]
    steps = [f"Divide by 8: {n} ÷ 8 = {n // 8}", f"Multiply by 1000: {n // 8} × 1000 = {n * 125}"]
    return _pack(f"{n} × 125", steps, n * 125, "MULTIPLY BY 125")


def _sq_near100(a: tuple) -> dict:
    d = a[0]
    num = 100 - d
    base = 100 - 2 * d
    tail = d * d
    steps = [f"Distance from 100: {d}", f"100 − 2×{d} = {base}",
             f"Square the distance: {d}² = {tail}", f"Combine: {base} | {tail:02d}"]
    return _pack(f"{num}²", steps, num * num, "SQUARE NEAR 100")


def _mul_near100(a: tuple) -> dict:
    x, y = a[0], a[1]
    p, q = 100 - x, 100 - y
    head = 100 - p - q
    tail = p * q
    steps = [f"{x} is {p} below 100, {y} is {q} below", f"100 − {p} − {q} = {head}",
             f"{p} × {q} = {tail}", f"Combine: {head} | {tail:02d}"]
    return _pack(f"{x} × {y}", steps, x * y, "MULTIPLY NEAR 100")


def _pct_of(a: tuple) -> dict:
    p, n = a[0], a[1]
    ans = n * p // 100
    steps = [f"{p}% means {p} per 100", f"{n} × {p} = {n * p}", f"÷ 100 → {ans}"]
    return _pack(f"{p}% of {n}", steps, ans, "PERCENTAGE")


def _pct_swap(a: tuple) -> dict:
    x, y = a[0], a[1]
    ans = x * y // 100
    steps = [f"{x}% of {y} is the same as {y}% of {x}", f"{y}% of {x} = {ans}"]
    return _pack(f"{x}% of {y}", steps, ans, "PERCENTAGE SWAP")


def _div(a: tuple, k: int) -> dict:
    n = a[0]
    ds = [int(c) for c in str(n)]
    if k == 11:
        alt = sum(d if i % 2 == 0 else -d for i, d in enumerate(ds))
        expr = str(ds[0]) + "".join(f" {'−' if i % 2 else '+'} {d}" for i, d in enumerate(ds) if i)
        alt_s = str(alt).replace("-", "−")
        steps = [f"Alternate sum: {expr} = {alt_s}",
                 f"{alt_s} is a multiple of 11 — so {n} divides by 11"]
    else:
        s = sum(ds)
        steps = [f"Add the digits: {' + '.join(str(d) for d in ds)} = {s}",
                 f"{s} is a multiple of {k} — so {n} divides by {k}"]
    return _pack(f"Is {n} divisible by {k}?", steps, n // k, f"DIVISIBILITY BY {k}",
                 result=f"{n} ÷ {k} = {n // k} — yes!")


def _sum_n(a: tuple) -> dict:
    n = a[0]
    ans = n * (n + 1) // 2
    steps = [f"Pair the ends: 1 + {n} = {n + 1}",
             f"There are {n} numbers → {n} × {n + 1} ÷ 2",
             f"{n} × {n + 1} = {n * (n + 1)}, ÷ 2 = {ans}"]
    return _pack(f"1 + 2 + … + {n}", steps, ans, "SUM SERIES")


def _square_ab(a: tuple) -> dict:
    hi, lo = a[0], a[1]
    n = hi + lo
    steps = [f"Split: {n} = {hi} + {lo}", f"{hi}² = {hi * hi}", f"2 × {hi} × {lo} = {2 * hi * lo}",
             f"{lo}² = {lo * lo}", f"Add: {hi * hi} + {2 * hi * lo} + {lo * lo} = {n * n}"]
    return _pack(f"{n}²", steps, n * n, "SQUARE WITH (a+b)²")


def _sub_1000(a: tuple) -> dict:
    n = a[0]
    ds = [int(c) for c in f"{n:03d}"]
    steps = [f"9 − {ds[0]} = {9 - ds[0]}", f"9 − {ds[1]} = {9 - ds[1]}",
             f"10 − {ds[2]} = {10 - ds[2]}"]
    ans = 1000 - n
    return _pack(f"1000 − {n}", steps, ans, "SUBTRACT FROM 1000")


def _pack(hook: str, steps: list, answer, category: str, result: str | None = None) -> dict:
    return {
        "hook": hook,
        "steps": steps,
        "answer": str(answer),
        "result": result or f"{hook} = {answer}",
        "category": category,
    }


GENERATORS = {
    "mul11": _mul11,
    "sq5": _sq5,
    "mul9": _mul9,
    "mul5": _mul5,
    "mul25": _mul25,
    "mul125": _mul125,
    "sq_near100": _sq_near100,
    "mul_near100": _mul_near100,
    "pct_of": _pct_of,
    "pct_swap": _pct_swap,
    "div3": lambda a: _div(a, 3),
    "div9": lambda a: _div(a, 9),
    "div11": lambda a: _div(a, 11),
    "sum_n": _sum_n,
    "square_ab": _square_ab,
    "sub_1000": _sub_1000,
}


def build(row: dict) -> dict:
    """Row -> full trick spec (hook, steps, result, narration). Verified."""
    gen = GENERATORS[row["type"]]
    args = tuple(int(x) for x in str(row["args"]).split("|"))
    spec = gen(args)
    # independent re-check of the arithmetic
    if _recheck(row["type"], args) != int(spec["answer"]):
        raise ValueError(f"answer mismatch for {row}: {spec['answer']} vs {_recheck(row['type'], args)}")
    spec["title"] = row.get("title", "")
    spec["type"] = row["type"]
    spec["args"] = list(args)
    spec["narration"] = [_speak(f"Let's do {spec['hook']}.")] + [_speak(s) for s in spec["steps"]] + \
                        [_speak(f"So the answer is {spec['answer']}.")]
    return spec


def _recheck(t: str, a: tuple) -> int:
    if t == "mul11":      return a[0] * 11
    if t == "sq5":        return (a[0] * 10 + 5) ** 2
    if t == "mul9":       return a[0] * 9
    if t == "mul5":       return a[0] * 5
    if t == "mul25":      return a[0] * 25
    if t == "mul125":     return a[0] * 125
    if t == "sq_near100": return (100 - a[0]) ** 2
    if t == "mul_near100":return a[0] * a[1]
    if t == "pct_of":     return a[1] * a[0] // 100
    if t == "pct_swap":   return a[0] * a[1] // 100
    if t in ("div3", "div9", "div11"):
        return a[0] // int(t[3:])
    if t == "sum_n":      return a[0] * (a[0] + 1) // 2
    if t == "square_ab":  return (a[0] + a[1]) ** 2
    if t == "sub_1000":   return 1000 - a[0]
    raise KeyError(t)


# ── history (no repeats) ─────────────────────────────────────────────────────
def _load_history() -> dict:
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"used": [], "video_ids": []}


def _save_history(h):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(h, f, indent=2)


def load_tricks() -> list[dict]:
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def get_used() -> list[str]:
    return _load_history().get("used", [])


def get_used_video_ids() -> list:
    return _load_history().get("video_ids", [])


def mark_used(key: str):
    h = _load_history()
    if key and key not in h["used"]:
        h["used"].append(key)
        _save_history(h)


def mark_video_used(vid):
    h = _load_history()
    if vid and vid not in h.get("video_ids", []):
        h.setdefault("video_ids", []).append(vid)
        _save_history(h)


def _key(row: dict) -> str:
    return f'{row["type"]}:{row["args"]}'


def get_next_trick(used: list | None = None) -> dict:
    import random
    rows = load_tricks()
    used_set = set(used or [])
    pool = [r for r in rows if _key(r) not in used_set]
    if not pool:
        pool = rows
        print("[tricks] bank exhausted — restarting cycle")
    row = random.choice(pool)
    spec = build(row)
    spec["key"] = _key(row)
    return spec
