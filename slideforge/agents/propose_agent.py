"""
Propose Agent - 根据主题生成多套定制设计方案

不使用固定模版，而是让 LLM 根据主题和受众动态创造配色+视觉风格。
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ColorProposal(BaseModel):
    """单套配色方案提案"""
    name: str = Field(description="方案名称，体现主题特点，如'深海探索蓝'")
    primary: str = Field(description="主色，十六进制色值")
    secondary: str = Field(description="辅色")
    accent: str = Field(description="强调色")
    background: str = Field(description="背景色")
    surface: str = Field(description="表面色")
    text_primary: str = Field(description="主要文本色")
    text_secondary: str = Field(description="次要文本色")
    text_disabled: str = Field(description="禁用文本色")
    border: str = Field(description="边框色")
    visual_style: str = Field(description="推荐视觉风格：minimalist/bold/elegant/corporate/playful")
    reasoning: str = Field(description="为什么这套配色适合该主题，50字以内")


class DesignProposals(BaseModel):
    """多套设计方案提案集合"""
    proposals: List[ColorProposal] = Field(description="3-5套方案，按推荐度排序")
    recommended_index: int = Field(description="最推荐方案的索引（0-based）")


SYSTEM_PROMPT = """你是顶尖的视觉设计师，擅长从主题中提取核心意象，转化为精准的配色方案。

## 任务
根据主题和受众，生成 3-5 套**高度差异化**的配色方案。

## 分析步骤
1. **提取主题关键词** — 从主题中识别核心概念（如"量子"→微观/不确定性/科技感）
2. **关联色彩意象** — 将概念映射到色彩心理学（量子→紫/蓝/银灰，代表神秘/理性/未来）
3. **受众适配** — 技术受众偏深色/高对比，大众受众偏柔和/亲和
4. **对比度验证** — 确保文字色在背景色上 WCAG AA ≥ 4.5:1

## 配色要求
1. **主色 (primary)** — 直接体现主题核心意象，非通用商务蓝/灰
2. **辅色 (secondary)** — 与主色形成呼应或对比，丰富层次
3. **强调色 (accent)** — 高饱和，用于 CTA 和关键信息
4. **背景/表面色** — 深色主题用 #0D-#1A 区间，浅色主题 ≥ #F5
5. **文字色** — 深背景用 #E0-#FF，浅背景用 #1A-#3A，确保对比度
6. **边框/禁用色** — 与背景形成微妙层次，对比度 2-3:1

## 方案多样性
- 方案1：最贴合主题的代表性配色（推荐方案）
- 方案2-3：从不同角度诠释主题（如深色/浅色，冷色/暖色）
- 方案4-5：突破常规的创意配色（如反转对比，多彩点缀）

## 方案命名规则
必须包含**主题关键词 + 色彩意象 + 情绪**，例如：
- ✅ "量子微光 - 深紫科技感"
- ✅ "神经网络 - 霓虹赛博风"
- ✅ "海洋保护 - 湛蓝生态系"
- ❌ "紫色科技方案"（太通用）
- ❌ "方案1"（无信息量）

## 主题强化检查
生成后自问：**如果去掉主题，这套配色是否仍有独特性？** 如果答案是"否"，说明主题强化不足。

---

**主题**：{topic}
**受众**：{audience}

直接输出 JSON，无其他文字。"""


def run_propose_agent(
    llm: BaseChatModel,
    topic: str,
    audience: str = ""
) -> DesignProposals:
    """
    让 LLM 根据主题生成多套定制设计方案

    Args:
        llm: LangChain 聊天模型
        topic: 幻灯片主题
        audience: 目标受众（可选）

    Returns:
        DesignProposals，包含 3-5 套配色+风格方案
    """
    prompt = SYSTEM_PROMPT.format(topic=topic, audience=audience or "通用受众")

    structured_llm = llm.with_structured_output(DesignProposals)
    result = structured_llm.invoke(prompt)

    return result


def print_proposals(proposals: DesignProposals) -> None:
    """打印方案列表，供用户选择"""
    print("\n" + "═" * 70)
    print("  🎨 定制设计方案（根据主题生成）")
    print("═" * 70)

    preview_paths = []
    for i, p in enumerate(proposals.proposals, 1):
        marker = "⭐ 推荐" if i - 1 == proposals.recommended_index else ""
        print(f"\n  [{i}] {p.name} {marker}")
        print(f"      风格: {p.visual_style}")
        print(f"      配色: 主色 {p.primary}  辅色 {p.secondary}  强调 {p.accent}")
        print(f"      背景: {p.background}  文字 {p.text_primary}")
        print(f"      理由: {p.reasoning}")

        # 生成预览图
        if PIL_AVAILABLE:
            preview_path = generate_preview_image(p)
            if preview_path:
                preview_paths.append((i, preview_path))
                print(f"      预览: {preview_path}")

    print("\n" + "═" * 70)

    if preview_paths and PIL_AVAILABLE:
        print("\n  💡 预览图已生成，可用图片查看器打开上述路径查看配色效果")
    elif not PIL_AVAILABLE:
        print("\n  ℹ️  安装 Pillow 可生成配色预览图：pip install Pillow")


def pick_proposal(proposals: DesignProposals) -> ColorProposal:
    """让用户选择一套方案"""
    print_proposals(proposals)

    while True:
        raw = input(f"\n请选择方案编号（1-{len(proposals.proposals)}，直接回车选推荐方案）: ").strip()

        if raw == "":
            idx = proposals.recommended_index
            print(f"  ✓ 已选择推荐方案：{proposals.proposals[idx].name}")
            return proposals.proposals[idx]

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(proposals.proposals):
                print(f"  ✓ 已选择：{proposals.proposals[idx].name}")
                return proposals.proposals[idx]

        print("  ✗ 无效输入，请重试")


def generate_preview_image(proposal: ColorProposal, output_path: str = None) -> Optional[str]:
    """
    生成配色方案预览图（色卡 + 文字示例）

    Args:
        proposal: 配色方案
        output_path: 输出路径（可选），默认保存到临时目录

    Returns:
        图片路径，若 PIL 不可用返回 None
    """
    if not PIL_AVAILABLE:
        return None

    # 画布 800x400
    W, H = 800, 400
    img = Image.new("RGB", (W, H), proposal.background)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 28)
        font_text = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 16)
        font_small = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 14)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # 左侧：色块展示 (300px)
    colors = [
        ("主色", proposal.primary, 40, 40, 120, 80),
        ("辅色", proposal.secondary, 160, 40, 240, 80),
        ("强调", proposal.accent, 40, 100, 120, 140),
        ("背景", proposal.background, 160, 100, 240, 140),
        ("文字", proposal.text_primary, 40, 160, 120, 200),
        ("边框", proposal.border, 160, 160, 240, 200),
    ]

    for label, color, x1, y1, x2, y2 in colors:
        draw.rectangle([x1, y1, x2, y2], fill=color, outline=proposal.border, width=2)
        draw.text((x1 + 5, y1 + 5), label, fill=proposal.text_secondary, font=font_small)
        draw.text((x1 + 5, y1 + 22), color, fill=proposal.text_primary, font=font_small)

    # 右侧：文字示例 (500px)
    right_x = 320

    # 标题
    draw.text((right_x, 30), proposal.name, fill=proposal.text_primary, font=font_title)

    # 视觉风格标签
    draw.rectangle([right_x, 70, right_x + 100, 95], fill=proposal.primary, outline=proposal.border, width=1)
    draw.text((right_x + 10, 75), proposal.visual_style, fill="#FFFFFF", font=font_text)

    # 正文示例
    sample_text = [
        "这是主要文本示例",
        "This is primary text sample",
        "",
        "这是次要文本示例",
        "Secondary text example",
    ]
    y_offset = 120
    for i, line in enumerate(sample_text):
        color = proposal.text_primary if i < 2 else proposal.text_secondary
        draw.text((right_x, y_offset + i * 25), line, fill=color, font=font_text)

    # 底部：设计理由
    reasoning_lines = _wrap_text(proposal.reasoning, 30)
    y_offset = 280
    for line in reasoning_lines[:3]:  # 最多3行
        draw.text((right_x, y_offset), line, fill=proposal.text_secondary, font=font_small)
        y_offset += 20

    # 保存
    if output_path is None:
        import tempfile
        output_path = Path(tempfile.gettempdir()) / f"slideforge_{proposal.name.replace(' ', '_')}.png"
    else:
        output_path = Path(output_path)

    img.save(output_path)
    return str(output_path)


def _wrap_text(text: str, width: int) -> List[str]:
    """简单的文字换行"""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current + word) <= width:
            current += word + " "
        else:
            lines.append(current.strip())
            current = word + " "
    if current:
        lines.append(current.strip())
    return lines
