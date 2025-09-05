# 变更：物品稀有度支持 + 双手占用时右手显示优化 + 移除操作弹窗中的装备区

日期：2025-09-05

## 修改摘要
- 在物品父类 `Item` 与 `EquipmentItem` 增加 `rarity` 字段，默认 `common`，供 UI 着色与排序使用。
- 为 `WeaponItem`/`ArmorItem`/`ShieldItem` 构造函数新增 `rarity` 透传参数，并在场景 JSON 解析中读取 `rarity`。
- `CardWidget`：当左手为双手武器时，右手按钮禁用但仍显示原右手装备名称，且保留悬浮信息并追加“被占用”说明。
- `OperationsPopup`：移除了“装备”分组（装备弹窗与卸下入口），统一由角色卡装备栏与装备对话框处理装备装卸。

## 影响范围
- 数据：`src/systems/inventory.py`、`src/systems/equipment_system.py` 的类构造签名；`src/game_modes/simple_pve_game.py` 的 JSON 解析。
- UI：`src/ui/pyqt/widgets/card.py`（右手显示逻辑）、`src/ui/pyqt/views/operations_popup.py`（删除装备区）。

## 风险与回滚
- 风险：外部代码若直接实例化 `EquipmentItem` 及其子类需关注新增关键字参数 `rarity`（为可选，默认 `common`，兼容旧用法）。
- 回滚：
  1. 将 `Item/EquipmentItem` 去除 `rarity` 字段；
  2. 恢复 `WeaponItem/ArmorItem/ShieldItem` 构造函数不带 `rarity`；
  3. 将 `simple_pve_game.py` 中对 `rarity` 的解析删除；
  4. 恢复 `operations_popup.py` 中的装备分组。

## 相关文档/测试
- 文档：后续将在 `README.pyqt.md` 中补充“稀有度配色来源与可配置方式”。
- 测试：建议补充装备对话框颜色渲染的快照测试与 JSON 解析单元测试；本次已通过快速冒烟脚本手工验证。
