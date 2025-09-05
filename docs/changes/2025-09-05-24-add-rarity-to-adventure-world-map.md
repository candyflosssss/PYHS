# 变更记录：为 adventure_pack/world_map.json 装备添加稀有度

日期：2025-09-05 24:00

## 修改摘要
- 为场景 `src/scenes/adventure_pack/world_map.json` 中的所有装备条目添加 `rarity` 字段（common/uncommon/rare/epic/legendary），以便 PyQt 装备窗口按设置着色显示。

## 影响范围
- 数据：仅影响该场景初始角色装备与初始背包物品的可视化描边颜色；不改变数值或规则。

## 风险与回滚
- 风险较低；UI 配色依赖 `settings.ui.tk.equipment.rarity_colors`。若用户未配置，将使用默认配色。
- 回滚：删除新增的 `"rarity":"..."` 键或恢复到修改前版本。

## 相关文档/测试
- 文档：参考 `docs/README.settings.md` 中“装备窗口（EquipmentDialog）”关于稀有度配色的说明。
- 测试：
  - 进入该场景，在 PyQt 装备窗口检查背包与已装备栏的描边颜色是否符合稀有度。
