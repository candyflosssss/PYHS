# 变更：装备窗口防止 Enter/Return 键意外关闭

日期：2025-09-05 24:00

## 修改摘要
- 在 `EquipmentDialog` 中覆盖 `keyPressEvent`：只有当焦点在 `QDialogButtonBox`（OK/Cancel）或其子按钮上时，才允许 Enter/Return 触发对话框关闭。
- 对左侧“卸下”按钮与右侧物品按钮已设置 `setAutoDefault(False) / setDefault(False) / setFocusPolicy(NoFocus)`，本次为进一步防抖，避免键盘回车导致误关闭。

## 影响范围
- 仅影响 PyQt6 装备窗口的键盘行为；鼠标交互不变。

## 风险与回滚
- 风险：极少数情况下用户希望用回车选择物品时被忽略。回车仍在 OK/Cancel 区域可用。
- 回滚方法：移除 `EquipmentDialog.keyPressEvent` 中的 Enter/Return 拦截逻辑即可。

## 相关文档/测试
- 已更新本变更记录。
- 手动测试建议：
  - 打开装备窗口，点击左侧“卸下”，按回车，窗口不应关闭。
  - 焦点在 OK 上时按回车，窗口应关闭且返回 Accepted。