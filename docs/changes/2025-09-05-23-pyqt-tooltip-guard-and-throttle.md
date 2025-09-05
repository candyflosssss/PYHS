# 变更记录：PyQt 悬浮框稳定性（全局隐藏保护 + 节流 + 范围限制）

日期：2025-09-05 23:00
作者：自动化代理（GitHub Copilot）

修改摘要：
- 修复并强化 `CardWidget` 悬浮框逻辑：
  - 仅对“卡片框架 + 三个装备按钮”安装 `eventFilter` 与 Hover 跟踪，避免子控件频繁触发导致闪动。
  - 引入“全局隐藏计时器 + 代次守卫”（_TT_TIMER/_TT_GEN/_TT_HIDE_GEN）：上一张卡启动的隐藏不再影响下一张卡的显示。
  - 支持配置 `ui.tk.tooltip.scope = container` 时，以窗口为 owner 并将可见区域限制为整个窗口矩形，跨卡移动时不提前隐藏。
  - 新增轻量节流：对相同目标/文本、极小位移且时间间隔很短的重复显示请求直接忽略，减少闪烁。
  - 修复此前编辑导致的 `card.py` 语法/缩进错误，恢复可运行状态。

影响范围：
- 文件：`src/ui/pyqt/widgets/card.py`、`src/settings.py`（读取配置）。
- 仅影响 PyQt 悬浮框的显示稳定性。

风险与回滚方法：
- 风险：特定平台/主题下 Qt 的 tooltip 行为差异可能导致边界情况。
- 回滚：撤销 `card.py` 中 `eventFilter` 悬浮相关分支的本次改动，恢复到前一版（无节流/无全局守卫）。

相关文档/测试：
- 已在 `settings.py` 默认配置中记录 `tooltip.scope` 与 `tooltip.hide_grace_ms`。 
- 建议手动验证：在两张卡与装备按钮之间快速移动鼠标，观察 tooltip 是否不再提前消失且无明显闪动。

操作指南（简要）：
- 可在用户配置 JSON 中调整：
```json
{
  "ui": { "tk": { "tooltip": {
    "scope": "container",         // container | card
    "hide_grace_ms": 150,          // 鼠标离开后的隐藏宽限
    "anchor": "top_right",
    "offset": [8, 0],
    "duration_ms": 8000,
    "constrain_to_card": true
  }}}
}
```
