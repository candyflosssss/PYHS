# game_modes 模块

运行时控制与内容定义。

- `simple_pve_game.py`：
  - 基于场景 JSON 的最小 PvE 引擎：玩家/敌人/资源均由场景文件决定。
  - 支持 `parent/back_to` 返回、`on_clear` 清场跳转、敌人 `on_death` 跳转/掉落。
  - 装备初始化：`board[].equip` 字段支持 type/name/slot/attack/defense/two_handed。
- `pve_controller.py`：
  - 命令行控制器，复用游戏引擎并提供完整指令集（s/p/a/i/take/use/equip/unequip/moveeq/craft/back/end）。
  - 统一渲染：区块视图、历史/信息区与彩色统计。
- `entities.py`：`Enemy`、`ResourceItem`、`Boss` 的通用定义。
- `pve_content_factory.py`：敌人/资源/Boss 工厂，提供可复用的预设。

数据流：Controller -> Game(State 变更/日志) -> UI（终端/Tkinter）。
