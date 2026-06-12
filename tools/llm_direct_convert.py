#!/usr/bin/env python3
"""
让 DeepSeek LLM 直接根据 HTML 渲染 PPTX。

LLM 自己分析 HTML 结构，自己写 python-pptx 代码来生成 PPTX。
不调用项目已有的转换函数，由 LLM 全权负责渲染。

用法:
    python3 tools/llm_direct_convert.py
    python3 tools/llm_direct_convert.py --html path/to/slides.html
"""

import os
import sys
import re
import subprocess
import argparse
import base64
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SYSTEM_PROMPT = """你是一个 PPT 生成专家。你的任务是根据用户提供的 HTML 幻灯片文件，
用 python-pptx 库编写 Python 代码，生成视觉上高度还原的 PPTX 文件。

## 核心要求
1. **提取 HTML 中 ALL `.slide` 元素的全部内容** —— 标题、副标题、列表项、数据、装饰线、页码，一个都不能少
2. **忠实还原视觉风格**：background（渐变/纯色）、font-size、color、padding、text-align
3. 输出 **纯 Python 代码**（```python ... ``` 包裹），不输出任何解释文字
4. 代码必须可直接执行，包含完整 import 和 prs.save()

## 技术规则
- 幻灯片尺寸: width=Inches(13.33), height=Inches(7.5)（1280×720 比例）
- 渐变背景用 fill.gradient() + gradient_stops，先 gradient() 再拿到 gradient_stops 对象
- 文字用 paragraph.font.size / color.rgb / bold / alignment
- 文本框大小和位置根据 HTML 布局合理估算
- 用 MSO_SHAPE.RECTANGLE 实现装饰线和色块
- HTML 中的 div 网格布局，用多个 textbox 或 shape 模拟
- 字体默认使用 'PingFang SC' 或 'Microsoft YaHei'

## python-pptx 常见陷阱（必须遵守！）
1. **gradient_stops 数量**: `fill.gradient()` 默认只创建 2 个 stop！如需更多，调用 `fill.gradient_stops.add()` 扩展：
   ```python
   fill.gradient()
   stops = fill.gradient_stops
   while len(stops) < 4:  # 按需扩展到目标数量
       stops.add()
   stops[0].position = 0.0
   stops[0].color.rgb = color1
   # ...
   ```
2. **slide.background.fill 与 shape.fill 不同**: slide 背景的 fill 对象 API 与形状的 fill 相同，直接用即可
3. **text_frame 首个段落**: `tf.paragraphs[0]` 始终存在，无需手动创建
4. **颜色值**: RGBColor 参数接受 0-255 整数，16进制写法 `RGBColor(0xFF, 0xFF, 0xFF)`
5. **导入必须完整**: `from pptx import Presentation; from pptx.util import Inches, Pt; from pptx.dml.color import RGBColor; from pptx.enum.text import PP_ALIGN`

## 内容完整性检查（非常重要！）
HTML 中每一页（.slide）的 **全部文字内容** 都必须出现在 PPTX 中。
- h1, h2 标题 → 幻灯片标题
- p 段落 → 文本框
- li 列表 → 多行文本框
- div 中的文字块 → 对应位置的文本框
- 所有 bullet points、数据、引用、说明文字都要保留

现在开始。"""


def read_html(html_path: Path) -> str:
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


def call_deepseek(user_prompt: str, api_key: str) -> str:
    """调用 DeepSeek API，返回生成的 Python 代码"""
    from openai import OpenAI
    client = OpenAI(base_url="https://api.deepseek.com", api_key=api_key)

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=8192,
    )
    return resp.choices[0].message.content


def extract_code(text: str) -> str:
    """从 LLM 回复中提取 Python 代码"""
    pattern = r"```python\s*\n(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # fallback: 匹配任意代码块
    pattern = r"```\s*\n(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def main():
    parser = argparse.ArgumentParser(description="DeepSeek LLM 直接渲染 HTML → PPTX")
    parser.add_argument("--html", default=str(PROJECT_ROOT / "output" / "slides_你好 旅行者.html"))
    parser.add_argument("--output", "-o", default=None)
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 请设置环境变量 DEEPSEEK_API_KEY")
        print("   export DEEPSEEK_API_KEY='your-api-key-here'")
        sys.exit(1)

    html_path = Path(args.html).resolve()
    if not html_path.exists():
        print(f"❌ 文件不存在: {html_path}")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        stem = html_path.stem.replace(" ", "_")
        output_path = html_path.parent / f"{stem}_llm.pptx"

    print(f"📄 读取 HTML: {html_path}")
    html_content = read_html(html_path)
    print(f"   文件大小: {len(html_content):,} 字符")

    # 发送完整 HTML，deepseek-chat 支持 64K 上下文
    prompt = f"""请将以下 HTML 幻灯片文件完整转换为 PPTX。

HTML 文件: {html_path}
输出 PPTX: {output_path}

完整 HTML 内容如下：
```html
{html_content}
```

请逐页分析 HTML 中每一个 .slide 元素，提取全部文字内容，
然后用 python-pptx 生成 PPTX。确保每页的标题、列表、数据、装饰元素都完整保留。"""

    print(f"\n🤖 调用 DeepSeek 生成 PPTX 代码...")
    reply = call_deepseek(prompt, api_key)
    print(f"   回复长度: {len(reply):,} 字符")

    code = extract_code(reply)
    code_path = output_path.with_suffix(".py")

    # 补全 output_path 变量
    if "output_path" not in code:
        code = code.replace("prs.save(", f"output_path = r'{output_path}'\nprs.save(")

    # 保存生成的代码
    code_path.write_text(code, encoding="utf-8")
    print(f"📝 代码已保存: {code_path}")

    max_fix_attempts = 3
    for attempt in range(max_fix_attempts + 1):
        print(f"\n⚡ 执行生成的 PPTX 代码 (第 {attempt + 1}/{max_fix_attempts + 1} 次)...")
        result = subprocess.run(
            [sys.executable, str(code_path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            break
        print(f"❌ 执行失败:")
        print(result.stderr[:2000])
        if attempt < max_fix_attempts:
            print(f"\n🤖 将错误发给 DeepSeek 修复 (剩余 {max_fix_attempts - attempt} 次)...")
            fix_prompt = f"生成的代码执行报错:\n{result.stderr[:2000]}\n\n请修复代码:\n```python\n{code}\n```"
            fix_reply = call_deepseek(
                f"请修复以下代码错误。\nHTML 文件: {html_path}\n\n{fix_prompt}\n\n输出 PPTX 保存到: {output_path}",
                api_key
            )
            code = extract_code(fix_reply)
            code_path.write_text(code, encoding="utf-8")
            print(f"📝 已更新代码: {code_path}")
        else:
            print(f"❌ 已尝试 {max_fix_attempts} 次修复，仍然失败")
            sys.exit(1)

    if output_path.exists():
        print(f"\n✅ PPTX 已生成: {output_path}")
        print(f"   文件大小: {output_path.stat().st_size / 1024:.1f} KB")
    else:
        print(f"\n⚠️ 文件未生成，检查代码 {code_path}")


if __name__ == "__main__":
    main()
