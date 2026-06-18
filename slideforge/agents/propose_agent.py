"""
Propose Agent - 根据主题生成多套定制设计方案

不使用固定模版，而是让 LLM 根据主题和受众动态创造配色+视觉风格。
"""

import colorsys
import re
from dataclasses import dataclass
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
    colors: Dict[str, str] = Field(description="配色字典，至少4个颜色，可以包含渐变。key为颜色用途（如'primary','gradient_bg','accent_1'），value为颜色值（纯色用十六进制如#1976D2，渐变用CSS格式如'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'）")
    visual_style: str = Field(description="推荐视觉风格：minimalist/bold/elegant/corporate/playful")
    reasoning: str = Field(description="为什么这套配色适合该主题，50字以内")

    # 为了兼容旧代码，提供便捷访问属性
    @property
    def primary(self) -> str:
        return self.colors.get('primary', '#1976D2')

    @property
    def secondary(self) -> str:
        return self.colors.get('secondary', '#424242')

    @property
    def accent(self) -> str:
        return self.colors.get('accent', '#FFC107')

    @property
    def background(self) -> str:
        return self.colors.get('background', '#FFFFFF')

    @property
    def surface(self) -> str:
        return self.colors.get('surface', self.colors.get('background', '#F5F5F5'))

    @property
    def text_primary(self) -> str:
        return self.colors.get('text_primary', '#212121')

    @property
    def text_secondary(self) -> str:
        return self.colors.get('text_secondary', '#757575')

    @property
    def text_disabled(self) -> str:
        return self.colors.get('text_disabled', '#BDBDBD')

    @property
    def border(self) -> str:
        return self.colors.get('border', '#E0E0E0')


class DesignProposals(BaseModel):
    """多套设计方案提案集合"""
    proposals: List[ColorProposal] = Field(description="3-5套方案，按推荐度排序")
    recommended_index: int = Field(description="最推荐方案的索引（0-based）")


_HEX_COLOR_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
_LINEAR_ANGLE_RE = re.compile(r"linear-gradient\(\s*([0-9.]+)deg", re.IGNORECASE)


@dataclass(frozen=True)
class BackgroundDescriptor:
    raw: str
    colors: tuple[tuple[int, int, int], ...]
    style: str
    angle: float | None
    hue: float
    lightness: float
    saturation: float
    tone: str
    temperature: str
    valid: bool


def _parse_hex_color(value: str) -> tuple[int, int, int] | None:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return None
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _extract_hex_colors(value: str) -> tuple[tuple[int, int, int], ...]:
    colors = []
    for match in _HEX_COLOR_RE.finditer(value or ""):
        parsed = _parse_hex_color(match.group(0))
        if parsed is not None:
            colors.append(parsed)
    return tuple(colors)


def _background_style(value: str) -> str:
    lowered = (value or "").strip().lower()
    if lowered.startswith("linear-gradient"):
        return "linear"
    if lowered.startswith("radial-gradient"):
        return "radial"
    if "gradient" in lowered:
        return "other_gradient"
    return "solid"


def _background_angle(value: str) -> float | None:
    match = _LINEAR_ANGLE_RE.search(value or "")
    if not match:
        return None
    return float(match.group(1))


def _average_hls(colors: tuple[tuple[int, int, int], ...]) -> tuple[float, float, float]:
    if not colors:
        return 0.0, 0.5, 0.0
    hues = []
    lightnesses = []
    saturations = []
    for r, g, b in colors:
        hue, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        hues.append(hue * 360)
        lightnesses.append(lightness)
        saturations.append(saturation)
    return (
        sum(hues) / len(hues),
        sum(lightnesses) / len(lightnesses),
        sum(saturations) / len(saturations),
    )


def _tone(lightness: float) -> str:
    if lightness >= 0.68:
        return "light"
    if lightness <= 0.35:
        return "dark"
    return "mid"


def _temperature(hue: float, saturation: float) -> str:
    if saturation < 0.18:
        return "neutral"
    if 20 <= hue <= 75 or hue >= 330:
        return "warm"
    return "cool"


def _analyze_background(value: str) -> BackgroundDescriptor:
    raw = value or ""
    colors = _extract_hex_colors(raw)
    hue, lightness, saturation = _average_hls(colors)
    return BackgroundDescriptor(
        raw=raw,
        colors=colors,
        style=_background_style(raw),
        angle=_background_angle(raw),
        hue=hue,
        lightness=lightness,
        saturation=saturation,
        tone=_tone(lightness),
        temperature=_temperature(hue, saturation),
        valid=bool(colors),
    )


def _hue_distance(a: float, b: float) -> float:
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def _backgrounds_are_similar(first: BackgroundDescriptor, second: BackgroundDescriptor) -> bool:
    if not first.valid or not second.valid:
        return False
    hue_close = _hue_distance(first.hue, second.hue) <= 28
    lightness_close = abs(first.lightness - second.lightness) <= 0.18
    saturation_close = abs(first.saturation - second.saturation) <= 0.28
    same_bucket = first.tone == second.tone and first.temperature == second.temperature
    same_gradient_family = first.style == second.style or (
        first.style != "solid" and second.style != "solid"
    )
    return same_bucket and same_gradient_family and hue_close and lightness_close and saturation_close


def _proposal_background_value(proposal: ColorProposal) -> str:
    colors = proposal.colors or {}
    return colors.get("gradient_bg") or colors.get("background") or colors.get("surface") or ""


def _clamp_recommended_index(index: int, count: int) -> int:
    if count <= 0:
        return 0
    if index < 0 or index >= count:
        return 0
    return index


def _coverage_gain(
    descriptor: BackgroundDescriptor,
    selected: list[BackgroundDescriptor],
    duplicate: bool,
) -> float:
    if not selected:
        return 10.0
    selected_tones = {item.tone for item in selected}
    selected_temperatures = {item.temperature for item in selected}
    selected_styles = {item.style for item in selected}
    score = 0.0
    if descriptor.tone not in selected_tones:
        score += 4.0
    if descriptor.temperature not in selected_temperatures:
        score += 3.0
    if descriptor.style not in selected_styles:
        score += 2.0
    if descriptor.valid:
        score += 1.0
    if duplicate:
        score -= 100.0
    return score


def diversify_color_proposals(proposals: DesignProposals, min_count: int = 3) -> DesignProposals:
    proposal_list = list(proposals.proposals or [])
    if not proposal_list:
        return proposals
    if len(proposal_list) <= min_count:
        return DesignProposals(
            proposals=proposal_list,
            recommended_index=_clamp_recommended_index(proposals.recommended_index, len(proposal_list)),
        )

    recommended_original = _clamp_recommended_index(proposals.recommended_index, len(proposal_list))
    descriptors = [_analyze_background(_proposal_background_value(proposal)) for proposal in proposal_list]

    selected_indices = [recommended_original]
    selected_descriptors = [descriptors[recommended_original]]
    remaining = [idx for idx in range(len(proposal_list)) if idx != recommended_original]
    rejected_indices = []

    while remaining:
        ranked = []
        for idx in remaining:
            duplicate = any(
                _backgrounds_are_similar(descriptors[idx], selected)
                for selected in selected_descriptors
            )
            score = _coverage_gain(descriptors[idx], selected_descriptors, duplicate)
            ranked.append((score, -idx, idx, duplicate))
        ranked.sort(reverse=True)
        _, _, best_idx, is_duplicate = ranked[0]
        remaining.remove(best_idx)
        if is_duplicate and len(selected_indices) >= min_count:
            rejected_indices.append(best_idx)
            rejected_indices.extend(remaining)
            break
        selected_indices.append(best_idx)
        selected_descriptors.append(descriptors[best_idx])

    needed_count = min(min_count, len(proposal_list))
    for idx in rejected_indices:
        if len(selected_indices) >= needed_count:
            break
        if idx not in selected_indices:
            selected_indices.append(idx)

    diversified = [proposal_list[idx] for idx in selected_indices]
    return DesignProposals(
        proposals=diversified,
        recommended_index=selected_indices.index(recommended_original)
        if recommended_original in selected_indices
        else 0,
    )


SYSTEM_PROMPT = """你是顶尖的视觉设计师，擅长从主题中提取核心意象，转化为精准的配色方案（包含渐变色）。

## 任务
根据主题和受众，生成 3-5 套**高度差异化**的配色方案。

## 分析步骤
1. **提取主题关键词** — 从主题中识别核心概念（如"深海"→深邃/神秘/流动/压力）
2. **关联色彩意象** — 将概念映射到色彩（深海→深蓝渐变至黑、生物荧光绿、深渊紫）
3. **渐变设计** — 根据主题动态特征设计渐变（海洋→蓝绿渐变，量子→紫蓝渐变，日落→橙红渐变）
4. **受众适配** — 技术受众偏深色/高对比，大众受众偏柔和/亲和
5. **对比度验证** — 确保文字色在背景色上 WCAG AA ≥ 4.5:1

## 配色要求
1. **数量自由** — 每套方案至少 4 个颜色，可以更多（6-10个）以满足层次需求
2. **颜色格式**：
   - 纯色：十六进制 `#1976D2`
   - 渐变：CSS `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
   - 径向渐变：`radial-gradient(circle, #ff6b6b 0%, #4ecdc4 100%)`
3. **颜色用途命名**（示例）：
   - `background` / `gradient_bg` — 背景（建议至少一个渐变背景）
   - `primary` / `primary_gradient` — 主色
   - `secondary` — 辅色
   - `accent` / `accent_light` / `accent_dark` — 强调色（可多个层次）
   - `text_primary` / `text_secondary` / `text_disabled` — 文字色
   - `surface` / `card_bg` — 表面/卡片背景
   - `border` / `divider` — 边框/分隔线
4. **渐变运用场景**：
   - 背景渐变增加空间深度（如深海从蓝渐变至黑）
   - 标题渐变增强视觉冲击（如量子紫蓝渐变文字）
   - 卡片/按钮渐变增加质感
5. **对比度** — 文字色在渐变背景上需测试多点对比度

## 方案多样性
- 方案1：最贴合主题的代表性配色，必须包含渐变（推荐方案）
- 方案2-3：从不同角度诠释主题（深色/浅色，冷色/暖色，至少一个用渐变）
- 方案4-5：突破常规的创意配色（多色渐变，大胆撞色）

## 视觉隐喻分轨
每套方案必须来自不同视觉隐喻，不要只是生成相近的深蓝/紫色渐变：
- 品牌身份：提炼主题已有品牌色、队伍色、产品色或行业识别色
- 环境场景：用地点、时间、天气、空间氛围建立背景
- 数据/科技：用仪表盘、光谱、网格、信号、算法感表达结构
- 人物情绪：用人物特质、成长弧线、紧张/希望/胜利等情绪表达
- 大胆反差：用少量高对比撞色或明暗反差提供创意选项

最终 3-5 套方案应覆盖不同明暗、冷暖和背景类型；除非主题强制要求，不要输出多套相似暗色冷调渐变。

## 方案命名规则
必须包含**主题关键词 + 色彩意象 + 情绪**，例如：
- ✅ "深海幽蓝渐变 - 神秘探索系"
- ✅ "量子紫光波 - 赛博未来感"
- ✅ "日落暖金流 - 温暖希望系"

## 主题强化检查
生成后自问：**配色是否体现主题的动态特征？渐变是否增强了主题表达？**

---

**主题**：{topic}
**受众**：{audience}

直接输出 JSON，colors 字段为字典，至少 4 个颜色，鼓励使用渐变。"""


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

    # 尝试 structured_output，失败则用 JSON mode
    try:
        structured_llm = llm.with_structured_output(DesignProposals)
        result = structured_llm.invoke(prompt)
        return diversify_color_proposals(result)
    except Exception as e:
        # Fallback: JSON mode
        import json
        from langchain_core.messages import HumanMessage, SystemMessage

        schema_str = json.dumps(DesignProposals.model_json_schema(), ensure_ascii=False, indent=2)
        json_prompt = prompt + "\n\n必须严格按照以下 JSON schema 输出：\n" + schema_str

        response = llm.invoke([
            SystemMessage(content="You are a professional visual designer. Output valid JSON only."),
            HumanMessage(content=json_prompt)
        ])

        # 提取 JSON
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        return diversify_color_proposals(DesignProposals(**data))


def print_proposals(proposals: DesignProposals, topic: str = "") -> None:
    """打印方案列表，供用户选择"""
    print("\n" + "═" * 70)
    print("  🎨 定制设计方案（根据主题生成）")
    print("═" * 70)

    for i, p in enumerate(proposals.proposals, 1):
        marker = "⭐ 推荐" if i - 1 == proposals.recommended_index else ""
        print(f"\n  [{i}] {p.name} {marker}")
        print(f"      风格: {p.visual_style}")
        print(f"      配色数量: {len(p.colors)} 个")

        # 显示所有颜色
        for key, value in list(p.colors.items())[:6]:  # 最多显示6个
            display_value = value[:50] + "..." if len(value) > 50 else value
            print(f"        • {key}: {display_value}")
        if len(p.colors) > 6:
            print(f"        ... 还有 {len(p.colors) - 6} 个颜色")

        print(f"      理由: {p.reasoning}")

    print("\n" + "═" * 70)


def pick_proposal(proposals: DesignProposals, topic: str = "") -> ColorProposal:
    """让用户在浏览器中点击选择一套方案"""
    from slideforge.preview_generator import generate_preview_html, wait_for_selection

    preview_path = generate_preview_html(proposals.proposals, topic or "主题演示")
    print(f"\n  💡 预览页面已生成：{preview_path}")

    import subprocess
    try:
        subprocess.run(["open", preview_path], check=False)
        print(f"  ✓ 已在浏览器中打开预览")
    except Exception:
        pass

    idx = wait_for_selection(len(proposals.proposals))
    chosen = proposals.proposals[idx]
    print(f"\n  ✓ 已选择方案 [{idx + 1}]：{chosen.name}")
    return chosen


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
