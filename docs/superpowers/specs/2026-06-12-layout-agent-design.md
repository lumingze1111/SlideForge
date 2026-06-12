# Layout Agent — LLM 智能布局调整

## 问题

当前 `_scaled_rect` + `_clamp_to_slide` 对每个元素独立进行中心缩放，再机械 clamp 到幻灯片边界，导致：

1. **相邻元素重叠**：各自从中心放大 1.5× 后，互相侵入对方空间
2. **边缘元素被推到角落**：clamp 把负坐标元素直接设到 x=0，破坏视觉节奏
3. **列/行关系错乱**：左右两栏各自左移后，栏间距先缩小再被 clamp 打断

## 方案

引入 **Layout Agent**（LLM Agent，沿用项目已有的 `langgraph` + `ChatOpenAI` 模式），
逐页分析幻灯片元素布局，智能调整位置，在 1.5× 缩放的前提下保持视觉和谐。

## 架构

```
measurement JSON (per slide)
         │
         ▼
┌─────────────────────────────────────────────┐
│          Layout Agent (per slide)            │
│                                             │
│  ReAct 循环：                                 │
│  1. get_slide_elements() → 查看布局           │
│  2. 分析分组 / 列 / 行结构                    │
│  3. propose_adjustments() → 输出调整方案      │
│  4. check_layout() → 验证是否还有溢出/重叠     │
│  5. 如有问题 → 回到步骤 3 精调                │
│                                             │
│  输出：{record_id: {x, y, w, h}}             │
└─────────────────────────────────────────────┘
         │ _adjusted_rect 挂载到 record
         ▼
    assemble_slide() 直接使用 _adjusted_rect
```

## 数据处理流

### 输入

每页 slide 的 records 数据，LLM 收到以下结构化信息：

- 幻灯片尺寸（1920×1080）
- 每个元素：
  - `id` — record 在数组中的下标
  - `kind` — text / shape / deco_snapshot / svg / img / canvas
  - `text`（如果有）— 文本内容前 40 字
  - `fontSize`（如果有）— 字号
  - `orig` — 原始 HTML 测量 rect `(x, y, w, h)`
  - `init` — 中心缩放 1.5× 后的初始 rect `(x, y, w, h)`（由 `_scaled_rect` 算出）
  - `tag` — html 标签名（辅助理解布局角色）

### 输出

```
{
  "adjustments": {
    "0": {"x": 0, "y": 0, "w": 1920, "h": 1080},
    "1": {"x": 30, "y": 30, "w": 400, "h": 45},
    ...
  },
  "reasoning": "左栏3个元素等距排列，右栏保持水平对齐..."
}
```

调整值为**绝对坐标**（CSS px 单位），assembly 阶段再转 EMU。

### 集成点

在 `assemble_slide()` 中，`_prepare_text_layouts()` 之后、渲染循环之前加入：

```python
def assemble_slide(slide, data):
    _prepare_text_layouts(data["records"])
    
    # ── Layout Agent 调优 ──
    try:
        from slideforge.agents.layout_agent import run_layout_agent
        llm = _get_layout_llm()  # 创建或复用 LLM 实例
        adjustments = run_layout_agent(llm, data["records"])
        for rec in data["records"]:
            adj = adjustments.get(rec.get("id"))
            if adj:
                rec["_adjusted_rect"] = (adj["x"], adj["y"], adj["w"], adj["h"])
    except Exception:
        pass  # fallback 到 _scaled_rect
    
    # ── 渲染循环 ──
    for rec in data["records"]:
        # 有 _adjusted_rect 则用，否则走 _scaled_rect
        ...
```

render 函数（`add_text_box` / `add_shape_box` 等）检查 `_adjusted_rect`：

```python
def add_text_box(slide, rec):
    r = rec.get("_adjusted_rect") or _scaled_rect(rec["rect"]...)
    x, y, w, h = px_to_emu(r[0]), px_to_emu(r[1]), px_to_emu(r[2]), px_to_emu(r[3])
    ...
```

## ReAct Tools

### `get_slide_elements()`

无参数。返回当前 slide 所有元素的结构化列表，格式见上方"输入"部分。

### `check_layout(adjustments: dict)`

接收 agent 输出的 adjustments `{id: {x, y, w, h}}`，返回：

```json
{
  "overflow_count": 2,
  "overflow_elements": ["元素4右边界超出幻灯片"],
  "overlap_count": 0,
  "overlap_pairs": [],
  "score": 85
}
```

检测逻辑：
- 遍历所有元素，检查 rect 是否在 `[0,1920]×[0,1080]` 内
- 两两检测是否有重叠（AABB 相交检测）
- score = 100 - overflow×10 - overlap×5

Agent 可根据此反馈迭代调整。

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `slideforge/agents/layout_agent.py` | **新增** | LayoutAgent：Pydantic model + create + run |
| `slideforge/pptx_engine/assemble.py` | **修改** | 集成 Agent 到 assemble_slide |

## 模型 & 配置

- 沿用现有 `ChatOpenAI` 配置（proxy / api_key 等从项目环境变量继承）
- 模型：gpt-4o（准确度高，适合空间推理）
- temperature: 0（布局调整需要确定性）
- 超时：每个 slide 最多 30 秒

## Fallback

Agent 在以下情况自动降级到 `_scaled_rect`：

- LLM 调用返回空或非法 JSON
- 连续 2 次 `check_layout` score 无提升
- 总耗时超过 30 秒
- LLM 调用异常（网络错误 / API 限流）

降级时在控制台输出 `[layout_agent] fallback to _scaled_rect for slide N`。

## 注意事项

1. **token 控制**：每个元素的数据压缩到 1 行，31 个元素约 1000-1500 token
2. **文本截断**：元素文本只取前 40 字符用于理解布局角色
3. **deco_snapshot 全屏元素**：跳过调整（保持全屏覆盖）
4. **输出一致性**：未在 adjustments 中出现的元素保持 `init` 位置

## 未来扩展

- 缓存同一 HTML 的调整结果，避免重复 LLM 调用
- 支持用户通过 prompt 自定义布局偏好（"标题靠左"、"间距再大些"等）
- 多 Agent 协作：Layout Agent + Style Agent 联合调整
