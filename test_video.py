"""Generate a test SAT video using the hardcoded sqrt50+sqrt8 fallback data."""
import asyncio, os, time

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from sat_renderer import create_sat_video, generate_sat_question

OUTPUT_DIR = "output/test_sat_video"
API_KEY    = open(".env").read().split("OPENROUTER_API_KEY=")[1].split()[0]

async def main():
    t0 = time.time()
    print("=" * 60)
    print("SAT VIDEO TEST — generating new question via LLM")
    print("=" * 60)

    print("[test] Calling generate_sat_question...")
    sat_data = generate_sat_question(API_KEY)
    print(f"[test] Got question: {sat_data.get('question_text', '?')[:60]}")

    final = await create_sat_video(sat_data, OUTPUT_DIR, voice="af_sarah")

    elapsed = time.time() - t0
    size_mb = os.path.getsize(final) / 1_048_576
    print(f"\n{'='*60}")
    print(f"Done in {elapsed:.0f}s  |  {size_mb:.1f} MB")
    print(f"Output: {final}")
    print(f"Thumbnail: {OUTPUT_DIR}/thumbnail.png")

asyncio.run(main())
