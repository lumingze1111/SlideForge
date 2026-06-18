# Background Diversity Design

## Context

SlideForge generates 3-5 color proposals for a topic, renders them in a browser preview, then uses the selected proposal to generate HTML slides and PPTX output. The current prompt asks for highly differentiated palettes, but there is no programmatic quality gate after the LLM response. As a result, several proposals can share visually similar backgrounds, especially dark blue or purple gradients.

## Goal

Make the color proposal selection step show backgrounds that are meaningfully different from each other while preserving topic-specific visual intent.

This change targets the proposal generation and preview-selection phase only. It does not alter HTML slide generation, PPTX conversion, layout assembly, image matching, or chart rendering.

## Selected Strategy

Use the A+B+C strategy chosen during visual review:

- A: add a programmatic similarity gate for proposal backgrounds.
- B: prefer coverage across light/dark, warm/cool/neutral, and background style categories.
- C: strengthen the LLM prompt so each proposal uses a distinct topic metaphor instead of nearby color variants.

## Architecture

Add a small color-diversity layer around `slideforge/agents/propose_agent.py`.

The layer will:

- Extract background candidates from `gradient_bg` or `background`.
- Parse solid hex colors and CSS gradients enough to classify their key colors.
- Compute simple descriptors: average hue, lightness, saturation, gradient type, and gradient angle when present.
- Classify each proposal into visual buckets: tone (`light`, `dark`, `mid`), temperature (`warm`, `cool`, `neutral`), and style (`solid`, `linear`, `radial`, `other_gradient`).
- Filter or reorder proposals so the final list avoids near-duplicate backgrounds and covers more buckets.

The prompt will also ask for distinct metaphor lanes, such as brand identity, environment, data/technology, human emotion, and bold contrast. These lanes guide the LLM before the programmatic gate cleans up the output.

## Components

### Prompt Update

`SYSTEM_PROMPT` will explicitly require each proposal to declare or reflect a distinct conceptual lane. It will instruct the LLM to avoid generating multiple dark cool gradients unless the topic requires them and each has a clearly different role.

### Background Analysis Helpers

New helper functions in `propose_agent.py` or a focused nearby module will parse background strings and produce descriptors. The parser will support:

- `#RRGGBB`
- `#RGB`
- `linear-gradient(...)`
- `radial-gradient(...)`

Unsupported color values will fall back to neutral descriptors instead of failing the run.

### Diversity Selection

A function such as `diversify_color_proposals(proposals)` will return a `DesignProposals` object with proposals filtered and reordered. It will preserve the recommended proposal when possible, but if the recommended proposal is a near-duplicate of a better-covered set, the function may update `recommended_index` to match the new order.

If fewer than 3 proposals remain after filtering, the function will restore the best available filtered-out proposals so the user still has choices.

## Data Flow

1. `run_propose_agent()` asks the LLM for `DesignProposals`.
2. The raw result is passed through `diversify_color_proposals()`.
3. The diversified proposals are shown by `pick_proposal()` and `preview_generator.py`.
4. The selected `ColorProposal.colors` continues into HTML slide generation unchanged.

## Error Handling

The diversity layer must be best-effort. It should not block presentation generation if parsing fails or the LLM returns unusual color strings.

- Invalid colors receive neutral fallback descriptors.
- Empty proposal lists pass through unchanged.
- Short proposal lists are preserved rather than aggressively filtered.
- The function avoids network calls and does not ask the LLM for repair during this change.

## Testing

Add focused unit tests for:

- Hex color parsing, including shorthand hex.
- Gradient color extraction and gradient type detection.
- Near-duplicate detection for similar dark blue gradients.
- Coverage preservation for clearly distinct light/dark and warm/cool proposals.
- Recommended index recalculation after filtering/reordering.
- Safe fallback when colors are invalid or missing.

## Acceptance Criteria

- Similar background proposals are filtered or deprioritized before preview.
- A set containing dark/cool, light/warm, and distinct gradient styles keeps that diversity.
- The browser preview still receives normal `ColorProposal` objects.
- Existing generation flow remains compatible when LLM output contains uncommon color formats.
