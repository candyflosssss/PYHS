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
        # 临时排除集合：记录已死亡但尚未从模型中移除的单位，避免阵型留空
        self._dead_exclude = set()

    def set_context(self, game):
        self.game = game

    def attach(self, container):
        self._container = container

    def mount(self):
        if self._subs:
            return
        for evt in ('card_damaged','card_healed','card_will_die','card_died'):
            self._subs.append((evt, subscribe_event(evt, self._on_proxy)))
        # equipment impacts ally stats and operations
        self._subs.append(('equipment_changed', subscribe_event('equipment_changed', self._on_equip_changed)))
        # stamina micro updates
        self._subs.append(('stamina_changed', subscribe_event('stamina_changed', self._on_stamina_changed)))

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
                if evt in ('card_will_die','card_died') or int(getattr(card, 'hp', 1)) <= 0:
                    # 标记为死亡排除，确保下一次渲染紧凑排布
                    try:
                        self._dead_exclude.add(card)
                    except Exception:
                        pass
                    # 去掉死亡动画：直接安排一次重渲染，让阵型用最新队伍紧凑重排
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
                        self.app.card_wraps.pop(idx, None)
                    except Exception:
                        pass
                    # 如果该索引正显示操作弹窗或被选中，则一并清除
                    try:
                        ops = (getattr(self.app, 'views', {}) or {}).get('ops')
                        if ops and getattr(ops, '_popup_for_index', None) == idx:
                            ops.hide_popup(force=True)
                    except Exception:
                        pass
                    try:
                        if getattr(self.app, 'selected_member_index', None) == idx:
                            self.app.selection.clear_all()
                    except Exception:
                        pass
                    self._pending_render = False
                    # 立即重渲染，确保上移补齐立刻可见
                    try:
                        self._render_now()
                    except Exception:
                        self._schedule_render()
                else:
                    # 更新文本
                    atk = int(getattr(card, 'get_total_attack')() if hasattr(card, 'get_total_attack') else getattr(card, 'attack', 0))
                    hp = int(getattr(card, 'hp', 0)); mhp = int(getattr(card, 'max_hp', hp))
                    defv = int(getattr(card, 'get_total_defense')() if hasattr(card, 'get_total_defense') else getattr(card, 'defense', 0))
                    ac = 10 + defv
                    inner._atk_var.set(str(atk))
                    inner._hp_var.set(f"HP {hp}/{mhp}")
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
                    inner._ac_var.set(str(ac))
                    # 动画：伤害/治疗
                    try:
                        kind = 'heal' if evt == 'card_healed' else 'damage'
                        ANIM.on_hit(self.app, wrap, kind=kind)
                        amt = max(0, int((payload or {}).get('amount', 0)))
                        if amt:
                            text = f"+{amt}" if kind == 'heal' else f"-{amt}"
                            try:
                                from src import settings as S
                                cols = (S.anim_cfg() or {}).get('colors') or {}
                                col = cols.get('heal', '#27ae60') if kind == 'heal' else cols.get('damage', '#c0392b')
                            except Exception:
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
                        inner._atk_var.set(str(atk))
                        inner._ac_var.set(str(10 + defv))
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
                                try:
                                    from .. import cards as tk_cards
                                    return tk_cards.equipment_tooltip(item, label)
                                except Exception:
                                    try:
                                        nm = getattr(item, 'name', '-') if item else None
                                        return f"{label}: {nm or '空槽'}"
                                    except Exception:
                                        return f"{label}: 空槽"
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

    def _on_stamina_changed(self, _evt: str, payload: dict):
        """体力变化：仅更新对应卡片的体力胶囊与标签。"""
        try:
            owner = (payload or {}).get('owner')
            if not owner:
                return
            cur = int((payload or {}).get('stamina', getattr(owner, 'stamina', 0)))
            mx = int((payload or {}).get('stamina_max', getattr(owner, 'stamina_max', cur or 1)))
            for idx, wrap in (getattr(self.app, 'card_wraps', {}) or {}).items():
                inner = next((ch for ch in wrap.winfo_children() if hasattr(ch, '_model_ref')), None)
                if inner is None or getattr(inner, '_model_ref', None) is not owner:
                    continue
                try:
                    caps = getattr(inner, '_st_caps', None)
                    col_on, col_off = getattr(inner, '_st_colors', ('#2ecc71','#e74c3c'))
                    if isinstance(caps, list):
                        for i, c in enumerate(caps):
                            fill = col_on if i < cur else col_off
                            try:
                                c.delete('all')
                                # 与 cards 一致：圆头直线
                                c.create_line(4, 2, 4, 14, fill=fill, width=4, capstyle='round')
                            except Exception:
                                pass
                except Exception:
                    pass
                break
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
        # capture old positions for slide animation
        old_pos: dict[object, tuple[int,int]] = {}
        try:
            for idx, wrap in (getattr(self.app, 'card_wraps', {}) or {}).items():
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
        self.app.card_wraps.clear()
        game = self.game or getattr(self.app.controller, 'game', None)
        if not game:
            return
        raw_board = getattr(game.player, 'board', [])
        # 清理临时排除集合，仅保留仍在当前棋盘列表中的对象，避免集合无限增长
        try:
            cur = list(raw_board or [])
            self._dead_exclude = {m for m in (self._dead_exclude or set()) if m in cur}
        except Exception:
            pass
        # 过滤已死亡或空位，确保阵型紧凑
        board = []
        for m in list(raw_board or []):
            try:
                if m is None:
                    continue
                if int(getattr(m, 'hp', 0)) <= 0:
                    continue
                if m in self._dead_exclude:
                    # 已在死亡排除集合中的成员也跳过
                    continue
            except Exception:
                pass
            board.append(m)
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
        # 确保容器可拉伸，便于 spacer 生效
        try:
            container.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        members = list(board)[:15]
        cols = 3
        # 仅渲染包含成员的行，并将成员向左对齐
        import math
        total = len(members)
        rows = min(5, max(1, math.ceil(total / cols)))
        for r_idx in range(rows):
            row_items = members[r_idx*cols : (r_idx+1)*cols]
            if not row_items:
                continue
            row_f = ttk.Frame(container)
            row_f.grid(row=r_idx, column=0, sticky='ew', pady=(2, 2))
            # 右对齐：左侧拉伸、右侧不拉伸 -> 使本行内容整体靠右
            row_f.grid_columnconfigure(0, weight=1)
            row_f.grid_columnconfigure(cols + 1, weight=0)
            inner_row = ttk.Frame(row_f)
            inner_row.grid(row=0, column=1, sticky='e')
            # 创建固定锚点（3列），卡片放入对应锚点中，行内呈现 321/654/... 模式
            anchors = []
            # 若启用体力展示，保证卡片最小高度，避免体力行被裁切
            _h = self.app.CARD_H
            try:
                stc = getattr(self.app, '_stamina_cfg', {}) or {}
                if stc.get('enabled', True):
                    _h = max(int(_h), 120)
            except Exception:
                pass
            for c_idx in range(cols):
                a = tk.Frame(inner_row, width=self.app.CARD_W, height=_h)
                try:
                    a.grid_propagate(False)
                except Exception:
                    pass
                a.grid(row=0, column=c_idx, padx=2, sticky='n')
                anchors.append(a)
            # 确保锚点坐标已计算
            try:
                self.app.root.update_idletasks()
            except Exception:
                pass
            for j, m in enumerate(row_items):
                # 右对齐且行内顺序反转（视觉 321/654/...）：把第 j 个放到最右侧再向左推
                c = cols - 1 - j
                m_index = r_idx * cols + j + 1  # 索引保持与数据顺序一致
                if m is None:
                    continue
                wrap = tk.Frame(anchors[c], highlightthickness=self.app._border_default, highlightbackground="#cccccc", width=self.app.CARD_W, height=_h)
                try:
                    wrap.pack_propagate(False)
                except Exception:
                    pass
                inner = self._create_character_card(wrap, m, m_index)
                inner.pack(fill=tk.BOTH, expand=True)
                # 若开启滑动动画且有旧位置，则从旧位置滑到新锚点；否则直接放入锚点
                def _final_pack(wrp=wrap, anc=anchors[c]):
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
                    start = old_pos.get(m)
                    if slide_enabled and start:
                        tx = int(anchors[c].winfo_rootx()); ty = int(anchors[c].winfo_rooty())
                        ANIM.slide_to(self.app, wrap, x0=start[0], y0=start[1], x1=tx, y1=ty, duration_ms=150, steps=12, on_done=_final_pack)
                    else:
                        _final_pack()
                except Exception:
                    _final_pack()
                def bind_all(w):
                    # 装备按钮不绑定操作栏行为
                    if getattr(w, '_is_equipment_slot', False):
                        return
                    # 先保持原有选中逻辑
                    def _on_select(_e=None, idx=m_index):
                        try:
                            self.app.selection.on_ally_click(idx)
                        except Exception:
                            pass
                    has_member = True
                    w.bind('<Button-1>', _on_select)
                    # 根据设置决定触发方式
                    trig = (getattr(self.app, '_ops_popup_cfg', {}) or {}).get('trigger', 'click')
                    if has_member and str(trig).lower() == 'click':
                        def _on_click_toggle(_e=None, idx=m_index, ww=w):
                            try:
                                ops = (getattr(self.app, 'views', {}) or {}).get('ops')
                                if not ops:
                                    return
                                cur = getattr(ops, '_popup_for_index', None)
                                vis = ops.is_popup_visible() if hasattr(ops, 'is_popup_visible') else bool(getattr(ops, '_popup', None))
                                # 如果当前就是同一索引：
                                # - 可见 -> 切换为隐藏
                                # - 不可见 -> 重新显示
                                if cur == idx:
                                    if vis:
                                        ops.hide_popup(force=True)
                                    else:
                                        ops.show_popup(idx, ww)
                                else:
                                    # 切换到新的卡片，直接显示
                                    ops.show_popup(idx, ww)
                            except Exception:
                                pass
                        # 附加到点击（在选中之后执行）
                        w.bind('<Button-1>', _on_click_toggle, add=True)
                    elif has_member:
                        # 悬浮操作窗：进入显示该成员的可用操作；离开轻微延迟后隐藏
                        def _on_enter(_e=None, idx=m_index, ww=w):
                            try:
                                ops = (getattr(self.app, 'views', {}) or {}).get('ops')
                                if ops and hasattr(ops, 'show_popup'):
                                    ops.show_popup(idx, ww)
                            except Exception:
                                pass
                        def _on_leave(_e=None):
                            try:
                                ops = (getattr(self.app, 'views', {}) or {}).get('ops')
                                if ops and hasattr(ops, 'hide_popup'):
                                    # 延迟隐藏，允许鼠标移动到悬浮窗
                                    delay = int((getattr(self.app, '_ops_popup_cfg', {}) or {}).get('hide_delay_ms', 300))
                                    self.app.root.after(delay, lambda: ops.hide_popup())
                            except Exception:
                                pass
                        w.bind('<Enter>', _on_enter)
                        w.bind('<Leave>', _on_leave)
                    for ch in getattr(w, 'winfo_children', lambda: [])():
                        bind_all(ch)
                bind_all(wrap)
                self.app.card_wraps[m_index] = wrap

    def _create_character_card(self, parent, m, m_index: int):
        from .. import cards as tk_cards
        return tk_cards.create_character_card(self.app, parent, m, m_index)
