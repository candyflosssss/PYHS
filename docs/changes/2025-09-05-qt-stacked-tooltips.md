# 变更记录：PyQt 自定义堆叠悬浮框（TooltipManager）

- 时间：2025-09-05
- 主题：替换基于 QToolTip 的单条提示为“自定义堆叠气泡 + 管理器”，支持在卡片边缘按段落堆叠展示，并根据盟友/敌人选择左/右侧。

## 修改摘要
- 新增 `src/ui/pyqt/widgets/tooltip.py`：
  - TooltipBubble：无边框 ToolTip 风格气泡，支持标题/正文、自动换行、最大宽度限制。
  - TooltipManager：窗口级管理器，支持多段气泡堆叠、屏幕边界约束、简单节流、延迟隐藏。
- 重写 `src/ui/pyqt/widgets/card.py` 悬浮逻辑：
  - 在 `eventFilter` 中组装段落：
    - 基础段：角色信息（名称/ATK/AC/HP/属性/装备清单）。
    - 额外段：当悬浮 ATK 显示“攻击力来源”；悬浮各装备槽显示对应装备详情。
  - 侧边：盟友卡片在左侧堆叠，敌人卡片在右侧堆叠；支持 `offset` 调整位置。
  - 离开时采用 `hide_grace_ms` 延迟隐藏，避免跨卡或在子控件间移动时闪烁。
- 补充设置项（`src/settings.py`）：
  - `ui.tk.tooltip.stack_spacing`（默认 6）：堆叠气泡的间距。
  - `ui.tk.tooltip.max_width`（默认 280）：每个气泡的最大宽度。

## 影响范围
- 仅影响 PyQt 前端的角色卡悬浮提示展示方式；
- 不修改核心规则与 Tk 前端；
- 装备栏交互与双手武器逻辑保持不变。

## 风险与回滚
- 风险：
  - 可能因屏幕缩放/多显示器导致位置计算与边界约束出现偏差；
  - 过窄的 `max_width` 可能造成频繁换行；过大的值可能导致遮挡。
- 回滚方法：
  - 将 `card.py` 的 `eventFilter` 中的 TooltipManager 分支替换回旧的 QToolTip 分支（保留在历史提交中）；
  - 或在用户配置中调大 `hide_grace_ms`、调整 `offset/stack_spacing/max_width` 以缓解体验问题。

## 相关文档/测试
- 设置项文档已更新（`src/settings.py` 中注释）。
- 建议在 `configs/user_config.json` 中覆盖 `ui.tk.tooltip` 相关键以微调对齐与宽度。
- 后续可补充 UI 回归脚本：模拟多控件 enter/leave 序列，验证延迟隐藏与节流不抖动。
