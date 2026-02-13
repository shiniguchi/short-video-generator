# Pitfalls Research

**Domain:** AI-powered short-form video generation pipeline
**Researched:** 2026-02-13
**Confidence:** MEDIUM-HIGH

## Critical Pitfalls

### Pitfall 1: Temporal Drift in AI Video Generation

**What goes wrong:**
Generated videos progressively degrade in quality as they extend beyond 2-3 seconds. Objects distort, faces blur, and motion becomes increasingly unrealistic. Stable Video Diffusion specifically suffers from autoregressive drift where each generated frame uses the previous frame as input, compounding any errors exponentially.

**Why it happens:**
Video diffusion models work sequentially, using each generated frame as the starting point for the next. Any error in frame N—a slightly deformed hand, a blurred face, an incorrect shadow—gets magnified in frame N+1 and exponentially worse as the sequence continues. Current models (including SVD) are limited to 4 seconds or less precisely because of this drift problem.

**How to avoid:**
- Design your pipeline to generate multiple short clips (2-4 seconds each) rather than one long video
- Use high-quality, clean keyframes with minimal visual ambiguity
- Implement quality gates that reject videos showing early drift signs (facial distortion, object deformation)
- Consider generating multiple candidates and selecting the best one
- Build composition logic that stitches short clips with transitions rather than relying on single long generations

**Warning signs:**
- Generated videos where the first second looks good but quality degrades noticeably
- Facial features or object boundaries becoming progressively blurrier
- Motion that starts smooth but becomes jerky or unnatural
- Background elements "melting" or warping over time

**Phase to address:**
Phase 1 (Core Infrastructure) - Build generation logic around 2-4 second clips from the start. Retrofitting this later requires rearchitecting the entire video generation and composition pipeline.

---

### Pitfall 2: GPU Resource Contention in Docker Microservices

**What goes wrong:**
Multiple containers compete for GPU resources, causing unpredictable performance, container hangs during video generation, and workers that claim to have GPU access but fall back to CPU. Particularly severe when Stable Video Diffusion tries to load models while FFmpeg is using GPU for encoding.

**Why it happens:**
Docker's GPU passthrough has several failure modes: (1) NVIDIA Container Runtime may ignore Docker Swarm's GPU resource assignments and expose all GPUs to all containers, (2) GPU decoder initialization fails inside containers even when the same code works on bare metal, (3) microservices containers can hang when transcoding certain video combinations with neither CPU nor GPU being utilized.

**How to avoid:**
- Use explicit GPU device specification in docker-compose.yml with `device_ids` rather than relying on Docker's automatic assignment
- Allocate one GPU device per container that needs it, avoiding shared GPU access across services
- Implement GPU memory monitoring and enforce hard limits
- Test GPU access verification as part of container health checks
- Consider sequential GPU-intensive operations (generate video first, then encode) rather than parallel
- Document GPU driver versions and container toolkit versions explicitly

**Warning signs:**
- Containers that work individually but hang when run together
- "CUDA out of memory" errors that resolve when services restart
- Video generation times that vary wildly (10x difference) between runs
- Health checks passing but actual GPU operations failing

**Phase to address:**
Phase 1 (Core Infrastructure) - GPU orchestration must be solved before any services run in production. This is not a scaling problem you can defer—it breaks basic functionality.

---

### Pitfall 3: Sequential Pipeline Failure Amnesia

**What goes wrong:**
A failure in step 5 of 8 forces the entire pipeline to restart from step 1, wasting GPU time, API credits, and processing hours. Even worse: when step 5 fails repeatedly (bad prompt, rate limit, malformed data), the system burns through resources rerunning steps 1-4 over and over without learning.

**Why it happens:**
Most sequential pipeline implementations lack checkpoint mechanisms. When an LLM-driven pipeline needs to pause, wait for external input, or recover from failure, there's no safe state to resume from. Pipeline state lives in memory, so any crash means starting over. No durability = expensive repetition.

**How to avoid:**
- Implement per-stage checkpointing with PostgreSQL or filesystem state storage
- Design each pipeline stage as an idempotent operation that can be safely retried
- Store intermediate artifacts (generated scripts, video clips, TTS audio) with unique IDs
- Build retry logic for individual stages, not entire pipelines
- Use Celery's task result backend to persist stage outputs
- Create a pipeline state machine that tracks progress and can resume from any step
- Log inputs and outputs for each stage to identify exactly where failures occurred

**Warning signs:**
- Monitoring shows the same video being processed through early stages multiple times
- High API costs for operations that should only run once per video
- Long delays before failure notification (because early stages need to re-run first)
- No way to manually restart from a specific pipeline stage

**Phase to address:**
Phase 2 (Basic Pipeline) - Build checkpointing from the first working pipeline. Adding this later means refactoring every stage and migrating to stateful architecture.

---

### Pitfall 4: Rate Limit Cascade Failures

**What goes wrong:**
The trend scraper hits Twitter's rate limit at 10am, causing all videos scheduled for the day to fail. By the time the rate limit resets at midnight, you've missed your publishing window. Or worse: multiple workers retry simultaneously, amplifying the rate limit problem instead of solving it.

**Why it happens:**
Social media platforms use sophisticated rate limiting (requests per IP per timeframe, not per worker). When not using official APIs, platforms employ aggressive blocking and detection. A 2025 WhatsApp vulnerability showed researchers bypassing UI throttling to scrape 3.5 billion accounts by hitting backend endpoints—and platforms learned from this to detect automation patterns more aggressively. Workers don't coordinate, so rate limit errors trigger simultaneous retries that make the problem worse.

**How to avoid:**
- Implement centralized rate limiting with Redis tracking requests across all workers
- Use exponential backoff with jitter (randomized delays) for retries: 1s, 2s, 4s, 8s + random(0-1s)
- Add delay randomization between requests (1-5 seconds) to mimic human behavior
- Use rotating residential proxies for scraping operations
- Implement circuit breakers that halt all requests to a service after threshold failures
- Monitor rate limit headers and proactively slow down before hitting limits
- Cache scraped content aggressively—regenerate from cache on rate limit errors
- Design trend collection to work on stale data (yesterday's trends) when scraping fails

**Warning signs:**
- Sudden spike in 429 errors across multiple services simultaneously
- Workers restarting and immediately hitting the same error
- Monitoring shows retry loops consuming resources without progress
- No visibility into remaining API quota or rate limit reset times

**Phase to address:**
Phase 1 (Core Infrastructure) - Build rate limiting and backoff mechanisms before any external API integration. Once you're blocked, you can't deploy a fix fast enough.

---

### Pitfall 5: Google Sheets as Database Anti-Pattern

**What goes wrong:**
Google Sheets becomes the bottleneck for the entire pipeline. Simple queries take seconds, writes fail silently, concurrent access causes version conflicts, and API quotas block operations during peak hours. The "single source of truth" becomes a single point of failure.

**Why it happens:**
Spreadsheets aren't databases. Google Sheets API has strict rate limits (60 requests/minute/user), no transaction support, no proper locking, and high latency (100-500ms per operation vs. <1ms for PostgreSQL). Survey data shows 60% of developers cite unclear requirements and improper tooling as primary contributors to project failures—using Sheets as a database is definitionally improper tooling.

**How to avoid:**
- Use Google Sheets ONLY as a human interface for configuration and manual review
- Sync Sheets data to PostgreSQL on a schedule (every 5-15 minutes) rather than reading directly
- Implement write-through caching: write to PostgreSQL immediately, sync to Sheets asynchronously
- Use batch operations for any Sheets API calls to minimize request count
- Never use Sheets for runtime data that changes frequently (task states, progress tracking)
- Design for Sheets unavailability: pipeline continues running on cached/stale data
- Validate all data from Sheets before use (users will put unexpected values in cells)

**Warning signs:**
- Pipeline speed varies dramatically based on time of day
- "Quota exceeded" errors during normal operations
- Race conditions where multiple services read stale data
- No way to know if a Sheets write actually succeeded
- Inability to roll back changes or audit history

**Phase to address:**
Phase 1 (Core Infrastructure) - Establish the Sheets-as-UI, PostgreSQL-as-database pattern from day one. Migrating from Sheets-as-database after building business logic around it requires rewriting the entire data layer.

---

### Pitfall 6: FFmpeg Filter Graph Complexity Explosion

**What goes wrong:**
Your video composition logic becomes a 500-line string of filter graph commands that works perfectly on one test video but produces corrupted output, frozen frames, or crashes on different input dimensions/codecs/frame rates. Debugging requires manually parsing filter graph syntax, and nobody on the team can maintain it.

**Why it happens:**
FFmpeg's filter graph syntax is notoriously difficult to work with programmatically. Even simple operations like "crossfade between two clips" require navigating complex input mapping, stream labeling, and filter chaining. Different video files have different colorspaces, pixel formats, and frame rates—and FFmpeg fails silently or produces corrupted output when assumptions don't hold.

**How to avoid:**
- Build a declarative composition layer that generates FFmpeg commands programmatically
- Normalize all AI-generated clips to consistent specs before composition: 1080x1920, 30fps, H.264, yuv420p
- Use separate, tested FFmpeg commands for each operation (resize, overlay, fade, audio mix) rather than one mega-command
- Implement input validation that checks video properties before processing
- Store working FFmpeg commands in version control as templates
- Build extensive test suite with various input types (different dimensions, codecs, durations)
- Never use fixed bitrate—use quality-based encoding (crf) or adaptive bitrate

**Warning signs:**
- FFmpeg commands that only work with specific test videos
- Output videos with visual glitches (green frames, frozen sections, corrupted audio sync)
- Team members afraid to modify composition logic
- No way to preview composition changes without processing full videos
- Different results when processing the same input twice

**Phase to address:**
Phase 2 (Basic Pipeline) - Build the composition abstraction layer during initial video assembly implementation. Refactoring raw FFmpeg commands to structured composition is extremely risky once production videos depend on exact command behavior.

---

### Pitfall 7: Prompt Engineering Without Output Format Specification

**What goes wrong:**
Your LLM-generated video scripts are inconsistent text blobs that require manual parsing, fail validation unpredictably, and break downstream TTS/video systems. One run produces perfect JSON, the next returns markdown, the third includes conversational preamble ("Here's a script for you...") that breaks your parser.

**Why it happens:**
40% of AI projects fail due to poorly crafted prompts. Without explicit format specifications, LLMs return unstructured text. Vague prompts like "write a TikTok script" leave the model guessing about structure, length, tone, and format. Missing role definition means inconsistent voice. Overloading with information confuses the model. The fundamental issue: assuming the LLM will infer your requirements rather than explicitly defining them.

**How to avoid:**
- Use structured output formats (JSON schema, Pydantic models) enforced at the API level
- Define explicit role and persona in every prompt: "You are a TikTok script writer optimizing for watch-through rate..."
- Specify exact output structure with examples in the prompt
- Include constraints explicitly: character limits, tone requirements, prohibited phrases
- Use few-shot examples showing input→output patterns
- Validate LLM output before passing to downstream systems
- Implement retry logic with refined prompts when validation fails
- Version control your prompts and test changes systematically

**Warning signs:**
- Parser errors requiring manual intervention
- Inconsistent script quality between runs with similar inputs
- Downstream systems failing because LLM output format changed
- No visibility into why some prompts work and others fail
- Scripts that sound robotic or off-brand

**Phase to address:**
Phase 2 (Basic Pipeline) - Build prompt engineering discipline during initial LLM integration. Production workarounds for bad prompts (manual parsing, exception handlers, retry logic) create permanent technical debt.

---

### Pitfall 8: Celery Task Memory Bloat with ETA Tasks

**What goes wrong:**
Your Celery workers consume progressively more memory until they crash, taking down scheduled video generation jobs. Memory usage doesn't correlate with active work—even idle workers leak memory. Restarting workers becomes a daily ritual.

**Why it happens:**
Celery's ETA/countdown tasks (scheduled for future execution) get assigned to a worker and reside in worker memory until they're ready to run. For a pipeline generating "1 video/day," this seems fine—until you have 100 videos scheduled across the next month, each holding video generation context in memory. The broker (Redis) also experiences high load from ETA tasks.

**How to avoid:**
- Use Celery Beat with periodic tasks instead of ETA/countdown for scheduled work
- Store task payloads in PostgreSQL and schedule lightweight "fetch and execute" tasks
- Configure Celery worker autoscaling to restart workers periodically
- Monitor worker memory usage and configure max-tasks-per-worker to force process recycling
- Use separate workers for scheduled vs. immediate tasks
- Minimize task payload size—pass IDs and fetch data from database in the task
- Configure task compression if payloads must be large

**Warning signs:**
- Worker memory growing steadily over hours/days
- Workers becoming unresponsive without high CPU usage
- Scheduled tasks not executing at their scheduled time
- Redis memory usage growing unexpectedly
- Worker restarts causing lost scheduled tasks

**Phase to address:**
Phase 3 (Scheduling & Orchestration) - Design task scheduling architecture to avoid ETA tasks before building scheduling features. Migrating from ETA to Beat requires rewriting scheduling logic.

---

### Pitfall 9: Async/Blocking Code Mixing in FastAPI

**What goes wrong:**
Your FastAPI server freezes completely when processing video uploads or making API calls. All incoming requests queue up waiting, even simple health checks. Users see timeouts on unrelated endpoints. The server appears completely dead despite low CPU usage.

**Why it happens:**
Using blocking operations (file I/O, synchronous API calls, subprocess.run for FFmpeg) inside async def functions freezes the entire event loop. FastAPI's async event loop can only process one blocking operation at a time—everything else waits. This is the single most common FastAPI production mistake.

**How to avoid:**
- Never use async def with blocking operations—use regular def functions for blocking work
- Use httpx.AsyncClient for external API calls, not requests
- Use aiofiles for file I/O operations
- Run blocking operations (FFmpeg, video processing) in background tasks via Celery
- Configure proper worker count: CPU cores × 2 for async workers
- Use async libraries: asyncpg instead of psycopg2, aioredis instead of redis-py
- Set appropriate timeouts for all external calls

**Warning signs:**
- Server becomes unresponsive periodically with low CPU usage
- Requests timing out that should be fast
- Health check endpoints timing out
- Logs showing long gaps with no activity
- Worker processes showing blocking I/O in system monitoring

**Phase to address:**
Phase 1 (Core Infrastructure) - Establish async/sync patterns during FastAPI setup. Mixing async/sync incorrectly creates subtle race conditions and performance issues that are extremely difficult to debug in production.

---

### Pitfall 10: TTS Audio Quality Lacks Human Review Gates

**What goes wrong:**
Your automated pipeline publishes videos with robotic-sounding narration, mispronounced words, wrong emphasis/tone, or completely wrong pacing that makes scripts unlistenable. By the time you notice, multiple low-quality videos have already been published, damaging your brand.

**Why it happens:**
TTS quality is subjective and context-dependent. Word Error Rate (WER) fails to capture naturalness, inflection, and emotional tone. ChatTTS and similar models suffer from stability issues: multi-speaker outputs, inconsistent audio quality, and autoregressive artifacts requiring multiple generations to get acceptable results. Unlike video where you can see quality issues, bad TTS requires listening—and automated metrics don't catch subtle problems like inappropriate tone or unnatural pacing.

**How to avoid:**
- Implement mandatory human review stage before publishing (Google Sheets review interface)
- Generate multiple TTS candidates (3-5) and use audio similarity/quality scoring to pick the best
- Build pronunciation dictionary for brand names, technical terms, and common mispronunciations
- Use SSML markup to control pacing, emphasis, and pauses
- Test TTS output with your target audience regularly
- Monitor published video engagement metrics to detect quality issues
- Configure TTS parameters explicitly: speaking rate, pitch, voice ID
- Build A/B testing for different TTS voices/settings

**Warning signs:**
- Comments complaining about "robotic voice" or "AI-sounding"
- Lower watch-through rates compared to videos with better narration
- Mispronunciations of brand names or technical terms
- Unnatural pauses or rushed pacing
- Inconsistent voice characteristics between videos

**Phase to address:**
Phase 4 (Review & Quality Control) - Build review gates before enabling automated publishing. Publishing low-quality audio destroys credibility faster than any other quality issue.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Running all services in one container | Faster local development, simpler docker-compose | Impossible to scale GPU vs non-GPU services separately, shared failure modes | Never—even MVP should separate GPU services |
| Using development server (fastapi dev) in production | Zero config deployment | Single-process bottleneck, no graceful shutdown, crashes lose all state | Never—use Gunicorn + Uvicorn from day one |
| Storing API keys in .env files | Quick local testing | Security breaches, leaked credentials, no rotation | Local dev only; use secrets manager for any deployed environment |
| Manual video publishing without review | Ship faster | Brand damage from quality issues, copyright problems, misinformation risks | Never for public content; maybe for internal testing |
| Hard-coded video dimensions in composition | Simpler code | Breaks when AI models change output format or platform requirements change | MVP only; must refactor before scaling |
| Polling Google Sheets every minute | Simple sync logic | API quota exhaustion, slow data propagation | Acceptable for MVP; migrate to webhook or manual sync trigger |
| Retrying failed tasks indefinitely | Resilient to transient errors | Infinite loops burning resources on permanent failures | Acceptable with max retry count (3-5) and exponential backoff |
| Using Redis for everything (cache + queue + state) | One service to manage | Single point of failure, unclear data guarantees, hard to debug state issues | Never—use PostgreSQL for state, Redis for cache/queue only |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Social Media APIs | Assuming rate limits are per-worker | Implement centralized rate tracking with Redis; limits are per-IP per-timeframe across all workers |
| Stable Video Diffusion | Expecting >4 second generations | Design for 2-4 second clips; compose multiple clips with transitions rather than generating long videos |
| Google Sheets API | Using as real-time database | Sync to PostgreSQL every 5-15min; read from DB, write-through to Sheets asynchronously |
| OpenAI/LLM APIs | Not specifying output format | Use structured outputs (JSON mode) with explicit schema; validate before downstream use |
| TTS APIs | Assuming pronunciation is correct | Build pronunciation dictionary; generate multiple candidates; implement human review |
| FFmpeg | Assuming input video format | Normalize all inputs to consistent specs (resolution, fps, codec, pixel format) before processing |
| Celery + Redis | Using ETA tasks for scheduling | Use Celery Beat + periodic tasks; store task data in PostgreSQL, not Redis memory |
| Docker GPU | Letting Docker auto-assign GPUs | Explicitly specify device_ids per container; test GPU access in health checks |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous pipeline execution | Long delays for each video (20+ minutes) | Run independent stages in parallel (TTS + video generation); use DAG orchestration | Day one—even single videos are slow |
| Loading AI models per-request | High memory usage, slow response times, OOM crashes | Load models at service startup; keep in GPU memory; implement model caching | >5 videos/day with model reloading overhead |
| Storing videos in PostgreSQL | Database bloat, slow queries, backup failures | Store videos in object storage (S3/MinIO); keep only metadata in PostgreSQL | >100 videos (multi-GB database size) |
| No connection pooling for PostgreSQL | Connection exhaustion, "too many connections" errors | Configure asyncpg connection pool; reuse connections across requests | >10 concurrent workers |
| Single worker processing all tasks | Queue backlog, missed deadlines, one failure stops everything | Configure multiple workers per task type; separate GPU-heavy from light tasks | >3 videos/day scheduled |
| No video preprocessing before composition | FFmpeg crashes, corrupted output, inconsistent results | Validate and normalize all video inputs to standard format before composition | First video with unexpected format (different codec, resolution, fps) |
| Unbounded retry loops | Resource exhaustion from infinitely retrying failed operations | Set max_retries (3-5) and exponential backoff; implement dead letter queues | First permanent failure (bad API key, invalid data) |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Not labeling AI-generated content | Platform bans, legal liability, misinformation accusations | Implement watermarking; add "AI-generated" disclaimer to metadata; follow TikTok/YouTube AI content policies |
| Scraping without proxy rotation | IP bans, account suspension, legal exposure | Use rotating residential proxies; implement rate limiting; respect robots.txt |
| No content validation before publishing | Copyright strikes, DMCA takedowns, account termination | Implement similarity detection; check against known copyrighted content; require human review |
| Storing training data or user content in logs | Privacy violations, data leaks, compliance issues | Sanitize logs; never log PII or API keys; use structured logging with automatic filtering |
| No authentication on admin endpoints | Unauthorized access, content manipulation, data exfiltration | Implement API key authentication; use OAuth for human interfaces; restrict by IP where possible |
| Exposing internal service ports | Direct database access, Redis exploitation, container escape | Use Docker networks; never expose ports to host except FastAPI ingress; implement network policies |
| No input sanitization for LLM prompts | Prompt injection attacks, inappropriate content generation, brand damage | Implement prompt templates; validate user inputs; use content filters; blacklist injection patterns |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress visibility for long operations | Users think system is broken; repeated submissions | Implement real-time progress updates via WebSocket or SSE; show estimated time remaining |
| Publishing on fixed schedule regardless of quality | Low-quality videos damage brand and audience trust | Require human approval before publishing; allow schedule adjustment based on review |
| No way to preview before publishing | Unable to catch quality issues until live | Build preview interface in Google Sheets integration; generate thumbnail + audio preview |
| Error messages that don't explain what to do | User frustration, support burden, abandonment | Provide actionable error messages with recovery steps; link to documentation |
| No notification when videos are ready/published | Users must manually check status; missed publishing windows | Implement notification system (email, Slack, webhook) for major status changes |
| Cannot edit or regenerate specific pipeline stages | Minor issues require full regeneration from scratch | Allow per-stage retry with parameter adjustment; save intermediate artifacts |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **AI-Generated Video:** Often missing quality validation — verify temporal consistency, object stability, facial coherence across frames
- [ ] **TTS Audio:** Often missing pronunciation correction — verify brand names, technical terms, and tone appropriateness
- [ ] **FFmpeg Composition:** Often missing input format validation — verify all inputs match expected dimensions, fps, codec before processing
- [ ] **Rate Limiting:** Often missing cross-worker coordination — verify rate limits are enforced globally with Redis, not per-worker
- [ ] **Error Handling:** Often missing retry strategy — verify max retries, exponential backoff, and dead letter queue configured
- [ ] **GPU Access:** Often missing health checks — verify GPU is actually accessible inside containers, not just driver installed
- [ ] **Pipeline Checkpointing:** Often missing recovery from mid-stage failures — verify can resume from any step without reprocessing earlier stages
- [ ] **Content Labeling:** Often missing AI-generated markers — verify videos include required platform disclosures and watermarks
- [ ] **Google Sheets Sync:** Often missing write failure handling — verify behavior when Sheets API is down or quota exceeded
- [ ] **API Authentication:** Often missing token rotation — verify secrets can be updated without service downtime

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Temporal Drift | LOW | Regenerate with shorter duration; increase quality of keyframe; generate multiple candidates and select best |
| GPU Contention | MEDIUM | Restart affected containers; reduce concurrent GPU operations; implement GPU queue management |
| Pipeline Failure | LOW-MEDIUM | Identify failed stage from logs; resume from checkpoint if available; otherwise retry from last completed stage |
| Rate Limit Hit | LOW | Wait for rate limit reset; switch to backup proxies/IPs; process queued items from cache if available |
| Google Sheets as Database | HIGH | Build PostgreSQL sync layer; migrate existing workflows; update all services to read from DB instead of Sheets |
| FFmpeg Filter Complexity | MEDIUM | Simplify to separate commands per operation; normalize inputs before processing; rebuild test suite |
| Bad Prompt Output | LOW | Refine prompt with explicit format; add validation; retry with corrected prompt; manual editing as last resort |
| Celery Memory Bloat | MEDIUM | Restart workers; migrate from ETA to Beat scheduling; configure worker max-tasks-per-worker |
| Async/Blocking Mix | MEDIUM | Identify blocking operations; move to def functions or background tasks; add timeouts; restart workers |
| TTS Quality Issues | LOW | Regenerate with different parameters; add to pronunciation dictionary; manual audio editing if urgent |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Temporal Drift | Phase 2 (Basic Pipeline) | Generate test videos >2 seconds; verify no quality degradation; reject if drift detected |
| GPU Contention | Phase 1 (Core Infrastructure) | Run concurrent GPU tasks; verify no hangs; monitor GPU utilization distribution |
| Pipeline Failure | Phase 2 (Basic Pipeline) | Simulate failures at each stage; verify checkpoint restore; confirm no duplicate work |
| Rate Limit Cascade | Phase 1 (Core Infrastructure) | Simulate rate limit errors; verify backoff behavior; confirm centralized tracking |
| Google Sheets Anti-Pattern | Phase 1 (Core Infrastructure) | Benchmark query performance; verify Sheets unavailable doesn't break pipeline |
| FFmpeg Complexity | Phase 2 (Basic Pipeline) | Test with various input formats; verify consistent output; confirm maintainability |
| Prompt Engineering | Phase 2 (Basic Pipeline) | Test prompts with edge cases; verify output format; confirm downstream system compatibility |
| Celery Memory Bloat | Phase 3 (Scheduling) | Monitor worker memory over 24 hours; verify scheduled tasks execute; confirm no memory leaks |
| Async/Blocking Mix | Phase 1 (Core Infrastructure) | Load test API endpoints; verify no request blocking; confirm appropriate timeouts |
| TTS Quality | Phase 4 (Review & Quality Control) | Human listening test; verify pronunciation; confirm tone appropriateness |

---

## Sources

### AI Video Generation
- [Top 10 Mistakes to Avoid When Using an AI Video Generator](https://medium.com/@ram-bharat/top-10-mistakes-to-avoid-when-using-an-ai-video-generator-6e37a250e62d)
- [Common Mistakes When Using Veo 3.1](https://vmake.ai/blog/common-mistakes-when-using-veo-3-1-how-to-get-the-best-results)
- [New AI system pushes the time limits of generative video](https://techxplore.com/news/2026-02-ai-limits-generative-video.html)
- [Common AI Video Creation Problems and Solutions](https://shortsninja.com/blog/common-ai-video-creation-problems-and-solutions/)
- [5 Common AI Video Mistakes Businesses Make](https://www.entrepreneur.com/growing-a-business/5-common-ai-video-mistakes-businesses-make-and-how-to/499769)

### Stable Video Diffusion
- [Stable Video Diffusion (Hugging Face)](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt)
- [Stable Diffusion Review 2026: Pros, Cons & Real Performance](https://saascrmreview.com/stable-diffusion-review/)

### Celery Task Queue
- [Celery: The Complete Guide for 2026](https://devtoolbox.dedyn.io/blog/celery-complete-guide)
- [The problems with (Python's) Celery](https://hatchet.run/blog/problems-with-celery)
- [Celery Official Documentation](https://docs.celeryq.dev/)

### FFmpeg
- [How I Built A Video Encoding And Streaming Service](https://medium.com/@amankumarsingh7702/how-i-built-a-video-processing-pipeline-and-then-set-it-on-fire-e6f6c3527600)
- [Building an Automated Video Processing Pipeline with FFmpeg](https://www.cincopa.com/learn/building-an-automated-video-processing-pipeline-with-ffmpeg)
- [FFmpeg Developer Documentation](https://www.ffmpeg.org/developer.html)

### Social Media Scraping
- [Social Media Scraping: The Complete Guide for 2026](https://sociavault.com/blog/social-media-scraping-complete-guide)
- [Best Social Media Scraping Tools for 2026](https://www.scrapingbee.com/blog/top-social-media-scraper-apis/)
- [Instagram: Logic bugs and the infinite life of scraped data](https://equixly.com/blog/2026/02/02/instagram-logic-bugs-and-the-infinite-life-of-scraped-data/)

### Docker GPU
- [Enable GPU support | Docker Docs](https://docs.docker.com/compose/how-tos/gpu-support/)
- [Using GPU With Docker: A How-to Guide](https://www.devzero.io/blog/docker-gpu)
- [Microservices container hangs with transcoding settings](https://github.com/immich-app/immich/issues/9939)

### Google Sheets API
- [Google Sheets API Best Practices and Common Mistakes](https://moldstud.com/articles/p-mastering-google-sheets-api-best-practices-common-pitfalls)
- [Avoid Common Mistakes in Structuring Google Sheets API Projects](https://moldstud.com/articles/p-avoid-common-mistakes-in-structuring-google-sheets-api-projects-a-comprehensive-guide)

### LLM Prompt Engineering
- [10 Common LLM Prompt Mistakes Killing Your AI's Performance](https://www.goinsight.ai/blog/llm-prompt-mistake/)
- [Top Prompt Engineering Pitfalls & Mistakes to Avoid in 2026](https://treyworks.com/common-prompt-engineering-mistakes-to-avoid/)
- [Common LLM Prompt Engineering Challenges and Solutions](https://latitude-blog.ghost.io/blog/common-llm-prompt-engineering-challenges-and-solutions/)

### Text-to-Speech
- [The Best Open-Source Text-to-Speech Models in 2026](https://www.bentoml.com/blog/exploring-the-world-of-open-source-text-to-speech-models)
- [Answers to TTS Problems: Avoid Bad Text-to-Speech Issues](https://murf.ai/blog/text-to-speech-voice-generation-common-issues-and-solutions)
- [Latency-Aware TTS Pipeline](https://www.emergentmind.com/topics/latency-aware-text-to-speech-tts-pipeline)

### PostgreSQL/Redis
- [Do You Need Redis? PostgreSQL Does Queuing, Locking, & Pub/Sub](https://spin.atomicobject.com/redis-postgresql/)
- [I replaced Redis with PostgreSQL and it was faster](https://medium.com/@dev_tips/i-replaced-redis-with-postgresql-and-it-was-faster-and-yes-i-was-surprised-too-0b07fa736bfa)
- [Why You Probably Don't Need Redis in 2026](https://medium.com/@morgan.e.ellis/why-you-probably-dont-need-redis-in-2026-a-deep-dive-into-postgres-18-036e89f00426)

### Pipeline Orchestration
- [AI Agent Orchestration Guide - Patterns and Tools (2026)](https://fast.io/resources/ai-agent-orchestration/)
- [Apache Airflow Resilience: Guide to Running Highly Available Data Pipelines](https://www.astronomer.io/airflow/resilience/)
- [Scalable MLOps Pipeline with Microservices](https://www.mdpi.com/2227-7080/14/1/45)

### Copyright and Legal
- [AI-Generated Content and Copyright Law: What We Know](https://builtin.com/artificial-intelligence/ai-copyright)
- [What are TikTok's AI content guidelines for 2026?](https://napolify.com/blogs/news/tiktok-ai-guidelines)
- [TikTok 2026 Policy Update - Brand & Creator Guide](https://www.darkroomagency.com/observatory/what-brands-need-to-know-about-tiktok-new-rules-2026)

### FastAPI Production
- [FastAPI Best Practices for Production: Complete 2026 Guide](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026)
- [FastAPI production deployment best practices](https://render.com/articles/fastapi-production-deployment-best-practices)
- [How to Deploy FastAPI in 2026](https://medium.com/@vamsichowdary54321/how-to-deploy-fastapi-in-2026-without-turning-deployment-into-a-side-project-ede4aae70627)

---
*Pitfalls research for: ViralForge AI Video Generation Pipeline*
*Researched: 2026-02-13*
