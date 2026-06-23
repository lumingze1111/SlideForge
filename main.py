"""
SlideForge - 完整独立的 PPT 生成流程

流程：
0. 用户输入主题和想法 → AI 分析并给出建议
1. AI 生成配色方案 → 用户浏览器选择
2. AI 生成大纲结构 → 用户浏览器选择
3. 生成详细内容 → 渲染 HTML → 导出 PPTX
3.5. 内容增强（图片搜索 + 图表生成）
4. 渲染 HTML 预览（支持图片）
5. 导出 PPTX
"""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

from langchain_openai import ChatOpenAI

from slideforge.agents.content_enhancement_agent import ContentEnhancementAgent
from slideforge.agents.html_generator import (
    generate_outline,
    generate_slides_html,
    generate_slides_html_with_images,
)
from slideforge.agents.outline_proposal import generate_outline_proposals, pick_outline_proposal
from slideforge.agents.propose_agent import pick_proposal, run_propose_agent
from slideforge.agents.layout_templates import TEMPLATE_FAMILIES
from slideforge.agents.topic_analyzer import analyze_topic, print_suggestion
from slideforge.error_tracking import ErrorReporter, ErrorTracker, set_error_tracker
from slideforge.pipeline import (
    GenerationArtifacts,
    GenerationConfig,
    GenerationDependencies,
    GenerationPipeline,
)


OUTPUT_DIR = Path(__file__).parent / "output"


def _open_file(path: Path) -> None:
    subprocess.run(["open", str(path)], check=False)


def _create_dependencies(error_tracker: ErrorTracker) -> GenerationDependencies:
    def analyze_with_progress(llm, topic: str, ideas: str):
        print("\n  🔍 正在分析主题...")
        suggestion = analyze_topic(llm, topic=topic, ideas=ideas)
        print_suggestion(suggestion, topic)
        return suggestion

    def generate_color_with_progress(llm, topic: str, audience: str):
        print("\n  🎨 正在生成配色方案...")
        proposals = run_propose_agent(llm, topic=topic, audience=audience)
        print(f"  ✓ 生成了 {len(proposals.proposals)} 套配色方案")
        return proposals

    def generate_outline_proposals_with_progress(llm, topic: str, audience: str, pages: int):
        print("\n  📋 正在生成大纲结构方案...")
        proposals = generate_outline_proposals(llm, topic=topic, audience=audience, pages=pages)
        print(f"  ✓ 生成了 {len(proposals.proposals)} 套大纲方案")
        return proposals

    def pick_template_family_with_progress(topic: str, suggestion, color, outline):
        from slideforge.preview_generator import generate_template_family_preview_html, wait_for_selection

        print("\n  🧩 正在准备模板风格选择...")
        preview_path = generate_template_family_preview_html(TEMPLATE_FAMILIES, topic)
        print(f"  💡 模板风格预览页面已生成：{preview_path}")
        _open_file(Path(preview_path))
        idx = wait_for_selection(len(TEMPLATE_FAMILIES))
        chosen = TEMPLATE_FAMILIES[idx]
        print(f"\n  ✓ 已选择模板风格 [{idx + 1}]：{chosen.name}")
        return chosen.key

    def generate_outline_with_progress(llm, topic: str, audience: str, pages: int, key_messages, research_facts):
        print(f"\n  📝 正在生成幻灯片详细内容（{pages} 页）...")
        outline = generate_outline(
            llm,
            topic=topic,
            audience=audience,
            pages=pages,
            key_messages=key_messages,
            research_facts=research_facts,
        )
        print(f"  ✓ 内容生成完成，共 {len(outline.slides)} 页")
        return outline

    def create_enhancement_agent(**kwargs):
        features = []
        if kwargs.get("enable_images"):
            features.append("图片")
        if kwargs.get("enable_charts"):
            features.append("图表")
        if features:
            print(f"\n  🎨 正在增强幻灯片内容（{' + '.join(features)}）...")
        return ContentEnhancementAgent(error_tracker=error_tracker, **kwargs)

    def generate_slides_html_with_progress(outline, colors, images, charts, output_path: str, theme_family: str = ""):
        generate_slides_html_with_images(
            outline,
            colors,
            images,
            charts,
            output_path=output_path,
            theme_family=theme_family,
        )
        print(f"  ✓ HTML 幻灯片：{output_path}")
        _open_file(Path(output_path))

    def generate_plain_html_with_progress(outline, colors, output_path: str, theme_family: str = ""):
        generate_slides_html(outline, colors, output_path=output_path, theme_family=theme_family)
        print(f"  ✓ HTML 幻灯片：{output_path}")
        _open_file(Path(output_path))

    def convert_with_fallback(html_path: str, pptx_path: str) -> int:
        print("\n  📊 正在导出 PPTX（LLM 直接渲染）...")
        llm_convert_script = str(Path(__file__).parent / "tools" / "llm_direct_convert.py")
        result = subprocess.run(
            [sys.executable, llm_convert_script, "--html", html_path, "--output", pptx_path],
            capture_output=False,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ⚠ LLM 直接渲染失败 (exit {result.returncode})，回退到传统流水线...")
            from slideforge.pptx_converter import convert_html_to_pptx

            convert_html_to_pptx(html_path, pptx_path, verbose=True)
        print(f"  ✓ PPTX 已生成：{pptx_path}")
        _open_file(Path(pptx_path))
        return result.returncode

    def create_error_report(topic: str, total_slides: int) -> None:
        try:
            error_reporter = ErrorReporter(
                error_tracker=error_tracker,
                topic=topic,
                total_slides=total_slides,
            )
            report_path = error_reporter.save_report()
            error_summary = error_tracker.get_summary()
            if error_summary["total_errors"] > 0:
                print(f"\n  📋 错误报告已生成：{report_path}")
                print(f"  共 {error_summary['total_errors']} 个错误，恢复率 {int(error_summary['recovery_rate'] * 100)}%")
                _open_file(Path(report_path))
        except Exception as exc:
            print(f"\n  ⚠ 错误报告生成失败：{exc}")

    return GenerationDependencies(
        analyze_topic=analyze_with_progress,
        generate_color_proposals=generate_color_with_progress,
        pick_color=pick_proposal,
        generate_outline_proposals=generate_outline_proposals_with_progress,
        pick_outline=pick_outline_proposal,
        pick_template_family=pick_template_family_with_progress,
        generate_outline=generate_outline_with_progress,
        create_enhancement_agent=create_enhancement_agent,
        generate_slides_html=generate_plain_html_with_progress,
        generate_slides_html_with_images=generate_slides_html_with_progress,
        convert_html_to_pptx=convert_with_fallback,
        open_file=_open_file,
        create_error_report=create_error_report,
    )


def main() -> None:
    try:
        config = GenerationConfig.from_env()
    except RuntimeError as exc:
        print(f"\n  ❌ {exc}")
        print("     export DEEPSEEK_API_KEY='your-api-key-here'\n")
        sys.exit(1)

    if config.image_disable_reason == "missing image provider API key":
        print("\n  ⚠ 警告：未配置图片搜索 API Key，将跳过图片搜索")
        print("     设置 UNSPLASH_ACCESS_KEY 或 PEXELS_API_KEY 以启用图片搜索\n")

    llm = ChatOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        temperature=config.temperature,
    )

    print("\n" + "═" * 70)
    print("  🎯 SlideForge — AI 驱动演示文稿生成器")
    if config.enable_images:
        print("  ✨ 图片搜索功能已启用")
    if config.enable_charts:
        print("  📊 图表生成功能已启用")
    print("═" * 70)

    if len(sys.argv) > 1:
        topic = sys.argv[1]
        ideas = sys.argv[2] if len(sys.argv) > 2 else ""
    else:
        topic = input("\n  💭 请输入演示主题：").strip()
        if not topic:
            topic = "AI与艺术的融合：探讨人工智能如何改变创意产业"
        ideas = input("  💡 你的想法/目标（可留空）：").strip()

    session_id = str(uuid.uuid4())[:8]
    OUTPUT_DIR.mkdir(exist_ok=True)
    error_tracker = ErrorTracker(session_id, OUTPUT_DIR)
    set_error_tracker(error_tracker)

    pipeline = GenerationPipeline(
        llm=llm,
        config=config,
        artifacts=GenerationArtifacts.for_topic(OUTPUT_DIR, topic),
        dependencies=_create_dependencies(error_tracker),
    )
    result = pipeline.run(topic=topic, ideas=ideas)

    print("\n" + "═" * 70)
    print("  🎉 生成完成！")
    print(f"  主题：{result.topic}")
    print(f"  配色方案：{result.color_name}")
    print(f"  大纲结构：{result.outline_name}")
    print(f"  模板风格：{result.template_family}")
    if result.image_count:
        print(f"  插入图片：{result.image_count} 张")
    if result.chart_count:
        print(f"  生成图表：{result.chart_count} 个")
    print(f"  HTML 预览：{result.html_path}")
    print(f"  PPTX 文件：{result.pptx_path}")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
