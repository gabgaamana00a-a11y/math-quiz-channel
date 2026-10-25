"""
math_tricks_renderer.py — renders a math-trick short with Manim.

Pipeline for one trick:
  1. narrate each line with a British edge-tts voice, measure durations
  2. write a Manim scene (vertical 1080x1920) whose steps are timed to the audio
  3. render it (subprocess, current python — must have manim installed)
  4. mux narration + loudnorm into the final MP4

No LaTeX is used (Manim Text only), so CI just needs cairo/pango + ffmpeg.
"""
from __future__ import annotations

import asyncio
import glob
import os
import subprocess
import sys

UK_VOICES = [
    "en-GB-SoniaNeural", "en-GB-RyanNeural", "en-GB-LibbyNeural",
    "en-GB-ThomasNeural", "en-GB-BellaNeural",
]


def pick_voice(voice: str | None = None) -> str:
    import random
    v = (voice or "").strip()
    if v.lower().startswith("en-gb"):
        return v
    return random.choice(UK_VOICES)


def _run_async(coro):
    """Run a coroutine even when called from inside a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


def _tts(text: str, out_path: str, voice: str, rate: str = "+6%") -> None:
    import edge_tts
    import soundfile as sf
    tmp = out_path + ".mp3"
    _run_async(edge_tts.Communicate(text, voice, rate=rate).save(tmp))
    data, sr = sf.read(tmp, dtype="float32")
    if data.ndim > 1:
        data = data[:, 0]
    sf.write(out_path, data, sr, subtype="PCM_16")
    os.remove(tmp)


def _build_narration(spec: dict, outdir: str, voice: str, min_dur: float = 1.3):
    import numpy as np
    import soundfile as sf
    durs, chunks, sr = [], [], None
    for i, line in enumerate(spec["narration"]):
        p = os.path.join(outdir, f"_n{i}.wav")
        _tts(line, p, voice)
        data, sr2 = sf.read(p, dtype="float32")
        if data.ndim > 1:
            data = data[:, 0]
        if sr is None:
            sr = sr2
        need = int(min_dur * sr2)
        if len(data) < need:
            data = np.pad(data, (0, need - len(data)))
        durs.append(len(data) / sr2)
        chunks.append(data)
        os.remove(p)
    narr_path = os.path.join(outdir, "narration.wav")
    sf.write(narr_path, np.concatenate(chunks), sr, subtype="PCM_16")
    return narr_path, durs


def _write_scene(scene_path: str, spec: dict, durs: list) -> None:
    code = f'''from manim import *

config.frame_width = 9.0
config.frame_height = 16.0
FONT = "DejaVu Sans"

CATEGORY = {spec["category"]!r}
HOOK = {spec["hook"]!r}
STEPS = {spec["steps"]!r}
RESULT = {spec["result"]!r}
DURS = {durs!r}


class TrickScene(Scene):
    def construct(self):
        self.camera.background_color = "#0B1533"
        cat = Text(CATEGORY, font_size=30, color=YELLOW, font=FONT).to_edge(UP, buff=0.6)
        hook = Text(HOOK, font_size=96, weight=BOLD, color=BLUE_B, font=FONT).move_to(UP * 3.6)
        self.play(FadeIn(cat, shift=DOWN * 0.3), FadeIn(hook, scale=1.15), run_time=0.5)
        self.wait(max(0.1, DURS[0] - 0.5))

        n = len(STEPS)
        top = (n - 1) * 1.15 / 2.0
        prev = None
        for i, s in enumerate(STEPS):
            obj = Text(s, font_size=38, color=WHITE, font=FONT).move_to(UP * (top - i * 1.15))
            anims = [FadeIn(obj, shift=RIGHT * 0.3)]
            if prev is not None:
                anims.append(prev.animate.set_color(GREY_B))
            self.play(*anims, run_time=0.35)
            self.wait(max(0.1, DURS[1 + i] - 0.35))
            prev = obj

        res = Text(RESULT, font_size=64, weight=BOLD, color=GREEN, font=FONT).move_to(DOWN * 6.3)
        self.play(FadeIn(res, scale=1.15), run_time=0.45)
        self.wait(max(0.2, DURS[-1] - 0.45 + 0.5))
'''
    with open(scene_path, "w", encoding="utf-8") as f:
        f.write(code)


def _render_scene(scene_path: str, media_dir: str) -> str:
    cmd = [sys.executable, "-m", "manim", "render", "-v", "ERROR",
           "--disable_caching", "--media_dir", media_dir,
           "-r", "1080,1920", "--fps", "30", scene_path, "TrickScene"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"manim render failed:\n{(r.stderr or r.stdout)[-1500:]}")
    hits = glob.glob(os.path.join(media_dir, "videos", "**", "TrickScene.mp4"), recursive=True)
    if not hits:
        raise RuntimeError("manim produced no mp4")
    return max(hits, key=os.path.getmtime)


def _mux(manim_mp4: str, narration: str, final: str) -> str:
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-i", manim_mp4, "-i", narration,
           "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "libx264", "-preset", "fast", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", final]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"mux failed:\n{r.stderr[-1200:]}")
    return final


def render_trick(spec: dict, output_dir: str, voice: str | None = None) -> dict:
    """Render one trick to {output_dir}/final_trick.mp4. Returns {final, voice, spec}."""
    os.makedirs(output_dir, exist_ok=True)
    voice = pick_voice(voice)
    print(f"[tricks] {spec['hook']}  (voice={voice})")
    narr, durs = _build_narration(spec, output_dir, voice)
    scene_path = os.path.join(output_dir, "scene.py")
    _write_scene(scene_path, spec, durs)
    media_dir = os.path.join(output_dir, "media")
    silent = _render_scene(scene_path, media_dir)
    final = os.path.join(output_dir, "final_trick.mp4")
    _mux(silent, narr, final)
    print(f"[tricks] done -> {final}")
    return {"final": final, "voice": voice, "spec": spec}
