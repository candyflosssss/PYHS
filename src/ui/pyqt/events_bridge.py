from __future__ import annotations

from typing import Callable, List, Tuple

try:
    from src.core.events import subscribe as subscribe_event, unsubscribe as unsubscribe_event  # type: ignore
except Exception:  # pragma: no cover
    def subscribe_event(*_a, **_k):  # type: ignore
        return None
    def unsubscribe_event(*_a, **_k):  # type: ignore
        return None


class EventsBridge:
    """Bridges core event bus to PyQt UI for incremental refresh/feedback."""

    def __init__(self, app_ctx, window):
        self.app_ctx = app_ctx
        self.window = window
        self._subs: List[Tuple[str, Callable]] = []

    def mount(self):
        if self._subs:
            return
        # equipment/stamina/hp changed => targeted card refresh
        def _on_stat(evt, payload):
            try:
                owner = (payload or {}).get('owner') or (payload or {}).get('card')
            except Exception:
                owner = None
            if not owner:
                return
            # determine side by membership
            try:
                game = self.app_ctx.controller.game
                is_enemy = owner in (getattr(game, 'enemies', []) or [])
                is_ally = owner in (getattr(getattr(game, 'player', None), 'board', []) or [])
            except Exception:
                is_enemy = False; is_ally = False
            try:
                if is_enemy:
                    self.window.battlefield.refresh_model(owner, is_enemy=True)
                if is_ally:
                    self.window.battlefield.refresh_model(owner, is_enemy=False)
            except Exception:
                pass
        for name in ('equipment_changed','stamina_changed','hp_changed'):
            self._subs.append((name, subscribe_event(name, _on_stat)))

        # damage/heal feedback
        def _on_damage(evt, payload):
            try:
                owner = (payload or {}).get('enemy') or (payload or {}).get('card')
            except Exception:
                owner = None
            if not owner:
                return
            kind = 'heal' if evt.endswith('healed') else 'damage'
            try:
                game = self.app_ctx.controller.game
                if owner in (getattr(game, 'enemies', []) or []):
                    self.window.battlefield.flash_card(owner, is_enemy=True, kind=kind)
                elif owner in (getattr(getattr(game, 'player', None), 'board', []) or []):
                    self.window.battlefield.flash_card(owner, is_enemy=False, kind=kind)
            except Exception:
                pass
        for name in ('enemy_damaged','card_damaged','card_healed'):
            self._subs.append((name, subscribe_event(name, _on_damage)))

        # resources/inventory => side pane refresh
        def _on_res_inv(_evt, _payload):
            try:
                self.window.resources.render(); self.window.resources.render_inventory()
            except Exception:
                pass
        for name in ('resource_changed','inventory_changed','resource_added','resource_removed','resources_cleared','resources_reset','resources_changed'):
            self._subs.append((name, subscribe_event(name, _on_res_inv)))

        # scene changed -> overlay + rebuild/refresh
        def _on_scene_changed(_evt, payload):
            try:
                self.window.show_scene_overlay()
            except Exception:
                pass
            # allow small delay then refresh and hide overlay
            try:
                from ..qt_compat import QtCore
                def do_refresh():
                    try:
                        self.window.refresh_all()
                    finally:
                        try:
                            self.window.hide_scene_overlay()
                        except Exception:
                            pass
                QtCore.QTimer.singleShot(250, do_refresh)
            except Exception:
                try:
                    self.window.refresh_all(); self.window.hide_scene_overlay()
                except Exception:
                    pass
        self._subs.append(('scene_changed', subscribe_event('scene_changed', _on_scene_changed)))

    def unmount(self):
        for evt, cb in (self._subs or []):
            try:
                unsubscribe_event(evt, cb)
            except Exception:
                pass
        self._subs = []


