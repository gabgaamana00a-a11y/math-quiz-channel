"""Generate math_tricks.csv (type, args, category, title) and verify every row."""
import csv
import hashlib
import itertools
import os

import math_tricks as mt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "math_tricks.csv")

TITLE_TPLS = [
    "{hook} in 3 seconds — try it ⏱️",
    "Can you do {hook} in your head? ⚡",
    "The {hook} trick nobody teaches 🤯",
    "Solve {hook} instantly 🧠",
    "{hook} — mental math shortcut ⚡",
    "No calculator needed for {hook} 🚫",
    "How to do {hook} fast ✅",
    "{hook} the easy way 🧠",
    "This {hook} hack feels illegal 🤯",
    "Do {hook} before the timer ⏱️",
]


def rows_for(type_id, arg_list, category):
    return [{"type": type_id, "args": "|".join(str(x) for x in args), "category": category}
            for args in arg_list]


def build_pools():
    rows = []
    rows += rows_for("mul11", [(n,) for n in range(12, 12 + 50)], "MULTIPLY BY 11")
    rows += rows_for("sq5", [(n,) for n in range(1, 41)], "SQUARE ENDING IN 5")
    rows += rows_for("mul9", [(n,) for n in range(12, 12 + 45)], "MULTIPLY BY 9")
    rows += rows_for("mul5", [(n,) for n in range(12, 12 + 70, 2)], "MULTIPLY BY 5")
    rows += rows_for("mul25", [(n,) for n in range(4, 4 + 25 * 4, 4)], "MULTIPLY BY 25")
    rows += rows_for("mul125", [(n,) for n in range(8, 8 + 18 * 8, 8)], "MULTIPLY BY 125")
    rows += rows_for("sq_near100", [(d,) for d in range(1, 13)], "SQUARE NEAR 100")
    rows += rows_for("mul_near100", [(x, y) for x, y in itertools.product(range(92, 100), repeat=2)][:55],
                     "MULTIPLY NEAR 100")
    pct = [(p, n) for p in (5, 10, 15, 20, 25, 30, 40, 50, 75)
           for n in range(20, 420, 40)][:55]
    rows += rows_for("pct_of", pct, "PERCENTAGE")
    swap = [(x, y) for x in (4, 8, 12, 16, 20, 24, 28, 32, 36, 44)
            for y in (25, 50, 20, 10, 75) if (x * y) % 100 == 0][:35]
    rows += rows_for("pct_swap", swap, "PERCENTAGE SWAP")
    rows += rows_for("div3", [(n,) for n in range(120, 120 + 40 * 3, 3)], "DIVISIBILITY BY 3")
    rows += rows_for("div9", [(n,) for n in range(126, 126 + 25 * 9, 9)], "DIVISIBILITY BY 9")
    rows += rows_for("div11", [(n,) for n in range(121, 121 + 22 * 11, 11)], "DIVISIBILITY BY 11")
    rows += rows_for("sum_n", [(n,) for n in range(10, 55)], "SUM SERIES")
    rows += rows_for("square_ab", [(hi, lo) for hi in range(10, 100, 10) for lo in range(1, 10)][:35],
                     "SQUARE WITH (a+b)²")
    rows += rows_for("sub_1000", [(n,) for n in range(147, 147 + 25 * 3, 3)], "SUBTRACT FROM 1000")

    # de-dupe on (type,args)
    seen, out = set(), []
    for r in rows:
        k = f'{r["type"]}:{r["args"]}'
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def assign_titles(rows):
    used = set()
    for r in rows:
        h = int(hashlib.md5(f'{r["type"]}:{r["args"]}'.encode()).hexdigest(), 16)
        hook = mt.GENERATORS[r["type"]](tuple(int(x) for x in r["args"].split("|")))["hook"]
        cands = [TITLE_TPLS[(h + i) % len(TITLE_TPLS)].format(hook=hook) for i in range(len(TITLE_TPLS))]
        cands += [f'{r["category"].title()}: ' + c for c in cands[:4]]
        title = next((c for c in cands if c not in used and len(c) <= 95), None)
        if title is None:
            n = 2
            while f"{hook} #{n}" in used:
                n += 1
            title = f"{hook} #{n}"
        used.add(title)
        r["title"] = title


def main():
    rows = build_pools()
    assign_titles(rows)
    # verify every row builds without an arithmetic error
    for r in rows:
        mt.build(r)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=mt._FIELDS)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    c = Counter(r["type"] for r in rows)
    print(f"rows: {len(rows)} | unique titles: {len({r['title'] for r in rows})} | types: {len(c)}")
    for t, n in c.most_common():
        print(f"  {n:3d}  {t}")
    print("\nsamples:")
    for r in rows[:8]:
        s = mt.build(r)
        print(f"  {r['title']}\n     hook: {s['hook']} -> {s['result']}")


if __name__ == "__main__":
    main()
