# 2025-09-05 设备选择对话框（PyQt）+ 武器防御读取修复

## 修改摘要
- 新增 `src/ui/pyqt/dialogs/equipment_dialog.py`：实现 PyQt 版装备选择对话框。
  - 左侧显示当前三槽（左手/盔甲/右手）概览；右侧展示背包中过滤后的可装备物品网格；悬浮显示完整属性/技能/描述；双手武器自动屏蔽右手。
  - 返回 inventory 的 1-based 索引，卡片在确认后调用背包 `use_item` 完成装备并刷新。
- 调整 `src/ui/pyqt/widgets/card.py`：装备按钮点击不再直接卸载，改为打开对话框并通过 `Inventory.use_item` 装备。
- 修复装备属性读取：`src/systems/equipment_system.py` 的 `WeaponItem` 新增 `defense` 字段与 `__str__` 展示，解决如“命运之杖”既有攻又有防时防御未读取的问题。

## 影响范围
- PyQt UI：角色卡装备交互、装备提示信息与选择流程。
- 系统：武器同时具有防御值时的显示与总防计算（`EquipmentSystem.get_total_defense` 已覆盖）。

## 风险与回滚
- 风险：
  - app_ctx.controller.game.player 结构若与当前假定不一致，对话框将无法列出背包物品（已做 try/except 保护）。
  - Index（1-based）映射依赖当前 `Inventory.slots`，若后续更改为稀疏结构需同步适配。
- 回滚方法：
  - 将 `card.py` 中 `_slot_click` 恢复为调用 `app_ctx._slot_click(index1, slot_key, item)` 的旧逻辑。
  - 用 git 回退本次提交或仅删除 `dialogs/equipment_dialog.py` 并恢复导入。

## 相关文档/测试
- 文档：本变更记录；稍后将扩充 `docs/README.pyqt.md` 与 `CONTRIBUTING.md` 的使用说明与扩展指南。
- 测试：
  - 现有 `scripts/qt_equipment_bar_sanity.py` 可用于基本 UI 状态校验；
  - 后续建议新增集成测试：模拟 inventory 含若干武器/盔甲/盾牌，验证过滤、双手屏蔽与 `use_item` 装备路径。
