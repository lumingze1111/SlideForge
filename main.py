"""
SlideForge - 完整独立的 PPT 生成流程

流程：
0. 用户输入主题和想法 → AI 分析并给出建议
1. AI 生成配色方案 → 用户浏览器选择
2. AI 生成大纲结构 → 用户浏览器选择
3. 生成详细内容 → 渲染 HTML → 导出 PPTX
3.5. 【新增】内容增强（图片搜索）
4. 渲染 HTML 预览（支持图片）
5. 导出 PPTX
"""

import os
import sys
import uuid
from pathlib import Path
from langchain_openai import ChatOpenAI
from slideforge.agents.topic_analyzer import analyze_topic, print_suggestion
from slideforge.agents.propose_agent import run_propose_agent, pick_proposal
from slideforge.agents.outline_proposal import generate_outline_proposals, pick_outline_proposal
from slideforge.agents.html_generator import generate_outline, generate_slides_html, generate_slides_html_with_images
from slideforge.agents.content_enhancement_agent import ContentEnhancementAgent
from slideforge.pptx_converter import convert_html_to_pptx
from slideforge.error_tracking import ErrorTracker, ErrorReporter, set_error_tracker


def main() -> None:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("\n  ❌ 请设置环境变量 DEEPSEEK_API_KEY")
        print("     export DEEPSEEK_API_KEY='your-api-key-here'\n")
        sys.exit(1)

    # 检查是否启用图片搜索
    enable_images = os.getenv("ENABLE_IMAGE_SEARCH", "true").lower() == "true"
    enable_charts = os.getenv("ENABLE_CHART_GENERATION", "true").lower() == "true"

    if enable_images and not (os.getenv("UNSPLASH_ACCESS_KEY") or os.getenv("PEXELS_API_KEY")):
        print("\n  ⚠ 警告：未配置图片搜索 API Key，将跳过图片搜索")
        print("     设置 UNSPLASH_ACCESS_KEY 或 PEXELS_API_KEY 以启用图片搜索\n")
        enable_images = False

    llm = ChatOpenAI(
        base_url="https://api.deepseek.com",
        api_key=api_key,
        model="deepseek-chat",
        temperature=0.7,
    )

    print("\n" + "═" * 70)
    print("  🎯 SlideForge — AI 驱动演示文稿生成器")
    if enable_images:
        print("  ✨ 图片搜索功能已启用")
    if enable_charts:
        print("  📊 图表生成功能已启用")
    print("═" * 70)

    # 创建错误追踪器
    session_id = str(uuid.uuid4())[:8]
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    error_tracker = ErrorTracker(session_id, output_dir)
    set_error_tracker(error_tracker)

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

    # ── 步骤 3.5：【新增】内容增强（图片搜索 + 图表生成）────────────────
    enhanced_outline = None
    if enable_images or enable_charts:
        try:
            features = []
            if enable_images:
                features.append("图片")
            if enable_charts:
                features.append("图表")

            print(f"\n  🎨 正在增强幻灯片内容（{' + '.join(features)}）...")

            enhancement_agent = ContentEnhancementAgent(
                llm=llm,
                error_tracker=error_tracker,
                output_dir=output_dir,
                enable_images=enable_images,
                enable_charts=enable_charts
            )
            enhanced_outline = enhancement_agent.enhance_outline(outline, chosen_color)

            summary = []
            if enhanced_outline.images:
                summary.append(f"{len(enhanced_outline.images)} 张图片")
            if enhanced_outline.charts:
                summary.append(f"{len(enhanced_outline.charts)} 个图表")

            if summary:
                print(f"  ✓ 内容增强完成：{' + '.join(summary)}")
            else:
                print(f"  ⚠ 未添加任何增强内容")

        except Exception as e:
            print(f"  ⚠ 内容增强失败：{e}")
            print(f"  继续生成基础幻灯片...")
            enhanced_outline = None

    # ── 步骤 4：渲染 HTML 预览 ──────────────────────────────────────────
    import subprocess
    slides_html_path = str(output_dir / f"slides_{topic[:10]}.html")

    if enhanced_outline and enhanced_outline.images:
        generate_slides_html_with_images(
            outline,
            chosen_color.colors,
            enhanced_outline.images,
            output_path=slides_html_path
        )
    else:
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

    # ── 生成错误报告 ────────────────────────────────────────────────────
    try:
        error_reporter = ErrorReporter(
            error_tracker=error_tracker,
            topic=topic,
            total_slides=len(outline.slides)
        )
        report_path = error_reporter.save_report()
        error_summary = error_tracker.get_summary()

        if error_summary['total_errors'] > 0:
            print(f"\n  📋 错误报告已生成：{report_path}")
            print(f"  共 {error_summary['total_errors']} 个错误，恢复率 {int(error_summary['recovery_rate'] * 100)}%")
            subprocess.run(["open", str(report_path)], check=False)
    except Exception as e:
        print(f"\n  ⚠ 错误报告生成失败：{e}")

    print("\n" + "═" * 70)
    print(f"  🎉 生成完成！")
    print(f"  主题：{topic}")
    print(f"  配色方案：{chosen_color.name}")
    print(f"  大纲结构：{chosen_outline.name}")
    if enhanced_outline:
        if enhanced_outline.images:
            print(f"  插入图片：{len(enhanced_outline.images)} 张")
        if enhanced_outline.charts:
            print(f"  生成图表：{len(enhanced_outline.charts)} 个")
    print(f"  HTML 预览：{slides_html_path}")
    print(f"  PPTX 文件：{output_pptx}")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
