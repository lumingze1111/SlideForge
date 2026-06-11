"""
SlideForge - 完整独立的 PPT 生成流程

流程：
1. LLM 生成配色方案 → 用户在浏览器选择
2. LLM 生成大纲结构方案 → 用户在浏览器选择
3. 根据选定方案生成详细内容
4. 渲染 HTML 预览
5. 导出 PPTX
"""

from langchain_openai import ChatOpenAI
from slideforge.agents.propose_agent import run_propose_agent, pick_proposal
from slideforge.agents.outline_proposal import generate_outline_proposals, pick_outline_proposal
from slideforge.agents.html_generator import generate_outline, generate_slides_html
from slideforge.pptx_exporter import export_pptx


def main() -> None:
    topic = "AI与艺术的融合：探讨人工智能如何改变创意产业"
    audience = "创意工作者与科技爱好者"
    pages = 8

    llm = ChatOpenAI(
        base_url="https://api.deepseek.com",
        api_key="sk-be370742a8c549eeb5a971664b2f7ac6",
        model="deepseek-chat",
        temperature=0.7,
    )

    print("\n" + "═" * 70)
    print("  🎯 SlideForge — AI 驱动演示文稿生成器")
    print("═" * 70)
    print(f"  主题：{topic}")
    print(f"  受众：{audience}")
    print(f"  页数：{pages}")

    # ── 步骤 1：配色方案选择 ─────────────────────────────────────────────
    print(f"\n  🎨 正在生成配色方案...")
    color_proposals = run_propose_agent(llm, topic=topic, audience=audience)
    print(f"  ✓ 生成了 {len(color_proposals.proposals)} 套配色方案")
    
    chosen_color = pick_proposal(color_proposals, topic=topic)

    # ── 步骤 2：大纲结构选择 ─────────────────────────────────────────────
    print(f"\n  📋 正在生成大纲结构方案...")
    outline_proposals = generate_outline_proposals(llm, topic=topic, audience=audience, pages=pages)
    print(f"  ✓ 生成了 {len(outline_proposals.proposals)} 套大纲方案")
    
    chosen_outline = pick_outline_proposal(outline_proposals, topic=topic)

    # ── 步骤 3：根据选定大纲生成详细内容 ────────────────────────────────
    print(f"\n  📝 正在生成幻灯片详细内容（{chosen_outline.slide_count} 页）...")
    outline = generate_outline(llm, topic=topic, audience=audience, pages=chosen_outline.slide_count)
    print(f"  ✓ 内容生成完成，共 {len(outline.slides)} 页")

    # ── 步骤 4：渲染 HTML 预览 ───────────────────────────────────────────
    slides_html_path = generate_slides_html(
        outline,
        chosen_color.colors,
        output_path="/tmp/slideforge_slides_AI艺术.html",
    )
    print(f"  ✓ HTML 幻灯片：{slides_html_path}")

    import subprocess
    subprocess.run(["open", slides_html_path], check=False)

    # ── 步骤 5：导出 PPTX ─────────────────────────────────────────────────
    output_pptx = "/tmp/slideforge_AI与艺术的融合.pptx"
    print(f"\n  📊 正在导出 PPTX...")
    export_pptx(outline, chosen_color.colors, output_path=output_pptx)
    print(f"  ✓ PPTX 已生成：{output_pptx}")
    subprocess.run(["open", output_pptx], check=False)

    print("\n" + "═" * 70)
    print(f"  🎉 生成完成！")
    print(f"  配色方案：{chosen_color.name}")
    print(f"  大纲结构：{chosen_outline.name}")
    print(f"  HTML 预览：{slides_html_path}")
    print(f"  PPTX 文件：{output_pptx}")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
