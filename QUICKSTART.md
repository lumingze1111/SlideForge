# 🚀 SlideForge 快速开始指南

**版本**: 1.0.0  
**最后更新**: 2026-06-14

---

## ⚡ 5 分钟快速开始

### 1. 安装依赖

```bash
cd /Users/lumingze/Desktop/SlideForge
pip install -r requirements.txt
```

### 2. 配置 API Keys

**最小配置**（仅文本幻灯片）:
```bash
export DEEPSEEK_API_KEY='your-deepseek-api-key'
```

**完整功能**（文本 + 图片 + 图表）:
```bash
export DEEPSEEK_API_KEY='your-deepseek-api-key'
export UNSPLASH_ACCESS_KEY='your-unsplash-key'
```

### 3. 运行

```bash
python main.py "库里"
```

### 4. 查看输出

- **HTML 预览**: `output/slides_库里.html`
- **PPTX 文件**: `output/slides_库里.pptx`
- **错误报告**: `output/error_logs/session_xxx/report.html`

---

## 🔑 获取 API Keys

### DeepSeek API Key（必需）

1. 访问 https://platform.deepseek.com/
2. 注册账号
3. 创建 API Key
4. 复制 API Key

```bash
export DEEPSEEK_API_KEY='sk-xxxxxxxxxxxxxxxx'
```

### Unsplash API Key（可选，推荐）

1. 访问 https://unsplash.com/developers
2. 注册开发者账号
3. 创建应用
4. 复制 Access Key

```bash
export UNSPLASH_ACCESS_KEY='xxxxxxxxxxxxxxxx'
```

**免费额度**: 5000 次/小时

### Pexels API Key（可选，备选）

1. 访问 https://www.pexels.com/api/
2. 注册账号
3. 生成 API Key

```bash
export PEXELS_API_KEY='xxxxxxxxxxxxxxxx'
```

**免费额度**: 200 次/小时

---

## 🎯 使用示例

### 基础使用

```bash
# 生成关于"库里"的演示文稿
python main.py "库里"
```

### 禁用图片搜索

```bash
ENABLE_IMAGE_SEARCH=false python main.py "主题"
```

### 禁用图表生成

```bash
ENABLE_CHART_GENERATION=false python main.py "主题"
```

### 纯文本模式

```bash
ENABLE_IMAGE_SEARCH=false ENABLE_CHART_GENERATION=false python main.py "主题"
```

---

## 📊 功能说明

### 自动图片搜索 🖼️

- 分析每页幻灯片内容
- 自动搜索相关图片
- 智能选择插入位置
- 支持背景图片、居中图片等

**示例**: 生成"库里"主题时，会自动搜索库里比赛的图片作为封面背景。

### 智能图表生成 📊

- 自动获取相关数据
- 生成多种图表类型
- 条形图、折线图、饼图等
- 自动选择最佳渲染方式

**示例**: 生成"库里"主题时，会自动获取职业生涯数据并生成趋势图表。

### 完整错误追踪 🐛

- 实时记录所有错误
- 生成美观的 HTML 报告
- 自动降级和恢复
- 多维度分析

---

## 🧪 测试

运行测试确保一切正常：

```bash
pytest tests/ -v
```

**预期结果**: 39 passed in 0.78s

---

## 📚 文档

- **设计文档**: `docs/superpowers/specs/2026-06-14-image-chart-enhancement-design.md`
- **实现总结**: `IMPLEMENTATION_COMPLETE.md`
- **测试报告**: `TEST_REPORT.md`
- **最终总结**: `FINAL_SUMMARY.md`

---

## ❓ 常见问题

### Q: 没有配置图片搜索 API Key 会怎样？

**A**: 系统会自动禁用图片搜索功能，但仍然可以生成文本和图表。

### Q: 图表数据从哪里来？

**A**: 系统使用免费的 DuckDuckGo 搜索和 Wikipedia API 自动获取数据。

### Q: 可以只生成文本幻灯片吗？

**A**: 可以，使用环境变量禁用图片和图表功能。

### Q: 生成需要多长时间？

**A**: 
- 仅文本: ~30 秒
- 文本 + 图片: ~60 秒
- 文本 + 图表: ~90 秒
- 完整功能: ~120 秒

### Q: 支持哪些图表类型？

**A**: 条形图、折线图、饼图、散点图、表格、热图、箱线图、雷达图（共 8 种）。

---

## 🆘 遇到问题？

1. **查看错误报告**: `output/error_logs/session_xxx/report.html`
2. **查看测试报告**: `TEST_REPORT.md`
3. **运行测试**: `pytest tests/ -v`
4. **检查 API Key**: 确保环境变量正确设置

---

## 🎉 成功案例

### 示例 1: 生成"库里"主题演示文稿

```bash
export DEEPSEEK_API_KEY='your-key'
export UNSPLASH_ACCESS_KEY='your-key'
python main.py "库里"
```

**输出**:
- ✅ 8 页幻灯片
- ✅ 3 张图片（封面背景、比赛照片）
- ✅ 2 个图表（职业生涯数据、得分趋势）
- ✅ 完整的演讲者备注

### 示例 2: 生成技术演讲

```bash
python main.py "Python 异步编程"
```

**输出**:
- ✅ 代码示例自动格式化
- ✅ 技术图表（性能对比）
- ✅ 架构图（可选）

---

## 📝 提示

### 最佳实践

1. **明确主题**: 使用具体的主题名称，如"库里的职业生涯"而不是"篮球"
2. **检查预览**: 生成后先查看 HTML 预览
3. **查看错误报告**: 即使生成成功，也查看错误报告了解潜在问题
4. **配置 API Keys**: 为了获得最佳效果，配置所有 API Keys

### 性能优化

1. **缓存图片**: 系统会自动下载图片到本地
2. **并行处理**: 未来版本将支持并行处理多页幻灯片
3. **减少 API 调用**: 使用 `ENABLE_*` 环境变量控制功能

---

## 🔄 更新日志

### v1.0.0 (2026-06-14)

✅ 初始版本发布
- 图片搜索与插入
- 数据获取与图表生成
- 错误追踪和报告
- ReAct 智能决策
- 完整测试套件

---

## 📧 反馈

如有问题或建议，请查看：
- 测试报告: `TEST_REPORT.md`
- 实现文档: `IMPLEMENTATION_COMPLETE.md`
- 设计文档: `docs/superpowers/specs/2026-06-14-image-chart-enhancement-design.md`

---

**祝你使用愉快！🚀**
