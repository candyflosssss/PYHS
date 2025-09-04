### PyQt 界面运行与迁移说明

本说明基于 `docs/ui_spec.md` 的规格，指导如何运行与扩展 PyQt 骨架界面。

## 运行
- 依赖：`PyQt5`
- 启动：
  - 命令行进入项目根目录后运行：
    ```bash
    python qt_main.py
    ```
  - 可传参：在 `run_qt(player_name, initial_scene)` 中设置默认玩家与初始场景

## 目录结构
- `src/ui/pyqt/`
  - `app.py`：应用上下文（控制器桥接、命令 `_send`、选择状态与高亮参数）
  - `main_window.py`：主窗口搭建，包含顶栏/战场区/资源与背包/操作行/日志
  - `views/`
    - `battlefield_view.py`：伙伴/敌人三列网格展示与点击选择
    - `resources_view.py`：资源按钮与背包刷新
    - `operations_view.py`：返回/结束回合操作行
  - `widgets/log_pane.py`：日志面板
  - `dialogs/equipment_dialog.py`：装备对话框占位（后续可对接装备逻辑）

## 与现有逻辑的对齐
- 控制器：沿用 `SimplePvEController`，通过 `GameQtApp._send(cmd)` 兼容既有命令映射
- 数据源：`game.player.board`（伙伴）与 `game.enemies`（敌人），刷新时一次性拉取
- UI 尺寸与高亮：遵循 `docs/ui_spec.md`；`CARD_W/H`、高亮色在 `GameQtApp` 中可配置

## 下一步（建议）
- 接入事件总线：把 Tk 视图中的订阅事件迁移为 Qt 信号/事件桥接，做增量刷新与动画
- 完成操作弹窗（技能/目标/确定/取消）与装备槽点击逻辑
- 把日志结构化彩色显示迁移到 Qt（可用富文本/自定义渲染）
- 引入样式主题（QSS）与深色模式切换


