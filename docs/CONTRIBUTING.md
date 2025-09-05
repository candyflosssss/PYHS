# 贡献指南（片段）

本项目采用分层结构：core（核心逻辑）、systems（系统）、ui（界面）、scenes（数据）、docs（文档）。新增或修改功能需同步完善文档与变更记录。

## 新增装备/校验 PyQt 装备对话框
- 在 `src/systems/equipment_system.py` 中定义装备类型（武器/盔甲/盾牌）。武器可同时具备攻击与防御：`WeaponItem(name, ..., attack=, defense=, slot_type=, is_two_handed=)`。
- 玩家背包位于 `player.inventory.slots`。对话框将过滤掉不适合当前槽位的物品（如右手在左手双手武器时不可用）。
- 在 PyQt 界面中，点击卡片右侧装备按钮会弹出 `EquipmentDialog`，选择后由 `Inventory.use_item(name, player=, target=成员)` 完成装备。

## 变更记录
- 每次提交请在 `docs/changes/` 创建 `YYYY-MM-DD-HH-title.md`，包含：修改摘要、影响范围、风险与回滚、相关文档/测试。
