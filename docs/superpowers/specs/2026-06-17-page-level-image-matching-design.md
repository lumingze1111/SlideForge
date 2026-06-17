# Page-Level Image Matching Design

Date: 2026-06-17

## Goal

Improve SlideForge image relevance so each inserted image matches the current slide's title and content, not just the overall presentation theme.

The immediate target is the existing issue where generated decks include images that are technically inserted but semantically wrong, such as a Stephen Curry deck showing unrelated soccer, architecture, or office photos.

## Non-Goals

- Do not redesign the PPTX conversion pipeline.
- Do not add image generation.
- Do not require visual model analysis of image pixels.
- Do not force every slide to contain an image.
- Do not require exact-person matching for every theme. Page-level relevance is the priority.

## Current Problem

`ContentEnhancementAgent.search_image()` asks the image provider for one result and accepts it directly. The query is chosen by the LLM inside the ReAct loop, and there is no deterministic relevance check against the slide title, bullets, or global topic.

This creates two failure modes:

- The query can drift away from the slide topic.
- The first provider result can be visually unrelated even when the query is reasonable.

## Proposed Flow

Add a page-level image matching layer between the enhancement agent and `ImageSearchTool`.

For each slide, build an `ImageQueryContext` with:

- presentation topic
- slide index
- slide type
- slide title
- slide subtitle
- bullet text
- key statistic and label

Generate 2-3 search queries from that context. Prefer English query terms for Unsplash and Pexels, while preserving important names from the original topic and slide title.

Search multiple candidates per query, then score all candidates before downloading. The agent should only download the selected candidate.

## Candidate Scoring

Use a deterministic score based on provider metadata:

- Strong positive weight for slide title keyword matches.
- Positive weight for global topic keyword matches.
- Positive weight for bullet and key statistic keyword matches.
- Positive weight for landscape images and usable dimensions.
- Negative weight for obvious unrelated terms when they do not appear in the context.

Examples of unrelated-term penalties:

- `soccer`, `football`, `tennis`, `volleyball` when the slide context is basketball/NBA.
- `office`, `desk`, `architecture`, `landscape`, `wedding`, `food` when not present in the context.

The first implementation can keep this as a small local keyword scorer. It does not need another LLM call.

## Threshold and Fallback

If the top candidate clears the relevance threshold, download and insert it.

If no candidate clears the threshold:

1. Retry once with a broader query based on `topic + slide title`.
2. If that still fails, skip image insertion for that slide.

Skipping an irrelevant image is preferred over inserting a wrong one.

## Integration Points

The change should stay inside the content enhancement/image search boundary:

- Add query-context and scoring helpers near `slideforge/agents/content_enhancement_agent.py` or in a focused helper module under `slideforge/tools/`.
- Update the `search_image` tool implementation to request multiple candidates and select the best one.
- Keep the returned `ImageSuggestion` schema compatible with the current HTML renderer.
- Keep existing environment variables and API key behavior unchanged.

## Acceptance Criteria

- For a slide titled "三分革命" in a Stephen Curry presentation, basketball/NBA/shooting candidates outrank soccer, office, and architecture candidates.
- If all candidates are unrelated, the slide receives no image suggestion.
- Existing image insertion into HTML remains compatible with `generate_slides_html_with_images()`.
- Existing tests still pass.
- New tests cover query construction, candidate scoring, and unrelated-candidate rejection.

## Test Plan

Add focused unit tests without real network calls:

- Build a query context from a slide and verify generated queries include the presentation topic and slide title concepts.
- Provide mocked `ImageResult` candidates for basketball, soccer, office, and architecture; verify the basketball candidate wins for a Curry/NBA shooting slide.
- Provide only unrelated candidates and verify no image is selected.
- Verify `ContentEnhancementAgent` still returns `ImageSuggestion` objects with the existing fields when a candidate is selected.
