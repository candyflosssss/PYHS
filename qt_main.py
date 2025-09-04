from __future__ import annotations

from typing import Optional

try:
    from src.ui.pyqt.qt_compat import QtWidgets  # type: ignore
except Exception:  # pragma: no cover
    from PyQt5 import QtWidgets  # type: ignore

from src.ui.pyqt.app import GameQtApp
from src.ui.pyqt.menu_window import MenuWindow


def run_qt(player_name: str = "玩家", initial_scene: Optional[str] = None) -> None:
    ctx = GameQtApp(player_name=player_name, initial_scene=initial_scene)
    menu = MenuWindow(ctx)
    menu.show()
    # PyQt5 has exec_(), PyQt6 uses exec()
    if hasattr(ctx.app, 'exec_'):
        ctx.app.exec_()
    else:
        ctx.app.exec()


if __name__ == '__main__':
    run_qt()


