# 变更：装备对话框点击不再自动关闭（需按“确定”）

日期：2025-09-05

## 修改摘要
- 调整 PyQt 装备对话框（`EquipmentDialog`）的交互：
  - 右侧物品点击仅“选中并高亮”，不再立即关闭窗口。
  - 左侧“卸下”按钮执行后不会关闭窗口，只刷新左侧槽位显示。
  - 只有按下“确定(Ok)”才会返回所选物品的 inventory 1-based 索引。

## 影响范围
- 文件：`src/ui/pyqt/dialogs/equipment_dialog.py`
- 相关 UI：角色卡装备栏点击打开的装备对话框。

## 风险与回滚方法
- 风险：调用方若依赖“点击即关闭”的旧行为，可能出现未选择即返回 None 的情况。
- 回滚：将 `EquipmentDialog._choose` 恢复为 `self.accept()` 行为；`_unequip` 中调用 `self.accept()` 即可回到旧逻辑。

## 相关文档/测试
- 更新本次变更记录。
- 交互说明将随后同步到 `docs/README.pyqt.md`（若需要更详细的使用指引）。
