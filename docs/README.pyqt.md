### PyQt 界面运行与迁移说明

本说明基于 `docs/ui_spec.md` 的规格，指导如何运行与扩展 PyQt 骨架界面。

## 运行
- 依赖：仅支持 `PyQt6`（已移除对 `PyQt5` 的回退）
- 启动：
  - 命令行进入项目根目录后运行：
    ```bash
    python qt_main.py
    ```
  - 可传参：在 `run_qt(player_name, initial_scene)` 中设置默认玩家与初始场景
  - 工具链：资源/界面编译请使用 `pyuic6`/`pyrcc6`

## 目录结构
- `src/ui/pyqt/`
  - `app.py`：应用上下文（控制器桥接、命令 `_send`、选择状态与高亮参数）
  - `main_window.py`：主窗口搭建，包含顶栏/战场区/资源与背包/操作行/日志
  - `qt_compat.py`：Qt 兼容层（统一从此处导入 QtWidgets/QtCore/QtGui）
  - `views/`
    - `battlefield_view.py`：伙伴/敌人三列网格展示与点击选择
    - `resources_view.py`：资源按钮与背包刷新
    - `operations_view.py`：返回/结束回合操作行
  - `widgets/log_pane.py`：日志面板
  - `dialogs/equipment_dialog.py`：装备选择对话框（左三槽预览 + 右侧网格过滤 + 悬浮属性提示），由卡片装备按钮触发。
    - 对话框会根据物品 `rarity` 字段为框体描边着色（common/uncommon/rare/epic/legendary），稀有度来自场景 JSON 或内部构造参数。

## 与现有逻辑的对齐
- 控制器：沿用 `SimplePvEController`，通过 `GameQtApp._send(cmd)` 兼容既有命令映射
- 数据源：`game.player.board`（伙伴）与 `game.enemies`（敌人），刷新时一次性拉取
- UI 尺寸与高亮：遵循 `docs/ui_spec.md`；`CARD_W/H`、高亮色在 `GameQtApp` 中可配置

## 下一步（建议）
- 接入事件总线：把 Tk 视图中的订阅事件迁移为 Qt 信号/事件桥接，做增量刷新与动画
- 操作弹窗仅保留“攻击/技能/目标/确定/取消”，装备操作统一通过角色卡装备栏弹出的对话框完成
- 把日志结构化彩色显示迁移到 Qt（可用富文本/自定义渲染）
- 引入样式主题（QSS）与深色模式切换

## 兼容性说明（Qt5 → Qt6）
- PyQt6 中枚举/Flags 需从具体作用域引用，如 `QtCore.Qt.AlignmentFlag.AlignLeft`。
- 按钮枚举位于 `QDialogButtonBox.StandardButton`，兼容层已统一：`DBOX_OK/DBOX_CANCEL/...`。
- 事件签名与多媒体/渲染模块在 Qt6 有调整，建议通过 `qt_compat` 间接引用 Qt API。


