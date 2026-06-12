# SlideForge

<div align="center">

🎨 **AI 驱动的演示文稿生成器**

一个完全独立的 PPT 生成系统，通过浏览器交互让用户选择配色方案和大纲结构

</div>

---

## 🏗️ 设计方案

SlideForge 采用 **多 Agent 协作 + 浏览器测量 + OOXML 装配** 的三阶段架构。

### 整体架构

```
用户输入主题
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  Agent 层（LLM 驱动）                                     │
│                                                          │
│  topic_analyzer  →  propose_agent  →  outline_proposal   │
│  （主题分析）         （配色方案）        （大纲生成）          │
│                                                          │
│  html_generator  ←  research_agent  ←  fact_checker      │
│  （HTML 渲染）        （事实检索）         （真实性核查）       │
│                                                          │
│  speaker_notes  ←  review_agent  ←  layout_agent         │
│  （演讲者备注）        （内容审校）         （位置调优）          │
└─────────────────────────────────────────────────────────┘
    │
    ▼  浏览器交互选择（配色 / 大纲）
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  转换层（HTML → PPTX）                                     │
│                                                          │
│  Playwright 测量  →  JSON 结构  →  OOXML 装配              │
│  （1920×1080 px）     （measure.py）   （assemble.py）       │
│                                                          │
│  1.5× 中心缩放 + Layout Agent 150px 右移补偿               │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  校验层（自动修复）                                        │
│                                                          │
│  渐变校验  →  格式校验  →  结构对比  →  循环修复（≤3轮）    │
└─────────────────────────────────────────────────────────┘
    │
    ▼
  PPTX 输出
```

### 核心设计决策

| 决策 | 方案 | 原因 |
|------|------|------|
| 中间格式 | JSON 结构化记录 | 解耦 HTML 渲染与 PPTX 生成，便于校验和修补 |
| 缩放策略 | 1.5× 中心缩放 | 1920px 视口 → 13.333" 幻灯片，元素以视觉中心为基准均匀放大 |
| 位置补偿 | init.x + 150px 全局右移 | 补偿中心缩放导致的左侧偏移，保持与 HTML 布局一致 |
| 字体渲染 | BCR × 1.12 余量 | 补偿 PPT 与浏览器字体度量差异，避免文字截断 |
| 渐变处理 | CSS → OOXML gradFill | 解析色标和角度，直接写入 slide XML |
| 校验机制 | 生成 → 校验 → 修补循环 | 自动检测并修复位置/样式/渐变偏差 |

### Agent 职责

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| `topic_analyzer` | 分析主题特征，提取关键词和风格倾向 | 用户主题 | 主题画像 |
| `propose_agent` | 生成多套配色方案（含渐变） | 主题画像 | 3-5 套配色 |
| `outline_proposal` | 生成多种大纲结构 | 主题 + 受众 | 大纲选项 |
| `html_generator` | 生成完整 HTML 幻灯片 | 大纲 + 配色 | HTML 文件 |
| `research_agent` | 搜索主题相关事实和数据 | 关键词 | 事实列表 |
| `fact_checker` | 核查生成内容的真实性 | 内容 + 事实 | 可信度评分 |
| `speaker_notes` | 生成演讲者备注 | 幻灯片内容 | 备注文本 |
| `review_agent` | 审校内容质量 | HTML 内容 | 修改建议 |
| `layout_agent` | 调整 1.5× 缩放后元素位置 | 测量记录 | 位置调整 |

---

## 📝 待优化

- **HTML 与 PPTX 格式对齐** — 进一步缩小浏览器渲染与 OOXML 输出之间的位置、字号、行距差异，减少校验循环的修正次数
- **TTS 语音合成** — 将演讲者备注自动合成为语音旁白，支持导出带配音的演示文稿或视频
- **主题相关图片** — 通过网络搜索或 AIGC（Stable Diffusion / DALL·E）自动匹配与幻灯片内容相关的配图
- **Agent 流程自进化** — Agent 根据校验反馈自动调整生成策略，持续优化输出质量，减少人工干预
- **用户可编辑 PPTX** — 生成后支持对 PPTX 的微调编辑（文字修改、图片替换、布局调整），无需回到源 HTML 重新生成

## 🎬 工作流程

```
1. 启动程序
   ↓
2. AI 生成配色方案 → 浏览器预览 → 用户点击选择
   ↓
3. AI 生成大纲结构 → 浏览器预览 → 用户点击选择
   ↓
4. 根据选择生成详细内容
   ↓
5. 渲染 HTML 预览（自动打开）
   ↓
6. 导出 PPTX 文件（自动打开）
```

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/lumingze1111/SlideForge.git
cd SlideForge

# 安装依赖
pip install langchain-openai pydantic python-pptx
```

## 🚀 快速开始

```bash
# 设置 API 密钥
export DEEPSEEK_API_KEY='your-api-key-here'

# 启动程序
python main.py
```

程序会自动：
1. 生成配色方案并在浏览器打开预览
2. 等待你选择配色方案（点击卡片 → 点击「确认方案」）
3. 生成大纲方案并在浏览器打开预览
4. 等待你选择大纲结构（点击卡片 → 点击「确认大纲」）
5. 自动生成完整 PPT 并打开

## 📸 预览

### 配色方案选择
![配色预览](docs/color_preview.png)

### 大纲结构选择
![大纲预览](docs/outline_preview.png)

### 幻灯片 HTML 预览
![HTML 预览](docs/slides_html.png)

### 生成的 PPT
![PPT 样例](docs/ppt_sample.png)

## 🎨 支持的配色特性

- **纯色配色** - 传统的十六进制颜色 `#1976D2`
- **渐变背景** - CSS 线性/径向渐变
  - `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
  - `radial-gradient(circle, #0d0d2b 0%, #1a1a3e 100%)`
- **渐变文字** - 使用 `background-clip: text` 实现渐变标题
- **自适应配色** - 根据主题自动生成高对比度配色

## 📋 支持的大纲结构

- **故事叙述型** - 引入 → 冲突 → 转折 → 解决 → 展望
- **数据驱动型** - 问题 → 数据洞察 → 趋势 → 结论
- **问题解决型** - 现状 → 问题 → 方案 → 效果
- **对比分析型** - 传统方式 vs 新方法 → 优劣对比

## 🛠️ 技术栈

- **LLM** - DeepSeek Chat API（可替换为其他 OpenAI 兼容 API）
- **Agent框架** - LangChain + Pydantic
- **PPT Generation** - python-pptx
- **Web Preview** - HTML + CSS + JavaScript
- **交互机制** - HTTP Server (多线程)

## 📂 项目结构

```
SlideForge/
├── main.py                          # 主入口
├── slideforge/
│   ├── agents/
│   │   ├── propose_agent.py         # 配色方案生成
│   │   ├── outline_proposal.py      # 大纲方案生成
│   │   ├── html_generator.py        # 内容生成与渲染
│   │   ├── topic_analyzer.py        # 主题分析
│   │   ├── style_agent.py           # 样式生成
│   │   ├── design_agent.py          # 设计 Agent
│   │   ├── research_agent.py        # 研究 Agent
│   │   ├── fact_checker.py          # 事实核查
│   │   ├── review_agent.py          # 审校 Agent
│   │   └── speaker_notes.py         # 演讲者备注
│   ├── pptx_engine/
│   │   ├── measure.py               # Playwright 测量（HTML → JSON 结构）
│   │   ├── assemble.py              # OOXML 装配（JSON → PPTX）
│   │   ├── embed_fonts.py           # 字体嵌入与映射
│   │   ├── font_paths.py            # 字体路径解析
│   │   ├── text_utils.py            # 文本工具（CJK 检测等）
│   │   ├── adapters.py              # 中间格式适配
│   │   └── _js_snippets.py          # 浏览器端 JS 测量片段
│   ├── design_system/
│   │   ├── colors.py                # 配色系统
│   │   └── typography.py            # 字体排版
│   ├── pptx_converter.py            # HTML → PPTX 转换入口
│   ├── pptx_exporter.py             # PPTX 导出器
│   ├── preview_generator.py         # 浏览器预览生成
│   └── interactive.py               # 交互式选择
├── tools/
│   ├── validate_gradients.py        # 渐变校验与修补
│   ├── validate_format.py           # 格式校验（元素、样式、字体）
│   └── structural_diff.py           # 结构性元素对比
└── README.md
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - LLM 应用框架
- [python-pptx](https://github.com/scanny/python-pptx) - PPTX 生成库
- [DeepSeek](https://www.deepseek.com/) - AI 模型支持

---

<div align="center">
Made with ❤️ by SlideForge Team
</div>
