from __future__ import annotations

import sys
import time

import os
ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(ROOT, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ui.pyqt.app import GameQtApp
from src.ui.pyqt.menu_window import MenuWindow


def log(msg: str):
    sys.stdout.write(msg + "\n"); sys.stdout.flush()


def run_sequence():
    ctx = GameQtApp(player_name="测试玩家", initial_scene=None)
    menu = MenuWindow(ctx)
    # menu.show()  # headless: don't need to show

    log("[1] Start game from menu")
    menu._menu_start()
    # Allow event loop to create window
    ctx.app.processEvents()

    # Find MainWindow
    from src.ui.pyqt.main_window import MainWindow
    main = getattr(ctx, '_last_main_window', None)
    if not isinstance(main, MainWindow):
        for w in list(ctx.app.topLevelWidgets()):
            if isinstance(w, MainWindow):
                main = w
                break
    assert main is not None, "MainWindow not found after start"

    # Render and ensure battlefield present
    log("[2] Refresh main and render battlefield")
    main.refresh_all(); ctx.app.processEvents()
    bf = main.battlefield
    assert bf is not None, "Battlefield missing"

    # Try click first ally to open popup
    log("[3] Click ally#1 to open operations popup")
    # Force render and fetch card map via protected field
    g = ctx.controller.game
    bf.render_from_game(g); ctx.app.processEvents()
    # If there is at least one ally
    has_ally = len(getattr(getattr(g, 'player', None), 'board', []) or []) > 0
    if has_ally and 1 in bf._ally_cards:  # type: ignore[attr-defined]
        bf._on_click(1, False, bf._ally_cards[1]); ctx.app.processEvents()  # type: ignore[attr-defined]

    # Begin attack from ally#1
    if has_ally:
        log("[4] Begin skill 'attack' for m1")
        ctx.begin_skill(1, 'attack')
        # Pick first enemy if exists
        enemies = list(getattr(g, 'enemies', []) or [])
        if enemies:
            log("[5] Select enemy e1")
            ctx.toggle_token('e1'); ctx.app.processEvents()
            log("[6] Confirm skill")
            ctx.confirm_skill(); ctx.app.processEvents()
        else:
            log("[5] No enemies to target; confirm without target")
            ctx.confirm_skill(); ctx.app.processEvents()

    # Pick first resource if exists
    log("[7] Pick resource if available")
    try:
        state = g.get_state()
        res = state.get('resources', [])
        if res:
            ctx._send('t r1')
            main.resources.render(); main.resources.render_inventory(); ctx.app.processEvents()
    except Exception:
        pass

    # End turn and then back
    log("[8] End turn and navigate back")
    ctx._send('end'); ctx.app.processEvents()
    ctx._send('back'); ctx.app.processEvents()

    # Return to menu via UI action
    log("[9] Return to menu window")
    main.on_back_to_menu(); ctx.app.processEvents()

    # Check menu exists again
    found_menu = False
    for w in list(ctx.app.topLevelWidgets()):
        if isinstance(w, MenuWindow):
            found_menu = True
            break
    assert found_menu, "MenuWindow not found after returning"

    log("[OK] UI smoke test finished")


if __name__ == '__main__':
    run_sequence()

