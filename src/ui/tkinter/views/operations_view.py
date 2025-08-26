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

    def mount(self):
        if self._subs:
            return
        # 资源/背包/装备变更会影响操作栏可用性
        self._subs.append(('inventory_changed', subscribe_event('inventory_changed', self._on_any)))
        self._subs.append(('resource_changed', subscribe_event('resource_changed', self._on_any)))
        for evt in ('resource_added','resource_removed','resources_cleared','resources_reset','resources_changed'):
            self._subs.append((evt, subscribe_event(evt, self._on_any)))
        self._subs.append(('equipment_changed', subscribe_event('equipment_changed', self._on_any)))

    def unmount(self):
        for evt, cb in (self._subs or []):
            try:
                unsubscribe_event(evt, cb)
            except Exception:
                pass
        self._subs.clear()

    def _on_any(self, _evt: str, _payload: dict):
        try:
            # 抑制窗口期间不渲染
            if getattr(self.app, '_suspend_ui_updates', False):
                setattr(self.app, '_pending_ops_refresh', True)
                return
            self.render(self.app.frm_operations)
        except Exception:
            pass

    # --- rendering ---
    def render(self, container):
        # 清空
        for ch in list(container.winfo_children()):
            try:
                ch.destroy()
            except Exception:
                pass
        sel = getattr(self.app, 'selected_member_index', None)
        if not sel:
            return
        ops = ttk.Frame(container)
        ops.grid(row=0, column=0, sticky='w', padx=6, pady=6)
        # 攻击
        ttk.Button(ops, text="攻击", command=lambda: getattr(self.app, 'selection', self.app).begin_skill(sel, 'attack'), style="Tiny.TButton").pack(side=tk.LEFT, padx=4)
        # 角色技能
        try:
            board = self.app.controller.game.player.board
            m = board[sel - 1]
            skills = list(getattr(m, 'skills', []) or [])
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
                b = ttk.Button(ops, text=text, command=_make_cmd(), style="Tiny.TButton")
                b.pack(side=tk.LEFT, padx=2)
                try:
                    desc = (rec or {}).get('desc') if rec else None
                    if desc:
                        U.attach_tooltip_deep(b, lambda d=desc: d)
                except Exception:
                    pass

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
