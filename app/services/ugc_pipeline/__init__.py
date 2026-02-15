"""UGC Product Ad Pipeline services."""
from app.services.ugc_pipeline.product_analyzer import analyze_product
from app.services.ugc_pipeline.script_engine import generate_ugc_script
from app.services.ugc_pipeline.asset_generator import (
    generate_hero_image,
    generate_aroll_assets,
    generate_broll_assets
)
from app.services.ugc_pipeline.ugc_compositor import compose_ugc_ad

__all__ = [
    "analyze_product",
    "generate_ugc_script",
    "generate_hero_image",
    "generate_aroll_assets",
    "generate_broll_assets",
    "compose_ugc_ad"
]
