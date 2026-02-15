"""Run the full UGC ad pipeline directly (without Celery/FastAPI).

Executes all pipeline steps sequentially and outputs the final video.
"""
import sys
import os
import logging
import time
from uuid import uuid4

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override DATABASE_URL for local SQLite (no PostgreSQL needed)
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///test_pipeline.db'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    pipeline_start = time.time()

    product_name = "HydroGlow Smart Bottle"
    description = (
        "Self-cleaning UV water bottle with temperature display. "
        "UV-C LED self-cleaning every 2 hours, temperature display on cap, "
        "keeps drinks cold for 24 hours, BPA-free stainless steel, "
        "USB-C rechargeable with 30-day battery."
    )
    target_duration = 30

    print("=" * 60)
    print("UGC x PRODUCT MARKETING AD - FULL PIPELINE")
    print("=" * 60)
    print(f"Product: {product_name}")
    print(f"Target Duration: {target_duration}s")
    print()

    # ── STEP 1: Product Analysis ────────────────────────────────
    print("=" * 60)
    print("STEP 1/7: Product Analysis (Gemini)")
    print("=" * 60)
    step_start = time.time()

    from app.services.ugc_pipeline.product_analyzer import analyze_product
    analysis = analyze_product(
        product_name=product_name,
        description=description,
        image_count=1,
        style_preference="selfie-review"
    )
    print(f"  Category: {analysis.category}")
    print(f"  UGC Style: {analysis.ugc_style}")
    print(f"  Tone: {analysis.emotional_tone}")
    print(f"  Visual Keywords: {analysis.visual_keywords[:3]}...")
    print(f"  Duration: {time.time() - step_start:.1f}s")
    print()

    # ── STEP 2: Product Reference Image ─────────────────────────
    print("=" * 60)
    print("STEP 2/7: Product Reference Image (Imagen)")
    print("=" * 60)
    step_start = time.time()

    from app.services.image_provider import get_image_provider
    image_provider = get_image_provider()

    product_image_paths = image_provider.generate_image(
        prompt=f"Product photography of a {product_name} - sleek silver stainless steel smart water bottle with digital temperature display on black cap, USB-C charging port, clean white background, studio lighting",
        width=720,
        height=1280,
        num_images=1
    )
    product_image_path = product_image_paths[0]
    print(f"  Product image: {product_image_path}")
    print(f"  Size: {os.path.getsize(product_image_path):,} bytes")
    print(f"  Duration: {time.time() - step_start:.1f}s")
    print()

    # ── STEP 3: Hero Image ──────────────────────────────────────
    print("=" * 60)
    print("STEP 3/7: Hero Image Generation (Imagen)")
    print("=" * 60)
    step_start = time.time()

    from app.services.ugc_pipeline.asset_generator import generate_hero_image
    hero_image_path = generate_hero_image(
        product_image_path=product_image_path,
        ugc_style=analysis.ugc_style,
        emotional_tone=analysis.emotional_tone,
        visual_keywords=analysis.visual_keywords
    )
    print(f"  Hero image: {hero_image_path}")
    print(f"  Size: {os.path.getsize(hero_image_path):,} bytes")
    print(f"  Duration: {time.time() - step_start:.1f}s")
    print()

    # ── STEP 4: Script Generation ───────────────────────────────
    print("=" * 60)
    print("STEP 4/7: Script Generation (Gemini 2-call)")
    print("=" * 60)
    step_start = time.time()

    from app.services.ugc_pipeline.script_engine import generate_ugc_script
    breakdown = generate_ugc_script(
        product_name=product_name,
        description=description,
        analysis=analysis,
        target_duration=target_duration
    )
    print(f"  A-Roll Scenes: {len(breakdown.aroll_scenes)}")
    for i, scene in enumerate(breakdown.aroll_scenes, 1):
        print(f"    Scene {i}: {scene.duration_seconds}s, {scene.camera_angle}")
    print(f"  B-Roll Shots: {len(breakdown.broll_shots)}")
    for i, shot in enumerate(breakdown.broll_shots, 1):
        print(f"    Shot {i}: overlay_start={shot.overlay_start}s")
    print(f"  Total Duration: {breakdown.total_duration}s")
    print(f"  Duration: {time.time() - step_start:.1f}s")
    print()

    # ── STEP 5: A-Roll Generation ───────────────────────────────
    print("=" * 60)
    print(f"STEP 5/7: A-Roll Generation ({len(breakdown.aroll_scenes)} clips via Veo)")
    print("=" * 60)
    step_start = time.time()

    from app.services.ugc_pipeline.asset_generator import generate_aroll_assets
    aroll_scenes_dicts = [s.model_dump() for s in breakdown.aroll_scenes]
    aroll_paths = generate_aroll_assets(
        aroll_scenes=aroll_scenes_dicts,
        hero_image_path=hero_image_path
    )
    print(f"  Generated {len(aroll_paths)} A-Roll clips:")
    for i, p in enumerate(aroll_paths, 1):
        size = os.path.getsize(p)
        is_real = size > 10000
        print(f"    Clip {i}: {p} ({size:,} bytes, real={is_real})")
    print(f"  Duration: {time.time() - step_start:.1f}s")
    print()

    # ── STEP 6: B-Roll Generation ───────────────────────────────
    print("=" * 60)
    print(f"STEP 6/7: B-Roll Generation ({len(breakdown.broll_shots)} clips via Imagen+Veo)")
    print("=" * 60)
    step_start = time.time()

    from app.services.ugc_pipeline.asset_generator import generate_broll_assets
    broll_shots_dicts = [s.model_dump() for s in breakdown.broll_shots]
    broll_paths = generate_broll_assets(
        broll_shots=broll_shots_dicts,
        product_images=[product_image_path]
    )
    print(f"  Generated {len(broll_paths)} B-Roll clips:")
    for i, p in enumerate(broll_paths, 1):
        size = os.path.getsize(p)
        is_real = size > 10000
        print(f"    Clip {i}: {p} ({size:,} bytes, real={is_real})")
    print(f"  Duration: {time.time() - step_start:.1f}s")
    print()

    # ── STEP 7: Final Composition ───────────────────────────────
    print("=" * 60)
    print("STEP 7/7: Final Composition (MoviePy)")
    print("=" * 60)
    step_start = time.time()

    from app.services.ugc_pipeline.ugc_compositor import compose_ugc_ad
    from app.config import get_settings

    settings = get_settings()
    output_path = os.path.join(settings.composition_output_dir, f"ugc_ad_{uuid4().hex[:8]}.mp4")
    os.makedirs(settings.composition_output_dir, exist_ok=True)

    broll_metadata = []
    for i, shot_dict in enumerate(broll_shots_dicts):
        broll_metadata.append({
            "path": broll_paths[i],
            "overlay_start": shot_dict.get("overlay_start", 0.0)
        })

    final_path = compose_ugc_ad(
        aroll_paths=aroll_paths,
        broll_metadata=broll_metadata,
        output_path=output_path
    )
    print(f"  Final video: {final_path}")
    print(f"  Size: {os.path.getsize(final_path):,} bytes")
    print(f"  Duration: {time.time() - step_start:.1f}s")
    print()

    # ── DONE ────────────────────────────────────────────────────
    total_time = time.time() - pipeline_start
    print("=" * 60)
    print("PIPELINE COMPLETE!")
    print("=" * 60)
    print(f"  Final Video: {final_path}")
    print(f"  Total Time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"  Product: {product_name}")
    print(f"  Category: {analysis.category}")
    print(f"  A-Roll Scenes: {len(aroll_paths)}")
    print(f"  B-Roll Shots: {len(broll_paths)}")


if __name__ == "__main__":
    main()
