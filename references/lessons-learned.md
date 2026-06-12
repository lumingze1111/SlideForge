# 经验沉淀

HTML → PPTX 转换中遇到的通用问题和修复方案。每次 audit 发现可复用的模式时追加至此。

## 快速分流

1. 整页空白 → 检查 activate / force-position 是否正确
2. 文字缺失 → 检查 text-leaf 识别 + inline/block 混合容器
3. 装饰缺失 → 检查 screenshot marker 记录 + PNG 兜底
4. 字体渲染错误 → 检查 OOXML `a:latin` / `a:ea` typeface 和字体嵌入
5. 多余换行 → 检查单行检测 + `bodyPr wrap`
6. 颜色错误 → 检查 rgba 解析 + alpha 通道传递
7. 元素位置偏移 → 检查 1.5× 缩放 + Layout Agent 偏移量

## HTML 反模式

源 HTML 应避免的写法。

| 模式 | 为什么破坏 PPT | HTML 改写 |
|------|---------------|-----------|
| | | |

## OOXML 边界

OOXML 或 PPT 渲染器能力之外的模式。

| CSS / DOM 模式 | OOXML 缺的能力 | 替代通路 |
|----------------|---------------|----------|
| `background-clip: text` + `linear-gradient` | OOXML 文字 fill 无渐变裁切 | 替换为 inline SVG 走截图通道 |
| `backdrop-filter` / `mix-blend-mode` | OOXML 无对应原语 | 走 `deco_snapshot` 像素截图 |
| 多层 `text-shadow` | OOXML 只支持单 `outerShdw` | 减成单层或接受简化 |
| CJK 斜体 | CJK 字体通常没真斜体 | 仅 Latin 字符标 `italic` |
| 大字号子元素在小字号容器内 | 行距按容器算导致叠压 | 给子元素独立设置 line-height |

## 渲染端边界（不是转换 bug）

- **PowerPoint 嵌入字体信任提示** — 正常提示，源可信则在 PowerPoint 里信任文档
- **网页版 PowerPoint 忽略嵌入字体** — 这些环境不认嵌入字体，以桌面 PowerPoint 为准
- **浏览器专属交互（动效/滚动/触控）** — PPT 只保留静态页
