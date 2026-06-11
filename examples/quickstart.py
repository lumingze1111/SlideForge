"""
Quick-start example: run all three agents against a slide description.

Usage:
    python examples/quickstart.py
"""

from langchain_openai import ChatOpenAI
from slideforge.agents import run_style_agent, run_design_agent, run_review_agent

LLM = ChatOpenAI(
    base_url="https://api.deepseek.com",
    api_key="YOUR_API_KEY",   # replace with your key
    model="deepseek-chat",
    temperature=0,
)

TOPIC = "Artificial Intelligence History"
AUDIENCE = "Technical practitioners and researchers"

SLIDE_DESC = """
Title: From Philosophical Speculation to Scientific Foundation
Content:
  - Left: AI timeline chart (Ancient Greece to 1956)
  - Right: Three-column cards (Thought Origins / Mechanical Implementation / Discipline Birth)
  - Bottom: One key insight quote
Element types: title + timeline chart + content cards + pull quote
"""

# 1. Pick a color scheme and visual style
style = run_style_agent(LLM, TOPIC, AUDIENCE)
print(f"Style  → {style.scheme_name} / {style.visual_style}")
print(f"       reasoning: {style.reasoning}")

# 2. Plan the slide layout and typography
design = run_design_agent(LLM, SLIDE_DESC, "content")
print(f"Design → {design.layout_type}")
for region, coords in design.regions.items():
    print(f"         {region}: {coords}")

# 3. Audit an existing HTML slide (provide your own path)
try:
    html = open("slide_sample.html").read()
    report = run_review_agent(LLM, html)
    print(f"Review → score={report.score}/100  passed={report.passed}")
    for issue in report.issues:
        print(f"         ❌ {issue}")
except FileNotFoundError:
    print("Review → skipped (slide_sample.html not found)")
