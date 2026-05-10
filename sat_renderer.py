"""
sat_renderer.py  —  SAT teaching-style Shorts renderer
Imitates @yoursatcoach / FutureAdmit.com visual style.

Frame-by-frame analysis of the 12M-view sqrt50+sqrt8 video revealed:
• Full-screen white/cream paper — NO dark blurred background
• Rainbow border (12 px) at screen edges
• Navy Q-number badge + gray bar at top
• Large LaTeX math expression — color changes: dark → red → blue → green
• "Work zone" between math and options: shows ONE annotation at a time
• A–D options: Gaussian-blurred during teaching, sharp for answer reveal
• Blue subtitle pill (white bold text, bottom) synced to narration phrases
• Yellow Bezier arrow on right (hook phase only)
• Answer reveal: correct option → green highlight; wrong → dimmed gray + strikethrough
• Typewriter animation on hook subtitle (chars appear letter-by-letter)
"""

import io, os, asyncio, shutil, subprocess, random, math as _math
from typing import Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FPS = 60
W, H = 1080, 1920
BT = 12   # rainbow border thickness

# ── Content edges ──────────────────────────────────────────────────────────────
CX1 = BT + 30     # 42
CX2 = W - BT - 30  # 1038
CW  = CX2 - CX1   # 996

# ── Vertical layout (proportions from real 608×1080 video scaled ×1.778) ───────
BADGE_Y1 = 98
BADGE_Y2 = 162
BADGE_W  = 72
QTEXT_Y  = 182     # "Solve for the problem"
MATH_TOP = 240     # main math expression top
WORK_CY  = 530     # work annotation vertical center
OPT_Y1   = 680     # options start (A row)
OPT_H    = 90      # option row height
OPT_GAP  = 14
OPT_Y2   = OPT_Y1 + 4 * (OPT_H + OPT_GAP) - OPT_GAP  # = 1082
WMARK_Y  = OPT_Y2 + 14
SUBTT_Y1 = 1555    # subtitle pill top  (~81% of 1920 — matches reference)
SUBTT_Y2 = 1660    # subtitle pill bottom

# ── Colors ─────────────────────────────────────────────────────────────────────
PAPER     = (246, 245, 243)
NAVY      = ( 42,  71, 153)
GRAY_BAR  = (215, 215, 215)
TEXT_DARK = ( 28,  28,  28)
WHITE     = (255, 255, 255)
BLUE_SUB  = ( 43, 144, 220)   # subtitle pill background
BLUE_WORK = ( 30, 110, 210)   # work zone annotation
GREEN_OK  = ( 40, 160,  70)   # correct answer
RED_WRG   = (195,  35,  35)   # wrong approach
DIM_CLR   = (190, 190, 190)   # dimmed wrong options
ARROW_CLR = (210, 165,   0)

_RB = [
    (255,   0, 128), (255,   0,   0), (255, 128,   0),
    (255, 220,   0), (  0, 220,   0), (  0, 200, 180),
    (  0, 100, 255), (128,   0, 255), (255,   0, 128),
]

# ── Font helper ────────────────────────────────────────────────────────────────

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    candidates = {
        "arialbd.ttf": ["arialbd.ttf",
                        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
        "arial.ttf":   ["arial.ttf",
                        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    }
    for c in candidates.get(name, [name]):
        for prefix in ["C:/Windows/Fonts/", ""]:
            try:
                return ImageFont.truetype(
                    c if c.startswith("/") else f"{prefix}{c}", size)
            except Exception:
                pass
    return ImageFont.load_default()


# ── LaTeX/math rendering ───────────────────────────────────────────────────────

_EQ_CACHE: dict = {}


def _sanitize_latex(text: str) -> str:
    """Replace LaTeX commands unsupported by matplotlib's math parser."""
    import re
    # Split on \implies and keep only the part after it (the result)
    # e.g. "x+3 = 5 \implies x = 2"  →  "x = 2"
    if r'\implies' in text:
        parts = re.split(r'\\implies', text)
        text = parts[-1].strip()
    # Other unsupported commands → safe equivalents
    replacements = {
        r'\Rightarrow':  r'\Rightarrow',   # matplotlib supports this one
        r'\therefore':   r'\therefore',     # supported
        r'\because':     '',
        r'\quad':        r'\;',
        r'\qquad':       r'\;',
        r'\text{':       r'\mathrm{',
        r'\operatorname{': r'\mathrm{',
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text.strip()


def _render_eq(text: str, fontsize: int = 44,
               color: tuple = TEXT_DARK) -> Optional[Image.Image]:
    text = _sanitize_latex(text)
    key = (text, fontsize, color)
    if key in _EQ_CACHE:
        return _EQ_CACHE[key]
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        r, g, b = color
        figw = max(1.8, len(text) * 0.09)
        fig  = plt.figure(figsize=(figw, 1.05))
        fig.patch.set_alpha(0.0)
        ax   = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        ax.text(0.5, 0.5, text, fontsize=fontsize,
                ha="center", va="center",
                color=(r/255, g/255, b/255),
                math_fontfamily="cm")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=200, transparent=True,
                    bbox_inches="tight", pad_inches=0.04)
        plt.close(fig)
        buf.seek(0)
        img = Image.open(buf).convert("RGBA")
        _EQ_CACHE[key] = img
        return img
    except Exception as e:
        print(f"[sat] math render error: {e}")
        return None


def _paste_eq(canvas: Image.Image, text: str, cx: int, top_y: int,
              fontsize: int = 48, max_w: int = 860, max_h: int = 160,
              color: tuple = TEXT_DARK) -> int:
    """Paste math centered at cx, starting at top_y. Returns bottom y."""
    img = _render_eq(text, fontsize, color)
    if img is None:
        d  = ImageDraw.Draw(canvas)
        f  = _font("arial.ttf", fontsize)
        bb = d.textbbox((0, 0), text, font=f)
        d.text((cx - (bb[2]-bb[0])//2, top_y), text, font=f, fill=(*color, 255))
        return top_y + (bb[3]-bb[1]) + 6
    scale = min(max_w / max(img.width, 1), max_h / max(img.height, 1), 1.0)
    if scale < 1.0:
        img = img.resize(
            (max(1, int(img.width*scale)), max(1, int(img.height*scale))),
            Image.LANCZOS)
    canvas.paste(img, (cx - img.width//2, top_y), img)
    return top_y + img.height + 4


# ── Rainbow border ─────────────────────────────────────────────────────────────

def _rb_arr(pos: np.ndarray) -> np.ndarray:
    stops = np.array(_RB, dtype=np.float32)
    n     = len(stops) - 1
    idx   = np.clip(pos * n, 0, n - 1e-6)
    lo    = idx.astype(np.int32)
    t     = (idx - lo)[:, None]
    return np.clip(stops[lo] + t*(stops[lo+1]-stops[lo]), 0, 255).astype(np.uint8)


def _rainbow_border(canvas: Image.Image) -> None:
    arr = np.array(canvas)
    cw = W; ch = H; p = float(2*(cw+ch))
    c = _rb_arr(np.arange(cw, dtype=np.float32)/p)
    arr[0:BT, 0:cw, :3] = c[np.newaxis, :, :]
    c = _rb_arr((cw+np.arange(ch, dtype=np.float32))/p)
    arr[0:ch, cw-BT:cw, :3] = c[:, np.newaxis, :]
    c = _rb_arr((cw+ch+np.arange(cw, dtype=np.float32))/p)[::-1]
    arr[ch-BT:ch, 0:cw, :3] = c[np.newaxis, :, :]
    c = _rb_arr((2*cw+ch+np.arange(ch, dtype=np.float32))/p)[::-1]
    arr[0:ch, 0:BT, :3] = c[:, np.newaxis, :]
    canvas.paste(Image.fromarray(arr.astype(np.uint8)), (0, 0))


# ── Animation helpers ─────────────────────────────────────────────────────────

def _ease(t: float) -> float:
    """Smoothstep easing: 0→0, 1→1, smooth in/out."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))

def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def _blend_frames(img_a: Image.Image, img_b: Image.Image, t: float) -> Image.Image:
    """Cross-dissolve two RGB frames. t=0→img_a, t=1→img_b."""
    a = np.array(img_a, dtype=np.float32)
    b = np.array(img_b, dtype=np.float32)
    return Image.fromarray(np.clip(a * (1 - t) + b * t, 0, 255).astype(np.uint8))


# ── Yellow Bezier arrow ────────────────────────────────────────────────────────

def _draw_arrow(canvas: Image.Image, opt_mid_y: int, alpha: float = 1.0) -> None:
    if alpha <= 0.01: return
    d  = ImageDraw.Draw(canvas)
    # blend arrow color with paper background for alpha effect
    ac = tuple(int(PAPER[i] * (1 - alpha) + ARROW_CLR[i] * alpha) for i in range(3))
    # Tail: lower-right; Head: points at option A (top of options list)
    tx = W - BT - 40;  ty = OPT_Y1 + 3*(OPT_H + OPT_GAP) + OPT_H//2
    hx = CX1 + 160;    hy = OPT_Y1 + OPT_H//2
    cx1 = W - BT - 80; cy1 = ty - 60
    cx2 = CX1 + 400;   cy2 = hy + 60
    pts = []
    for i in range(80):
        t = i/79.0; mt = 1-t
        pts.append((
            int(mt**3*tx + 3*mt**2*t*cx1 + 3*mt*t**2*cx2 + t**3*hx),
            int(mt**3*ty + 3*mt**2*t*cy1 + 3*mt*t**2*cy2 + t**3*hy),
        ))
    for i in range(len(pts)-1):
        d.line([pts[i], pts[i+1]], fill=ac, width=14)
    dx  = pts[-1][0]-pts[-4][0]; dy = pts[-1][1]-pts[-4][1]
    ang = _math.atan2(dy, dx); sz = 34; tip = pts[-1]
    p1  = (int(tip[0]+sz*_math.cos(ang+2.25)), int(tip[1]+sz*_math.sin(ang+2.25)))
    p2  = (int(tip[0]+sz*_math.cos(ang-2.25)), int(tip[1]+sz*_math.sin(ang-2.25)))
    d.polygon([tip, p1, p2], fill=ac)


# ── Subtitle pill ─────────────────────────────────────────────────────────────

def _draw_subtitle(canvas: Image.Image, text: str, chars: int = -1,
                   hook_style: bool = False) -> None:
    """
    Subtitle at bottom of card.
    hook_style=True  → plain bold blue text (typewriter, no pill — matches hook phase)
    hook_style=False → blue rounded-rect pill with white text (narration phase)
    chars = -1 → full text. chars = N → typewriter (first N chars shown).
    """
    if not text:
        return
    visible = text if chars < 0 else text[:max(0, chars)]
    if not visible:
        return
    d = ImageDraw.Draw(canvas)
    f = _font("arialbd.ttf", 44)
    words = visible.split()
    lines = []
    line  = ""
    for w in words:
        test = (line+" "+w).strip()
        bb   = d.textbbox((0, 0), test, font=f)
        if bb[2]-bb[0] > CW - 60:
            if line:
                lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    lines = lines[-2:]  # max 2 lines

    lh   = f.size + 10
    cy_pill = (SUBTT_Y1 + SUBTT_Y2)//2

    if hook_style:
        # Plain bold blue text centered — no pill background
        ty = cy_pill - (len(lines) * lh) // 2
        for ln in lines:
            bb  = d.textbbox((0, 0), ln, font=f)
            lw  = bb[2]-bb[0]
            x   = W//2 - lw//2
            d.text((x+2, ty+2), ln, font=f, fill=(0, 0, 0, 80))
            d.text((x,   ty  ), ln, font=f, fill=(*BLUE_SUB, 255))
            ty += lh
        return

    bh   = len(lines)*lh + 28
    by1  = cy_pill - bh//2
    by2  = by1 + bh
    max_w = max(d.textbbox((0,0), l, font=f)[2] for l in lines)
    bx1  = max(CX1+10, W//2 - max_w//2 - 28)
    bx2  = min(CX2-10, W//2 + max_w//2 + 28)

    d.rounded_rectangle([bx1, by1, bx2, by2], radius=22, fill=(*BLUE_SUB, 255))
    cy = by1 + 14
    for ln in lines:
        bb  = d.textbbox((0, 0), ln, font=f)
        lw  = bb[2]-bb[0]
        x   = W//2 - lw//2
        d.text((x+2, cy+2), ln, font=f, fill=(0, 0, 0, 90))
        d.text((x,   cy  ), ln, font=f, fill=WHITE)
        cy += lh


# ── Core frame renderer ───────────────────────────────────────────────────────

def draw_frame(
    q_text:         str,
    math_expr:      str,
    options:        dict,
    q_num:          int,
    math_color:     tuple = TEXT_DARK,
    math_alpha:     float = 1.0,
    work_expr:      str   = "",
    work_color:     tuple = BLUE_WORK,
    work_alpha:     float = 1.0,
    work_slide_y:   int   = 0,
    subtitle:       str   = "",
    subtitle_chars: int   = -1,
    subtitle_hook:  bool  = False,
    blur_radius:    int   = 0,
    arrow_alpha:    float = 1.0,
    correct:        str   = None,
    dim_t:          float = 0.0,
    show_arrow:     bool  = True,
) -> Image.Image:
    """
    Render a single 1080×1920 RGB frame matching @yoursatcoach style.
    Pure white paper background (no dark overlay).
    """
    canvas = Image.new("RGB", (W, H), PAPER)
    d      = ImageDraw.Draw(canvas)

    # ── Gray bar + navy badge ──────────────────────────────────────────────────
    d.rectangle([BT, BADGE_Y1, W-BT, BADGE_Y2], fill=GRAY_BAR)
    bx1 = BT + 10; bx2 = bx1 + BADGE_W
    d.rounded_rectangle([bx1, BADGE_Y1, bx2, BADGE_Y2], radius=6, fill=NAVY)
    fb  = _font("arialbd.ttf", 30)
    bcx = (bx1+bx2)//2; bcy = (BADGE_Y1+BADGE_Y2)//2
    d.text((bcx+1, bcy+1), str(q_num), font=fb, fill=(0,0,0,110), anchor="mm")
    d.text((bcx,   bcy  ), str(q_num), font=fb, fill=WHITE,       anchor="mm")

    # ── Question intro text ────────────────────────────────────────────────────
    if q_text:
        fq = _font("arial.ttf", 34)
        d.text((CX1, QTEXT_Y), q_text, font=fq, fill=TEXT_DARK)

    # ── Main math expression ──────────────────────────────────────────────────
    if math_alpha < 0.99:
        _math_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _paste_eq(_math_layer, math_expr, W//2, MATH_TOP,
                  fontsize=54, max_w=CW-40, max_h=150, color=math_color)
        _mr, _mg, _mb, _ma = _math_layer.split()
        _ma = _ma.point(lambda v: int(v * max(0.0, min(1.0, math_alpha))))
        _math_layer = Image.merge("RGBA", (_mr, _mg, _mb, _ma))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), _math_layer).convert("RGB")
        d = ImageDraw.Draw(canvas)
    else:
        _paste_eq(canvas, math_expr, W//2, MATH_TOP,
                  fontsize=54, max_w=CW-40, max_h=150, color=math_color)

    # ── Work zone annotation ──────────────────────────────────────────────────
    if work_expr and work_alpha > 0.01:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        eq_y  = WORK_CY - 80 + work_slide_y
        _paste_eq(layer, work_expr, W//2, eq_y,
                  fontsize=62, max_w=CW-40, max_h=220, color=work_color)
        if work_alpha < 1.0:
            r2, g2, b2, a2 = layer.split()
            a2 = a2.point(lambda v: int(v * work_alpha))
            layer = Image.merge("RGBA", (r2, g2, b2, a2))
        canvas = canvas.convert("RGBA")
        canvas = Image.alpha_composite(canvas, layer)
        canvas = canvas.convert("RGB")
        d = ImageDraw.Draw(canvas)

    # ── Options A–D ───────────────────────────────────────────────────────────
    opt_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od        = ImageDraw.Draw(opt_layer)
    fo        = _font("arial.ttf", 36)
    opt_mid_y = OPT_Y1 + 2*(OPT_H + OPT_GAP)

    for i, letter in enumerate("ABCD"):
        oy1 = OPT_Y1 + i*(OPT_H+OPT_GAP)
        oy2 = oy1 + OPT_H
        is_correct = bool(correct and letter == correct)
        is_wrong   = dim_t > 0 and not is_correct and correct is not None

        if is_correct:
            od.rounded_rectangle([CX1, oy1, CX2, oy2], radius=8,
                                  fill=(40,160,70, 55))

        clr    = GREEN_OK if is_correct else (_lerp_color(TEXT_DARK, DIM_CLR, dim_t) if is_wrong else TEXT_DARK)
        lbl    = f"{letter})  "
        lbl_w  = int(od.textlength(lbl, font=fo))
        lbl_y  = oy1 + (OPT_H - 36)//2
        od.text((CX1, lbl_y), lbl, font=fo, fill=(*clr, 255))

        val   = options.get(letter, "")
        val_x = CX1 + lbl_w + 4
        max_vw = CX2 - val_x - 12

        if "$" in val:
            vimg = _render_eq(val, fontsize=32, color=clr)
            if vimg is not None:
                scale = min(max_vw/max(vimg.width,1), (OPT_H-10)/max(vimg.height,1), 1.0)
                if scale < 1.0:
                    vimg = vimg.resize(
                        (max(1,int(vimg.width*scale)), max(1,int(vimg.height*scale))),
                        Image.LANCZOS)
                vy = oy1 + (OPT_H - vimg.height)//2
                opt_layer.paste(vimg, (val_x, vy), vimg)
            else:
                od.text((val_x, lbl_y), val, font=fo, fill=(*clr, 255))
        else:
            od.text((val_x, lbl_y), val, font=fo, fill=(*clr, 255))

        if is_correct:
            ck_x = CX2-48; ck_y = (oy1+oy2)//2; s = 14
            od.line([(ck_x-s, ck_y), (ck_x-s//3, ck_y+s), (ck_x+s, ck_y-s)],
                    fill=(40,160,70,255), width=5)

        if is_wrong and dim_t > 0.5:
            sy  = (oy1+oy2)//2
            sw  = int((CX2-CX1-8) * min((dim_t-0.5)/0.5, 1.0))
            stk = _lerp_color(TEXT_DARK, DIM_CLR, dim_t)
            od.line([(CX1+4, sy), (CX1+4+sw, sy)], fill=(*stk, 200), width=3)

    if blur_radius > 0:
        region = opt_layer.crop((0, OPT_Y1-10, W, OPT_Y2+10))
        region = region.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        opt_layer.paste(region, (0, OPT_Y1-10))

    canvas = canvas.convert("RGBA")
    canvas = Image.alpha_composite(canvas, opt_layer)
    canvas = canvas.convert("RGB")
    d = ImageDraw.Draw(canvas)

    # ── Rainbow border ────────────────────────────────────────────────────────
    _rainbow_border(canvas)

    # ── Arrow (hook phase only) ───────────────────────────────────────────────
    if show_arrow:
        _draw_arrow(canvas, 0, arrow_alpha)

    # ── Subtitle (pill or plain hook style) ─────────────────────────────
    _draw_subtitle(canvas, subtitle, subtitle_chars, hook_style=subtitle_hook)

    return canvas


# ── ffmpeg helper ─────────────────────────────────────────────────────────────

def _run_ffmpeg(cmd: list, label: str) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"[sat] {label} failed:\n{res.stderr[-1600:]}")


# ── Clip builders ─────────────────────────────────────────────────────────────

def _static_clip(img: Image.Image, duration: float, path: str,
                 ffmpeg: str) -> None:
    """One PNG → short H.264 clip (looped)."""
    tmp = path + "_tmp.png"
    img.save(tmp)
    _run_ffmpeg([
        ffmpeg, "-y",
        "-loop", "1", "-t", f"{duration:.3f}", "-i", tmp,
        "-vf", f"fps={FPS},scale={W}:{H}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-t", f"{duration:.3f}", path,
    ], f"static {os.path.basename(path)}")
    os.remove(tmp)


def _frames_clip(frames: list, fps: float, path: str, ffmpeg: str) -> None:
    """List of PIL RGB images → H.264 clip via rawvideo pipe."""
    proc = subprocess.Popen([
        ffmpeg, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24",
        "-r", str(fps), "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", path,
    ], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for f in frames:
        proc.stdin.write(f.convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"[sat] frames_clip failed: {path}")


def _concat_wavs(paths: list, out: str, ffmpeg: str) -> None:
    """Concatenate multiple WAV files into one using ffmpeg concat demuxer."""
    list_txt = out + "_list.txt"
    with open(list_txt, "w", encoding="utf-8") as _f:
        for p in paths:
            abs_p = os.path.abspath(p).replace("\\", "/")
            _f.write(f"file '{abs_p}'\n")
    _run_ffmpeg([
        ffmpeg, "-y", "-f", "concat", "-safe", "0",
        "-i", list_txt, "-c", "copy", out
    ], "concat_wavs")
    os.remove(list_txt)


def _vis_state_for_scene(seg: dict, steps: list, wrong_apr: str,
                         correct: str, answer_expr: str, lt: float) -> dict:
    """
    Return draw_frame kwargs for a script segment.
    Each segment snaps to its FINAL visual state immediately from frame 0 —
    no entrance animations — so every spoken word matches what is on screen.
    lt is only used for the hook arrow pulse (continuous ambient motion).
    """
    stype = seg.get("scene", "hook")
    if stype == "hook":
        arr_a = 0.55 + 0.45 * (_math.sin(lt * 6 * _math.pi) * 0.5 + 0.5)
        return dict(math_color=TEXT_DARK, math_alpha=1.0,
                    show_arrow=True, arrow_alpha=arr_a, subtitle_hook=True)
    elif stype == "wrong":
        return dict(math_color=RED_WRG, math_alpha=0.18,
                    work_expr=wrong_apr, work_color=RED_WRG,
                    work_alpha=1.0, work_slide_y=0,
                    blur_radius=0, show_arrow=False)
    elif stype == "step":
        si = max(0, min(seg.get("step_index", 0), len(steps) - 1)) if steps else 0
        wc = GREEN_OK if steps and si == len(steps) - 1 else BLUE_WORK
        return dict(math_color=TEXT_DARK, math_alpha=0.18,
                    work_expr=steps[si].get("math", "") if steps else "",
                    work_color=wc, work_alpha=1.0, work_slide_y=0,
                    blur_radius=4, show_arrow=False)
    else:  # "answer" or "cta"
        return dict(math_color=TEXT_DARK, math_alpha=0.18,
                    work_expr=answer_expr, work_color=GREEN_OK,
                    work_alpha=1.0, work_slide_y=0, blur_radius=0,
                    correct=correct, dim_t=1.0, show_arrow=False)


def _script_from_narration(sat_data: dict) -> list:
    """
    Build a script array from old-style spoken_narration.
    Used as backward-compat fallback when sat_data has no 'script' key.
    """
    import re
    narration = sat_data.get("spoken_narration", "")
    steps     = sat_data.get("solution_steps", [])
    wrong_apr = sat_data.get("wrong_approach", "")
    phrases   = [p.strip() for p in re.split(r'(?<=[.,!?;:])\s+', narration) if p.strip()]
    n = len(phrases)
    script = []
    for i, p in enumerate(phrases):
        frac = i / max(n - 1, 1)
        if frac < 0.15:
            script.append({"scene": "hook", "text": p})
        elif frac < 0.30 and wrong_apr:
            script.append({"scene": "wrong", "text": p})
        elif frac < 0.90:
            span = 0.75 if wrong_apr else 0.90
            base = 0.30 if wrong_apr else 0.15
            step_frac = (frac - base) / span
            si = min(int(step_frac * max(len(steps), 1)), max(len(steps) - 1, 0))
            script.append({"scene": "step", "step_index": si, "text": p})
        elif frac < 0.97:
            script.append({"scene": "answer", "text": p})
        else:
            script.append({"scene": "cta", "text": p})
    return script


# ── Full animated video builder ────────────────────────────────────────────────

async def create_sat_video(
    sat_data:   dict,
    output_dir: str,
    voice:      str = "af_sarah",
) -> str:
    """
    Generate ~60s SAT teaching Short — fully frame-by-frame at 24fps.

    Script-first approach: sat_data['script'] is a list of segments, each with:
      {"scene": "hook"|"wrong"|"step"|"answer"|"cta", "text": "...", "step_index": N}

    Each segment is TTS'd individually to get its EXACT duration.
    Frames are rendered for that exact duration showing the matching visual.
    This guarantees every spoken word matches what is shown on screen.

    Falls back to _script_from_narration() if no 'script' key in sat_data.
    """
    import soundfile as sf
    from imageio_ffmpeg import get_ffmpeg_exe
    from quiz_renderer import _tts, _normalize_tts, _strip_latex

    ffmpeg = get_ffmpeg_exe()
    os.makedirs(output_dir, exist_ok=True)
    tmp = os.path.join(output_dir, "_clips")
    os.makedirs(tmp, exist_ok=True)

    q_text      = sat_data.get("question_text", "Solve for the problem")
    math_expr   = sat_data.get("math_expr", "")
    options     = sat_data.get("options", {})
    correct     = sat_data["correct"]
    q_num       = sat_data.get("q_num", random.randint(1, 44))
    wrong_apr   = sat_data.get("wrong_approach", "")
    steps       = sat_data.get("solution_steps", [])
    answer_expr = options.get(correct, correct)
    script      = sat_data.get("script", [])
    if not script:
        script = _script_from_narration(sat_data)

    narr_path = os.path.join(output_dir, "narration.wav")

    print(f"[sat] Animated video #{q_num}: {q_text[:50]}")
    print(f"[sat] Script: {len(script)} segments | Steps: {len(steps)}")

    # ── 1. Pre-warm LaTeX cache ───────────────────────────────────────────────
    print("[sat] Pre-warming LaTeX cache...")
    for _e in ([math_expr, wrong_apr, answer_expr] + [s.get("math", "") for s in steps]):
        if _e and "$" in _e:
            for _c in [TEXT_DARK, RED_WRG, BLUE_WORK, GREEN_OK, NAVY]:
                _render_eq(_e, fontsize=52, color=_c)
    for _v in options.values():
        if "$" in _v:
            for _c in [TEXT_DARK, DIM_CLR, GREEN_OK]:
                _render_eq(_v, fontsize=32, color=_c)
    print("[sat] Cache ready.")

    # ── 2. TTS each segment individually → exact duration per segment ─────────
    print(f"[sat] TTS {len(script)} segments...")
    seg_wavs = []
    seg_durs = []
    for _i, _seg in enumerate(script):
        _wav = os.path.join(tmp, f"seg_{_i:03d}.wav")
        await _tts(_normalize_tts(_seg["text"]), _wav, voice=voice)
        _dur = sf.info(_wav).duration
        seg_wavs.append(_wav)
        seg_durs.append(_dur)
        print(f"[sat]  seg {_i+1}/{len(script)}: {_dur:.2f}s  \"{_seg['text'][:45]}\"")
    total_dur = sum(seg_durs)
    print(f"[sat] Narration: {total_dur:.1f}s")

    # ── 3. Concatenate WAV segments → single narration.wav ───────────────────
    _concat_wavs(seg_wavs, narr_path, ffmpeg)

    # ── 4. Render frames segment-by-segment → pipe to ffmpeg ─────────────────
    # XFADE: cross-dissolve length in frames.
    # Scene-change transitions also get a flash-to-white at midpoint.
    XFADE       = 25          # 417ms @ 60fps — long enough to feel smooth
    FLASH_PEAK  = 0.55        # max white overlay strength at midpoint (0=off, 1=full white)
    _WHITE      = np.full((H, W, 3), 255, dtype=np.float32)
    total_frames = int(total_dur * FPS)
    print(f"[sat] Rendering ~{total_frames} frames across {len(script)} segments...")

    silent = os.path.join(tmp, "silent.mp4")
    _ffmpeg_log  = os.path.join(tmp, "ffmpeg_enc.log")
    _ffmpeg_logf = open(_ffmpeg_log, "wb")
    enc = subprocess.Popen([
        ffmpeg, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24",
        "-r", str(FPS), "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        "-pix_fmt", "yuv420p", silent,
    ], stdin=subprocess.PIPE, stderr=_ffmpeg_logf)

    prev_last   = None
    prev_scene  = None
    thumb_saved = False

    def _render_frame(seg, lt):
        vp = _vis_state_for_scene(seg, steps, wrong_apr, correct, answer_expr, lt)
        return draw_frame(
            q_text=q_text, math_expr=math_expr, options=options, q_num=q_num,
            subtitle=_strip_latex(seg["text"]), **vp,
        )

    for seg_i, (seg, dur) in enumerate(zip(script, seg_durs)):
        n         = max(int(dur * FPS), 1)
        cur_scene = seg.get("scene", "hook")

        # ── Smart frame generation:
        # Hook scenes animate (arrow pulse varies with lt) → render every frame.
        # All other scenes are visually static within the segment → render ONE
        # frame and duplicate it, only rendering XFADE boundary frames individually.
        is_animated = (cur_scene == "hook")

        if is_animated:
            # Full per-frame render (arrow pulse)
            buf = []
            for fi in range(n):
                lt = fi / max(n - 1, 1)
                buf.append(_render_frame(seg, lt))
        else:
            # Render a single representative frame for the static body
            static_frame = _render_frame(seg, 0.0)
            if not thumb_saved and cur_scene in ("answer", "cta"):
                static_frame.save(os.path.join(output_dir, "thumbnail.png"))
                thumb_saved = True
            # Only materialise XFADE head + 1 tail frame; body will be written directly
            xfade_n = min(XFADE, n) if prev_last is not None else 0
            buf_head = [static_frame] * xfade_n   # will be overwritten by blend below
            buf_tail = static_frame                 # last frame (for next seg's xfade)

        # ── Transition from previous segment (crossfade blend) ────────────────
        if prev_last is not None:
            scene_change = (cur_scene != prev_scene)
            prev_arr = np.array(prev_last.convert("RGB"), dtype=np.float32)
            xfade_count = min(XFADE, n)

            if is_animated:
                for i in range(xfade_count):
                    t = _ease(i / (XFADE - 1))
                    cur_arr = np.array(buf[i].convert("RGB"), dtype=np.float32)
                    blended = prev_arr * (1 - t) + cur_arr * t
                    if scene_change:
                        mid_t   = 1.0 - abs(i / (XFADE - 1) - 0.5) * 2
                        flash_t = _ease(mid_t) * FLASH_PEAK
                        blended = blended * (1 - flash_t) + _WHITE * flash_t
                    buf[i] = Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))
            else:
                static_arr = np.array(static_frame.convert("RGB"), dtype=np.float32)
                for i in range(xfade_count):
                    t = _ease(i / (XFADE - 1))
                    blended = prev_arr * (1 - t) + static_arr * t
                    if scene_change:
                        mid_t   = 1.0 - abs(i / (XFADE - 1) - 0.5) * 2
                        flash_t = _ease(mid_t) * FLASH_PEAK
                        blended = blended * (1 - flash_t) + _WHITE * flash_t
                    buf_head[i] = Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))

        # ── Pipe frames to ffmpeg ─────────────────────────────────────────────
        if is_animated:
            prev_last = buf[-1]
            for frame in buf:
                enc.stdin.write(frame.convert("RGB").tobytes())
        else:
            xfade_count = len(buf_head) if prev_last is not None else 0
            # Write blended head
            for frame in buf_head:
                enc.stdin.write(frame.convert("RGB").tobytes())
            # Write static body (n - xfade_count copies) — avoid storing in memory
            static_rgb = static_frame.convert("RGB").tobytes()
            for _ in range(n - xfade_count):
                enc.stdin.write(static_rgb)
            prev_last = buf_tail

        prev_scene = cur_scene

        if seg_i % 5 == 0 or seg_i == len(script) - 1:
            mode = "anim" if is_animated else "static"
            print(f"[sat]  seg {seg_i+1}/{len(script)}: {n}f ({mode})  \"{seg['text'][:35]}\"")

    try:
        enc.stdin.close()
    except BrokenPipeError:
        pass
    _ffmpeg_logf.close()
    enc.wait()
    if enc.returncode != 0:
        log_txt = open(_ffmpeg_log, "rb").read().decode("utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"[sat] video encoding failed (rc={enc.returncode}):\n{log_txt}")

    # ── 7. Background music ───────────────────────────────────────────────────
    music = None
    music_dir = os.path.join(os.path.dirname(__file__), "music")
    if os.path.isdir(music_dir):
        tracks = [os.path.join(music_dir, f) for f in os.listdir(music_dir)
                  if f.lower().endswith((".mp3", ".wav"))]
        if tracks:
            music = random.choice(tracks)
    if not music:
        from quiz_renderer import _generate_suspense_music
        music = _generate_suspense_music(
            os.path.join(tmp, "_bg.wav"), duration=total_dur + 3)

    # ── 8. Mix audio + video ──────────────────────────────────────────────────
    final = os.path.join(output_dir, "final_short.mp4")
    _run_ffmpeg([
        ffmpeg, "-y",
        "-i", silent,
        "-i", narr_path,
        "-i", music,
        "-filter_complex",
        (f"[2:a]volume=0.18,atrim=duration={total_dur:.2f}[mus];"
         f"[1:a][mus]amix=inputs=2:duration=first:dropout_transition=2[aout]"),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total_dur:.2f}", final,
    ], "mix audio")

    # ── 9. Loudnorm ──────────────────────────────────────────────────────────
    norm_tmp = final.replace(".mp4", "_ln.mp4")
    try:
        _run_ffmpeg([
            ffmpeg, "-y", "-i", final,
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", norm_tmp,
        ], "loudnorm")
        os.replace(norm_tmp, final)
        print("[sat] Loudnorm ✓")
    except Exception as e:
        print(f"[sat] Loudnorm skipped: {e}")
        if os.path.exists(norm_tmp):
            os.remove(norm_tmp)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"[sat] Done -> {final}  ({total_dur:.1f}s)")
    return final


# ── LLM question + teaching script generator ──────────────────────────────────

def generate_sat_question(api_key: str, hook_hint: str = "") -> dict:
    """
    Call OpenRouter (Gemini 2.0 Flash Lite) to generate a SAT teaching Short.
    Falls back to hardcoded sqrt50+sqrt8 example on failure.
    """
    import requests as _req, time, json as _json

    _HOOKS = [
        "This SAT question is easy BUT everyone gets it wrong",
        "An impossible SAT problem",
        "The SAT wants you to overthink this",
        "Will you get fooled by this SAT question",
        "Elon Musk solved this SAT question in seconds",
        "Only 1% can solve this SAT problem",
        "This question tanks perfect SAT math scores",
        "This SAT question tricks 90% of people",
        "The cheat code to solving tricky exponents",
        "The weirdest question on the SAT",
        "This SAT question looks SO simple but it isn't",
        "The secret SAT hack most students never learn",
        "This tricky SAT question tricks everyone",
        "The easiest question on the SAT — or is it?",
        "This SAT problem ruins perfect scores",
    ]
    hook  = hook_hint or random.choice(_HOOKS)
    q_num = random.randint(1, 44)

    prompt = f"""You are a viral SAT tutor creating YouTube Shorts for @yoursatcoach style.

Generate a SAT math problem video in EXACTLY this JSON format. No markdown, no extra text.

{{
  "question_text": "Short phrase above the math, max 8 words (e.g. 'Solve for the problem')",
  "math_expr": "LaTeX in $...$ (e.g. '$\\\\sqrt{{50}} + \\\\sqrt{{8}} = ?$')",
  "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
  "correct": "one of A B C D",
  "hook_text": "{hook}",
  "q_num": {q_num},
  "wrong_approach": "LaTeX in $...$ showing the COMMON WRONG calculation students do",
  "solution_steps": [
    {{"label": "Step label max 5 words", "math": "$LaTeX$"}},
    {{"label": "Step label", "math": "$LaTeX$"}},
    {{"label": "It's X!", "math": "$final = answer$"}}
  ],
  "script": [
    {{"scene": "hook", "text": "Hook line — casual, punchy, under 20 words. No LaTeX."}},
    {{"scene": "hook", "text": "Read the question casually out loud."}},
    {{"scene": "wrong", "text": "Present the wrong approach students jump to. ('Easy, just... right?')"}},
    {{"scene": "wrong", "text": "Reveal why that's wrong. ('Except that's not how math works. Stop.')"}},
    {{"scene": "step", "step_index": 0, "text": "Explain step 0 conversationally. No LaTeX — spell out math verbally."}},
    {{"scene": "step", "step_index": 1, "text": "Explain step 1."}},
    {{"scene": "step", "step_index": 2, "text": "Explain step 2."}},
    {{"scene": "answer", "text": "Reveal answer. e.g. 'It's D. [answer spelled out]. Booyah.'"}},
    {{"scene": "cta", "text": "Want more SAT hacks? Click the video below."}}
  ]
}}

RULES:
- Genuine SAT-level math (algebra, radicals, exponents, percents, geometry — vary it, NOT always square roots).
- solution_steps: 3-5 steps. Last step label = 'It's [letter]!' or 'Answer: [letter]'.
- Most common wrong answer must be one of the options.
- script: each "text" is plain English, NO LaTeX, no dollar signs. Spell out all math verbally.
- script style: Gen-Z casual tutor. Use 'radical jail', 'ugly roots', 'smash together', 'booyah', 'silly goose', 'sus', 'Okay.', 'Stop.', 'Wait.' where natural.
- Add one script segment per solution_step (step_index 0 through N-1). Can split a step into 2 segments.
- CRITICAL: each "text" value must be MAX 20 words. Split longer thoughts into separate segments.
- Total script segments: 8-16. Always end with the cta segment exactly as shown.
- CRITICAL: The "answer" scene text MUST say the EXACT letter from your "correct" field. If correct="B", say "It's B." Never say a different letter.
- Return ONLY raw JSON, no markdown fences."""

    for attempt in range(2):
        try:
            resp = _req.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"model": "google/gemini-2.0-flash-lite-001",
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=90,
            )
            if resp.status_code == 429:
                if attempt == 0:
                    print("[sat] Rate limited — retrying in 15s...")
                    time.sleep(15); continue
                break
            if resp.status_code != 200:
                print(f"[sat] OpenRouter error {resp.status_code}: {resp.text[:200]}")
                break
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = _json.loads(raw)
            for k in ("math_expr", "options", "correct", "script"):
                if k not in data:
                    raise ValueError(f"Missing key: {k}")
            # Auto-split any segment over 20 words into shorter chunks
            split_script = []
            for seg in data["script"]:
                words = seg["text"].split()
                if len(words) <= 20:
                    split_script.append(seg)
                else:
                    # Split at sentence boundaries first, else at word 15
                    import re as _re
                    sentences = _re.split(r'(?<=[.!?])\s+', seg["text"])
                    base = {k2: v for k2, v in seg.items() if k2 != "text"}
                    for sent in sentences:
                        sent = sent.strip()
                        if not sent:
                            continue
                        sent_words = sent.split()
                        while sent_words:
                            chunk = sent_words[:18]
                            sent_words = sent_words[18:]
                            split_script.append({**base, "text": " ".join(chunk)})
            data["script"] = split_script

            # ── Enforce answer consistency ─────────────────────────────────
            import re as _re
            correct_letter = data["correct"].strip().upper()
            # Strip LaTeX for display (simple inline version — no import needed)
            correct_val = _re.sub(r'\$[^$]+\$', lambda m: _re.sub(r'\\[a-zA-Z]+|\{|\}', '', m.group()[1:-1]), data["options"].get(correct_letter, correct_letter)).strip()
            for seg in data["script"]:
                if seg.get("scene") == "answer":
                    txt = seg["text"]
                    txt = _re.sub(r"\b[Ii]t'?s\s+[A-D]\b",  f"It's {correct_letter}", txt)
                    txt = _re.sub(r"\bAnswer[:\s]+[A-D]\b",   f"Answer: {correct_letter}", txt)
                    seg["text"] = txt

            print(f"[sat] Generated: {data.get('math_expr','')[:60]}")
            print(f"[sat] Script: {len(data.get('script', []))} segments")
            print(f"[sat] Correct: {correct_letter} = {correct_val}")
            return data
        except Exception as e:
            print(f"[sat] generate error (attempt {attempt+1}): {e}")

    # ── Hardcoded fallback ─────────────────────────────────────────────────────
    return {
        "question_text": "Solve for the problem",
        "math_expr":     r"$\sqrt{50} + \sqrt{8} = ?$",
        "options": {
            "A": r"$\sqrt{58}$",
            "B": r"$\sqrt{78}$",
            "C": r"$\sqrt{88}$",
            "D": r"$\sqrt{98}$",
        },
        "correct": "D",
        "hook_text": "This SAT question is easy BUT everyone gets it wrong",
        "q_num": 18,
        "wrong_approach": r"$\sqrt{50} + \sqrt{8} = \sqrt{58}$",
        "solution_steps": [
            {"label": "Need LIKE terms to add",
             "math": r"$\sqrt{50} \neq \sqrt{8}$"},
            {"label": "Simplify sqrt(50):",
             "math": r"$\sqrt{50} = \sqrt{25 \cdot 2} = 5\sqrt{2}$"},
            {"label": "Simplify sqrt(8):",
             "math": r"$\sqrt{8} = \sqrt{4 \cdot 2} = 2\sqrt{2}$"},
            {"label": "Combine like terms:",
             "math": r"$5\sqrt{2} + 2\sqrt{2} = 7\sqrt{2}$"},
            {"label": "It's D!",
             "math": r"$7\sqrt{2} = \sqrt{49 \cdot 2} = \sqrt{98}$"},
        ],
        "script": [
            {"scene": "hook",  "text": "This SAT question is easy, but everyone gets it wrong."},
            {"scene": "hook",  "text": "Root 50 plus root 8. Look at this."},
            {"scene": "wrong", "text": "Okay, easy. Just add them up. Root 58, right?"},
            {"scene": "wrong", "text": "Except that's not how math works. Stop."},
            {"scene": "step",  "step_index": 0, "text": "Think of these ugly roots like two different variables. X and Y."},
            {"scene": "step",  "step_index": 0, "text": "We can't combine X plus Y. They're not the same letter. They're not like terms."},
            {"scene": "step",  "step_index": 1, "text": "So we need to simplify. Fifty is 25 times 2."},
            {"scene": "step",  "step_index": 1, "text": "Root of 25 is 5. So we pull that out of radical jail. Five root 2."},
            {"scene": "step",  "step_index": 2, "text": "Now look at 8. Eight is 4 times 2. Root of 4 is 2. So 2 root 2."},
            {"scene": "step",  "step_index": 3, "text": "Now both have root 2. Same letter. We can add. 5 plus 2 is 7. Seven root 2."},
            {"scene": "step",  "step_index": 4, "text": "To put the 7 back inside the root, square it. 49 times 2 is 98. Root 98."},
            {"scene": "answer","text": "It's D. Root 98. Booyah."},
            {"scene": "cta",   "text": "Want more SAT hacks? Click the video below."},
        ],
    }
