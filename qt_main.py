from __future__ import annotations

from typing import Optional

from src.ui.pyqt.qt_compat import QtWidgets  # type: ignore

from src.ui.pyqt.app import GameQtApp
from src.ui.pyqt.menu_window import MenuWindow


def run_qt(player_name: str = "玩家", initial_scene: Optional[str] = None) -> None:
    ctx = GameQtApp(player_name=player_name, initial_scene=initial_scene)
    menu = MenuWindow(ctx)
    menu.show()
    # 仅 PyQt6：事件循环使用 exec()
    ctx.app.exec()


if __name__ == '__main__':
    run_qt()


