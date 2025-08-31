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
        self._container = None
        self._pending_render = False

    def set_context(self, game):
        """Bind current game (scene, zones, entities)."""
        self.game = game

    def attach(self, container):
        """Attach the container to render enemy cards into."""
        self._container = container

    def mount(self):
        if self._subs:
            return
        # per-enemy changes
        self._subs.append(('enemy_damaged', subscribe_event('enemy_damaged', self._on_proxy)))
        self._subs.append(('enemy_will_die', subscribe_event('enemy_will_die', self._on_proxy)))
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
                self._pending_render = True
                return
            enemy = (payload or {}).get('enemy')
            if not enemy:
                return
            found = False
            for idx, wrap in (getattr(self.app, 'enemy_card_wraps', {}) or {}).items():
                inner = next((ch for ch in wrap.winfo_children() if hasattr(ch, '_model_ref')), None)
                if inner is None or getattr(inner, '_model_ref', None) is not enemy:
                    continue
                if evt in ('enemy_will_die','enemy_died') or int(getattr(enemy, 'hp', 1)) <= 0:
                    # 去掉死亡动画，直接重渲染让阵型紧凑重排
                    try:
                        ANIM.cancel_widget_anims(wrap)
                    except Exception:
                        pass
                    # 立即销毁控件，避免在下一次渲染前残留
                    try:
                        wrap.destroy()
                    except Exception:
                        pass
                    try:
                        self.app.enemy_card_wraps.pop(idx, None)
                    except Exception:
                        pass
                    # 若当前选中的是该敌人，清空选中与高亮
                    try:
                        if getattr(self.app, 'selected_enemy_index', None) == idx:
                            self.app.selected_enemy_index = None
                            try:
                                self.app._reset_highlights()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    self._pending_render = False
                    # 立即重渲染，确保上移补齐立刻可见
                    try:
                        self._render_now()
                    except Exception:
                        self._schedule_render()
                else:
                    atk = int(getattr(enemy, 'attack', 0))
                    hp = int(getattr(enemy, 'hp', 0)); mhp = int(getattr(enemy, 'max_hp', hp))
                    defv = int(getattr(enemy, 'get_total_defense')() if hasattr(enemy, 'get_total_defense') else getattr(enemy, 'defense', 0))
                    ac = 10 + defv
                    inner._atk_var.set(str(atk))
                    inner._hp_var.set(f"HP {hp}/{mhp}")
                    inner._ac_var.set(str(ac))
                    # 重绘血条
                    try:
                        if hasattr(inner, '_hp_canvas'):
                            inner._hp_cur = hp
                            inner._hp_max = mhp
                            w = max(1, int(inner._hp_canvas.winfo_width() or 1))
                            h = int(getattr(self.app, '_hp_bar_cfg', {}).get('height', 12))
                            bg = getattr(self.app, '_hp_bar_cfg', {}).get('bg', '#e5e7eb')
                            fg = getattr(self.app, '_hp_bar_cfg', {}).get('fg', '#e74c3c')
                            tx = getattr(self.app, '_hp_bar_cfg', {}).get('text', '#ffffff')
                            inner._hp_canvas.delete('all')
                            ratio = 0 if mhp <= 0 else max(0.0, min(1.0, float(hp)/float(mhp)))
                            fill_w = int(w * ratio)
                            inner._hp_canvas.create_rectangle(0, 0, w, h, fill=bg, outline=bg, width=0)
                            if fill_w > 0:
                                inner._hp_canvas.create_rectangle(0, 0, fill_w, h, fill=fg, outline=fg, width=0)
                            inner._hp_canvas.create_text(w//2, h//2, text=f"{hp}/{mhp}", fill=tx, font=("Segoe UI", 8))
                    except Exception:
                        pass
                    try:
                        ANIM.on_hit(self.app, wrap, kind='damage')
                        amt = max(0, int((payload or {}).get('amount', 0)))
                        if amt:
                            try:
                                from src import settings as S
                                col = ((S.anim_cfg() or {}).get('colors') or {}).get('damage', '#c0392b')
                            except Exception:
                                col = '#c0392b'
                            ANIM.float_text(self.app, wrap, f"-{amt}", color=col)
                    except Exception:
                        pass
                found = True
                break
            if not found:
                self._schedule_render()
        except Exception:
            self._schedule_render()

    def _on_zone(self, _evt: str, _payload: dict):
        self._schedule_render()

    def _schedule_render(self):
        if not self._container:
            return
        if self._pending_render:
            return
        self._pending_render = True
        try:
            self.app.root.after(0, self._render_now)
        except Exception:
            self._render_now()

    def _render_now(self):
        self._pending_render = False
        try:
            self.render_all(self._container)
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
        # capture old positions for slide animation
        old_pos: dict[object, tuple[int,int]] = {}
        try:
            for idx, wrap in (getattr(self.app, 'enemy_card_wraps', {}) or {}).items():
                try:
                    inner = next((ch for ch in wrap.winfo_children() if hasattr(ch, '_model_ref')), None)
                    if inner is None:
                        continue
                    x = int(wrap.winfo_rootx()); y = int(wrap.winfo_rooty())
                    old_pos[getattr(inner, '_model_ref')] = (x, y)
                except Exception:
                    pass
        except Exception:
            old_pos = {}
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
        raw = getattr(g, 'enemies', None) or getattr(g, 'enemy_zone', []) or []
        # 过滤空位/死亡，保持紧凑
        enemies = []
        for e in list(raw or []):
            try:
                if e is None:
                    continue
                if int(getattr(e, 'hp', 0)) <= 0:
                    continue
            except Exception:
                pass
            enemies.append(e)
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
        # 确保容器可拉伸，便于左右 spacer 生效
        try:
            container.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        members = list(enemies)[:15]
        cols = 3
        import math
        total = len(members)
        rows_cnt = min(5, max(1, math.ceil(total / cols)))
        # 创建各行与固定锚点（列）
        anchors: list[list[tk.Frame]] = []
        # 统一卡片最小高度（考虑体力槽）
        _h = self.app.CARD_H
        try:
            stc = getattr(self.app, '_stamina_cfg', {}) or {}
            if stc.get('enabled', True):
                _h = max(int(_h), 120)
        except Exception:
            pass
        for r_idx in range(rows_cnt):
            row_f = ttk.Frame(container)
            row_f.grid(row=r_idx, column=0, sticky='ew', pady=(2, 2))
            # 左对齐：左 spacer=0、右 spacer=1
            row_f.grid_columnconfigure(0, weight=0)
            row_f.grid_columnconfigure(cols + 1, weight=1)
            inner_row = ttk.Frame(row_f)
            inner_row.grid(row=0, column=1, sticky='w')
            row_anchors: list[tk.Frame] = []
            for c_idx in range(cols):
                a = tk.Frame(inner_row, width=self.app.CARD_W, height=_h)
                try:
                    a.grid_propagate(False)
                except Exception:
                    pass
                a.grid(row=0, column=c_idx, padx=2, sticky='n')
                row_anchors.append(a)
            anchors.append(row_anchors)
        # 确保锚点布局完成
        try:
            self.app.root.update_idletasks()
        except Exception:
            pass
        # 将敌人按顺序 123/456/... 放入锚点（从上到下、从左到右），保证向上紧凑
        for i, e in enumerate(members):
            r = i // cols
            c = i % cols
            e_index = i + 1
            if e is None:
                continue
            parent = anchors[r][c]
            wrap = tk.Frame(parent, highlightthickness=self.app._border_default, highlightbackground="#cccccc", width=self.app.CARD_W, height=_h)
            try:
                wrap.pack_propagate(False)
            except Exception:
                pass
            inner = self._create_enemy_card(wrap, e, e_index)
            inner.pack(fill=tk.BOTH, expand=True)
            def _final_pack(wrp=wrap, par=parent):
                try:
                    wrp.pack(fill=tk.BOTH, expand=True)
                except Exception:
                    pass
            try:
                # 开关：settings.anim_cfg().slide.enabled / slide_enabled
                slide_enabled = False
                try:
                    from src import settings as S
                    cfg = (S.anim_cfg() or {}).get('slide') or {}
                    slide_enabled = bool(cfg.get('enabled', False) or cfg.get('slide_enabled', False))
                except Exception:
                    slide_enabled = False
                start = old_pos.get(e)
                if slide_enabled and start:
                    tx = int(parent.winfo_rootx()); ty = int(parent.winfo_rooty())
                    ANIM.slide_to(self.app, wrap, x0=start[0], y0=start[1], x1=tx, y1=ty, duration_ms=150, steps=12, on_done=_final_pack)
                else:
                    _final_pack()
            except Exception:
                _final_pack()
            def bind_all(w):
                w.bind('<Button-1>', lambda _e, idx=e_index: self.app.selection.on_enemy_click(idx))
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
