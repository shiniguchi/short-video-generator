"""Cloudflare analytics client — queries Worker /analytics/:lp_id endpoint."""

import httpx
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


class CloudflareAnalyticsClient:
    """Queries the Cloudflare Worker analytics endpoint with Bearer auth."""

    def __init__(self):
        settings = get_settings()
        self.worker_url = settings.cf_worker_url.rstrip("/")
        self.api_key = settings.cf_worker_api_key

    async def get_lp_analytics(self, lp_id: str) -> dict:
        """Fetch analytics for a landing page from the Cloudflare Worker.

        Returns graceful fallback dict when Worker URL is not configured.
        """
        # Return empty stats when Worker not configured (local dev)
        if not self.worker_url:
            return {
                "lp_id": lp_id,
                "pageviews": 0,
                "form_submissions": 0,
                "top_referrers": [],
                "error": "Analytics not configured",
            }

        url = f"{self.worker_url}/analytics/{lp_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            logger.warning("Analytics Worker request failed for %s: %s", lp_id, e)
            return {
                "lp_id": lp_id,
                "pageviews": 0,
                "form_submissions": 0,
                "top_referrers": [],
                "error": str(e),
            }
