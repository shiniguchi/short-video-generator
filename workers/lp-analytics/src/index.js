/**
 * Cloudflare Worker: LP Analytics
 *
 * Routes:
 *   OPTIONS *            - CORS preflight (204)
 *   POST   /track        - Receive beacon from LP page, write to D1 (204)
 *   GET    /analytics/:lp_id - Return per-LP stats (requires Bearer auth)
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const { pathname } = url;
    const method = request.method;

    // CORS preflight — must respond before any route check
    if (method === 'OPTIONS') {
      return corsResponse(null, 204);
    }

    // POST /track — fire-and-forget beacon from LP page
    if (pathname === '/track' && method === 'POST') {
      return handleTrack(request, env, ctx);
    }

    // GET /analytics/:lp_id — gated by Bearer token, called by Python backend
    const analyticsMatch = pathname.match(/^\/analytics\/([^/]+)$/);
    if (analyticsMatch && method === 'GET') {
      return handleAnalytics(request, env, analyticsMatch[1]);
    }

    return new Response('Not Found', { status: 404 });
  },
};

/**
 * POST /track
 * Parses beacon payload and writes to D1 asynchronously.
 * Uses request.text() + JSON.parse() because sendBeacon sends Content-Type: text/plain.
 */
async function handleTrack(request, env, ctx) {
  // Parse body — sendBeacon sends text/plain, so request.json() would fail
  const text = await request.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    return corsResponse(JSON.stringify({ error: 'invalid JSON' }), 400);
  }

  const { lp_id, event, referrer } = body;

  if (!lp_id || !event) {
    return corsResponse(JSON.stringify({ error: 'missing lp_id or event' }), 400);
  }

  // Non-blocking D1 write — response returns before DB write completes
  ctx.waitUntil(
    (async () => {
      if (event === 'pageview') {
        await env.DB.prepare(
          'INSERT INTO pageviews (lp_id, referrer, tracked_at) VALUES (?, ?, ?)'
        )
          .bind(lp_id, referrer || 'direct', Date.now())
          .run();
      } else if (event === 'form_submit') {
        await env.DB.prepare(
          'INSERT INTO form_submissions (lp_id, tracked_at) VALUES (?, ?)'
        )
          .bind(lp_id, Date.now())
          .run();
      }
    })()
  );

  // Return immediately — beacon is fire-and-forget
  return corsResponse(null, 204);
}

/**
 * GET /analytics/:lp_id
 * Returns pageview count, form submission count, and top 10 referrers.
 * Requires Authorization: Bearer <API_KEY>.
 */
async function handleAnalytics(request, env, lp_id) {
  // Auth gate
  const auth = request.headers.get('Authorization') || '';
  if (auth !== `Bearer ${env.API_KEY}`) {
    return new Response('Unauthorized', { status: 401 });
  }

  // Parallel count queries
  const [pvResult, fsResult] = await env.DB.batch([
    env.DB.prepare('SELECT COUNT(*) as count FROM pageviews WHERE lp_id = ?').bind(lp_id),
    env.DB.prepare('SELECT COUNT(*) as count FROM form_submissions WHERE lp_id = ?').bind(lp_id),
  ]);

  // Top referrers (separate query — batch only takes statements, not all queries)
  const referrers = await env.DB.prepare(
    'SELECT referrer, COUNT(*) as count FROM pageviews WHERE lp_id = ? GROUP BY referrer ORDER BY count DESC LIMIT 10'
  )
    .bind(lp_id)
    .all();

  return corsResponse(
    JSON.stringify({
      lp_id,
      pageviews: pvResult.results[0]?.count ?? 0,
      form_submissions: fsResult.results[0]?.count ?? 0,
      top_referrers: referrers.results,
    }),
    200
  );
}

/**
 * Builds a Response with CORS headers on every response.
 * body=null → empty response (e.g. 204).
 */
function corsResponse(body, status = 200) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Content-Type': body ? 'application/json' : 'text/plain',
  };
  return new Response(body, { status, headers });
}
