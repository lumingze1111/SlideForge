# SlideForge

A LangChain-powered multi-agent system for generating design-compliant presentation slides. Three specialized ReAct agents collaborate to enforce a formal design system — color theory, typographic scale, 8px spacing grid, and WCAG contrast — before a single pixel of HTML is written.

## Full Pipeline

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         INPUT                                            │
│          Topic (str)  +  Audience (str)  +  Slide description (str)     │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  STAGE 1 — Style Agent  (LangChain ReAct loop)                          │
│                                                                          │
│   list_schemes(mood)  ──▶  get_scheme_detail(name)  ──▶  check_contrast │
│                                                                          │
│   Decides:  scheme_name · visual_style · heading_font · body_font        │
│   Output:   StyleDecision                                                │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ StyleDecision
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  STAGE 2 — Design Agent  (LangChain ReAct loop)                         │
│                                                                          │
│   get_typography_spec()  ──▶  get_layout_spec(type)                     │
│   ──▶  suggest_element_size(content_type, priority)  (×N)               │
│                                                                          │
│   Decides:  layout_type · regions {x,y,w,h} · font_sizes · spacing      │
│   Output:   LayoutDecision                                               │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ StyleDecision + LayoutDecision
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  STAGE 3 — HTML Generator  (deterministic, no LLM)                      │
│                                                                          │
│   Applies color tokens, pixel-precise region coords, allowed font        │
│   sizes (from type scale), and 8px-grid spacing to produce clean HTML   │
│                                                                          │
│   Output:  slide_XX.html  (guaranteed compliant with design system)      │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ HTML string
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  STAGE 4 — Review Agent  (local Python + LLM scoring)                   │
│                                                                          │
│   preprocess_html() — runs locally, no API call:                        │
│     parse_html_structure · count_inline_styles · check_font_sizes       │
│     check_spacing · check_contrast_html                                  │
│          │                                                               │
│          └──▶  compact text report  ──▶  LLM scores JSON                │
│                                                                          │
│   Output:  ReviewReport { passed, score/100, issues[], suggestions[] }  │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ score ≥ 70 → passed ✅
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  EXPORT  —  html2pptx  (Node.js + Playwright + pptxgenjs)               │
│                                                                          │
│   node html2pptx_cli.js --html_dir slides/ --output deck.pptx           │
│                                                                          │
│   Output:  deck.pptx  (real OOXML, opens in PowerPoint / Keynote)       │
└──────────────────────────────────────────────────────────────────────────┘
```

### Stage Summary

| Stage | Driver | Key constraint enforced |
|-------|--------|------------------------|
| 1 · Style | ReAct agent | WCAG AA contrast ≥ 4.5:1 |
| 2 · Design | ReAct agent | 8px spacing grid, type scale |
| 3 · Generate | Deterministic template | Zero font/spacing violations |
| 4 · Review | Local + LLM | Score ≥ 70 gate |
| 5 · Export | Node CLI | Real PPTX (not PDF) |

## Architecture

## Design System

### Color Schemes

Six curated palettes, each validated against WCAG AA contrast (≥ 4.5:1):

| Key | Mood | Use case |
|-----|------|----------|
| `blue_professional` | professional | Corporate reports, business plans |
| `green_creative` | creative | Marketing, creative pitches |
| `purple_tech` | tech | Tech demos, product launches |
| `orange_warm` | warm | Education, community talks |
| `gray_modern` | modern | Design portfolios, product showcases |
| `teal_academic` | academic | Research papers, academic presentations |

### Typography Scale

Based on a modular type scale (px):

| Level | Size | Weight |
|-------|------|--------|
| H1 | 48 | 700 |
| H2 | 36 | 700 |
| H3 | 28 | 600 |
| H4 | 22 | 600 |
| H5 | 18 | 600 |
| H6 | 16 | 400 |
| Body | 16 | 400 |
| Body small | 14 | 400 |
| Caption | 12 | 400 |

### Layout Grid

- Canvas: **1280 × 720 px** (16:9)
- Safe margin: **60 px** horizontal, **40 px** vertical
- 12-column grid, 20 px gutter
- Spacing: **8 px grid** (xs=4 / sm=8 / md=16 / lg=24 / xl=32 / xxl=48)

Supported layout types: `single`, `two_column`, `sidebar_left`, `sidebar_right`, `header_content`

### Review Scoring (0 – 100)

| Check | Max points |
|-------|-----------|
| Inline style ratio < 20% | +20 |
| All font sizes on scale | +25 |
| All spacing on 8px grid | +25 |
| WCAG AA contrast | +30 |

A slide **passes** at score ≥ 70.

## Installation

```bash
pip install -r requirements.txt
```

Requires Python ≥ 3.11.

## Quick Start

```python
from langchain_openai import ChatOpenAI
from slideforge.agents import run_style_agent, run_design_agent, run_review_agent

llm = ChatOpenAI(
    base_url="https://api.deepseek.com",
    api_key="YOUR_KEY",
    model="deepseek-chat",
    temperature=0,
)

# 1. Choose color scheme and visual style
style = run_style_agent(llm, "AI History", "engineers")
print(style.scheme_name, style.visual_style)

# 2. Plan layout regions and font sizes
design = run_design_agent(llm, slide_description, "content")
print(design.layout_type, design.regions)

# 3. Audit an HTML slide
report = run_review_agent(llm, html_string)
print(report.score, report.passed, report.issues)
```

See `examples/quickstart.py` for a full walkthrough.

## Project Structure

```
SlideForge/
├── slideforge/
│   ├── agents/
│   │   ├── style_agent.py     # Color scheme selection (ReAct)
│   │   ├── design_agent.py    # Layout & typography planning (ReAct)
│   │   └── review_agent.py    # HTML quality audit (local + LLM scoring)
│   └── design_system/
│       ├── colors.py          # 6 color schemes + WCAG helpers
│       └── typography.py      # Type scale, spacing grid, layout regions
├── examples/
│   └── quickstart.py
└── requirements.txt
```

## Agent Details

### Style Agent

Uses a ReAct loop to compare color schemes before committing to one. Typical trace:

```
→ list_schemes(mood='tech')
→ list_schemes(mood='academic')
→ get_scheme_detail(name='purple_tech')
→ check_contrast(fg='#E6EDF3', bg='#0D1117')  # 16:1 — passes AAA
→ [final JSON decision]
```

Output (`StyleDecision`):

```python
class StyleDecision(BaseModel):
    scheme_name: str
    visual_style: str   # minimalist / bold / elegant / corporate / playful
    heading_font: str
    body_font: str
    reasoning: str
```

### Design Agent

Queries the design system tools to build pixel-precise layout regions. Typical trace:

```
→ get_typography_spec()
→ get_layout_spec(layout_type='header_content')
→ suggest_element_size(content_type='title', priority='primary')
→ suggest_element_size(content_type='body', priority='normal')
→ [final JSON decision]
```

Output (`LayoutDecision`):

```python
class LayoutDecision(BaseModel):
    layout_type: str
    regions: Dict[str, Dict]    # {"name": {"x", "y", "w", "h"}}
    font_sizes: Dict[str, int]
    spacing: Dict[str, int]
    reasoning: str
```

### Review Agent

Preprocessing runs entirely in Python (no LLM), then passes a compact text report to the LLM for scoring. This avoids context-window truncation when the HTML is large.

```
preprocess_html(html)  →  compact text report (local, no API call)
        ↓
LLM scoring agent      →  ReviewReport JSON
```

Output (`ReviewReport`):

```python
class ReviewReport(BaseModel):
    passed: bool
    score: int          # 0-100
    issues: List[str]
    suggestions: List[str]
```

## LLM Compatibility

Tested with **DeepSeek Chat** (`deepseek-chat`) via the OpenAI-compatible endpoint. Any model supported by `langchain-openai` that handles tool calling should work — OpenAI GPT-4o, Qwen-Max, etc.

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="https://api.deepseek.com",  # or https://api.openai.com/v1
    api_key="...",
    model="deepseek-chat",                # or gpt-4o, qwen-max, etc.
    temperature=0,
)
```

## License

MIT
