# 变更记录：PyQt 卡片悬浮数据框（对齐 Tk 逻辑）

日期：2025-09-05

修改摘要：
- 为 `src/ui/pyqt/widgets/card.py` 增加卡片悬浮数据框：鼠标进入卡片时显示包含名称、攻击（基础+装备）、HP、AC、六维属性及装备清单的 tooltip；离开时隐藏。
- 逻辑参考了 Tk 版 `src/ui/tkinter/cards.py` 中的 `card_tip` 构造方式，并复用现有的 AC 计算函数。

影响范围：
- 影响 PyQt 卡片的悬浮行为；不更改业务逻辑，仅 UI 呈现增强。

风险与回滚方法：
- 风险：极端情况下 `model.dnd` 结构异常可能导致属性显示不完整（已 try/except 兜底）。
- 回滚：还原 `card.py` 中 `_build_card_tooltip` 与 `eventFilter` 的 Enter/Leave 分支改动即可。

相关文档/测试：
- 与 Tk 的行为保持一致，无需额外文档。
- 可在运行时将鼠标悬停到卡片上，观察 tooltip 是否显示预期信息。
