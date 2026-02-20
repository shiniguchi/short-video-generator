# Feature Research

**Domain:** Linear Review Pipeline UI — AI-Generated Video Ad Workflow
**Researched:** 2026-02-20
**Confidence:** MEDIUM

> Scope: NEW milestone only. Existing v1 CLI pipeline and v2 LP/analytics web UI are already built.
> This file covers the review workflow UI that lets users approve/reject/regenerate each pipeline stage.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Stage progress indicator (stepper) | Every multi-step tool shows current position. Users need orientation in a 5-stage pipeline. | LOW | Horizontal stepper, numbered, with checkmarks for done stages. Step N blocked until N-1 approved. |
| Per-item approve / reject actions | Binary decision is the baseline interaction in every content review tool (Frame.io, Filestage, Streamwork). | LOW | Each item (scene, image, clip) has explicit Approve / Reject buttons. Approve enables next stage. |
| Single-item regeneration | Users expect to re-run one bad item, not the entire stage. Visla, Runway Gen-4 both offer scene-level regeneration. | MEDIUM | Regenerate fires AI job for that item only. Does not reset approved siblings. |
| Inline prompt editing before regeneration | Guided regeneration (Notion, Copilot pattern) — user adjusts prompt or params, then reruns. "Blind regenerate" alone is frustrating. | MEDIUM | Show current prompt. Allow edit. Fire regeneration with new prompt. Save new prompt on approval. |
| Generation status / progress feedback | Pipeline jobs take 30–120s. Users need confidence the system is working. SSE streaming already exists in v2. | LOW | Reuse existing SSE infrastructure. Show per-item spinner while generating. |
| Thumbnail/preview grid per stage | Visual review requires seeing all items at once — grid is the standard (Frame.io, Boords, Visla). | MEDIUM | Script: text cards. Images: thumbnail grid. Video clips: playable thumbnails. |
| Stage gate enforcement | Approve stage N before stage N+1 starts. This is the linear pipeline contract. | LOW | Backend: stage N+1 jobs blocked until all stage N items approved. UI: next stage greyed/locked. |
| Rejection with reason (optional) | Gives AI regeneration context. Industry standard in content moderation tools. | LOW | Optional free-text on reject. Passed to regeneration prompt as constraint. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but change the experience.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Bulk approve-all shortcut | Most tools require per-item approval. One-click "Approve All" at stage level saves time when output quality is good. | LOW | Single button approves all items in stage at once. Gate still enforced — all items must be approved before next stage unlocks. |
| Side-by-side version comparison | Branching regeneration mode (not overwrite). User regenerates an item and can compare old vs. new before committing. ShapeOfAI research confirms branching beats overwrite for creative work. | MEDIUM | Show original and regenerated side-by-side. "Keep original" or "Use new" choice. No auto-overwrite. |
| Stage-level re-run (reset and redo) | If all items in a stage are bad, user can reset the entire stage and regenerate from scratch with updated params. | MEDIUM | Clears all items in stage. Re-fires generation job. Preserves approved items in prior stages. |
| Persistent prompt history per item | Track prompt evolution per scene/frame. User can see what changed between generations. Useful for iterating toward quality. | MEDIUM | Store each generation's prompt. Show as collapsed history under each item. |
| LP module review inline | Extend the same approve/reject/regenerate pattern to LP modules (headline, hero, CTA sections) using the same UI component. | LOW | Reuse review card component. Different content type, same interaction. Feeds into existing LP pipeline. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time collaborative review | Teams want to review together | Authentication, locking, presence, conflict resolution — massive scope for a single-user tool | Single-user review. Export review link (read-only) if sharing is needed |
| Full video timeline editor (trim, effects) | Users want to fix small issues in clips | Competes with CapCut/Premiere. 3-6 month build. Not a differentiator. | Regenerate with adjusted prompt. Export clip and edit externally. |
| Auto-advance to next stage on approval | Seems efficient — remove a click | Kills user control. Users need to verify the full stage before progressing. Accidental stage advances cause lost work. | Explicit "Proceed to Stage N+1" button after all items approved. |
| Parallel stage review (all stages open simultaneously) | Power users want to scan everything | Breaks the linear pipeline contract. Stage N+1 output depends on N approval. Invalid state if stages run out of order. | Linear only. Keep future stages locked. |
| Inline video clip editing (cut, crop) | Avoid external tool for minor tweaks | Requires integrating a video editor — FFmpeg wrappers, seeking, frame rendering. Months of work. | Prompt-driven regeneration handles most needs. Export and re-import for edge cases. |
| Persistent "undo" across stages | Users want to roll back approvals | Cascading regeneration invalidates all downstream work. State machine becomes unpredictable. | Show "reset stage" on current stage only. Prior stages stay approved. |

---

## Feature Dependencies

```
Stage Progress Indicator
    └──requires──> Stage Gate Enforcement (gating logic must exist to show locked/unlocked states)

Per-Item Approve / Reject
    └──requires──> Generation Status Feedback (items must exist before they can be reviewed)
    └──gates──> Stage Gate Enforcement (all items approved = stage complete)

Single-Item Regeneration
    └──requires──> Inline Prompt Editing (regeneration without prompt control = blind rerun, low value)
    └──requires──> Side-by-Side Comparison (regeneration without comparison = accidental overwrites)

Side-by-Side Version Comparison
    └──requires──> Single-Item Regeneration (no comparison without multiple versions)

Bulk Approve-All
    └──requires──> Per-Item Approve / Reject (shortcut for the baseline action)

LP Module Review
    └──requires──> Per-Item Approve / Reject (reuses same component)
    └──depends-on──> existing LP generation pipeline (v2 already built)

Stage-Level Re-Run
    └──requires──> Stage Gate Enforcement (must reset gate state)
    └──conflicts-with──> Persistent Undo Across Stages (don't build both)
```

### Dependency Notes

- **Inline prompt editing is prerequisite to regeneration:** Blind regeneration is frustrating. Users need prompt control before the feature has value.
- **Side-by-side comparison is prerequisite to single-item regeneration:** Without comparison, regeneration risks overwriting the best result. Build together.
- **Stage gate enforcement is the backbone:** All other features depend on the pipeline state machine being correct. Build this first.
- **LP module review reuses the review card component:** Design component once, extend to LP stage for free.

---

## MVP Definition

### Launch With (v1 — this milestone)

Minimum to make the review pipeline usable and gate-safe.

- [ ] Stage progress indicator (stepper) — user orientation in 5-stage flow
- [ ] Stage gate enforcement — blocks N+1 until N is fully approved
- [ ] Per-item approve / reject buttons — baseline review interaction
- [ ] Generation status / progress feedback — reuse SSE, show spinners per item
- [ ] Thumbnail/preview grid per stage — script as text cards, images as thumbnails, video as playable clips
- [ ] Inline prompt editing + single-item regeneration — must ship together; regeneration without prompt control is low value
- [ ] Rejection with optional reason — passed to regeneration prompt as constraint

### Add After Validation (v1.x)

Add once core review flow is working and users validate stage gating.

- [ ] Bulk approve-all — trigger: users report approval is tedious when output quality is good
- [ ] Side-by-side version comparison — trigger: users report accidentally losing a good generation
- [ ] Stage-level re-run — trigger: users report needing to redo a whole stage with different params
- [ ] LP module review — trigger: LP pipeline and review UI are both stable enough to extend

### Future Consideration (v2+)

Defer — scope, complexity, or dependencies not yet justified.

- [ ] Persistent prompt history per item — deferred: nice to have, not needed for core workflow. Add when users iterate extensively.
- [ ] Export review link (read-only share) — deferred: multi-user is out of scope for now
- [ ] Analytics on review patterns (rejection rates by stage) — deferred: no user base yet to analyze

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Stage gate enforcement | HIGH | LOW | P1 |
| Stage progress indicator | HIGH | LOW | P1 |
| Per-item approve / reject | HIGH | LOW | P1 |
| Generation status feedback | HIGH | LOW | P1 |
| Thumbnail/preview grid | HIGH | MEDIUM | P1 |
| Inline prompt editing | HIGH | MEDIUM | P1 |
| Single-item regeneration | HIGH | MEDIUM | P1 |
| Rejection with reason | MEDIUM | LOW | P1 |
| Bulk approve-all | HIGH | LOW | P2 |
| Side-by-side comparison | HIGH | MEDIUM | P2 |
| Stage-level re-run | MEDIUM | MEDIUM | P2 |
| LP module review | MEDIUM | LOW | P2 |
| Persistent prompt history | LOW | MEDIUM | P3 |
| Export review link | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch — without these the pipeline is not reviewable
- P2: Should have — prevents frustration after initial usage
- P3: Nice to have — future consideration

---

## Competitor Feature Analysis

| Feature | Frame.io | Visla Director Mode | Boords | ViralForge (Our Approach) |
|---------|----------|---------------------|--------|---------------------------|
| Per-asset approve/reject | Yes | Comment-based | Yes | Yes — explicit Approve/Reject per item |
| Stage-gating | No (parallel review) | Yes (storyboard then video) | No | Yes — linear gate, N+1 blocked until N done |
| Single-item regeneration | Via Firefly (Enterprise) | Yes — per scene | No | Yes — per scene/image/clip |
| Inline prompt editing | No | Yes | No | Yes — show/edit current prompt before regenerate |
| Bulk approve-all | No | No | No | Yes (v1.x) — differentiator |
| Side-by-side comparison | Yes (version compare) | No | No | Yes (v1.x) |
| Stepper/stage indicator | No (folder-based) | Yes | No | Yes — 5-stage horizontal stepper |
| LP module review | No | No | No | Yes (v1.x) — extend same component |

**Positioning:** ViralForge review UI is the only tool designed for a strict linear gate pipeline from script through video through LP. Competitors handle either collaborative document review (Frame.io) or storyboard-to-video (Visla) — not the full ad generation pipeline in a single review surface.

---

## Sources

- [AI UX Patterns: Regenerate — ShapeOfAI](https://www.shapeof.ai/patterns/regenerate) — overwrite vs. branching modes, guided regeneration patterns
- [The 4 Stages of AI Image Generation — Nielsen Norman Group](https://www.nngroup.com/articles/ai-imagegen-stages/) — define, explore, refine, export user model
- [Introducing AI Director Mode — Visla](https://www.visla.us/blog/news/introducing-ai-director-mode-storyboard-first-ai-video-with-real-control/) — scene-by-scene regeneration, selective scene-to-clip conversion
- [Frame.io at Adobe MAX 2025](https://blog.frame.io/2025/10/28/adobe-max-2025-connected-creativity-for-modern-content-production/) — per-asset approval, Firefly-powered variation generation
- [How to Speed Up Video Reviews Using AI — Spiel Creative](https://www.spielcreative.com/blog/ai-video-review-approval-workflow/) — timestamped comments, version control patterns
- [Stepper UI Examples — Eleken](https://www.eleken.co/blog-posts/stepper-ui-examples) — horizontal stepper, one-task-per-screen, visual completion states
- [How AI Content Generation Tools Handle Approval Workflows — Storyteq](https://storyteq.com/blog/how-do-ai-content-generation-tools-handle-content-approval-workflows/) — tiered approval pathways, per-stage reviewer routing
- [Content Review and Approval Best Practices — zipBoard](https://zipboard.co/blog/collaboration/content-review-and-approval-best-practices-tools-automation/) — status tracking, rapid iteration loops
- [Video Post-Production Review Process — MASV](https://massive.io/workflow/video-post-production-review-process/) — review-at-every-stage best practice
- [Free AI Storyboard Generator — Boords](https://boords.com/ai-storyboard-generator) — frame-specific feedback, approval status tracking

---
*Feature research for: Linear review pipeline UI (ViralForge v3)*
*Researched: 2026-02-20*
