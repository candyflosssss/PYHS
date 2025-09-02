from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Any
from .. import cards as Cards
from .. import animations as ANIM
try:
    from src.core.events import subscribe as subscribe_event, unsubscribe as unsubscribe_event
except Exception:  # pragma: no cover
    def subscribe_event(*_a, **_k):  # type: ignore
        return None
    def unsubscribe_event(*_a, **_k):  # type: ignore
        return None


class BattlefieldView:
    """A mirrored battlefield container with flow-compact grids for allies (right) and enemies (left).

    Features:
    - Flow-compact grid (3 columns, up to 5 rows) per side.
    - Mirrored alignment: allies right-aligned per row, enemies left-aligned.
    - Dynamic add/remove tokens; slide-to-anchor reposition animation; shake feedback.
    - Responsive anchors: cards follow on container resize.

    This view renders minimalist colored squares (placeholders). Integrate real cards later.
    """

    COLS = 3
    CARD_W = 88
    CARD_H = 96

    def __init__(self, owner: Any):
        # owner 可以是 Tk root 或 app 实例；尽量自动识别
        if isinstance(owner, tk.Misc):
            self.root = owner
            self.app = None
        else:
            self.app = owner
            self.root = getattr(owner, 'root', None)
        self.container = None
        # two side panels
        self._ally_panel = None
        self._enemy_panel = None
        # overlay layers to place wrappers absolutely
        self._ally_overlay = None
        self._enemy_overlay = None
        # anchor holders
        self._ally_grid = None
        self._enemy_grid = None
        # 若由 app 构造，则采用 app 的卡面尺寸
        try:
            if getattr(self, 'app', None) is not None:
                self.CARD_W = int(getattr(self.app, 'CARD_W', self.CARD_W))
                self.CARD_H = int(getattr(self.app, 'CARD_H', self.CARD_H))
        except Exception:
            pass
        # data
        self._allies: List[object] = []
        self._enemies: List[object] = []
        # token -> wrapper
        self._ally_wraps: Dict[object, tk.Frame] = {}
        self._enemy_wraps: Dict[object, tk.Frame] = {}
        # side states for stable reposition snapshots
        self._side_state: Dict[str, Dict[str, Any]] = {'ally': {}, 'enemy': {}}
        self._ally_bound = False
        self._enemy_bound = False
        # click handlers (provided by host app)
        self._on_ally_click = None
        self._on_enemy_click = None
        # external dicts to export wrappers for highlighting (1-based index -> wrapper)
        self._export_ally_wraps: Optional[Dict[int, tk.Frame]] = None
        self._export_enemy_wraps: Optional[Dict[int, tk.Frame]] = None
        # event subscriptions
        self._subs: List[Any] = []

    # --- public API ---
    def attach(self, container: tk.Frame):
        self.container = container
        self._build_base()
        self._mount_events()

    def set_click_handlers(self, on_ally_click, on_enemy_click):
        """Register click callbacks receiving 1-based index for ally/enemy."""
        self._on_ally_click = on_ally_click
        self._on_enemy_click = on_enemy_click

    def export_wraps_to(self, ally_map: Dict[int, tk.Frame], enemy_map: Dict[int, tk.Frame]):
        """Provide dicts to populate 1-based index -> wrapper mappings for external highlighting."""
        self._export_ally_wraps = ally_map
        self._export_enemy_wraps = enemy_map

    def set_allies(self, items: List[object]):
        self._allies = list(items or [])[:15]
        self._render_side(is_enemy=False)

    def set_enemies(self, items: List[object]):
        self._enemies = list(items or [])[:15]
        self._render_side(is_enemy=True)

    def add(self, is_enemy: bool, token: object, index: Optional[int] = None):
        seq = self._enemies if is_enemy else self._allies
        if token in seq:
            return
        if index is None or index < 0 or index > len(seq):
            seq.append(token)
        else:
            seq.insert(index, token)
        self._render_side(is_enemy=is_enemy)

    def remove(self, is_enemy: bool, token: object):
        seq = self._enemies if is_enemy else self._allies
        try:
            seq.remove(token)
        except ValueError:
            return
        self._render_side(is_enemy=is_enemy)

    def move(self, is_enemy: bool, token: object, new_index: int):
        seq = self._enemies if is_enemy else self._allies
        if token not in seq:
            return
        try:
            seq.remove(token)
        except ValueError:
            return
        new_index = max(0, min(new_index, len(seq)))
        seq.insert(new_index, token)
        self._render_side(is_enemy=is_enemy)

    def shake(self, is_enemy: bool, token: object):
        wraps = self._enemy_wraps if is_enemy else self._ally_wraps
        w = wraps.get(token)
        if not w:
            return
        self._shake_widget(w)

    def reset(self):
        """Clear all UI state and data for a fresh scene load without destroying the view."""
        try:
            # destroy existing wrappers
            for w in list(self._ally_wraps.values()):
                try:
                    w.destroy()
                except Exception:
                    pass
            for w in list(self._enemy_wraps.values()):
                try:
                    w.destroy()
                except Exception:
                    pass
            self._ally_wraps.clear(); self._enemy_wraps.clear()
            # clear exported maps (keep object identity)
            try:
                (self._export_ally_wraps or {}).clear()
            except Exception:
                pass
            try:
                (self._export_enemy_wraps or {}).clear()
            except Exception:
                pass
            # clear anchors (rows) from grid holders
            for grid in (self._ally_grid, self._enemy_grid):
                try:
                    for ch in list(getattr(grid, 'winfo_children', lambda: [])()):
                        ch.destroy()
                except Exception:
                    pass
            # clear sequences and side snapshots
            self._allies = []
            self._enemies = []
            self._side_state = {'ally': {}, 'enemy': {}}
            # ensure overlays exist and on top
            try:
                self._ally_overlay and self._ally_overlay.lift()
            except Exception:
                pass
            try:
                self._enemy_overlay and self._enemy_overlay.lift()
            except Exception:
                pass
        except Exception:
            pass

    # --- internals ---
    def _build_base(self):
        assert self.container is not None
        c = self.container
        for ch in list(c.winfo_children()):
            ch.destroy()
        # layout: [enemy_panel] [spacer] [ally_panel]
        c.grid_columnconfigure(0, weight=1)
        c.grid_columnconfigure(1, weight=0)
        c.grid_columnconfigure(2, weight=1)
        c.grid_rowconfigure(0, weight=1)
        # 注意：按用户期望，伙伴区在左，敌人区在右
        # 增加外边框以便清晰区分两个区域
        self._ally_panel = tk.Frame(c, highlightthickness=1, highlightbackground="#7EC6F6", bd=0)
        self._ally_panel.grid(row=0, column=0, sticky='nsew', padx=(6, 3), pady=4)
        self._enemy_panel = tk.Frame(c, highlightthickness=1, highlightbackground="#FAD96B", bd=0)
        self._enemy_panel.grid(row=0, column=2, sticky='nsew', padx=(3, 6), pady=4)
        # spacer (could show VS divider later)
        sep = ttk.Separator(c, orient='vertical')
        sep.grid(row=0, column=1, sticky='ns', padx=2)

        # overlays and grids per side
        # enemy side (right)
        self._enemy_overlay = tk.Frame(self._enemy_panel)
        self._enemy_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._enemy_grid = ttk.Frame(self._enemy_panel)
        self._enemy_grid.pack(fill=tk.X, anchor='n')
        try:
            self._enemy_overlay.lift()
        except Exception:
            pass

        # ally side (left)
        self._ally_overlay = tk.Frame(self._ally_panel)
        self._ally_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._ally_grid = ttk.Frame(self._ally_panel)
        self._ally_grid.pack(fill=tk.X, anchor='n')
        try:
            self._ally_overlay.lift()
        except Exception:
            pass

    def _mount_events(self):
        # 订阅与卡片/敌人展示相关的事件，做就地刷新/增删与动画反馈
        try:
            if self._subs:
                return
            # 轻量属性变化（装备/体力）：只刷新对应卡面
            def _on_evt(evt, payload):
                try:
                    owner = (payload or {}).get('owner')
                except Exception:
                    owner = None
                if owner is None:
                    return
                # 判断在哪一侧
                is_enemy = owner in self._enemies
                is_ally = owner in self._allies
                try:
                    if is_ally:
                        self._refresh_one(owner, is_enemy=False)
                    if is_enemy:
                        self._refresh_one(owner, is_enemy=True)
                except Exception:
                    # 回退：找不到则重绘该侧
                    try:
                        if is_ally:
                            self._render_side(is_enemy=False)
                        if is_enemy:
                            self._render_side(is_enemy=True)
                    except Exception:
                        pass
            for name in ('equipment_changed','stamina_changed','hp_changed'):
                self._subs.append((name, subscribe_event(name, _on_evt)))

            # 我方卡片新增（来自 Player.play_card）
            def _on_card_added(_evt, payload):
                try:
                    card = (payload or {}).get('card')
                    owner = (payload or {}).get('owner')
                except Exception:
                    card = owner = None
                if not card or not owner:
                    return
                # 仅当为当前游戏的玩家时加入 allies
                try:
                    game = getattr(getattr(self.app, 'controller', None), 'game', None)
                    if game and owner is getattr(game, 'player', None):
                        self.add(is_enemy=False, token=card)
                except Exception:
                    pass
            self._subs.append(('card_added', subscribe_event('card_added', _on_card_added)))

            # 我方受伤/治疗：动画 + 轻量刷新
            def _on_card_hp(evt, payload):
                try:
                    card = (payload or {}).get('card')
                    amount = int((payload or {}).get('amount', 0))
                except Exception:
                    card, amount = None, 0
                if not card:
                    return
                if card not in self._allies:
                    return
                wrap = self._ally_wraps.get(card)
                if wrap:
                    try:
                        if evt == 'card_damaged':
                            ANIM.on_hit(self.app, wrap, kind='damage')
                            if amount:
                                ANIM.float_text(self.app, wrap, f"-{amount}", color='#c0392b')
                        else:
                            ANIM.on_hit(self.app, wrap, kind='heal')
                            if amount:
                                ANIM.float_text(self.app, wrap, f"+{amount}", color='#27ae60')
                    except Exception:
                        pass
                # 刷新数值
                try:
                    self._refresh_one(card, is_enemy=False)
                except Exception:
                    pass
            self._subs.append(('card_damaged', subscribe_event('card_damaged', _on_card_hp)))
            self._subs.append(('card_healed', subscribe_event('card_healed', _on_card_hp)))

            # 我方死亡：播放死亡动画后移除
            def _on_card_died(_evt, payload):
                try:
                    card = (payload or {}).get('card')
                except Exception:
                    card = None
                if not card or card not in self._allies:
                    # 即使不在本地列表中，也尝试一次对齐（可能 game 已先行移除）
                    try:
                        self._sync_allies_from_game()
                    except Exception:
                        pass
                    return
                wrap = self._ally_wraps.get(card)
                if wrap:
                    # 避免重复触发死亡动画
                    if getattr(wrap, '_dying', False):
                        return
                    try:
                        setattr(wrap, '_dying', True)
                    except Exception:
                        pass
                    try:
                        ANIM.on_death(self.app, wrap, on_removed=lambda: self.remove(False, card))
                        return
                    except Exception:
                        pass
                # 回退：直接移除
                self.remove(False, card)
                # 最后再对齐一次 allies 列表，防止不同步
                try:
                    self.root.after(120, self._sync_allies_from_game)
                except Exception:
                    pass
            self._subs.append(('card_will_die', subscribe_event('card_will_die', _on_card_died)))
            self._subs.append(('card_died', subscribe_event('card_died', _on_card_died)))

            # 敌人区：列表变化事件（ObservableList） -> 全量更新敌人列表
            def _reload_enemies(_evt=None, _payload=None):
                try:
                    game = getattr(getattr(self.app, 'controller', None), 'game', None)
                    if not game:
                        return
                    self.set_enemies(list(getattr(game, 'enemies', []) or []))
                except Exception:
                    pass
            for name in ('enemy_added','enemy_removed','enemies_cleared','enemies_reset','enemies_changed'):
                self._subs.append((name, subscribe_event(name, _reload_enemies)))

            # 敌人受伤/死亡：动画 + 刷新或移除
            def _on_enemy_damaged(_evt, payload):
                try:
                    enemy = (payload or {}).get('enemy')
                    amount = int((payload or {}).get('amount', 0))
                except Exception:
                    enemy, amount = None, 0
                if not enemy or enemy not in self._enemies:
                    return
                wrap = self._enemy_wraps.get(enemy)
                if wrap:
                    try:
                        ANIM.on_hit(self.app, wrap, kind='damage')
                        if amount:
                            ANIM.float_text(self.app, wrap, f"-{amount}", color='#c0392b')
                    except Exception:
                        pass
                try:
                    self._refresh_one(enemy, is_enemy=True)
                except Exception:
                    pass
            self._subs.append(('enemy_damaged', subscribe_event('enemy_damaged', _on_enemy_damaged)))

            def _on_enemy_died(_evt, payload):
                try:
                    enemy = (payload or {}).get('enemy')
                    changed = bool((payload or {}).get('scene_changed', False))
                except Exception:
                    enemy, changed = None, False
                if not enemy:
                    return
                # 若切场景，交由场景事件处理；否则局部动画/移除
                if changed:
                    return
                if enemy in self._enemies:
                    wrap = self._enemy_wraps.get(enemy)
                    if wrap:
                        if getattr(wrap, '_dying', False):
                            return
                        try:
                            setattr(wrap, '_dying', True)
                        except Exception:
                            pass
                        try:
                            ANIM.on_death(self.app, wrap, on_removed=lambda: self.remove(True, enemy))
                            return
                        except Exception:
                            pass
                    self.remove(True, enemy)
            self._subs.append(('enemy_died', subscribe_event('enemy_died', _on_enemy_died)))
        except Exception:
            self._subs = []

    def _refresh_one(self, token: object, *, is_enemy: bool):
        wraps = self._enemy_wraps if is_enemy else self._ally_wraps
        w = wraps.get(token)
        if not w:
            # 不在当前侧显示：忽略
            return
        # 找到卡片根框架并请求刷新
        try:
            children = list(w.winfo_children())
        except Exception:
            children = []
        for ch in children:
            try:
                # 仅处理我们创建的卡片根（ttk.Frame），它在 create_character_card 中挂了若干属性
                if hasattr(ch, '_model_ref'):
                    try:
                        Cards.refresh_character_card(self.app, ch)
                    except Exception:
                        pass
                    break
            except Exception:
                pass

    def _render_side(self, is_enemy: bool):
        panel = self._enemy_panel if is_enemy else self._ally_panel
        overlay = self._enemy_overlay if is_enemy else self._ally_overlay
        grid_holder = self._enemy_grid if is_enemy else self._ally_grid
        items = (self._enemies if is_enemy else self._allies)
        wraps = (self._enemy_wraps if is_enemy else self._ally_wraps)
        if not (panel and overlay and grid_holder):
            return

        # Capture old positions (overlay-relative) for slide animation
        old_pos = {}
        try:
            ov_rx0, ov_ry0 = int(overlay.winfo_rootx()), int(overlay.winfo_rooty())
        except Exception:
            ov_rx0 = ov_ry0 = 0
        for t, w in list(wraps.items()):
            try:
                info = w.place_info()
                if info:
                    x = int(float(info.get('x', '0')))
                    y = int(float(info.get('y', '0')))
                else:
                    x = int(w.winfo_rootx()) - ov_rx0
                    y = int(w.winfo_rooty()) - ov_ry0
                old_pos[t] = (x, y)
            except Exception:
                pass

        # Build/Reuse anchors (mirrored per side) without destroying existing rows to reduce flicker
        cols = self.COLS
        total = len(items)
        rows = min(5, max(1, math.ceil(total / cols)))
        anchors_by_idx: Dict[int, tk.Frame] = {}

        existing_rows = list(grid_holder.winfo_children())

        def ensure_row(idx: int):
            if idx < len(existing_rows):
                rf = existing_rows[idx]
                # make sure rf has inner and anchors list
                inner = getattr(rf, '_inner', None)
                if inner is None:
                    inner = ttk.Frame(rf)
                    rf._inner = inner  # type: ignore[attr-defined]
                # align per side
                inner.grid(row=0, column=0, sticky=('e' if (not is_enemy) else 'w'))
                anchors = getattr(rf, '_anchors', None)
                if anchors is None:
                    anchors = []
                    rf._anchors = anchors  # type: ignore[attr-defined]
            else:
                rf = ttk.Frame(grid_holder)
                rf.pack(fill=tk.X, pady=2)
                rf.grid_columnconfigure(0, weight=1)
                inner = ttk.Frame(rf)
                inner.grid(row=0, column=0, sticky=('e' if (not is_enemy) else 'w'))
                rf._inner = inner  # type: ignore[attr-defined]
                anchors = []
                rf._anchors = anchors  # type: ignore[attr-defined]
                existing_rows.append(rf)
            # ensure anchors count
            while len(anchors) < cols:
                a = tk.Frame(inner, width=self.CARD_W, height=self.CARD_H)
                a.grid(row=0, column=len(anchors), padx=2, sticky='n')
                try:
                    a.grid_propagate(False)
                except Exception:
                    pass
                anchors.append(a)
            # show row if hidden
            if rf.winfo_manager() != 'pack':
                rf.pack(fill=tk.X, pady=2)
            return rf

        for r in range(rows):
            rf = ensure_row(r)
            row_anchors: List[tk.Frame] = getattr(rf, '_anchors')  # type: ignore[attr-defined]
            # map global indices to anchors, mirrored per side
            row_items = items[r*cols : (r+1)*cols]
            for j, _tok in enumerate(row_items):
                gidx = r * cols + j
                vis_col = (j if is_enemy else (cols - 1 - j))
                anchors_by_idx[gidx] = row_anchors[vis_col]

        # hide extra rows if any
        for idx in range(rows, len(existing_rows)):
            try:
                existing_rows[idx].pack_forget()
            except Exception:
                pass

        # ensure geometry (limit scope to this panel)
        try:
            panel.update_idletasks()
            grid_holder.update_idletasks()
        except Exception:
            pass

        # Place or animate wrappers to anchors
        try:
            base_rx, base_ry = int(overlay.winfo_rootx()), int(overlay.winfo_rooty())
        except Exception:
            base_rx = base_ry = 0

        # Remove wrappers for tokens no longer present
        for t, w in list(wraps.items()):
            if t not in items:
                try:
                    w.destroy()
                except Exception:
                    pass
                wraps.pop(t, None)

    # Create/position wrappers for current items
        any_slide = False
        for idx, tok in enumerate(items):
            anc = anchors_by_idx.get(idx)
            if not anc:
                continue
            x1, y1 = int(anc.winfo_rootx()), int(anc.winfo_rooty())
            rx, ry = x1 - base_rx, y1 - base_ry
            w = wraps.get(tok)
            created = False
            if not w:
                # 使用应用的固定描边粗细，避免选中时粗细跳变
                border_thick = int(getattr(self.app, '_border_default', 3)) if getattr(self, 'app', None) is not None else 3
                w = tk.Frame(overlay, width=self.CARD_W, height=self.CARD_H,
                             highlightthickness=border_thick, highlightbackground="#bbb",
                             bg=("#f7f7f7"))
                try:
                    w.pack_propagate(False)
                except Exception:
                    pass
                # 标注归属，供点击处理动态解析当前索引
                try:
                    setattr(w, '_token_ref', tok)
                    setattr(w, '_is_enemy', bool(is_enemy))
                except Exception:
                    pass
                # 如果可用 app，则使用真实卡片，否则保留占位方块
                if getattr(self, 'app', None) is not None:
                    # 清空并挂载卡片
                    for ch in list(w.winfo_children()):
                        try:
                            ch.destroy()
                        except Exception:
                            pass
                    try:
                        card = Cards.create_character_card(self.app, w, tok, idx+1, is_enemy=is_enemy)
                        card.pack(fill=tk.BOTH, expand=True)
                        # 绑定点击到卡片所有子控件，避免内部控件吞掉事件
                        try:
                            def _skip_eq(widget):
                                return bool(getattr(widget, '_is_equipment_slot', False))
                            handler = self._click_handler_for(w)
                            self._bind_click_recursive(card, handler, skip_predicate=_skip_eq)
                        except Exception:
                            pass
                    except Exception:
                        # 回退到简单色块
                        sq = tk.Frame(w, bg=("#e74c3c" if is_enemy else "#3498db"))
                        sq.place(relx=0.5, rely=0.5, anchor='center', width=self.CARD_W-16, height=self.CARD_H-16)
                else:
                    # demo 模式：仅占位色块
                    sq = tk.Frame(w, bg=("#e74c3c" if is_enemy else "#3498db"))
                    sq.place(relx=0.5, rely=0.5, anchor='center', width=self.CARD_W-16, height=self.CARD_H-16)
                wraps[tok] = w
                created = True

            def _final_place(wrp=w, lx=rx, ly=ry):
                try:
                    wrp.place(in_=overlay, x=int(lx), y=int(ly), width=self.CARD_W, height=self.CARD_H)
                except Exception:
                    try:
                        wrp.place(x=int(lx), y=int(ly), width=self.CARD_W, height=self.CARD_H)
                    except Exception:
                        pass

            # bind click on first creation（使用动态索引处理器，不会因重排/转场失效）
            if created:
                try:
                    w.configure(cursor='hand2')
                except Exception:
                    pass
                try:
                    handler = self._click_handler_for(w)
                    w.bind('<Button-1>', handler)
                except Exception:
                    pass
                _final_place()
            else:
                # slide from old_pos if available; only animate when position changes
                x0, y0 = old_pos.get(tok, (rx, ry))
                if x0 != rx or y0 != ry:
                    any_slide = True
                    self._slide_to(w, x0, y0, rx, ry, duration_ms=160, steps=12, on_done=_final_place)
                else:
                    _final_place()

        # store side snapshot and bind (once) to isolated reposition handler
        side = 'enemy' if is_enemy else 'ally'
        self._side_state[side] = {
            'overlay': overlay,
            'panel': panel,
            'grid': grid_holder,
            'anchors': anchors_by_idx,
            'order': list(items),  # stable order snapshot
            'wraps': wraps,
        }

        def _call_repos(_e=None, which=side):
            try:
                self._reposition_side(which)
            except Exception:
                pass

        try:
            if side == 'ally' and not self._ally_bound:
                grid_holder.bind('<Configure>', _call_repos)
                panel.bind('<Configure>', _call_repos)
                self._ally_bound = True
            elif side == 'enemy' and not self._enemy_bound:
                grid_holder.bind('<Configure>', _call_repos)
                panel.bind('<Configure>', _call_repos)
                self._enemy_bound = True
        except Exception:
            pass

        # export wrappers for external highlighting (1-based indices)
        try:
            if side == 'ally' and self._export_ally_wraps is not None:
                self._export_ally_wraps.clear()
                for i, tok in enumerate(items, start=1):
                    w = wraps.get(tok)
                    if w:
                        self._export_ally_wraps[i] = w
            if side == 'enemy' and self._export_enemy_wraps is not None:
                self._export_enemy_wraps.clear()
                for i, tok in enumerate(items, start=1):
                    w = wraps.get(tok)
                    if w:
                        self._export_enemy_wraps[i] = w
        except Exception:
            pass

        # Avoid endpoint flash when slides are animating
        if not any_slide:
            try:
                self._reposition_side(side)
            except Exception:
                pass

    def _reposition_side(self, side: str):
        st = self._side_state.get(side) or {}
        overlay = st.get('overlay')
        anchors_by_idx: Dict[int, tk.Frame] = st.get('anchors') or {}
        order: List[object] = st.get('order') or []
        wraps: Dict[object, tk.Frame] = st.get('wraps') or {}
        if not overlay:
            return
        try:
            brx, bry = int(overlay.winfo_rootx()), int(overlay.winfo_rooty())
        except Exception:
            brx = bry = 0
        for idx, tok in enumerate(order):
            anc = anchors_by_idx.get(idx)
            w = wraps.get(tok)
            if not (anc and w):
                continue
            if getattr(w, '_shaking', False) or getattr(w, '_sliding', False):
                continue
            try:
                ax, ay = int(anc.winfo_rootx()) - brx, int(anc.winfo_rooty()) - bry
                w.place_configure(x=int(ax), y=int(ay), width=self.CARD_W, height=self.CARD_H)
            except Exception:
                pass

    def _sync_allies_from_game(self):
        """Resync allies from app.controller.game.player.board and re-render.
        Safe no-op if context is missing.
        """
        try:
            game = getattr(getattr(self.app, 'controller', None), 'game', None)
            if not game:
                return
            board = list(getattr(getattr(game, 'player', None), 'board', []) or [])
            self.set_allies(board)
        except Exception:
            pass

    def _click_handler_for(self, wrapper: tk.Widget):
        """Return an event handler that computes current index from token/side at click time."""
        def _handler(_evt=None):
            try:
                tok = getattr(wrapper, '_token_ref', None)
                is_enemy = bool(getattr(wrapper, '_is_enemy', False))
                items = (self._enemies if is_enemy else self._allies)
                idx = items.index(tok) + 1 if tok in items else None
                if not idx:
                    return
                if is_enemy and callable(self._on_enemy_click):
                    self._on_enemy_click(idx)
                elif (not is_enemy) and callable(self._on_ally_click):
                    self._on_ally_click(idx)
            except Exception:
                pass
        return _handler

    # --- basic animations ---
    def _bind_click_recursive(self, root: tk.Widget, handler, skip_predicate=None):
        """Bind left-click to root and all descendants, unless skip_predicate(widget) is True.
        Tkinter事件不会自动冒泡到父容器，此处手动为子控件也绑定同一处理函数。
        """
        try:
            if not root:
                return
            if not (callable(handler)):
                return
            def _should_skip(w):
                try:
                    return bool(skip_predicate(w)) if callable(skip_predicate) else False
                except Exception:
                    return False
            if not _should_skip(root):
                try:
                    root.bind('<Button-1>', handler, add='+')
                except Exception:
                    pass
            # 遍历子节点
            try:
                children = list(getattr(root, 'winfo_children', lambda: [])())
            except Exception:
                children = []
            for ch in children:
                self._bind_click_recursive(ch, handler, skip_predicate)
        except Exception:
            pass

    def _slide_to(self, widget: tk.Widget, x0: int, y0: int, x1: int, y1: int,
                  duration_ms: int = 160, steps: int = 12, on_done=None):
        if steps <= 0:
            steps = 1
        dx = (x1 - x0) / steps
        dy = (y1 - y0) / steps

        def step(i=0, cx=x0, cy=y0):
            nx = int(round(cx + dx))
            ny = int(round(cy + dy))
            try:
                widget.place_configure(x=nx, y=ny)
            except Exception:
                pass
            if i + 1 >= steps:
                if on_done:
                    try:
                        on_done()
                    except Exception:
                        pass
                try:
                    widget._sliding = False  # type: ignore[attr-defined]
                except Exception:
                    pass
                return
            self.root.after(max(8, duration_ms // steps), lambda: step(i + 1, nx, ny))

        try:
            widget.place(x=x0, y=y0)
        except Exception:
            pass
        try:
            widget._sliding = True  # type: ignore[attr-defined]
        except Exception:
            pass
        step()

    def _shake_widget(self, widget: tk.Widget, amplitude: int = 10, cycles: int = 8, interval_ms: int = 18):
        try:
            info = widget.place_info()
            x0 = int(float(info.get('x', 0)))
            y0 = int(float(info.get('y', 0)))
        except Exception:
            x0 = y0 = 0

        def do_cycle(i=0):
            if i >= cycles:
                try:
                    widget.place_configure(x=x0, y=y0)
                    widget._shaking = False  # type: ignore[attr-defined]
                except Exception:
                    pass
                return
            dx = amplitude if (i % 2 == 0) else -amplitude
            try:
                widget.place_configure(x=x0 + dx, y=y0)
            except Exception:
                pass
            self.root.after(interval_ms, lambda: do_cycle(i + 1))

        try:
            widget._shaking = True  # type: ignore[attr-defined]
        except Exception:
            pass
