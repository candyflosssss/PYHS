# systems 模块

提供与内容无关的系统能力：背包、装备与技能判定。

- `inventory.py`：
  - Item/ItemStack/Inventory 三件套；支持堆叠、拆分、排序、显示。
  - `use_item(name, amount, player, target)`：
    - 消耗品：带 `effect(player, target)` 回调。
    - 装备：需 `target.equipment`，成功后从背包移除。
- `equipment_system.py`：
  - 槽位：`left_hand`/`right_hand`/`armor`；双手武器占用左手并清空右手。
  - 属性：累加 `attack/defense`；提供 `__str__` 摘要与统一日志通道。
  - `equip(item, game=None)` 会将被替换装备尝试退回玩家背包（若可获取到 `game.player`）。
- `skills.py`：
  - 轻量判定：`has_tag`、`get_passive`、`is_healer`、`get_heal_amount`、`should_counter`。
  - 面向 UGC：基于随从的 `tags/passive/skills` 字段做语义判定。

与其它模块的关系：
- 被 `core.cards` 与 `core.player` 引用。
- `game_modes.pve_controller` 通过 `player.inventory` 实现交互命令。
