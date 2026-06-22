# SlideForge Layout Template Pool Design

Date: 2026-06-22
Status: Draft for review

## Goal

Current PPTX output feels visually fixed because each `slide_type` maps to one mostly static HTML structure, and the PPTX conversion layer preserves that structure with deterministic scaling. The first iteration will add a stable layout template pool so generated decks can vary page composition without destabilizing HTML-to-PPTX conversion. The design should also leave a clean path to evolve into theme-driven template families later.

## Direction

Use "A iterating toward B":

- First release: deterministic template pool selected by slide type, content shape, media presence, and page position.
- Follow-up path: theme-driven template families such as business report,人物故事, technical explainer, and data insight.

This keeps the first implementation testable while preventing the architecture from becoming a dead end.

## In Scope

- Add a layout template model separate from raw HTML string rendering.
- Provide multiple templates for the common slide types: `cover`, `section`, `content`, `two_column`, `data`, and `closing`.
- Select templates deterministically so test runs and repeated generations remain predictable.
- Support media-aware variants when images or charts exist.
- Preserve the existing 1280x720 HTML slide contract and PPTX conversion assumptions.
- Add tests for template selection and generated HTML variation.

## Out of Scope

- No LLM-driven layout search in the first release.
- No visual scoring loop in the first release.
- No changes to the LLM direct PPTX converter prompt unless the template HTML exposes a clear compatibility issue.
- No browser-based slide editor in this change.

## Architecture

Introduce a small template layer between `PresentationOutline` and HTML rendering:

- `LayoutTemplate`: describes a named layout variant, supported slide types, media requirements, density preference, and future theme tags.
- `TemplateContext`: normalized inputs for selection, including slide type, slide index, total slides, bullet count, title length, media flags, and optional theme family.
- `TemplateSelector`: chooses one template deterministically using the context.
- Template renderer functions: render a slide into HTML using the chosen template.

The first version can live near the existing HTML generation code, but the selector and template metadata should be isolated enough to test without invoking LLMs, image search, or PPTX conversion.

## Template Set

Minimum first-release variants:

- `cover`: centered title, split hero, image/background hero.
- `section`: left rail, centered chapter, large numeral marker.
- `content`: classic bullets, right visual panel, stacked insight cards.
- `two_column`: comparison cards, pros/cons split, asymmetric feature story.
- `data`: big-stat plus notes, chart-forward, KPI strip.
- `closing`: centered conclusion, action list, quote/summary layout.

Not every slide needs every variant. The selector should prefer safe templates when content is sparse or media is missing.

## Selection Rules

The selector should be deterministic and explainable:

- Cover and closing pages can vary by deck position and media availability.
- High bullet count prefers templates with larger text regions.
- Data slides with charts prefer chart-forward templates.
- Slides with images prefer split or background templates depending on slide type.
- Without media, content slides rotate through text-only templates based on slide index.

Future theme-driven behavior can use `theme_family` and template tags without changing call sites.

## Data Flow

1. `GenerationPipeline` builds or enhances the outline as it does today.
2. HTML generation groups images and charts by slide index.
3. For each slide, create a `TemplateContext`.
4. `TemplateSelector` returns a `LayoutTemplate`.
5. The renderer uses that template to create slide HTML.
6. Existing PPTX conversion paths consume the HTML as before.

## Compatibility

The generated HTML must keep:

- `.slide` root with `data-pptx-slide`.
- 1280x720 fixed slide dimensions.
- Inline styles or measurable CSS that Playwright can inspect reliably.
- `data-notes` behavior for speaker notes.
- Existing image/chart insertion compatibility, or a replacement path with equivalent behavior.

## Error Handling

Template selection should never fail a generation run. If a template is unavailable or incompatible with the slide context, fall back to a default template for that slide type. Unknown slide types should use the content default.

## Testing

Add focused tests before implementation:

- Selector returns different templates across slide indexes for repeated content slides.
- Selector chooses media-aware templates when images or charts exist.
- High-density content avoids narrow or highly decorative templates.
- HTML rendering preserves `data-pptx-slide`, notes, fixed dimensions, and slide count.
- Existing image matching, color diversity, layout, and assembly tests still pass.

## Migration Path To Theme-Driven Templates

The first release should include template tags even if they are not fully used:

- `business`
- `story`
- `technical`
- `data`
- `minimal`

A later theme classifier can map topic analysis or chosen color proposal style into a `theme_family`, then the selector can prefer matching template tags. This evolves the system from a stable template pool into theme-driven template families without replacing the renderer.

## Acceptance Criteria

- A generated deck can contain multiple layout variants within the same slide type.
- Existing generation flow still works with and without images/charts.
- The template selection logic is covered by deterministic unit tests.
- The PPTX conversion interface remains unchanged.
- The implementation creates a visible foundation for future theme-driven template families.
