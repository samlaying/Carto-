# LLM 驱动的 Windows 虚拟机点击 Agent 设计（方案三）

## 1. 目标

实现一个可自动探索 Windows 虚拟机 UI 的 Agent：

1. 获取当前屏幕截图。
2. 把截图和运行时状态发送给 LLM。
3. 让 LLM 返回页面语义、下一步动作、是否完成当前路径。
4. 执行动作并循环。
5. 最终生成结构化功能地图与可复现步骤。

---

## 2. 总体架构

```text
┌──────────────────────────────────────────────────────────┐
│                     Orchestrator                         │
│          (循环控制、去重、终止、文档输出)               │
└──────────────────────────────────────────────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ Screenshot Layer │   │  LLM Planner     │   │ Action Executor  │
│ - ADB/scrcpy/RDP │   │ - 页面理解        │   │ - click/drag/back│
│ - 截图压缩与标注  │   │ - 下一步动作规划  │   │ - 等待/重试/校验  │
└──────────────────┘   └──────────────────┘   └──────────────────┘
            │                    │                    │
            └──────────► State Store / Graph ◄────────┘
                           - 页面签名
                           - 已访问路径
                           - 动作结果
```

---

## 3. 核心数据模型

### 3.1 页面状态（PageState）

- `screen_id`: 截图哈希（感知哈希 + OCR 文本哈希）
- `window_title`: 当前窗口标题（可选）
- `ocr_texts`: 识别出的关键文本
- `detected_controls`: 可点击控件列表（文本、类型、bbox）
- `breadcrumbs`: 当前路径（例如：`设置 > 网络 > 代理`）

### 3.2 动作（Action）

- `type`: `click | double_click | right_click | drag | scroll | hotkey | back | wait`
- `target`: `point` 或 `bbox` 或 `text`
- `confidence`: 0~1
- `reason`: 为什么执行这一步

### 3.3 探索图（ExplorationGraph）

- `nodes`: 页面节点（PageState 指纹）
- `edges`: 动作迁移（Action + before/after）
- `status`: `unexplored | exploring | done | dead_end`

---

## 4. Agent Loop（推荐实现）

1. **采集截图**
   - 从虚拟机窗口抓图（优先无损、固定分辨率）。
2. **状态构建**
   - OCR + 简单 UI 检测（按钮、菜单、输入框）。
   - 生成页面签名，检查是否重复。
3. **LLM 规划**
   - 输入：截图 + 上下文 + 已访问动作。
   - 输出：页面描述、下一动作、是否当前路径完成。
4. **动作执行**
   - 执行鼠标/键盘事件。
   - 执行后等待 UI 稳定（例如 600~1500ms + diff check）。
5. **结果评估**
   - 页面是否变化。
   - 动作是否成功，是否进入新节点。
6. **循环与终止**
   - 当无可用动作或到达预算上限即回溯。
   - 全图完成后输出文档。

---

## 5. LLM 输出 JSON Schema（强约束）

```json
{
  "page": {
    "module": "string",
    "feature": "string",
    "summary": "string"
  },
  "action": {
    "type": "click|double_click|right_click|drag|scroll|hotkey|back|wait",
    "x": 0,
    "y": 0,
    "x2": 0,
    "y2": 0,
    "text": "optional",
    "keys": ["optional"],
    "duration_ms": 300,
    "reason": "string"
  },
  "path_status": {
    "is_current_path_done": false,
    "need_backtrack": false
  },
  "confidence": 0.0
}
```

建议：使用结构化输出（JSON mode / tool calling），避免自然语言歧义。

---

## 6. Prompt 策略

### System Prompt（关键约束）

- 你是 Windows GUI 自动化探索 Agent。
- 目标是“覆盖路径”而非“完成业务”。
- 同一页面不要重复点击同一控件。
- 优先探索未访问控件，若无则返回上级。
- 不能确定时先选择低风险动作（空白区域单击、滚动、返回）。

### User Prompt（每轮注入）

- 当前截图。
- 最近 N 步动作与结果。
- 已探索控件列表（文本或坐标哈希）。
- 当前深度、回溯次数、预算剩余。

---

## 7. 关键工程点

1. **去重机制**
   - 页面签名 + 可点击元素签名，避免死循环。
2. **回溯策略**
   - DFS + 启发式：优先未访问高置信控件。
3. **容错**
   - 动作失败重试最多 2 次。
   - 识别“加载中”状态，自动等待。
4. **安全保护**
   - 黑名单区域（删除/格式化/关机按钮）。
   - 高风险动作需二次确认策略。
5. **可观测性**
   - 每轮日志：截图、prompt、模型输出、执行结果。

---

## 8. 输出文档格式（最终产物）

- `site_map.json`
  - 模块树、页面节点、动作边。
- `journeys.md`
  - 每个模块的可复现路径（步骤 + 截图编号）。
- `coverage_report.md`
  - 页面数、动作数、死链、失败点、未覆盖估计。

---

## 9. MVP 里程碑

### M1（1~2 天）

- 打通截图 -> LLM -> 点击单步闭环。
- 实现基础日志与 JSON 输出校验。

### M2（3~5 天）

- 引入页面去重、回溯、探索图。
- 能稳定跑完一个设置模块。

### M3（1~2 周）

- 增加 OCR/控件检测融合。
- 输出完整结构化文档与覆盖率报告。

---

## 10. 技术栈建议

- 自动化执行：`pyautogui` / `playwright + remote desktop` / WinAppDriver（视环境）。
- 视觉识别：`easyocr` 或系统 OCR。
- 存储：`sqlite` + 本地文件日志。
- 编排：Python 异步循环（可选）。

> 若你当前真的是通过 ADB 控制 Android 虚拟机窗口，也可以沿用同一 loop，仅替换截图与输入执行层。
