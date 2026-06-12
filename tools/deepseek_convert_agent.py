#!/usr/bin/env python3
"""
DeepSeek LLM Agent — HTML → PPTX 转换工具

将 slides_你好 旅行者.html 转换为专业 PPTX 文件。
使用 DeepSeek 大模型作为 Agent，规划并监督整个转换流程，
确保每一步正确执行，最终交付可用的 PPTX。

用法：
    python tools/deepseek_convert_agent.py
    python tools/deepseek_convert_agent.py --html slides_你好.html --output my.pptx

环境变量：
    DEEPSEEK_API_KEY  必需。在 https://platform.deepseek.com/ 获取
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path

# ── 确保项目根目录在 sys.path 上 ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from openai import OpenAI


# ═══════════════════════════════════════════════════════════════════════
# Agent Prompt 定义
# ═══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """你是一个专业的 PPT 生成 Agent，名叫 SlideForge Agent。

你的核心任务是将 HTML 幻灯片文件转换为高质量 PPTX 文件。
你需要严格按照以下流程操作，每一步都向用户报告进展和结果。

## 你的能力
1. 分析 HTML 文件结构，判断幻灯片质量和完整性
2. 调用项目的 PPTX 转换引擎执行转换
3. 验证转换结果，确保 PPTX 文件可打开、内容完整
4. 发现问题时给出修复方案

## 工作流程
Step 1 — 分析 HTML：检查 HTML 文件是否存在、幻灯片页数、内容结构
Step 2 — 执行转换：调用 convert_html_to_pptx 函数
Step 3 — 验证输出：确认 PPTX 文件已生成、文件大小合理
Step 4 — 总结报告：向用户汇报转换结果

## 规则
- 每个步骤必须输出清晰的状态信息
- 如果某一步失败，分析原因并给出明确修复指令
- 最终输出必须包含输出文件的绝对路径
- 保持中文回复
"""


def step_analyze_prompt(html_path: Path) -> str:
    """Step 1: 分析 HTML 文件的 prompt"""
    return f"""请分析以下 HTML 幻灯片文件的基本信息：

文件路径：{html_path}
文件名：{html_path.name}
文件大小：{html_path.stat().st_size / 1024:.1f} KB

请读取文件内容，并回答：
1. 共有多少张幻灯片（.slide 元素）？
2. 每张幻灯片的标题是什么？
3. 幻灯片使用了什么配色/风格？
4. 内容质量是否完整？有无明显缺失？
5. 是否适合转换为 PPTX？

请输出分析结论，明确给出"可以转换"或"需要修复"的判断。
"""


def step_convert_prompt(html_path: Path, output_path: Path) -> str:
    """Step 2: 执行转换的 prompt"""
    return f"""现在执行 HTML → PPTX 转换。

输入文件：{html_path}
输出文件：{output_path}

请调用项目的 convert_html_to_pptx 函数执行转换。
参数建议：
- screenshot_mode=False（精确模式，非截图模式）
- validate_gradients=True（校验渐变）
- verbose=True（输出详细信息）

执行后，请确认转换是否成功。
"""


def step_verify_prompt(output_path: Path) -> str:
    """Step 3: 验证输出的 prompt"""
    size_kb = output_path.stat().st_size / 1024 if output_path.exists() else 0
    return f"""请验证转换结果：

输出文件：{output_path}
文件是否存在：{output_path.exists()}
文件大小：{size_kb:.1f} KB

确认项：
1. 文件是否成功生成？
2. 文件大小是否合理（大于 10KB 为正常）？
3. 是否需要打开预览？

输出验证结论。
"""


def step_report_prompt(html_path: Path, output_path: Path, elapsed: float, success: bool) -> str:
    """Step 4: 总结报告的 prompt"""
    status = "✅ 成功" if success else "❌ 失败"
    return f"""请生成最终的转换报告。

## 转换摘要
- 源文件：{html_path.name}
- 输出文件：{output_path.name}
- 输出路径：{output_path}
- 文件大小：{output_path.stat().st_size / 1024:.1f} KB（{output_path.exists()}）
- 耗时：{elapsed:.1f} 秒
- 状态：{status}

请用中文写一段总结，包括：
1. 转换结果概述
2. 文件位置
3. 下一步建议（如打开查看、调整内容等）
"""


# ═══════════════════════════════════════════════════════════════════════
# 核心 Agent 逻辑
# ═══════════════════════════════════════════════════════════════════════

def call_llm(client: OpenAI, messages: list[dict]) -> str:
    """调用 DeepSeek Chat API，返回 LLM 回复文本。"""
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.3,        # 低温度保证确定性
        max_tokens=2048,
    )
    return resp.choices[0].message.content


def run_agent(
    html_path: Path,
    output_path: Path | None = None,
    api_key: str | None = None,
    verbose: bool = True,
) -> dict:
    """运行 SlideForge Agent，将 HTML 转换为 PPTX。

    Args:
        html_path: 输入 HTML 文件路径
        output_path: 输出 PPTX 路径（None 则自动生成）
        api_key: DeepSeek API Key（None 则从环境变量读取）
        verbose: 是否打印 LLM 思考过程

    Returns:
        {"success": bool, "output_path": str, "elapsed": float}
    """
    # ── 参数校验 ──────────────────────────────────────────────────
    if not html_path.exists():
        raise FileNotFoundError(f"HTML 文件不存在: {html_path}")

    if output_path is None:
        output_path = html_path.with_suffix(".pptx")
    output_path = Path(output_path).resolve()

    if api_key is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError(
            "未设置 DEEPSEEK_API_KEY。\n"
            "请执行: export DEEPSEEK_API_KEY='your-api-key-here'\n"
            "或在 https://platform.deepseek.com/ 获取"
        )

    client = OpenAI(
        base_url="https://api.deepseek.com",
        api_key=api_key,
    )
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    t_start = time.perf_counter()

    # ── Step 1: 分析 HTML ─────────────────────────────────────────
    if verbose:
        print("\n" + "═" * 70)
        print("  Step 1/4 — 分析 HTML 文件...")
        print("═" * 70)

    history.append({"role": "user", "content": step_analyze_prompt(html_path)})
    analysis = call_llm(client, history)
    history.append({"role": "assistant", "content": analysis})

    if verbose:
        print(analysis)
        print()

    # ── Step 2: 执行转换 ─────────────────────────────────────────
    if verbose:
        print("═" * 70)
        print("  Step 2/4 — 执行 HTML → PPTX 转换...")
        print("═" * 70)

    # 让 LLM "思考"转换策略（实际转换仍由本地引擎执行）
    history.append({"role": "user", "content": step_convert_prompt(html_path, output_path)})
    plan = call_llm(client, history)
    history.append({"role": "assistant", "content": plan})

    if verbose:
        print(plan)
        print()

    # ── 真正执行转换 ──────────────────────────────────────────────
    from slideforge.pptx_converter import convert_html_to_pptx

    try:
        if verbose:
            print("  ⚡ 调用转换引擎...")
        t_conv = time.perf_counter()
        result_path = convert_html_to_pptx(
            str(html_path),
            str(output_path),
            embed_fonts=False,
            verbose=verbose,
            validate_gradients=True,
            screenshot_mode=False,
        )
        conv_time = time.perf_counter() - t_conv
        if verbose:
            print(f"  ✓ 转换完成（{conv_time:.1f}s）: {result_path}")
    except Exception as e:
        error_msg = f"转换失败: {e}"
        if verbose:
            print(f"  ❌ {error_msg}")
        history.append({
            "role": "user",
            "content": f"转换执行时发生异常: {error_msg}\n请分析原因并给出修复建议。"
        })
        fix_advice = call_llm(client, history)
        if verbose:
            print(f"\n  🔧 LLM 修复建议:\n{fix_advice}")
        return {"success": False, "output_path": str(output_path),
                "elapsed": time.perf_counter() - t_start, "error": str(e)}

    # ── Step 3: 验证输出 ─────────────────────────────────────────
    if verbose:
        print("\n" + "═" * 70)
        print("  Step 3/4 — 验证转换结果...")
        print("═" * 70)

    history.append({"role": "user", "content": step_verify_prompt(output_path)})
    verification = call_llm(client, history)
    history.append({"role": "assistant", "content": verification})

    if verbose:
        print(verification)
        print()

    # ── Step 4: 总结报告 ─────────────────────────────────────────
    success = output_path.exists() and output_path.stat().st_size > 10240
    elapsed = time.perf_counter() - t_start

    if verbose:
        print("═" * 70)
        print("  Step 4/4 — 生成转换报告...")
        print("═" * 70)

    history.append({
        "role": "user",
        "content": step_report_prompt(html_path, output_path, elapsed, success)
    })
    report = call_llm(client, history)

    if verbose:
        print(report)
        print("═" * 70 + "\n")

    return {
        "success": success,
        "output_path": str(output_path),
        "elapsed": elapsed,
        "report": report,
    }


# ═══════════════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="DeepSeek LLM Agent — HTML 转 PPTX",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/deepseek_convert_agent.py
  python tools/deepseek_convert_agent.py --html slides_你好.html --output final.pptx
        """,
    )
    parser.add_argument(
        "--html",
        default=str(PROJECT_ROOT / "output" / "slides_你好 旅行者.html"),
        help="输入 HTML 文件路径（默认: output/slides_你好 旅行者.html）",
    )
    parser.add_argument("--output", "-o", default=None, help="输出 PPTX 路径")
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="静默模式，只输出最终结果 JSON"
    )
    args = parser.parse_args()

    html_path = Path(args.html).resolve()
    output_path = Path(args.output).resolve() if args.output else None

    try:
        result = run_agent(
            html_path=html_path,
            output_path=output_path,
            verbose=not args.quiet,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"\n  ❌ {e}", file=sys.stderr)
        sys.exit(1)

    if args.quiet:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "✅ 成功" if result["success"] else "❌ 失败"
        print(f"  状态: {status}")
        print(f"  输出: {result['output_path']}")
        print(f"  耗时: {result['elapsed']:.1f}s")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
