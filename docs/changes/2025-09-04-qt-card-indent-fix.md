# 2025-09-04 Qt CardWidget indentation fix and stamina/HP parity

## 修改摘要
- 修复 `src/ui/pyqt/widgets/card.py` 中 `__init__` 的缩进错误（由体力/血量区块合并时引入）。
- 将 Qt 体力显示对齐 Tk 语义：独立背景行容器、胶囊颗粒（开/关色）、0 间距、8x16 圆角形态；HP 采用灰底+绿色进度，统一视觉。

## 影响范围
- PyQt 角色卡 `CardWidget` 的初始化与布局。
- 体力/血量的视觉一致性与刷新逻辑（行为不变，仅视觉统一）。

## 风险与回滚方法
- 风险：若仍有缩进/样式问题，会导致 PyQt 导入失败或界面错位。
- 回滚：将 `src/ui/pyqt/widgets/card.py` 回退到上一个可工作版本，或移除此提交并恢复旧渲染逻辑。

## 相关文档/测试
- 已更新：本变更记录。
- 已新增：`tests/test_pyqt_card_import_smoke.py`（导入级冒烟，防回归到语法/缩进错误）。
- 说明：如需完整 UI 冒烟，可运行 `scripts/qt_ui_smoke_test.py`。
