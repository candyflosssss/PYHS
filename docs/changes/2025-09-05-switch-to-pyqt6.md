# 变更记录：切换到 PyQt6 优先

- 修改摘要：
  - `src/ui/pyqt/qt_compat.py` 改为仅导入 PyQt6，完全移除 PyQt5 回退。
  - `qt_main.py` 移除直接导入 PyQt5 的回退，统一从 `qt_compat` 导入。
  - `docs/README.pyqt.md` 更新运行与兼容说明，标注 `pyuic6/pyrcc6` 工具与 Qt6 枚举差异。

- 影响范围：
  - 所有通过 `qt_compat` 导入 Qt 的 PyQt 界面模块。
  - 启动入口 `qt_main.py`。

- 风险与回滚方法：
  - 风险：若环境未安装 `PyQt6`，应用将无法启动。
  - 回滚：仅能通过安装 `PyQt6` 或基于历史提交恢复至支持 PyQt5 的版本（本次提交已移除该路径）。

- 相关文档/测试：
  - 已更新 `docs/README.pyqt.md`。
  - 可运行 `scripts/qt_ui_smoke_test.py` 做无头冒烟验证。
