"""
trick_scene.py - Manim scene for one math-trick short (vertical 1080x1920).

The spec (type, args, hook, steps, result, durs) is read from the JSON file named
by $TRICK_SPEC. Every step of narration gets its own visual; the scene clock is
re-synced to the narration after each step so video never drifts from audio.
Text only (no LaTeX) so CI needs just cairo/pango + ffmpeg.
"""
import json
import math
import os
import random

import numpy as np
from manim import *

config.frame_width = 9.0
config.frame_height = 16.0

FONT = "DejaVu Sans"
BG = "#0B1533"
PANEL = "#16224A"
EDGE = "#3B4E9A"
C_MAIN = "#7FD8FF"
C_HI = "#FFD34D"
C_GOOD = "#5CE08A"
C_BAD = "#FF6B7A"
C_ORANGE = "#FF9F43"
GREY = "#8C97C4"
FPS = 1 / 30


# ── building blocks ───────────────────────────────────────────────────────────
def T(s, size=48, color=WHITE, bold=True):
    return Text(str(s), font=FONT, font_size=size, color=color,
                weight=BOLD if bold else NORMAL)


def fit(m, w=None, h=None):
    if w is not None and m.width > w:
        m.scale_to_fit_width(w)
    if h is not None and m.height > h:
        m.scale_to_fit_height(h)
    return m


def wrap(s, limit=28):
    if len(s) <= limit or " " not in s:
        return s
    mid = len(s) // 2
    i = min((k for k, c in enumerate(s) if c == " "), key=lambda k: abs(k - mid))
    return s[:i] + "\n" + s[i + 1:]


def card(txt, size=100, color=WHITE, w=1.7, h=2.2, fill=PANEL, stroke=EDGE):
    box = RoundedRectangle(corner_radius=0.25, width=w, height=h)
    box.set_fill(fill, 1).set_stroke(stroke, 4)
    t = fit(T(txt, size, color), w=w - 0.3, h=h - 0.3)
    t.move_to(box)
    return VGroup(box, t)


def retext(c, s, size=100, color=WHITE):
    new = fit(T(s, size, color), w=c[0].width - 0.3, h=c[0].height - 0.3)
    new.move_to(c[0])
    return new


def count_anim(c, a, b, size, color=WHITE, pad=0):
    """Number inside card `c` ticks from a to b."""
    def upd(m, alpha):
        v = int(round(a + (b - a) * alpha))
        s = str(v).zfill(pad) if v >= 0 else str(v).replace("-", "\u2212")
        new = fit(T(s, size, color), w=m[0].width - 0.3, h=m[0].height - 0.3)
        new.move_to(m[0])
        m.submobjects[1] = new
    return UpdateFromAlphaFunc(c, upd)


class Chain:
    """Vertical calculation flow: node -> (badge on arrow) -> node ..."""

    def __init__(self, sc, ys, size=88, w=6.4, h=1.5):
        self.sc, self.ys, self.size, self.w, self.h = sc, ys, size, w, h
        self.nodes, self.vals = [], []

    def first(self, v):
        c = card(v, self.size, WHITE, self.w, self.h).move_to(UP * self.ys[0])
        self.nodes.append(c)
        self.vals.append(v)
        return c

    def step(self, label, new, kind="count", color=C_MAIN):
        sc = self.sc
        i = len(self.nodes)
        prev, a = self.nodes[-1], self.vals[-1]
        node = card(a, self.size, color, self.w, self.h).move_to(UP * self.ys[i])
        arrow = Arrow(prev.get_bottom() + DOWN * 0.05, node.get_top() + UP * 0.05,
                      buff=0, color=C_HI, stroke_width=8, tip_length=0.28,
                      max_tip_length_to_length_ratio=0.6)
        badge = card(label, 36, C_HI, w=2.3, h=0.7).move_to(arrow.get_center() + RIGHT * 2.0)
        sc.beat(GrowArrow(arrow), FadeIn(badge, shift=LEFT * 0.3),
                FadeIn(node, shift=DOWN * 0.3), rt=0.6)
        if kind == "zeros":
            k = len(str(new)) - len(str(a))
            txt = fit(T(str(new), self.size, color), w=self.w - 0.3, h=self.h - 0.3)
            txt.move_to(node[0])
            txt[len(str(new)) - k:].set_color(C_HI)
            sc.beat(Transform(node[1], txt), rt=0.8)
        else:
            sc.beat(count_anim(node, a, new, self.size, color), rt=0.9)
        self.nodes.append(node)
        self.vals.append(new)
        return node


# ── per-trick visuals: each returns one closure per narration step ───────────
def v_flow(sc, n, ops):
    ch = Chain(sc, [3.0, 0.5, -2.0])

    def s0():
        sc.beat(FadeIn(ch.first(n), shift=DOWN * 0.3), rt=0.5)
        ch.step(*ops[0])

    def s1():
        ch.step(*ops[1], color=C_GOOD)
    return [s0, s1]


def v_mul11(sc, a):
    n = a[0]
    t, u = n // 10, n % 10
    s = t + u
    carry = s >= 10
    cy = 1.8
    L, R = LEFT * 2.35 + UP * cy, RIGHT * 2.35 + UP * cy
    ct = card(t, 120, C_MAIN, h=2.3).move_to(LEFT * 1.0 + UP * cy)
    cu = card(u, 120, C_ORANGE, h=2.3).move_to(RIGHT * 1.0 + UP * cy)
    st = {}

    def s0():
        sc.beat(FadeIn(ct, shift=DOWN * 0.4), FadeIn(cu, shift=DOWN * 0.4), rt=0.6)
        sc.beat(ct.animate.move_to(L), cu.animate.move_to(R), rt=0.6)

    def s1():
        bub = Circle(radius=1.0, color=C_HI, stroke_width=6).set_fill(PANEL, 1).move_to(UP * cy)
        tt, pl, uu = T(t, 52, C_MAIN), T("+", 52), T(u, 52, C_ORANGE)
        row = VGroup(tt, pl, uu).arrange(RIGHT, buff=0.18).move_to(bub)
        sc.beat(GrowFromCenter(bub), rt=0.4)
        sc.beat(TransformFromCopy(ct[1], tt), FadeIn(pl, scale=0.5),
                TransformFromCopy(cu[1], uu), rt=0.7)
        total = T(s, 76, C_HI).move_to(bub)
        sc.beat(ReplacementTransform(row, total), rt=0.5)
        st["bub"], st["total"] = bub, total

    def merge():
        cs = card(s % 10, 120, C_HI, h=2.3).move_to(UP * cy)
        sc.beat(ct.animate.move_to(UP * cy + LEFT * 1.9),
                cu.animate.move_to(UP * cy + RIGHT * 1.9),
                ReplacementTransform(VGroup(st["bub"], st["total"]), cs), rt=0.7)
        row = VGroup(ct, cs, cu)
        sc.beat(row.animate.arrange(RIGHT, buff=0.12).move_to(UP * cy), rt=0.5)
        sc.beat(Indicate(row, color=C_GOOD, scale_factor=1.08), rt=0.6)

    if not carry:
        return [s0, s1, merge]

    def s2():
        cb = VGroup(Circle(radius=0.48).set_fill(C_ORANGE, 1).set_stroke(WHITE, 3),
                    T("+1", 34, BG)).move_to(st["bub"].get_top() + UP * 0.2)
        sc.beat(Transform(st["total"], T(s % 10, 76, C_HI).move_to(st["bub"])),
                FadeIn(cb, scale=0.4), rt=0.5)
        sc.beat(cb.animate.move_to(ct.get_top() + UP * 0.75), rt=0.6)
        st["cb"] = cb

    def s3():
        sc.beat(Transform(ct[1], retext(ct, t + 1, 120, C_MAIN)),
                FadeOut(st["cb"], scale=0.3), rt=0.5)
        merge()
    return [s0, s1, s2, s3]


def v_sq5(sc, a):
    n = a[0]
    hi = n * (n + 1)
    cy = 2.8
    ct = card(n, 120, C_MAIN, h=2.3).move_to(LEFT * 1.0 + UP * cy)
    c5 = card(5, 120, GREY, h=2.3).move_to(RIGHT * 1.0 + UP * cy)
    st = {}

    def s0():
        sc.beat(FadeIn(ct, shift=DOWN * 0.4), FadeIn(c5, shift=DOWN * 0.4), rt=0.6)
        sc.beat(Circumscribe(ct, color=C_HI), c5.animate.set_opacity(0.35), rt=0.9)

    def s1():
        a_ = card(n, 64, C_MAIN, w=1.3, h=1.4)
        x_ = T("\u00d7", 56)
        b_ = card(n + 1, 64, C_ORANGE, w=1.5, h=1.4)
        e_ = T("=", 56)
        r_ = card(hi, 64, C_HI, w=1.9, h=1.4)
        VGroup(a_, x_, b_, e_, r_).arrange(RIGHT, buff=0.25).move_to(UP * 0.2)
        sc.beat(FadeIn(a_[0]), FadeIn(x_), FadeIn(b_, shift=LEFT * 0.3), rt=0.4)
        sc.beat(TransformFromCopy(ct[1], a_[1]), rt=0.5)
        sc.beat(FadeIn(e_), FadeIn(r_, scale=0.6), rt=0.6)
        st["r"] = r_

    def s2():
        h2 = st["r"].copy().move_to(UP * -2.0 + LEFT * 0.9)
        c25 = card(25, 64, C_ORANGE, w=1.5, h=1.4).move_to(UP * -2.0 + RIGHT * 3.3)
        fin = card(f"{hi}25", 100, C_GOOD, w=5.6, h=1.7).move_to(UP * -2.0)
        sc.beat(TransformFromCopy(st["r"], h2), FadeIn(c25, shift=LEFT * 1.0), rt=0.7)
        sc.beat(c25.animate.next_to(h2, RIGHT, buff=0.05), rt=0.5)
        sc.beat(ReplacementTransform(VGroup(h2, c25), fin), rt=0.6)
        sc.beat(Flash(fin.get_center(), color=C_HI, line_length=0.4, num_lines=14,
                      flash_radius=1.2), rt=0.5)
    return [s0, s1, s2]


def v_near100(sc, a, square):
    if square:
        d = a[0]
        x = y = 100 - d
        p = q = d
    else:
        x, y = a
        p, q = 100 - x, 100 - y
    head, tail = 100 - p - q, p * q
    cy = 3.0
    cx = card(x, 80, C_MAIN, w=3.0, h=1.7).move_to(LEFT * 2.3 + UP * cy)
    cyy = card(y, 80, C_ORANGE, w=3.0, h=1.7).move_to(RIGHT * 2.3 + UP * cy)
    times = T("\u00d7", 70).move_to(UP * cy)
    st = {}

    def s0():
        sc.beat(FadeIn(cx, shift=DOWN * 0.3), FadeIn(cyy, shift=DOWN * 0.3),
                FadeIn(times, scale=0.5), rt=0.6)
        bx = card(f"\u2212{p}", 44, C_BAD, w=1.8, h=0.9).move_to(cx.get_bottom() + DOWN * 1.1)
        by = card(f"\u2212{q}", 44, C_BAD, w=1.8, h=0.9).move_to(cyy.get_bottom() + DOWN * 1.1)
        lx = Line(cx.get_bottom(), bx.get_top(), color=C_BAD, stroke_width=5)
        ly = Line(cyy.get_bottom(), by.get_top(), color=C_BAD, stroke_width=5)
        sc.beat(Create(lx), Create(ly), GrowFromCenter(bx), GrowFromCenter(by), rt=0.8)

    def s1():
        left = card(100, 80, C_HI, w=2.6, h=1.5).move_to(LEFT * 1.7 + DOWN * 0.9)
        sc.beat(FadeIn(left, shift=DOWN * 0.3), rt=0.5)
        sc.beat(count_anim(left, 100, head, 80, C_HI), rt=0.9)
        st["l"] = left

    def s2():
        right = card(0, 80, C_ORANGE, w=2.6, h=1.5).move_to(RIGHT * 1.7 + DOWN * 0.9)
        sc.beat(FadeIn(right, shift=DOWN * 0.3), rt=0.5)
        sc.beat(count_anim(right, 0, tail, 80, C_ORANGE, pad=2), rt=0.9)
        st["r"] = right

    def s3():
        fin = card(f"{head}{tail:02d}", 100, C_GOOD, w=4.4, h=1.7).move_to(DOWN * 2.6)
        sc.beat(ReplacementTransform(VGroup(st["l"], st["r"]), fin), rt=0.8)
        sc.beat(Flash(fin.get_center(), color=C_HI, line_length=0.4, num_lines=14,
                      flash_radius=1.3), rt=0.5)
    return [s0, s1, s2, s3]


def v_pct_of(sc, a):
    p, n = a
    ans = n * p // 100
    sq = [Square(side_length=0.26).set_fill(PANEL, 1).set_stroke(EDGE, 1.5) for _ in range(100)]
    grid = VGroup(*sq).arrange_in_grid(10, 10, buff=0.05).scale(0.8).move_to(LEFT * 1.2 + UP * 3.5)
    lab = T(f"{p}%", 84, C_HI).move_to(RIGHT * 2.55 + UP * 3.5)
    ch = Chain(sc, [1.0, -0.9, -2.8], size=64, h=0.9)

    def s0():
        sc.beat(LaggedStart(*[FadeIn(s) for s in sq], lag_ratio=0.01), rt=0.7)
        sc.beat(LaggedStart(*[s.animate.set_fill(C_HI, 1) for s in sq[:min(p, 100)]],
                            lag_ratio=0.03), FadeIn(lab, scale=0.6), rt=1.1)

    def s1():
        sc.beat(FadeIn(ch.first(n), shift=DOWN * 0.3), rt=0.5)
        ch.step(f"\u00d7 {p}", n * p)

    def s2():
        ch.step("\u00f7 100", ans, color=C_GOOD)
    return [s0, s1, s2]


def v_pct_swap(sc, a):
    x, y = a
    ans = x * y // 100
    top = card(f"{x}% of {y}", 64, C_MAIN, w=6.4, h=1.4).move_to(UP * 3.0)
    bot = card(f"{y}% of {x}", 64, C_ORANGE, w=6.4, h=1.4).move_to(UP * 0.4)
    eq = T("=", 80, C_HI).move_to(UP * 1.7)
    out = card(0, 90, C_GOOD, w=4.0, h=1.6).move_to(DOWN * 2.4)

    def s0():
        sc.beat(FadeIn(top, shift=DOWN * 0.3), rt=0.5)
        sc.beat(TransformFromCopy(top, bot), FadeIn(eq, scale=0.5), rt=0.9)
        sc.beat(Flash(eq.get_center(), color=C_HI, line_length=0.3, num_lines=12,
                      flash_radius=0.8), rt=0.5)

    def s1():
        arrow = Arrow(bot.get_bottom() + DOWN * 0.05, out.get_top() + UP * 0.05, buff=0,
                      color=C_HI, stroke_width=8, tip_length=0.28)
        sc.beat(Circumscribe(bot, color=C_GOOD), rt=0.6)
        sc.beat(GrowArrow(arrow), FadeIn(out, shift=DOWN * 0.3), rt=0.5)
        sc.beat(count_anim(out, 0, ans, 90, C_GOOD), rt=0.9)
    return [s0, s1]


def v_div(sc, a, k):
    n = a[0]
    ds = [int(c) for c in str(n)]
    alt = k == 11
    cols = [C_MAIN if (not alt or i % 2 == 0) else C_ORANGE for i in range(len(ds))]
    w = min(1.5, 7.8 / len(ds) - 0.15)
    cards = VGroup(*[card(d, 90, cols[i], w=w, h=1.9) for i, d in enumerate(ds)])
    cards.arrange(RIGHT, buff=0.15).move_to(UP * 2.8)
    st = {}

    def s0():
        sc.beat(LaggedStart(*[FadeIn(c, shift=DOWN * 0.3) for c in cards], lag_ratio=0.2), rt=0.8)
        toks, dtoks, total = [], [], 0
        for i, d in enumerate(ds):
            sign = 1 if (not alt or i % 2 == 0) else -1
            total += sign * d
            if i:
                toks.append(T("+" if sign > 0 else "\u2212", 56))
            dt = T(d, 64, cols[i])
            dtoks.append(dt)
            toks.append(dt)
        tot = T(str(total).replace("-", "\u2212"), 70, C_HI)
        toks += [T("=", 56), tot]
        line = VGroup(*toks).arrange(RIGHT, buff=0.22)
        fit(line, w=7.8).move_to(UP * 0.5)
        sc.beat(LaggedStart(*[TransformFromCopy(cards[i][1], dtoks[i]) for i in range(len(ds))],
                            lag_ratio=0.25), rt=1.0)
        rest = [m for m in toks if m not in dtoks]
        sc.beat(*[FadeIn(m, scale=0.6) for m in rest], rt=0.6)
        st["tot"] = tot

    def s1():
        badge = card(f"\u2713 divisible by {k}", 52, C_GOOD, w=6.6, h=1.3).move_to(DOWN * 1.2)
        quot = T(f"{n} \u00f7 {k} = {n // k}", 64).move_to(DOWN * 2.8)
        sc.beat(Circumscribe(st["tot"], color=C_GOOD), FadeIn(badge, scale=0.6), rt=0.7)
        sc.beat(FadeIn(quot, shift=UP * 0.3), rt=0.6)
    return [s0, s1]


def v_sum_n(sc, a):
    n = a[0]
    P = n * (n + 1)
    labels = list(range(1, n + 1)) if n <= 8 else [1, 2, 3, None, n - 2, n - 1, n]
    m = len(labels)
    ry = 2.0
    items = []
    for i, lab in enumerate(labels):
        x = (i - (m - 1) / 2) * 1.2
        g = T("\u2026", 60, GREY) if lab is None else card(lab, 44, WHITE, w=1.05, h=1.0)
        items.append(g.move_to([x, ry, 0]))
    pairs = [(0, m - 1), (1, m - 2), (2, m - 3)] if n > 8 else [(i, m - 1 - i) for i in range(m // 2)]

    def s0():
        sc.beat(LaggedStart(*[FadeIn(g, shift=DOWN * 0.2) for g in items], lag_ratio=0.1), rt=0.8)
        groups = []
        for i, j in pairs:
            arc = ArcBetweenPoints(items[i].get_top() + UP * 0.1, items[j].get_top() + UP * 0.1,
                                   angle=-PI / 2, color=C_HI, stroke_width=5)
            lab = fit(T(n + 1, 30, C_HI), w=0.9)
            bg = RoundedRectangle(corner_radius=0.15, width=lab.width + 0.3, height=0.5)
            bg.set_fill(BG, 1).set_stroke(C_HI, 2)
            tag = VGroup(bg, lab).move_to(arc.point_from_proportion(0.5))
            groups.append(AnimationGroup(Create(arc), FadeIn(tag, scale=0.5)))
        sc.beat(LaggedStart(*groups, lag_ratio=0.45), rt=1.4)

    def s1():
        f = card(f"{n} \u00d7 {n + 1} \u00f7 2", 60, WHITE, w=6.4, h=1.3).move_to(UP * 0.0)
        sc.beat(FadeIn(f, shift=UP * 0.3), rt=0.6)
        sc.beat(Indicate(f, color=C_HI, scale_factor=1.06), rt=0.6)

    def s2():
        n1 = card(n, 64, C_MAIN, w=6.4, h=1.2).move_to(DOWN * 1.4)
        n2 = card(P, 64, C_GOOD, w=6.4, h=1.2).move_to(DOWN * 2.9)
        sc.beat(FadeIn(n1, shift=DOWN * 0.2), rt=0.4)
        sc.beat(count_anim(n1, n, P, 64, C_MAIN), rt=0.8)
        sc.beat(FadeIn(n2, shift=DOWN * 0.2), rt=0.4)
        sc.beat(count_anim(n2, P, P // 2, 64, C_GOOD), rt=0.8)
    return [s0, s1, s2]


def v_square_ab(sc, a):
    hi, lo = a
    n = hi + lo
    S = 4.6
    f = min(max(lo / n, 0.22), 0.42)
    hw, lw = S * (1 - f), S * f
    x0, y0 = -2.3, 3.4

    def rect(w, h, cx, cy):
        return Rectangle(width=w, height=h).set_stroke(WHITE, 3).set_fill(WHITE, 0).move_to([cx, cy, 0])
    A = rect(hw, hw, x0 + hw / 2, y0 - hw / 2)
    B = rect(lw, hw, x0 + hw + lw / 2, y0 - hw / 2)
    C = rect(hw, lw, x0 + hw / 2, y0 - hw - lw / 2)
    D = rect(lw, lw, x0 + hw + lw / 2, y0 - hw - lw / 2)

    def lbl(s, r, size, color=WHITE):
        return fit(T(s, size, color), w=r.width - 0.2, h=r.height - 0.2).move_to(r)
    la, lb, lc, ld = lbl(f"{hi}\u00b2", A, 52), lbl(f"{hi}\u00d7{lo}", B, 34), \
        lbl(f"{hi}\u00d7{lo}", C, 34), lbl(f"{lo}\u00b2", D, 40)
    ty, cyy = y0 + 0.5, -2.3
    tops = [T(hi, 44, C_MAIN).move_to([x0 + hw / 2, ty, 0]),
            T(lo, 44, C_ORANGE).move_to([x0 + hw + lw / 2, ty, 0]),
            T(hi, 44, C_MAIN).move_to([x0 - 0.55, y0 - hw / 2, 0]),
            T(lo, 44, C_ORANGE).move_to([x0 - 0.55, y0 - hw - lw / 2, 0])]
    chips = [card(hi * hi, 44, C_MAIN, w=2.3, h=1.1).move_to([-2.9, cyy, 0]),
             card(2 * hi * lo, 44, C_ORANGE, w=2.3, h=1.1).move_to([0, cyy, 0]),
             card(lo * lo, 44, C_GOOD, w=2.3, h=1.1).move_to([2.9, cyy, 0])]

    def s0():
        sc.beat(*[Create(r) for r in (A, B, C, D)], rt=0.8)
        sc.beat(*[FadeIn(t, scale=0.6) for t in tops], rt=0.5)

    def s1():
        sc.beat(A.animate.set_fill(C_MAIN, 0.55), FadeIn(la, scale=0.6), rt=0.5)
        sc.beat(FadeIn(chips[0], shift=UP * 0.3), rt=0.5)

    def s2():
        sc.beat(B.animate.set_fill(C_ORANGE, 0.55), C.animate.set_fill(C_ORANGE, 0.55),
                FadeIn(lb, scale=0.6), FadeIn(lc, scale=0.6), rt=0.6)
        sc.beat(FadeIn(chips[1], shift=UP * 0.3), rt=0.5)

    def s3():
        sc.beat(D.animate.set_fill(C_GOOD, 0.55), FadeIn(ld, scale=0.6), rt=0.5)
        sc.beat(FadeIn(chips[2], shift=UP * 0.3), rt=0.5)

    def s4():
        pl = [T("+", 44).move_to([-1.45, cyy, 0]), T("+", 44).move_to([1.45, cyy, 0])]
        fin = card(n * n, 70, C_GOOD, w=5.6, h=1.3).move_to([0, cyy, 0])
        sc.beat(*[FadeIn(p, scale=0.5) for p in pl], rt=0.4)
        sc.beat(ReplacementTransform(VGroup(*chips, *pl), fin), rt=0.8)
        sc.beat(Flash(fin.get_center(), color=C_HI, line_length=0.4, num_lines=14,
                      flash_radius=1.3), rt=0.5)
    return [s0, s1, s2, s3, s4]


def v_sub1000(sc, a):
    n = a[0]
    ds = [int(c) for c in f"{n:03d}"]
    res = [9 - ds[0], 9 - ds[1], 10 - ds[2]]
    xs = [-2.3, 0.0, 2.3]
    tops = [card(ds[i], 100, GREY if (i == 0 and ds[0] == 0) else WHITE, w=1.9, h=1.9)
            .move_to([xs[i], 2.9, 0]) for i in range(3)]
    bots = [card(res[i], 100, C_GOOD, w=1.9, h=1.9).move_to([xs[i], -0.9, 0]) for i in range(3)]

    def col(i):
        def f():
            if i == 0:
                sc.beat(*[FadeIn(t, shift=DOWN * 0.3) for t in tops], rt=0.6)
            arrow = Arrow(tops[i].get_bottom() + DOWN * 0.05, bots[i].get_top() + UP * 0.05,
                          buff=0, color=C_HI if i < 2 else C_ORANGE, stroke_width=8, tip_length=0.28)
            badge = card(f"{9 if i < 2 else 10} \u2212 {ds[i]}", 40, C_HI, w=1.9, h=0.8)
            badge.move_to(arrow.get_center())
            sc.beat(Indicate(tops[i], color=C_HI), GrowArrow(arrow), FadeIn(badge, scale=0.6), rt=0.7)
            sc.beat(FadeIn(bots[i], shift=DOWN * 0.3), FadeOut(badge), rt=0.5)
        return f
    return [col(0), col(1), col(2)]


VISUALS = {
    "mul11": v_mul11,
    "sq5": v_sq5,
    "mul9": lambda sc, a: v_flow(sc, a[0], [("\u00d7 10", a[0] * 10, "zeros"),
                                            (f"\u2212 {a[0]}", a[0] * 9, "count")]),
    "mul5": lambda sc, a: v_flow(sc, a[0], [("\u00d7 10", a[0] * 10, "zeros"),
                                            ("\u00f7 2", a[0] * 5, "count")]),
    "mul25": lambda sc, a: v_flow(sc, a[0], [("\u00f7 4", a[0] // 4, "count"),
                                             ("\u00d7 100", a[0] * 25, "zeros")]),
    "mul125": lambda sc, a: v_flow(sc, a[0], [("\u00f7 8", a[0] // 8, "count"),
                                              ("\u00d7 1000", a[0] * 125, "zeros")]),
    "sq_near100": lambda sc, a: v_near100(sc, a, True),
    "mul_near100": lambda sc, a: v_near100(sc, a, False),
    "pct_of": v_pct_of,
    "pct_swap": v_pct_swap,
    "div3": lambda sc, a: v_div(sc, a, 3),
    "div9": lambda sc, a: v_div(sc, a, 9),
    "div11": lambda sc, a: v_div(sc, a, 11),
    "sum_n": v_sum_n,
    "square_ab": v_square_ab,
    "sub_1000": v_sub1000,
}


# ── scene ─────────────────────────────────────────────────────────────────────
class TrickScene(Scene):
    def construct(self):
        with open(os.environ["TRICK_SPEC"], encoding="utf-8") as f:
            self.spec = json.load(f)
        self.durs = self.spec["durs"]
        self.steps = self.spec["steps"]
        self.total = sum(self.durs)
        self.camera.background_color = BG
        self._chrome()

        t = self.durs[0]
        self._intro(t)
        fns = self._visuals()
        for i, fn in enumerate(fns):
            t += self.durs[1 + i]
            self.cur, self.t_end, self._first = i, t, True
            fn()
            if self._first:
                self.beat(rt=FPS)
            self._hold()
        self._outro(t + self.durs[-1])

    # timing: every beat is clamped to the narration clock
    def beat(self, *anims, rt=0.8):
        pre = []
        if self._first and self.cur is not None:
            pre = self._caption_anims()
            self._first = False
        d = max(FPS, min(rt, self.t_end - self.time))
        self.play(*pre, *anims, run_time=d)

    def _hold(self):
        rem = self.t_end - self.time
        if rem > FPS:
            self.wait(rem)

    def _visuals(self):
        fn = VISUALS.get(self.spec["type"])
        try:
            fns = fn(self, self.spec["args"]) if fn else []
        except Exception as e:  # never lose a video over a visual
            print(f"[scene] visual build failed: {e}")
            fns = []
        if len(fns) != len(self.steps):
            fns = [lambda: None for _ in self.steps]
        return fns

    def _chrome(self):
        rnd = random.Random(11)
        syms = list("0123456789+\u2212\u00d7\u00f7=%\u00b2\u221a\u03c0")
        fl = VGroup()
        for _ in range(18):
            m = T(rnd.choice(syms), rnd.randint(46, 120), WHITE).set_opacity(0.045)
            m.move_to([rnd.uniform(-4.2, 4.2), rnd.uniform(-8, 8), 0])
            m.speed = rnd.uniform(0.12, 0.4)
            fl.add(m)

        def drift(g, dt):
            for m in g:
                m.shift(UP * m.speed * dt)
                if m.get_y() > 8.8:
                    m.set_y(-8.8)
        fl.add_updater(drift)

        track = Rectangle(width=8.6, height=0.12, stroke_width=0).set_fill(WHITE, 0.12)
        track.move_to(DOWN * 7.7)
        bar = Rectangle(width=0.02, height=0.12, stroke_width=0).set_fill(C_HI, 1)

        def grow(m, dt):
            m.stretch_to_fit_width(max(0.02, 8.6 * min(1.0, self.time / self.total)))
            m.move_to(track.get_left(), aligned_edge=LEFT)
        bar.add_updater(grow)
        self.add(fl, track, bar)
        self._keep = [fl, track, bar]

        self.panel = RoundedRectangle(corner_radius=0.35, width=8.3, height=1.9)
        self.panel.set_fill(PANEL, 0.96).set_stroke(EDGE, 3).move_to(DOWN * 4.7)
        self.dots = VGroup(*[Circle(radius=0.1).set_fill(GREY, 1).set_stroke(width=0)
                             for _ in self.steps]).arrange(RIGHT, buff=0.35).move_to(DOWN * 6.1)
        pt = T(self.spec["category"], 28, C_HI)
        box = RoundedRectangle(corner_radius=0.3, width=pt.width + 0.9, height=0.7)
        box.set_fill(PANEL, 1).set_stroke(C_HI, 2)
        self.pill = VGroup(box, pt).move_to(UP * 7.1)
        self.cap = fit(T("Watch how it works", 36, GREY, bold=False), w=7.6).move_to(self.panel)
        self.cur = None
        self._first = False

    def _caption_anims(self):
        i = self.cur
        new = fit(Text(wrap(self.steps[i]), font=FONT, font_size=36, color=WHITE, line_spacing=1.1),
                  w=7.6, h=1.5).move_to(self.panel)
        anims = [FadeIn(new, shift=UP * 0.25), FadeOut(self.cap, shift=UP * 0.25)]
        self.cap = new
        if i > 0:
            anims.append(self.dots[i - 1].animate.set_color(C_GOOD).scale(1 / 1.4))
        anims.append(self.dots[i].animate.set_color(C_HI).scale(1.4))
        return anims

    def _intro(self, dur):
        self.t_end = dur
        hook = fit(T(self.spec["hook"], 120, C_MAIN), w=8.2).move_to(UP * 2.4)
        self.hook = hook
        self.beat(FadeIn(self.pill, shift=DOWN * 0.3), FadeIn(hook, scale=0.6), rt=0.55)
        self.beat(Flash(hook.get_center(), color=C_HI, line_length=0.5, num_lines=14,
                        flash_radius=1.6), rt=0.45)
        rem = self.t_end - 0.6 - self.time
        if rem > FPS:
            self.wait(rem)
        self.beat(hook.animate.scale(0.62).move_to(UP * 5.7),
                  FadeIn(self.panel, shift=UP * 0.3), FadeIn(self.dots), FadeIn(self.cap), rt=0.6)
        self._hold()

    def _outro(self, t_end):
        self.t_end = t_end
        stage = [m for m in self.mobjects if not any(m is k for k in self._keep)]
        self.beat(*[FadeOut(m) for m in stage], rt=0.4)

        res = fit(T(self.spec["result"], 76, C_GOOD), w=7.6).move_to(UP * 2.4)
        frame = RoundedRectangle(corner_radius=0.4, width=res.width + 0.9, height=res.height + 1.0)
        frame.set_fill(PANEL, 1).set_stroke(C_GOOD, 5).move_to(res)
        rnd = random.Random(3)
        cols = [C_HI, C_GOOD, C_MAIN, C_BAD, C_ORANGE, "#B58CFF"]
        origin = frame.get_center()
        bits, bursts = [], []
        for _ in range(46):
            sq = Square(side_length=rnd.uniform(0.12, 0.24)).set_fill(rnd.choice(cols), 1)
            sq.set_stroke(width=0).move_to(origin)
            ang, r = rnd.uniform(0, TAU), rnd.uniform(2.0, 5.0)
            tgt = origin + np.array([math.cos(ang) * r, math.sin(ang) * r * 0.9, 0])

            def f(m, a, tgt=tgt):
                m.move_to(origin + (tgt - origin) * (1 - (1 - a) ** 3) + DOWN * 1.6 * a * a)
                m.set_fill(opacity=1 - a * a)
                m.rotate(0.12)
            bits.append(sq)
            bursts.append(UpdateFromAlphaFunc(sq, f))
        self.add(*bits)
        self.beat(FadeIn(frame, scale=0.6), FadeIn(res, scale=0.6),
                  Flash(origin, color=C_HI, line_length=0.6, num_lines=18, flash_radius=2.0),
                  *bursts, rt=0.9)
        self.remove(*bits)

        tag = T("New math trick every day", 40, GREY, bold=False).move_to(DOWN * 0.8)
        btn = VGroup(RoundedRectangle(corner_radius=0.5, width=5.4, height=1.4)
                     .set_fill("#FF1F1F", 1).set_stroke(WHITE, 3),
                     T("\u25b6 SUBSCRIBE", 50, WHITE)).move_to(DOWN * 2.6)
        self.beat(FadeIn(tag, shift=UP * 0.2), FadeIn(btn, shift=UP * 0.5, scale=0.8), rt=0.5)
        while self.t_end - self.time > 0.7:
            self.beat(btn.animate.scale(1.08), rt=0.3)
            self.beat(btn.animate.scale(1 / 1.08), rt=0.3)
        self._hold()
