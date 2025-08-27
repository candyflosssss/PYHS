from __future__ import annotations

from typing import Any, Callable

from .. import ui_utils as U

try:
    from src.core.events import subscribe as subscribe_event, unsubscribe as unsubscribe_event
except Exception:  # pragma: no cover
    def subscribe_event(*_a, **_k):  # type: ignore
        return None
    def unsubscribe_event(*_a, **_k):  # type: ignore
        return None


class AlliesView:
    """拥有盟友卡牌事件并触发微更新。

    订阅 card_damaged/card_healed/card_died 事件，并根据区域等变化安排战场刷新
    （目前，棋盘突变通过应用中的战场刷新调用器反映）.
    """

    def __init__(self, app):
        self.app = app
        self._subs: list[tuple[str, Callable]] = []
        self.game = None
        self._container = None
        self._pending_render = False

    def set_context(self, game):
        self.game = game

    def attach(self, container):
        self._container = container

    def mount(self):
        if self._subs:
            return
        for evt in ('card_damaged','card_healed','card_died'):
            self._subs.append((evt, subscribe_event(evt, self._on_proxy)))
        # equipment impacts ally stats and operations
        self._subs.append(('equipment_changed', subscribe_event('equipment_changed', self._on_equip_changed)))

    def unmount(self):
        for evt, cb in (self._subs or []):
            try:
                unsubscribe_event(evt, cb)
            except Exception:
                pass
        self._subs.clear()

    def _on_proxy(self, evt: str, payload: dict):
        from .. import animations as ANIM
        try:
            if getattr(self.app, '_suspend_ui_updates', False):
                self._pending_render = True
                return
            card = (payload or {}).get('card')
            if not card:
                return
            found = False
            for idx, wrap in (getattr(self.app, 'card_wraps', {}) or {}).items():
                inner = next((ch for ch in wrap.winfo_children() if hasattr(ch, '_model_ref')), None)
                if inner is None or getattr(inner, '_model_ref', None) is not card:
                    continue
                if evt == 'card_died' or int(getattr(card, 'hp', 1)) <= 0:
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
                            self.app.card_wraps.pop(idx, None)
                        except Exception:
                            pass
                        try:
                            self._pending_render = False
                        except Exception:
                            pass
                        self._schedule_render()
                    ANIM.on_death(self.app, wrap, on_removed=_remove_idx)
                else:
                    # 更新文本
                    atk = int(getattr(card, 'get_total_attack')() if hasattr(card, 'get_total_attack') else getattr(card, 'attack', 0))
                    hp = int(getattr(card, 'hp', 0)); mhp = int(getattr(card, 'max_hp', hp))
                    defv = int(getattr(card, 'get_total_defense')() if hasattr(card, 'get_total_defense') else getattr(card, 'defense', 0))
                    ac = 10 + defv
                    inner._atk_var.set(f"ATK {atk}")
                    inner._hp_var.set(f"HP {hp}/{mhp}")
                    inner._ac_var.set(f"AC {ac}")
                    # 动画：伤害/治疗
                    try:
                        kind = 'heal' if evt == 'card_healed' else 'damage'
                        ANIM.on_hit(self.app, wrap, kind=kind)
                        amt = max(0, int((payload or {}).get('amount', 0)))
                        if amt:
                            text = f"+{amt}" if kind == 'heal' else f"-{amt}"
                            col = "#27ae60" if kind == 'heal' else "#c0392b"
                            ANIM.float_text(self.app, wrap, text, color=col)
                    except Exception:
                        pass
                found = True
                break
            if not found:
                self._schedule_render()
        except Exception:
            try:
                self._schedule_render()
            except Exception:
                pass

    def _on_equip_changed(self, evt: str, payload: dict):
        """装备变化：尽量做微更新，并请求操作栏重渲染。"""
        try:
            # 优先微更新：直接刷新受影响卡片文本（若能找到控件）
            card = (payload or {}).get('owner') or (payload or {}).get('card')
            if card:
                for idx, wrap in (getattr(self.app, 'card_wraps', {}) or {}).items():
                    inner = next((ch for ch in wrap.winfo_children() if hasattr(ch, '_model_ref')), None)
                    if inner is None or getattr(inner, '_model_ref', None) is not card:
                        continue
                    try:
                        atk = int(getattr(card, 'get_total_attack')() if hasattr(card, 'get_total_attack') else getattr(card, 'attack', 0))
                        defv = int(getattr(card, 'get_total_defense')() if hasattr(card, 'get_total_defense') else getattr(card, 'defense', 0))
                        cur = int(getattr(card, 'hp', 0)); mx = int(getattr(card, 'max_hp', cur))
                        inner._atk_var.set(f"ATK {atk}")
                        inner._ac_var.set(f"AC {10 + defv}")
                        inner._hp_var.set(f"HP {cur}/{mx}")
                        # 同步装备按钮文字与 tooltip（不重建控件，避免闪烁）
                        try:
                            eq = getattr(card, 'equipment', None)
                            lh = getattr(eq, 'left_hand', None) if eq else None
                            rh_raw = getattr(eq, 'right_hand', None) if eq else None
                            ar = getattr(eq, 'armor', None) if eq else None
                            # 双手武器占用右手显示
                            rh = lh if getattr(lh, 'is_two_handed', False) else rh_raw
                            def _slot_text(label, item):
                                return (getattr(item, 'name', '-')) if item else f"{label}: -"
                            def _tip_text(item, label):
                                if not item:
                                    return f"{label}: 空槽"
                                parts = []
                                try:
                                    av = int(getattr(item, 'attack', 0) or 0)
                                    if av:
                                        parts.append(f"+{av} 攻")
                                except Exception:
                                    pass
                                try:
                                    dv = int(getattr(item, 'defense', 0) or 0)
                                    if dv:
                                        parts.append(f"+{dv} 防")
                                except Exception:
                                    pass
                                if getattr(item, 'is_two_handed', False):
                                    parts.append('双手')
                                head = getattr(item, 'name', '')
                                tail = ' '.join(parts)
                                return head + (("\n" + tail) if tail else '')
                            def _rebind_tip(btn, provider):
                                try:
                                    btn.unbind('<Enter>'); btn.unbind('<Leave>'); btn.unbind('<Motion>')
                                except Exception:
                                    pass
                                try:
                                    U.attach_tooltip_deep(btn, provider)
                                except Exception:
                                    pass
                            if hasattr(inner, '_btn_left') and inner._btn_left:
                                inner._btn_left.config(text=_slot_text('左手', lh))
                                _rebind_tip(inner._btn_left, lambda it=lambda: getattr(getattr(card, 'equipment', None), 'left_hand', None): _tip_text(it(), '左手'))
                            if hasattr(inner, '_btn_right') and inner._btn_right:
                                # 注意：若左手为双手武器，右手按钮显示左手物品
                                _provider = lambda: (getattr(getattr(card, 'equipment', None), 'left_hand', None)
                                                    if getattr(getattr(getattr(card, 'equipment', None), 'left_hand', None), 'is_two_handed', False)
                                                    else getattr(getattr(card, 'equipment', None), 'right_hand', None))
                                inner._btn_right.config(text=_slot_text('右手', rh))
                                _rebind_tip(inner._btn_right, lambda it=_provider: _tip_text(it(), '右手'))
                            if hasattr(inner, '_btn_armor') and inner._btn_armor:
                                inner._btn_armor.config(text=_slot_text('盔甲', ar))
                                _rebind_tip(inner._btn_armor, lambda it=lambda: getattr(getattr(card, 'equipment', None), 'armor', None): _tip_text(it(), '盔甲'))
                        except Exception:
                            pass
                    except Exception:
                        pass
                    break
            # 操作栏重渲染
            try:
                ops = (getattr(self.app, 'views', {}) or {}).get('ops')
                if ops and hasattr(self.app, 'frm_operations'):
                    ops.render(self.app.frm_operations)
            except Exception:
                pass
        except Exception:
            pass

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
        self.app.card_wraps.clear()
        game = self.game or getattr(self.app.controller, 'game', None)
        if not game:
            return
        board = getattr(game.player, 'board', [])
        if not board:
            try:
                container.grid_columnconfigure(0, weight=1)
            except Exception:
                pass
            lbl = ttk.Label(container, text="(队伍为空)", foreground="#888")
            try:
                lbl.grid(row=0, column=0, sticky='n', pady=(2, 6))
            except Exception:
                pass
            return
        members = list(board)[:10]
        max_per_row = 5
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
            for j, m in enumerate(row_members):
                m_index = r_idx * max_per_row + j + 1
                wrap = tk.Frame(row_f, highlightthickness=self.app._border_default, highlightbackground="#cccccc", width=self.app.CARD_W, height=self.app.CARD_H)
                try:
                    wrap.pack_propagate(False)
                except Exception:
                    pass
                inner = self._create_character_card(wrap, m, m_index)
                inner.pack(fill=tk.BOTH, expand=True)
                col = start + j
                wrap.grid(row=0, column=col, padx=2, sticky='n')
                def bind_all(w):
                    w.bind('<Button-1>', lambda _e, idx=m_index: self.app.selection.on_ally_click(idx))
                    for ch in getattr(w, 'winfo_children', lambda: [])():
                        bind_all(ch)
                bind_all(wrap)
                self.app.card_wraps[m_index] = wrap

    def _create_character_card(self, parent, m, m_index: int):
        from .. import cards as tk_cards
        return tk_cards.create_character_card(self.app, parent, m, m_index)
