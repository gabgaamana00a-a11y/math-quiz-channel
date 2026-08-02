"""Generate a test UK trivia short — renders the video, does NOT upload."""
import asyncio, os, time

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from main import create_single_short
from uk_trivia import get_used_questions, load_questions

OUTPUT_DIR = "output/test_uk_trivia"

async def main():
    t0 = time.time()
    print("=" * 60)
    print("UK TRIVIA VIDEO TEST — render only, NO upload to YouTube/TikTok")
    print("=" * 60)
    print(f"[test] Questions in bank: {len(load_questions())}")
    print(f"[test] Already used:      {len(get_used_questions())}")

    result = await create_single_short(
        topic="UK trivia test",
        niche="uk_trivia",
        output_dir=OUTPUT_DIR,
        upload=False,
        voice="af_sarah",
    )

    elapsed = time.time() - t0
    final = result["paths"]["final"]
    size_mb = os.path.getsize(final) / 1_048_576 if os.path.exists(final) else 0
    print(f"\n{'='*60}")
    print(f"Done in {elapsed:.0f}s  |  {size_mb:.1f} MB")
    print(f"Final:     {final}")
    print(f"Thumbnail: {result['paths']['thumbnail']}")
    print(f"post.txt:  {OUTPUT_DIR}/post.txt")

asyncio.run(main())
