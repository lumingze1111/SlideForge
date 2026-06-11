"""
AI 定制设计方案示例

展示如何让 Agent 根据主题生成专属配色+视觉风格，而非使用固定模版。
自动生成配色预览图，方便视觉对比。
"""

from langchain_openai import ChatOpenAI
from slideforge.agents.propose_agent import run_propose_agent, print_proposals, pick_proposal, generate_preview_image
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
print("  方式一：生成主题定制配色方案")
print("=" * 70)

proposals = run_propose_agent(
    llm,
    topic="深海探索与海洋保护",
    audience="环保组织和海洋科学家"
)

# print_proposals 会自动生成预览图并打印路径
print_proposals(proposals)

# 可以为单个方案手动生成预览图
chosen = proposals.proposals[0]
preview_path = generate_preview_image(chosen, output_path="./sea_theme_preview.png")
print(f"\n单独预览图已保存到：{preview_path}")


# 方式二：在交互式向导中使用 AI 定制
print("\n\n" + "=" * 70)
print("  方式二：完整交互式向导（含 AI 定制选项）")
print("=" * 70)

spec = select_design_spec(
    llm=llm,
    topic="深海探索与海洋保护",
    audience="环保组织和海洋科学家"
)

print(f"\n  最终设计规范：")
print(f"  配色：{spec.color_scheme.name}")
print(f"  主色：{spec.color_scheme.primary}")
print(f"  布局：{spec.layout_type}")
print(f"  风格：{spec.visual_style}")

