# 变更记录：还原角色卡悬浮窗为系统 ToolTip（移除堆叠管理器）

日期：2025-09-05
作者：自动化代理（GitHub Copilot）

修改摘要：
- 回退 PyQt 角色卡（CardWidget）的悬浮行为到「系统自带 QToolTip」：
  - 取消 `TooltipManager.show_stacked_for_card` 的使用与相关隐藏定时器。
  - 不再在 `eventFilter` 中处理 Enter/Leave/Hover/ToolTip，交给 Qt 默认逻辑。
  - 在 `refresh()` 中为按钮/HP/ATK/整卡设置静态 ToolTip 文本。
- 目的：按“还原角色卡的悬浮窗”需求恢复为单框提示，降低复杂度，避免堆叠与跨控件守卫引入的抖动问题。

影响范围：
- 文件：`src/ui/pyqt/widgets/card.py`（删除自定义堆叠气泡逻辑与隐藏定时器）。
- 仅影响 PyQt 前端卡片的悬浮提示显示方式；不影响核心逻辑与 Tk 版。

风险与回滚方法：
- 风险：系统 QToolTip 在部分平台上可能仍存在跨控件移动易隐藏的问题。
- 回滚：若需要再次启用堆叠气泡，只需恢复 `card.py` 中的 `eventFilter` 悬浮分支并调用 `widgets/tooltip.py` 的 `TooltipManager`。

相关文档/测试：
- 保持 `settings.py` 中 `ui.tk.tooltip.*` 配置不变（此回退未读取 `offset/stack_spacing/max_width`）。
- 建议手动验证：运行 PyQt 入口，将鼠标悬停在卡片与装备按钮上，确认系统 ToolTip 正常显示/隐藏。

操作指南（简要）：
- 若需重新使用自定义堆叠气泡：
  - 在 `CardWidget.eventFilter` 中恢复 Enter/Hover/ToolTip 的处理，并调用 `widgets/tooltip.get_manager(window).show_stacked_for_card(...)`。
