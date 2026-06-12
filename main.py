"""
SlideForge - 完整独立的 PPT 生成流程

流程：
0. 用户输入主题和想法 → AI 分析并给出建议
1. AI 生成配色方案 → 用户浏览器选择
2. AI 生成大纲结构 → 用户浏览器选择
3. 生成详细内容 → 渲染 HTML → 导出 PPTX
"""

import os
import sys
from langchain_openai import ChatOpenAI
from slideforge.agents.topic_analyzer import analyze_topic, print_suggestion
from slideforge.agents.propose_agent import run_propose_agent, pick_proposal
from slideforge.agents.outline_proposal import generate_outline_proposals, pick_outline_proposal
from slideforge.agents.html_generator import generate_outline, generate_slides_html
from slideforge.pptx_converter import convert_html_to_pptx


def main() -> None:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("\n  ❌ 请设置环境变量 DEEPSEEK_API_KEY")
        print("     export DEEPSEEK_API_KEY='your-api-key-here'\n")
        sys.exit(1)

    llm = ChatOpenAI(
        base_url="https://api.deepseek.com",
        api_key=api_key,
        model="deepseek-chat",
        temperature=0.7,
    )

    print("\n" + "═" * 70)
    print("  🎯 SlideForge — AI 驱动演示文稿生成器")
    print("═" * 70)

    # ── 步骤 0：主题分析 ──────────────────────────────────────────────────
    if len(sys.argv) > 1:
        topic = sys.argv[1]
        ideas = sys.argv[2] if len(sys.argv) > 2 else ""
    else:
        topic = input("\n  💭 请输入演示主题：").strip()
        if not topic:
            topic = "AI与艺术的融合：探讨人工智能如何改变创意产业"
        ideas = input("  💡 你的想法/目标（可留空）：").strip()

    print(f"\n  🔍 正在分析主题...")
    suggestion = analyze_topic(llm, topic=topic, ideas=ideas)
    print_suggestion(suggestion, topic)

    input("\n  按 Enter 继续生成方案...")

    # ── 步骤 1：配色方案选择 ────────────────────────────────────────────
    print(f"\n  🎨 正在生成配色方案...")
    color_proposals = run_propose_agent(
        llm, 
        topic=topic, 
        audience=suggestion.target_audience
    )
    print(f"  ✓ 生成了 {len(color_proposals.proposals)} 套配色方案")
    
    chosen_color = pick_proposal(color_proposals, topic=topic)

    # ── 步骤 2：大纲结构选择 ────────────────────────────────────────────
    print(f"\n  📋 正在生成大纲结构方案...")
    outline_proposals = generate_outline_proposals(
        llm,
        topic=topic,
        audience=suggestion.target_audience,
        pages=suggestion.estimated_pages
    )
    print(f"  ✓ 生成了 {len(outline_proposals.proposals)} 套大纲方案")
    
    chosen_outline = pick_outline_proposal(outline_proposals, topic=topic)

    # ── 步骤 3：生成详细内容 ────────────────────────────────────────────
    print(f"\n  📝 正在生成幻灯片详细内容（{chosen_outline.slide_count} 页）...")
    outline = generate_outline(
        llm,
        topic=topic,
        audience=suggestion.target_audience,
        pages=chosen_outline.slide_count,
        key_messages=suggestion.key_messages,  # 传递关键信息用于研究
        research_facts=None  # 自动搜索
    )
    print(f"  ✓ 内容生成完成，共 {len(outline.slides)} 页")

    # ── 步骤 4：渲染 HTML 预览 ──────────────────────────────────────────
    import subprocess
    from pathlib import Path
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    slides_html_path = str(output_dir / f"slides_{topic[:10]}.html")
    generate_slides_html(outline, chosen_color.colors, output_path=slides_html_path)
    print(f"  ✓ HTML 幻灯片：{slides_html_path}")
    subprocess.run(["open", slides_html_path], check=False)

    # ── 步骤 5：导出 PPTX ────────────────────────────────────────────────
    output_pptx = str(output_dir / f"slides_{topic[:20].replace(' ', '_')}.pptx")
    print(f"\n  📊 正在导出 PPTX（LLM 直接渲染）...")
    llm_convert_script = str(Path(__file__).parent / "tools" / "llm_direct_convert.py")
    result = subprocess.run(
        [sys.executable, llm_convert_script, "--html", slides_html_path, "--output", output_pptx],
        capture_output=False, text=True,
    )
    if result.returncode != 0:
        print(f"  ⚠ LLM 直接渲染失败 (exit {result.returncode})，回退到传统流水线...")
        convert_html_to_pptx(slides_html_path, output_pptx, verbose=True)
    print(f"  ✓ PPTX 已生成：{output_pptx}")
    subprocess.run(["open", output_pptx], check=False)

    print("\n" + "═" * 70)
    print(f"  🎉 生成完成！")
    print(f"  主题：{topic}")
    print(f"  配色方案：{chosen_color.name}")
    print(f"  大纲结构：{chosen_outline.name}")
    print(f"  HTML 预览：{slides_html_path}")
    print(f"  PPTX 文件：{output_pptx}")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
