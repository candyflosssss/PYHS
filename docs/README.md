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
面向命令行与 Tkinter GUI 的轻量级 PvE 合作卡牌原型，支持场景包、装备/背包与基础随从战斗。

## 快速开始

- 运行命令行版：在 `yyy/` 目录下执行 `python main.py`
- `core/`：基础模型（`cards.py` 随从/效果，`player.py` 玩家与战场）
- `systems/`：系统能力（`inventory.py` 背包物品，`equipment_system.py` 装备槽/加成，`skills.py` 标签/被动/技能判定）
- `game_modes/`：运行时逻辑（`simple_pve_game.py` 场景版 PvE，`pve_controller.py` CLI 控制器，`entities.py` 与 `pve_content_factory.py` 内容工厂）
- `ui/`：界面与配色（`colors.py` ANSI 主题；Tkinter GUI 实现在 `ui/tkinter`）
基础字段（示例见 `scenes/default_scene.json` 与各包文件）：
- `title|name`：场景标题
- `on_clear`: { action: "transition", to: "xxx.json", preserve_board: true }
- `board`: 我方初始随从数组，元素可为 { atk, hp, name?, tags?, passive?, skills?, equip? }
- `enemies`: 敌人数组，可为字符串名称或 { name, hp, attack, drops?, on_death? }

- `s [0-5]` 查看区块；`h` 帮助；`q` 退出
- `p <手牌序号> [目标]` 出牌；`a <mN> e<编号>` 攻击敌人

## 设计要点

- 装备三槽位：left_hand / right_hand / armor；双手武器占用左手并清空右手
- 攻击与防御：随从 attack = base_atk + 装备加成；伤害至少为 1
- 技能/被动：通过 `tags/passive/skills` 元数据判定（见 `systems/skills.py`）

更多细节请见各目录下的 README。
## 打包与配置

- 打包脚本：`yyy/build_exe.bat` 会生成：
	- CLI：`yyy/dist/COMOS-CLI.exe`
	- GUI：`yyy/dist/COMOS-GUI.exe`
	- 源码运行：`yyy/user_config.json`
	- 打包运行：`%LOCALAPPDATA%\PYHS\user_config.json`

## 展示场景（Showcase）

- 新增 `scenes/test_showcase.json`，涵盖：多职业随从（含初始装备）、常见敌人（掉落装备/材料）、资源区多类型（药水/材料/装备）、清场后跳转回默认场景。
- 在 Tk GUI 主菜单：选择地图组“基础”，选主地图 `test_showcase.json` 启动即可。
