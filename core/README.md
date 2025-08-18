# core 模块

基础模型与战斗单元。

- `cards.py`：
  - Card 基类，包含基础攻击/生命、装备系统、日志辅助。
  - 扩展卡牌：抽牌、风怒、战吼、亡语、组合等；支持 `info()` 与 `on_play()`/`on_death()`
  - UGC 扩展字段：`tags`、`passive`、`skills`，用于技能/被动判定。
- `player.py`：
  - 玩家对象：手牌、战场、生命值、与 `Inventory` 集成。
  - 行为：抽牌、出牌（统一回调到 `on_play`）、攻击、治疗、死亡清理。
  - 统计：总攻/总防 计算包含装备加成。

与其它模块的关系：
- 依赖 `systems.equipment_system`（随从装备）、`systems.inventory`（玩家背包）。
- 被 `game_modes.simple_pve_game` 作为运行时容器使用。

常见扩展位：
- 新增卡牌类时复用 `_log(game, text)`，以统一输出。
- 自定义随从名称：设置 `display_name`。
