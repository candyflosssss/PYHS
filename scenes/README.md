# scenes 目录

存放基础场景与场景包。

- 根目录场景：`default_scene.json`、`scene_2.json` 等
- 包目录：`adventure_pack/`、`dungeon_pack/`，各含 `pack.json` 与多个场景
- 产物：`scene_graph.html`（由 `tools/gen_scene_graph.py` 生成）

常用字段：
- `title|name`：展示标题
- `parent|back_to`：返回上级场景（导航）
- `on_clear`: { action: "transition", to: "xxx.json", preserve_board: true }
- `board[]`：我方随从（可含 `equip` 初始装备配置）
- `enemies[]`：敌人（可含 `drops`、`on_death` 跳转）
- `resources[]`：可拾取资源（weapon/armor/shield/potion/material）

约定：相对路径优先在当前包目录解析；否则退回 `scenes/` 根解析。
