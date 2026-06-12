"""HTML → PPTX 转换引擎

基于 claude-skill-html-to-pptx 的流水线架构，核心步骤：

1. measure — 用 Playwright 打开 HTML，提取每个 slide 所有可见元素的位置/样式/文本
2. assemble — 根据测量数据装配 OOXML（python-pptx 底层 XML 操作）
"""
