# ui 模块

UI 说明：

- `colors.py`：
  - ANSI 主题（default/mono/high-contrast），尊重 `NO_COLOR`；提供 `heading/friendly/enemy/resource` 等语义着色。
  - `strip()` 去除 ANSI，便于日志纯文本化。

Tkinter GUI：

- 主 GUI 实现在 `ui/tkinter`，包含紧凑的角色卡、资源竖列、底部并排的信息/日志区以及操作栏。

提示：默认 GUI 使用标准库中的 Tkinter；无需额外依赖。
