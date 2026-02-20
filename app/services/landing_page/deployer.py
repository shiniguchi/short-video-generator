"""Deploy landing pages to Cloudflare Pages via wrangler CLI."""

import asyncio
import os
import re
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


async def deploy_to_cloudflare_pages(html_path: str, run_id: str, settings) -> str:
    """Deploy LP HTML to Cloudflare Pages. Returns deployed URL.

    Flow: read HTML -> inject analytics beacon -> write to temp dir -> wrangler deploy.
    Raises RuntimeError on failure.
    """
    # Lazy import — optimizer may pull in dependencies
    from app.services.landing_page.optimizer import inject_analytics_beacon

    # Read original HTML (never has beacon — beacon is deploy-time only)
    html = Path(html_path).read_text(encoding="utf-8")

    # Inject analytics beacon if Worker URL configured
    html = inject_analytics_beacon(html, settings.cf_worker_url, run_id)

    # Validate config
    if not settings.cf_api_token:
        raise RuntimeError("CLOUDFLARE_API_TOKEN not set — configure cf_api_token in .env")
    if not settings.cf_pages_project_name:
        raise RuntimeError("CF_PAGES_PROJECT_NAME not set — configure cf_pages_project_name in .env")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write as index.html — CF Pages serves index.html at root
        out_path = Path(tmpdir) / "index.html"
        out_path.write_text(html, encoding="utf-8")

        # Build env for subprocess — inherit PATH for npx, add CF credentials
        env = os.environ.copy()
        env["CLOUDFLARE_API_TOKEN"] = settings.cf_api_token
        if settings.cf_account_id:
            env["CLOUDFLARE_ACCOUNT_ID"] = settings.cf_account_id

        cmd = [
            "npx", "wrangler", "pages", "deploy", tmpdir,
            "--project-name", settings.cf_pages_project_name,
            "--branch", "main",
            "--commit-dirty=true",
        ]

        logger.info("Deploying LP %s to Cloudflare Pages...", run_id)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )

        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("wrangler deploy timed out after 120s")

        output = stdout.decode()

        if proc.returncode != 0:
            logger.error("wrangler deploy failed:\n%s", output)
            raise RuntimeError(f"wrangler deploy failed (exit {proc.returncode}): {output[:500]}")

        # Parse deployed URL from wrangler stdout
        url = _extract_pages_url(output)
        if url:
            logger.info("LP %s deployed to: %s", run_id, url)
            return url

        # URL parsing failed but deploy succeeded — return project URL as fallback
        logger.warning("Could not parse URL from wrangler output, returning project URL")
        return f"https://{settings.cf_pages_project_name}.pages.dev"


def _extract_pages_url(output: str) -> str | None:
    """Extract deployed URL from wrangler stdout. Returns None if not found."""
    for line in output.splitlines():
        if "pages.dev" in line or "http" in line:
            m = re.search(r"https?://\S+", line)
            if m:
                return m.group(0).rstrip(".)")
    return None
