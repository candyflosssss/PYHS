from __future__ import annotations

import json
from typing import Callable

import tkinter as tk
from tkinter import ttk

from src import app_config as CFG
from .. import ui_utils as U

try:
    from src.core.events import subscribe as subscribe_event, unsubscribe as unsubscribe_event
except Exception:  # pragma: no cover
    def subscribe_event(*_a, **_k):  # type: ignore
        return None
    def unsubscribe_event(*_a, **_k):  # type: ignore
        return None


_SKILL_CATALOG_CACHE = None

def _load_skill_catalog():
    global _SKILL_CATALOG_CACHE
    if _SKILL_CATALOG_CACHE is not None:
        return _SKILL_CATALOG_CACHE
    try:
        p = CFG.skills_catalog_path()
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get('skills'), list):
            _SKILL_CATALOG_CACHE = { rec.get('id'): rec for rec in data['skills'] if isinstance(rec, dict) and rec.get('id') }
            return _SKILL_CATALOG_CACHE
    except Exception:
        pass
    _SKILL_CATALOG_CACHE = {}
    return _SKILL_CATALOG_CACHE


class OperationsView:
    """操作栏视图：自订阅、自治渲染。

    - 订阅 inventory/resource/equipment 相关事件，必要时主动 render。
    - 选中/目标变更由 SelectionController 直接调用 render（无事件总线时）。
    """

    def __init__(self, app):
        self.app = app
        self._subs: list[tuple[str, Callable]] = []
        # hover popup
        self._popup = None           # type: ignore[assignment]
        self._popup_for_index = None # type: ignore[assignment]
        self._hide_job = None        # type: ignore[assignment]
        self._popup_anchor = None    # type: ignore[assignment]
        self._global_click_bind_id = None  # type: ignore[assignment]

    def mount(self):
        if self._subs:
            return
        # 资源/背包/装备变更会影响操作栏可用性
        self._subs.append(('inventory_changed', subscribe_event('inventory_changed', self._on_any)))
        self._subs.append(('resource_changed', subscribe_event('resource_changed', self._on_any)))
        for evt in ('resource_added','resource_removed','resources_cleared','resources_reset','resources_changed'):
            self._subs.append((evt, subscribe_event(evt, self._on_any)))
        self._subs.append(('equipment_changed', subscribe_event('equipment_changed', self._on_any)))
        # 体力变化会影响按钮可用性
        self._subs.append(('stamina_changed', subscribe_event('stamina_changed', self._on_any)))
        # 全局点击：点击非弹窗区域时隐藏操作栏
        try:
            if not self._global_click_bind_id:
                bid = self.app.root.bind('<Button-1>', self._on_global_click, add='+')
                self._global_click_bind_id = bid
        except Exception:
            self._global_click_bind_id = None

    def unmount(self):
        for evt, cb in (self._subs or []):
            try:
                unsubscribe_event(evt, cb)
            except Exception:
                pass
        self._subs.clear()
        # 解除全局点击绑定
        try:
            if self._global_click_bind_id:
                self.app.root.unbind('<Button-1>', self._global_click_bind_id)
        except Exception:
            pass
        self._global_click_bind_id = None
        # close popup if any
        try:
            self.hide_popup(force=True)
        except Exception:
            pass

    def _is_descendant(self, child, ancestor) -> bool:
        try:
            w = child
            while w is not None:
                if w is ancestor:
                    return True
                w = getattr(w, 'master', None)
        except Exception:
            pass
        return False

    def _on_global_click(self, event):
        """在根窗口任何点击时触发：若点击发生在弹窗/锚点之外，则关闭操作栏。"""
        try:
            if not self.is_popup_visible():
                return
            w = getattr(event, 'widget', None)
            pop = self._popup
            anch = self._popup_anchor
            if w is None or pop is None:
                self.hide_popup(force=True)
                return
            # 点击在弹窗内：忽略
            if self._is_descendant(w, pop):
                return
            # 点击在锚点（或其子孙）内：忽略（由卡片自身逻辑决定是否切换弹窗）
            if anch is not None and self._is_descendant(w, anch):
                return
            # 其他任何区域：关闭
            self.hide_popup(force=True)
        except Exception:
            try:
                self.hide_popup(force=True)
            except Exception:
                pass

    def _on_any(self, _evt: str, _payload: dict):
        try:
            # 抑制窗口期间不渲染
            if getattr(self.app, '_suspend_ui_updates', False):
                setattr(self.app, '_pending_ops_refresh', True)
                return
            self.render(self.app.frm_operations)
            # 若弹窗正在显示，刷新其内容以反映体力/装备变化
            try:
                if self._popup and self._popup_for_index and self._popup_anchor:
                    self.show_popup(self._popup_for_index, self._popup_anchor)
            except Exception:
                pass
        except Exception:
            pass

    # --- rendering ---
    def render(self, container):
        # 底部操作栏已废弃：清空容器，不显示任何内容
        for ch in list(container.winfo_children()):
            try:
                ch.destroy()
            except Exception:
                pass
        return
        # 旧实现保留在下方（如需回退可启用）
        sel = getattr(self.app, 'selected_member_index', None)
        if not sel:
            return
        ops = ttk.Frame(container)
        ops.grid(row=0, column=0, sticky='w', padx=6, pady=6)
        # 攻击（根据体力禁用；tooltip 显示体力消耗）
        atk_btn = ttk.Button(ops, text="攻击", command=lambda: getattr(self.app, 'selection', self.app).begin_skill(sel, 'attack'), style="Tiny.TButton")
        try:
            board = self.app.controller.game.player.board
            m = board[sel - 1]
            from src import settings as S
            atk_cost = int(getattr(S, 'get_skill_cost')('attack', 1))
            if int(getattr(m, 'stamina', 0)) < atk_cost:
                atk_btn.config(state=tk.DISABLED)
            U.attach_tooltip_deep(atk_btn, lambda c=atk_cost: f"需要体力 {c}")
        except Exception:
            pass
        atk_btn.pack(side=tk.LEFT, padx=4)
        # 角色技能
        try:
            board = self.app.controller.game.player.board
            m = board[sel - 1]
            skills = list(getattr(m, 'skills', []) or [])
            # 装备授予的主动技能（左手/右手/盔甲）
            try:
                eq = getattr(m, 'equipment', None)
                for it in (getattr(eq, 'left_hand', None), getattr(eq, 'right_hand', None), getattr(eq, 'armor', None)):
                    if it and getattr(it, 'active_skills', None):
                        for sid in it.active_skills:
                            if sid and sid not in skills:
                                skills.append(sid)
            except Exception:
                pass
            if not skills:
                prof = getattr(m, 'profession', None)
                if not prof:
                    try:
                        tags = [str(t).lower() for t in (getattr(m, 'tags', []) or [])]
                        for hint in ('warrior','mage','tank','priest','healer'):
                            if hint in tags:
                                prof = 'priest' if hint == 'healer' else hint
                                break
                    except Exception:
                        prof = None
                if prof:
                    try:
                        p = CFG.profession_skills_path()
                        with open(p, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, dict):
                            cand = data.get(str(prof).lower())
                            if isinstance(cand, list) and cand:
                                skills = list(cand)
                    except Exception:
                        fallback = {
                            'warrior': ['sweep','drain'],
                            'mage': ['arcane_missiles'],
                            'tank': ['taunt'],
                            'priest': ['basic_heal'],
                        }
                        skills = list(fallback.get(str(prof).lower(), []))
        except Exception:
            skills = []
        if skills:
            catalog = _load_skill_catalog()
            ttk.Label(ops, text="技能:", foreground="#555").pack(side=tk.LEFT, padx=(12, 4))
            for sk in skills:
                sid = None
                label = None
                rec = None
                if isinstance(sk, dict):
                    sid = sk.get('id') or sk.get('name')
                    label = sk.get('label') or sk.get('name')
                    rec = catalog.get(sid) if sid else None
                elif isinstance(sk, str):
                    sid = sk
                    rec = catalog.get(sid) if sid else None
                    if rec:
                        label = rec.get('name_cn') or rec.get('name_en') or label or sid
                text = label or (sid if sid else str(sk))
                def _make_cmd(name0=sk, _sid0=sid):
                    def _run():
                        getattr(self.app, 'selection', self.app).begin_skill(sel, (_sid0 or name0))
                    return _run
                # cost & enable state
                cost = 1
                try:
                    from src import settings as S
                    cost = int(getattr(S, 'get_skill_cost')(sid or text, 1))
                except Exception:
                    pass
                b = ttk.Button(ops, text=f"{text}", command=_make_cmd(), style="Tiny.TButton")
                try:
                    if int(getattr(m, 'stamina', 0)) < cost:
                        b.config(state=tk.DISABLED)
                    U.attach_tooltip_deep(b, lambda c=cost, base=(rec or {}).get('desc') if rec else None: (f"需要体力 {c}\n" + base) if base else f"需要体力 {c}")
                except Exception:
                    # 原有描述提示
                    desc = (rec or {}).get('desc') if rec else None
                    if desc:
                        U.attach_tooltip_deep(b, lambda d=desc: d)
                b.pack(side=tk.LEFT, padx=2)

        # 目标会话内联区域
        te = getattr(self.app, 'target_engine', None)
        ctx = getattr(te, 'ctx', None) if te else None
        if ctx and ctx.state in ('Selecting','Confirmable'):
            ttk.Label(ops, text=" | 目标:", foreground="#666").pack(side=tk.LEFT, padx=(8, 2))
            wrap = ttk.Frame(ops)
            wrap.pack(side=tk.LEFT)
            for tok in (ctx.candidates or []):
                txt = tok
                try:
                    if tok.startswith('e'):
                        i = int(tok[1:])
                        e = self.app.controller.game.enemies[i-1]
                        txt = f"{tok}:{getattr(e,'name',tok)}"
                    elif tok.startswith('m'):
                        i = int(tok[1:])
                        m = self.app.controller.game.player.board[i-1]
                        txt = f"{tok}:{getattr(m,'name',tok)}"
                except Exception:
                    pass
                ttk.Button(wrap, text=txt, style="Tiny.TButton", command=(lambda t=tok: self.app.selection.toggle_token(t))).pack(side=tk.LEFT, padx=2)
        ready = te.is_ready() if te else False
        ttk.Button(ops, text="确定", command=getattr(self.app, 'selection', self.app).confirm_skill, state=(tk.NORMAL if ready else tk.DISABLED), style="Tiny.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(ops, text="取消", command=getattr(self.app, 'selection', self.app).cancel_skill, style="Tiny.TButton").pack(side=tk.LEFT)

    # --- hover popup API ---
    def _ensure_popup(self):
        if self._popup and tk.Toplevel.winfo_exists(self._popup):
            return self._popup
        try:
            win = tk.Toplevel(self.app.root)
            win.withdraw()
            win.overrideredirect(True)
            win.attributes('-topmost', True)
            frm = ttk.Frame(win, relief='ridge', borderwidth=1)
            frm.pack(fill=tk.BOTH, expand=True)
            win._content = frm  # type: ignore[attr-defined]
            self._popup = win
            return win
        except Exception:
            self._popup = None
            return None

    def is_popup_visible(self) -> bool:
        """当前操作弹窗是否处于可见状态。"""
        try:
            if not self._popup:
                return False
            # 可见：未 withdraw 且可见
            st = ''
            try:
                st = self._popup.state()  # type: ignore[attr-defined]
            except Exception:
                st = ''
            return (st != 'withdrawn') and bool(self._popup.winfo_viewable())
        except Exception:
            return False

    def show_popup(self, m_index: int, anchor_widget: tk.Widget):
        """显示针对某个友方的操作悬浮窗，锚定在其卡片附近。"""
        # 切场景/抑制期间不显示弹窗
        try:
            if getattr(self.app, '_suspend_ui_updates', False) or getattr(self.app, '_scene_overlay', None) is not None:
                return
        except Exception:
            pass
        self._popup_for_index = m_index
        self._popup_anchor = anchor_widget
        # 取消隐藏定时
        if self._hide_job:
            try:
                self.app.root.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None
        pop = self._ensure_popup()
        if not pop:
            return
        # 清空内容
        content = getattr(pop, '_content', None)
        for ch in list(getattr(content, 'winfo_children', lambda: [])()):
            try:
                ch.destroy()
            except Exception:
                pass
        # 标题
        try:
            board = self.app.controller.game.player.board
            m = board[m_index - 1]
            ttk.Label(content, text=getattr(m, 'name', f"m{m_index}"), style="TinyBold.TLabel").pack(anchor='w', padx=8, pady=(6, 2))
        except Exception:
            pass
        # 按钮区
        btns = ttk.Frame(content)
        btns.pack(fill=tk.X, expand=True, padx=6, pady=(0, 6))
        def _mk_btn(text: str, cmd, enabled: bool, tip: str | None = None):
            b = ttk.Button(btns, text=text, command=cmd, style="Tiny.TButton")
            state = tk.NORMAL if enabled else tk.DISABLED
            try:
                b.config(state=state)
            except Exception:
                pass
            if tip:
                try:
                    U.attach_tooltip_deep(b, lambda t=tip: t)
                except Exception:
                    pass
            b.pack(side=tk.LEFT, padx=2)
            return b
        # 攻击
        atk_cost = 1
        stamina = 0
        try:
            from src import settings as S
            atk_cost = int(S.get_skill_cost('attack', 1))
            board = self.app.controller.game.player.board
            m = board[m_index - 1]
            stamina = int(getattr(m, 'stamina', 0))
        except Exception:
            pass
        def _begin_and_refresh(sel=m_index, sk='attack'):
            getattr(self.app, 'selection', self.app).begin_skill(sel, sk)
            try:
                self.app.root.after(0, lambda: self.show_popup(sel, self._popup_anchor or anchor_widget))
            except Exception:
                pass
        # 攻击提示：体力 + 描述（若技能表有记录）
        try:
            rec_catalog = _load_skill_catalog()
            atk_desc = None
            arec = rec_catalog.get('attack') if isinstance(rec_catalog, dict) else None
            if arec:
                atk_desc = arec.get('desc')
            tip_txt = f"需要体力 {atk_cost}" + (f"\n{atk_desc}" if atk_desc else '')
        except Exception:
            tip_txt = f"需要体力 {atk_cost}"
        _mk_btn("攻击", lambda: _begin_and_refresh(m_index, 'attack'), stamina >= atk_cost, tip_txt)
        # 技能
        skills = []
        rec_catalog = _load_skill_catalog()
        try:
            board = self.app.controller.game.player.board
            m = board[m_index - 1]
            skills = list(getattr(m, 'skills', []) or [])
            # 装备主动
            try:
                eq = getattr(m, 'equipment', None)
                for it in (getattr(eq, 'left_hand', None), getattr(eq, 'right_hand', None), getattr(eq, 'armor', None)):
                    if it and getattr(it, 'active_skills', None):
                        for sid in it.active_skills:
                            if sid and sid not in skills:
                                skills.append(sid)
            except Exception:
                pass
            if not skills:
                prof = getattr(m, 'profession', None)
                if not prof:
                    try:
                        tags = [str(t).lower() for t in (getattr(m, 'tags', []) or [])]
                        for hint in ('warrior','mage','tank','priest','healer'):
                            if hint in tags:
                                prof = 'priest' if hint == 'healer' else hint
                                break
                    except Exception:
                        prof = None
                if prof:
                    try:
                        p = CFG.profession_skills_path()
                        with open(p, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, dict):
                            cand = data.get(str(prof).lower())
                            if isinstance(cand, list) and cand:
                                skills = list(cand)
                    except Exception:
                        fallback = {
                            'warrior': ['sweep','drain'],
                            'mage': ['arcane_missiles'],
                            'tank': ['taunt'],
                            'priest': ['basic_heal'],
                        }
                        skills = list(fallback.get(str(prof).lower(), []))
        except Exception:
            skills = []
        if skills:
            ttk.Label(content, text="技能:", foreground="#555").pack(anchor='w', padx=8, pady=(0, 2))
            row = ttk.Frame(content)
            row.pack(fill=tk.X, padx=6, pady=(0, 6))
            for sk in skills:
                sid = sk.get('id') if isinstance(sk, dict) else sk
                rec = rec_catalog.get(sid) if sid else None
                label = None
                if isinstance(sk, dict):
                    label = sk.get('label') or sk.get('name')
                if rec and not label:
                    label = rec.get('name_cn') or rec.get('name_en') or sid
                text = label or (sid or str(sk))
                cost = 1
                try:
                    from src import settings as S
                    cost = int(S.get_skill_cost(sid or text, 1))
                except Exception:
                    pass
                # 技能提示：体力 + 描述
                desc_txt = None
                try:
                    if rec:
                        desc_txt = rec.get('desc')
                except Exception:
                    desc_txt = None
                tip_txt = f"需要体力 {cost}" + (f"\n{desc_txt}" if desc_txt else '')
                _mk_btn(text, lambda sel=m_index, _sid=sid or text: _begin_and_refresh(sel, _sid), stamina >= cost, tip_txt)
        # 目标选择/确认区（如正在选择）
        te = getattr(self.app, 'target_engine', None)
        ctx = getattr(te, 'ctx', None) if te else None
        if ctx and ctx.state in ('Selecting','Confirmable') and self._popup_for_index == m_index:
            ttk.Label(content, text="目标:", foreground="#666").pack(anchor='w', padx=8)
            wrap = ttk.Frame(content)
            wrap.pack(fill=tk.X, padx=6, pady=(0, 6))
            for tok in (ctx.candidates or []):
                txt = tok
                try:
                    if tok.startswith('e'):
                        i = int(tok[1:]); e = self.app.controller.game.enemies[i-1]
                        txt = f"{tok}:{getattr(e,'name',tok)}"
                    elif tok.startswith('m'):
                        i = int(tok[1:]); m2 = self.app.controller.game.player.board[i-1]
                        txt = f"{tok}:{getattr(m2,'name',tok)}"
                except Exception:
                    pass
                def _toggle_and_refresh(t=tok, sel=m_index):
                    try:
                        self.app.selection.toggle_token(t)
                    finally:
                        try:
                            self.app.root.after(0, lambda: self.show_popup(sel, self._popup_anchor or anchor_widget))
                        except Exception:
                            pass
                ttk.Button(wrap, text=txt, style="Tiny.TButton", command=_toggle_and_refresh).pack(side=tk.LEFT, padx=2)
            ready = te.is_ready() if te else False
            ctrls = ttk.Frame(content)
            ctrls.pack(fill=tk.X, padx=6, pady=(0, 6))
            def _confirm_then_refresh(sel=m_index):
                try:
                    getattr(self.app, 'selection', self.app).confirm_skill()
                finally:
                    # 保持弹窗开启，并刷新其内容（按钮可用性/目标区会变化）
                    try:
                        self.app.root.after(0, lambda: self.show_popup(sel, self._popup_anchor or anchor_widget))
                    except Exception:
                        pass
            def _cancel_then_refresh(sel=m_index):
                try:
                    getattr(self.app, 'selection', self.app).cancel_skill()
                finally:
                    try:
                        self.app.root.after(0, lambda: self.show_popup(sel, self._popup_anchor or anchor_widget))
                    except Exception:
                        pass
            ttk.Button(ctrls, text="确定", command=_confirm_then_refresh, state=(tk.NORMAL if ready else tk.DISABLED), style="Tiny.TButton").pack(side=tk.LEFT, padx=(0,6))
            ttk.Button(ctrls, text="取消", command=_cancel_then_refresh, style="Tiny.TButton").pack(side=tk.LEFT)

        # 定位 popup 到 anchor 右上方（支持偏移设置）
        try:
            ax = anchor_widget.winfo_rootx(); ay = anchor_widget.winfo_rooty()
            aw = anchor_widget.winfo_width()
            cfg = getattr(self.app, '_ops_popup_cfg', {}) or {}
            off = cfg.get('offset', [4, 0])
            try:
                dx, dy = int(off[0]), int(off[1])
            except Exception:
                dx, dy = 4, 0
            pop.geometry(f"+{ax + aw + dx}+{ay + dy}")
            pop.deiconify(); pop.lift()
        except Exception:
            try:
                pop.deiconify(); pop.lift()
            except Exception:
                pass
        # 绑定隐藏策略：hover 模式使用延迟隐藏；click 模式不自动隐藏
        try:
            trig = (getattr(self.app, '_ops_popup_cfg', {}) or {}).get('trigger', 'click')
            if str(trig).lower() == 'hover':
                def _cancel_hide(_e=None):
                    if self._hide_job:
                        try:
                            self.app.root.after_cancel(self._hide_job)
                        except Exception:
                            pass
                    self._hide_job = None
                def _schedule_hide(_e=None):
                    if self._hide_job:
                        return
                    delay = int((getattr(self.app, '_ops_popup_cfg', {}) or {}).get('hide_delay_ms', 300))
                    self._hide_job = self.app.root.after(delay, lambda: self.hide_popup())
                pop.bind('<Enter>', _cancel_hide)
                pop.bind('<Leave>', _schedule_hide)
        except Exception:
            pass

    def hide_popup(self, force: bool = False):
        if not self._popup:
            return
        if self._hide_job and not force:
            try:
                self.app.root.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None
        try:
            self._popup.withdraw()
        except Exception:
            pass
        if force:
            # 强制隐藏时清空索引/锚点，便于点击同一角色时重新弹出
            try:
                self._popup_for_index = None
                self._popup_anchor = None
            except Exception:
                pass
