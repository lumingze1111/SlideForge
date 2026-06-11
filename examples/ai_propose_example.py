"""
AI 定制设计方案示例

展示如何让 Agent 根据主题生成专属配色+视觉风格，而非使用固定模版。
"""

from langchain_openai import ChatOpenAI
from slideforge.agents.propose_agent import run_propose_agent, print_proposals, pick_proposal
from slideforge.interactive import select_design_spec

# 配置 LLM
llm = ChatOpenAI(
    base_url="https://api.deepseek.com",
    api_key="YOUR_API_KEY",   # 替换为你的 DeepSeek API Key
    model="deepseek-chat",
    temperature=0.7,  # 稍高的温度让方案更有创意
)

# 方式一：单独调用 Propose Agent
print("=" * 70)
print("  方式一：单独生成配色方案")
print("=" * 70)

proposals = run_propose_agent(
    llm,
    topic="量子计算的未来",
    audience="技术研究人员和投资人"
)

print_proposals(proposals)
chosen = pick_proposal(proposals)

print(f"\n  已选择：{chosen.name}")
print(f"  主色：{chosen.primary}")
print(f"  视觉风格：{chosen.visual_style}")


# 方式二：在交互式向导中使用 AI 定制
print("\n\n" + "=" * 70)
print("  方式二：完整交互式向导（含 AI 定制选项）")
print("=" * 70)

spec = select_design_spec(
    llm=llm,
    topic="量子计算的未来",
    audience="技术研究人员和投资人"
)

print(f"\n  最终设计规范：")
print(f"  配色：{spec.color_scheme.name}")
print(f"  布局：{spec.layout_type}")
print(f"  风格：{spec.visual_style}")
