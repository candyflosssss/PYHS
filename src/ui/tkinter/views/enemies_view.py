from __future__ import annotations

from typing import Any, Callable

try:
    from src.core.events import subscribe as subscribe_event, unsubscribe as unsubscribe_event
except Exception:  # pragma: no cover
    def subscribe_event(*_a, **_k):  # type: ignore
        return None
    def unsubscribe_event(*_a, **_k):  # type: ignore
        return None


class EnemiesView:
    """Owns enemy-related event subscriptions and triggers UI updates.

    Responsibilities:
    - Zone mutations: enemy_added/removed/cleared/reset/changed -> schedule battlefield refresh
    - Per-entity events: enemy_damaged/enemy_died -> reuse app._on_event_enemy_changed
    """

    def __init__(self, app):
        self.app = app
        self._subs: list[tuple[str, Callable]] = []
        self.game = None

    def set_context(self, game):
        """Bind current game (scene, zones, entities)."""
        self.game = game

    def mount(self):
        if self._subs:
            return
        # per-enemy changes
        self._subs.append(('enemy_damaged', subscribe_event('enemy_damaged', self._on_proxy)))
        self._subs.append(('enemy_died', subscribe_event('enemy_died', self._on_proxy)))
        # zone changes
        for evt in ('enemy_added','enemy_removed','enemies_cleared','enemies_reset','enemies_changed'):
            self._subs.append((evt, subscribe_event(evt, self._on_zone)))

    def unmount(self):
        for evt, cb in (self._subs or []):
            try:
                unsubscribe_event(evt, cb)
            except Exception:
                pass
        self._subs.clear()

    # enemy event handler (micro-update without forwarding to app)
    def _on_proxy(self, evt: str, payload: dict):
        from .. import animations as ANIM
        try:
            # defer during scene-change suppression window
            if getattr(self.app, '_suspend_ui_updates', False):
                self.app._pending_battlefield_refresh = True
                return
            enemy = (payload or {}).get('enemy')
            if not enemy:
                return
            found = False
            for idx, wrap in (getattr(self.app, 'enemy_card_wraps', {}) or {}).items():
                inner = next((ch for ch in wrap.winfo_children() if hasattr(ch, '_model_ref')), None)
                if inner is None or getattr(inner, '_model_ref', None) is not enemy:
                    continue
                if evt == 'enemy_died' or int(getattr(enemy, 'hp', 1)) <= 0:
                    try:
                        ANIM.on_hit(self.app, wrap, kind='damage')
                        amt = max(0, int((payload or {}).get('amount', 0)))
                        if amt:
                            ANIM.float_text(self.app, wrap, f"-{amt}", color="#c0392b")
                    except Exception:
                        pass
                    def _remove_idx():
                        try:
                            ANIM.cancel_widget_anims(wrap)
                        except Exception:
                            pass
                        try:
                            self.app.enemy_card_wraps.pop(idx, None)
                        except Exception:
                            pass
                        self.app._schedule_battlefield_refresh()
                    ANIM.on_death(self.app, wrap, on_removed=_remove_idx)
                else:
                    atk = int(getattr(enemy, 'attack', 0))
                    hp = int(getattr(enemy, 'hp', 0)); mhp = int(getattr(enemy, 'max_hp', hp))
                    defv = int(getattr(enemy, 'get_total_defense')() if hasattr(enemy, 'get_total_defense') else getattr(enemy, 'defense', 0))
                    ac = 10 + defv
                    inner._atk_var.set(f"ATK {atk}")
                    inner._hp_var.set(f"HP {hp}/{mhp}")
                    inner._ac_var.set(f"AC {ac}")
                    try:
                        ANIM.on_hit(self.app, wrap, kind='damage')
                        amt = max(0, int((payload or {}).get('amount', 0)))
                        if amt:
                            ANIM.float_text(self.app, wrap, f"-{amt}", color="#c0392b")
                    except Exception:
                        pass
                found = True
                break
            if not found:
                self.app._schedule_battlefield_refresh()
        except Exception:
            try:
                self.app._schedule_battlefield_refresh()
            except Exception:
                pass

    def _on_zone(self, _evt: str, _payload: dict):
        try:
            self.app._schedule_battlefield_refresh()
        except Exception:
            pass

    # --- rendering ---
    def render_all(self, container):
        """Render enemy cards into container, using app helpers for card creation and animations.
        Mirrors previous app._render_enemy_cards but scoped to this view.
        """
        import tkinter as tk
        from tkinter import ttk
        from .. import animations as ANIM
        # clear
        for w in list(container.winfo_children()):
            try:
                ANIM.cancel_widget_anims(w)
            except Exception:
                pass
            try:
                w.destroy()
            except Exception:
                pass
        self.app.enemy_card_wraps.clear()
        g = self.game or getattr(self.app.controller, 'game', None)
        enemies = getattr(g, 'enemies', None) or getattr(g, 'enemy_zone', []) or []
        if not enemies:
            try:
                container.grid_columnconfigure(0, weight=1)
            except Exception:
                pass
            lbl = ttk.Label(container, text="(无敌人)", foreground="#888")
            try:
                lbl.grid(row=0, column=0, sticky='n', pady=(2, 4))
            except Exception:
                pass
            return
        max_per_row = 6
        members = list(enemies)[:12]
        rows = [members[:max_per_row], members[max_per_row:]]
        for r_idx, row_members in enumerate(rows):
            if not row_members:
                continue
            row_f = ttk.Frame(container)
            row_f.grid(row=r_idx, column=0, sticky='ew', pady=(2, 2))
            for c in (0, max_per_row + 1):
                row_f.grid_columnconfigure(c, weight=1)
            k = len(row_members)
            start = 1 + (max_per_row - k) // 2
            for j, e in enumerate(row_members):
                e_index = r_idx * max_per_row + j + 1
                wrap = tk.Frame(row_f, highlightthickness=self.app._border_default, highlightbackground="#cccccc", width=self.app.CARD_W, height=self.app.CARD_H)
                try:
                    wrap.pack_propagate(False)
                except Exception:
                    pass
                inner = self._create_enemy_card(wrap, e, e_index)
                inner.pack(fill=tk.BOTH, expand=True)
                col = start + j
                wrap.grid(row=0, column=col, padx=2, sticky='n')
                def bind_all(w):
                    w.bind('<Button-1>', lambda _e, idx=e_index: self.app._on_enemy_card_click(idx))
                    for ch in getattr(w, 'winfo_children', lambda: [])():
                        bind_all(ch)
                bind_all(wrap)
                self.app.enemy_card_wraps[e_index] = wrap

    def _create_enemy_card(self, parent, e, e_index: int):
        from .. import cards as tk_cards
        try:
            return tk_cards.create_character_card(self.app, parent, e, e_index, is_enemy=True)
        except Exception:
            from tkinter import ttk
            frame = ttk.Frame(parent, relief='ridge', padding=4)
            ttk.Label(frame, text=getattr(e, 'name', f'敌人#{e_index}')).pack()
            return frame
