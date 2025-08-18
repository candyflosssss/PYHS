# COMOS - PvE 合作卡牌游戏

🎮 **项目状态**: ✅ 精简为纯PvE合作模式，模块化架构

## 📁 项目文件结构 (PvE专用)

### 📂 **core/** - 核心游戏组件
- `player.py` - PvE玩家类，包含背包系统和简化战斗
- `cards.py` - 卡牌系统和各种卡牌类型

### 📂 **systems/** - 系统模块  
- `equipment_system.py` - 装备系统（武器/防具/盾牌）
- `inventory.py` - 背包和物品系统

### 📂 **game_modes/** - PvE游戏模式
- `pve_multiplayer_game.py` - PvE游戏核心架构
- `pve_controller.py` - PvE游戏控制器
- `pve_content_factory.py` - PvE内容工厂(敌人/资源/Boss)

### 📂 **ui/** - 用户界面
- `game_display.py` - 游戏界面显示系统
# COMOS - PvE 合作卡牌（简明版）

面向命令行与 Textual 的轻量级 PvE 合作卡牌原型，支持场景包、装备/背包与基础随从战斗。

## 快速开始

- 运行命令行版：在 `yyy/` 目录下执行 `python main.py`
- 运行 Textual UI：`python textual_main.py`（需安装 textual 与 rich）
- Windows 可双击 `start_game.bat`

最低环境：Python 3.10+（纯标准库；Textual UI 需额外安装 textual>=0.58）

## 目录一览

- `core/`：基础模型（`cards.py` 随从/效果，`player.py` 玩家与战场）
- `systems/`：系统能力（`inventory.py` 背包物品，`equipment_system.py` 装备槽/加成，`skills.py` 标签/被动/技能判定）
- `game_modes/`：运行时逻辑（`simple_pve_game.py` 场景版 PvE，`pve_controller.py` CLI 控制器，`entities.py` 与 `pve_content_factory.py` 内容工厂）
- `ui/`：界面与配色（`colors.py` ANSI 主题，`textual_app.py` Textual 外壳）
- `scenes/`：场景与关卡包（`default_scene.json` 及子包 `adventure_pack/`、`dungeon_pack/`）
- `tools/`：工具脚本（`gen_scene_graph.py` 生成场景拓扑图 `scene_graph.html`）

## 场景 JSON 速览

基础字段（示例见 `scenes/default_scene.json` 与各包文件）：
- `title|name`：场景标题
- `parent|back_to`：返回上级场景（用于导航）
- `on_clear`: { action: "transition", to: "xxx.json", preserve_board: true }
- `board`: 我方初始随从数组，元素可为 { atk, hp, name?, tags?, passive?, skills?, equip? }
- `enemies`: 敌人数组，可为字符串名称或 { name, hp, attack, drops?, on_death? }
- `resources`: 资源数组，可为字符串或 { name, type: weapon|armor|shield|potion|material, value }

装备初始化（board.equip）支持：
- 列表或对象形式，字段：type, name, attack/defense, slot(left_hand|right_hand|armor), two_handed, desc

## 常用命令（CLI 与 Textual 共用）

- `s [0-5]` 查看区块；`h` 帮助；`q` 退出
- `p <手牌序号> [目标]` 出牌；`a <mN> e<编号>` 攻击敌人
- `i|inv` 背包；`take <rN|编号>` 拾取资源
- `use <物品名> [mN]` 使用/装备；`equip <物品名|iN> mN` 装备到目标
- `unequip mN <left|right|armor>` 卸下；`moveeq mA <slot> mB` 移动装备
- `c|craft [list|索引|名称]` 合成；`back|b` 返回上级；`end` 结束回合

## 设计要点

- 装备三槽位：left_hand / right_hand / armor；双手武器占用左手并清空右手
- 攻击与防御：随从 attack = base_atk + 装备加成；伤害至少为 1
- 技能/被动：通过 `tags/passive/skills` 元数据判定（见 `systems/skills.py`）
- 场景驱动：清场或敌人 on_death 可触发场景跳转；支持保留随从

更多细节请见各目录下的 README。
### 卡牌系统
