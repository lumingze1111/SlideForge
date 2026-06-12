# SlideForge

<div align="center">

**AI 驱动的演示文稿生成器**

输入主题，自动生成配色、大纲、内容，一键导出 PPTX

</div>

---

## 架构

SlideForge 采用 **Agent 协作** 思路：多个 LLM Agent 分工完成主题分析、配色提案、大纲生成和内容创作，最终通过两种可选路径将 HTML 幻灯片转换为 PPTX。

```
用户输入主题
    │
    ▼
┌─────────────────────────────────────────────┐
│  Agent 层（LLM 驱动）                         │
│                                              │
│  topic_analyzer → propose_agent → outline    │
│  （主题分析）      （配色方案）     （大纲）     │
│                                              │
│  html_generator ← research_agent ← fact_     │
│  （HTML 渲染）     （事实检索）     checker    │
│                                              │
│  speaker_notes ← review_agent ← layout_agent │
│  （演讲备注）      （内容审校）    （位置调优）  │
└─────────────────────────────────────────────┘
    │
    ▼  浏览器交互选择（配色 / 大纲）
    │
    ▼
┌─────────────────────────────────────────────┐
│  转换层（HTML → PPTX）                        │
│                                              │
│  路径 A（默认）：LLM 直接渲染                   │
│  DeepSeek 分析 HTML → 写 python-pptx 代码     │
│  → 执行生成 PPTX（最多 3 轮自动修复）           │
│                                              │
│  路径 B（回退）：传统流水线                      │
│  Playwright 测量 → JSON 结构 → OOXML 装配      │
│  校验循环（渐变 + 格式 ≤3 轮）                  │
└─────────────────────────────────────────────┘
    │
    ▼
  PPTX 输出
```

### Agent 职责

| Agent | 职责 |
|-------|------|
| `topic_analyzer` | 分析主题特征，提取关键词和风格倾向 |
| `propose_agent` | 生成 3-5 套配色方案（含渐变） |
| `outline_proposal` | 生成多种大纲结构 |
| `html_generator` | 生成完整 HTML 幻灯片 |
| `research_agent` | 搜索主题相关事实和数据 |
| `fact_checker` | 核查生成内容的真实性 |
| `speaker_notes` | 生成演讲者备注 |
| `review_agent` | 审校内容质量 |
| `layout_agent` | 调整 1.5x 缩放后元素位置 |

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt
pip install python-pptx openai

# 设置 API Key
export DEEPSEEK_API_KEY='your-api-key-here'

# 启动
python main.py "你的主题"
```

程序会依次：
1. 分析主题并给出建议
2. 生成配色方案 → 浏览器预览 → 点击选择
3. 生成大纲结构 → 浏览器预览 → 点击选择
4. 生成完整内容并渲染 HTML 预览
5. LLM 直接渲染 PPTX（失败则回退传统流水线）

---

## 项目结构

```
SlideForge/
├── main.py                         # 主入口
├── slideforge/
│   ├── agents/
│   │   ├── topic_analyzer.py       # 主题分析
│   │   ├── propose_agent.py        # 配色方案生成
│   │   ├── outline_proposal.py     # 大纲方案生成
│   │   ├── html_generator.py       # 内容生成与 HTML 渲染
│   │   ├── research_agent.py       # 事实检索
│   │   ├── fact_checker.py         # 真实性核查
│   │   ├── review_agent.py         # 内容审校
│   │   ├── speaker_notes.py        # 演讲者备注
│   │   ├── layout_agent.py         # 布局调优
│   │   ├── style_agent.py          # 样式生成
│   │   └── design_agent.py         # 设计 Agent
│   ├── pptx_engine/
│   │   ├── measure.py              # Playwright 测量（HTML → JSON）
│   │   ├── assemble.py             # OOXML 装配（JSON → PPTX）
│   │   ├── adapters.py             # 中间格式适配
│   │   ├── text_utils.py           # 文本工具（CJK 检测等）
│   │   ├── embed_fonts.py          # 字体嵌入
│   │   └── font_paths.py           # 字体路径解析
│   ├── pptx_converter.py           # HTML → PPTX 转换入口
│   ├── pptx_renderer.py            # PPTX → PNG 渲染（LibreOffice）
│   ├── visual_audit.py             # 视觉对比审计
│   ├── preview_generator.py        # 浏览器预览
│   └── interactive.py              # 交互式选择
├── tools/
│   ├── llm_direct_convert.py       # LLM 直接渲染（路径 A，默认）
│   ├── validate_gradients.py       # 渐变校验与修补
│   ├── validate_format.py          # 格式校验（元素、样式、字体）
│   └── structural_diff.py          # 结构性元素对比
├── tests/
│   ├── test_layout_agent.py
│   └── test_assemble_layout_agent.py
├── references/
│   └── lessons-learned.md          # HTML→PPTX 经验沉淀
├── docs/                           # 截图等文档资源
└── requirements.txt
```

---

## 两种转换路径

### 路径 A：LLM 直接渲染（默认）

`tools/llm_direct_convert.py` 将完整 HTML 发给 DeepSeek，让 LLM 自己分析结构、写 python-pptx 代码生成 PPTX。执行失败时自动将错误发回 LLM 修复，最多 3 轮。

```bash
python tools/llm_direct_convert.py --html slides.html --output output.pptx
```

### 路径 B：传统流水线（回退）

`slideforge/pptx_converter.py` 用 Playwright 测量 DOM 元素位置与样式，转为 JSON 中间格式，再用 python-pptx 装配成 OOXML。支持截图模式（整页截图 + 透明文字叠层）和视觉审计。

```bash
python -c "
from slideforge.pptx_converter import convert_html_to_pptx
convert_html_to_pptx('slides.html', 'output.pptx')
"
```

---

## 📝 待优化

- **LLM 渲染精度** — LLM 直接渲染的渐变、布局、字体大小与源 HTML 仍有偏差，需优化 system prompt 或引入自检机制
- **TTS 语音合成** — 将演讲者备注自动合成为语音旁白，支持导出带配音的演示文稿或视频
- **主题相关图片** — 通过网络搜索或 AIGC（Stable Diffusion / DALL·E）自动匹配与幻灯片内容相关的配图
- **Agent 流程自进化** — Agent 根据校验反馈自动调整生成策略，持续优化输出质量，减少人工干预
- **用户可编辑 PPTX** — 生成后支持对 PPTX 的微调编辑（文字修改、图片替换、布局调整），无需回到源 HTML 重新生成

---

## 技术栈

| 层 | 技术 |
|----|------|
| LLM | DeepSeek Chat API（OpenAI 兼容） |
| Agent 框架 | LangChain + Pydantic |
| PPT 生成 | python-pptx（路径 A/B 共用） |
| Web 预览 | HTML + CSS + JavaScript + HTTP Server |
| 测量（路径 B） | Playwright |
| 渲染审计 | LibreOffice headless + pdf2image + Pillow |

---

## License

MIT
