# ui 模块

终端与 Textual 用户界面。

- `colors.py`：
  - ANSI 主题（default/mono/high-contrast），尊重 `NO_COLOR`；提供 `heading/friendly/enemy/resource` 等语义着色。
  - `strip()` 去除 ANSI，便于日志纯文本化。
- `textual_app.py`：
  - Textual 外壳，左-中-右 三栏布局 + 底部命令输入，直接调用控制器 `_process_command`。
  - 与 CLI 指令完全对齐，可点击按钮快速发出常用命令。

提示：Textual 不是必需依赖；仅在运行 `textual_main.py` 时需要。
