"""Operations toolbar rendering for selected member."""
from __future__ import annotations
from src import app_config as CFG

import tkinter as tk
from tkinter import ttk
from typing import Any
import os, json
from . import ui_utils as U

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
            # map id -> record
            _SKILL_CATALOG_CACHE = { rec.get('id'): rec for rec in data['skills'] if isinstance(rec, dict) and rec.get('id') }
            return _SKILL_CATALOG_CACHE
    except Exception:
        pass
    _SKILL_CATALOG_CACHE = {}
    return _SKILL_CATALOG_CACHE


def render_operations(app, container: tk.Widget):
    for ch in list(container.winfo_children()):
        ch.destroy()
    sel = getattr(app, 'selected_member_index', None)
    if not sel:
        # 未选目标时，操作栏为空
        return
    ops = ttk.Frame(container)
    ops.grid(row=0, column=0, sticky='w', padx=6, pady=6)
    # 攻击 (保留)。若进入技能选择流程，则不直接执行
    ttk.Button(ops, text="攻击", command=lambda: app.begin_skill(sel, 'attack'), style="Tiny.TButton").pack(side=tk.LEFT, padx=4)
    # 角色技能（来自 m.skills）
    try:
        board = app.controller.game.player.board
        m = board[sel - 1]
        skills = list(getattr(m, 'skills', []) or [])
        # UI 兜底：若未携带 skills，则按 profession/tags 动态映射一次，避免旧场景无职业字段时技能不显示
        if not skills:
            import os, json
            prof = getattr(m, 'profession', None)
            # 若 profession 缺失，尝试从 tags 猜测
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
                    data = None
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        cand = data.get(str(prof).lower())
                        if isinstance(cand, list) and cand:
                            skills = list(cand)
                except Exception:
                    # 简单内置回退
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
            def _make_cmd(name=sk, _sid=sid):
                def _run():
                    # 统一入口
                    app.begin_skill(sel, (_sid or name))
                return _run
            b = ttk.Button(ops, text=text, command=_make_cmd(sid or sk), style="Tiny.TButton")
            b.pack(side=tk.LEFT, padx=2)
            # 悬浮说明：来自 skills_catalog.json 的 desc
            try:
                desc = (rec or {}).get('desc') if rec else None
                if desc:
                    U.attach_tooltip_deep(b, lambda d=desc: d)
            except Exception:
                pass

    # 若处于目标会话：内联候选区（不新开窗）
    te = getattr(app, 'target_engine', None)
    ctx = getattr(te, 'ctx', None) if te else None
    if ctx and ctx.state in ('Selecting','Confirmable'):
        ttk.Label(ops, text=" | 目标:", foreground="#666").pack(side=tk.LEFT, padx=(8, 2))
        wrap = ttk.Frame(ops)
        wrap.pack(side=tk.LEFT)
        # 渲染候选 chip 按钮；单选或多选都使用 toggle 行为
        for tok in (ctx.candidates or []):
            txt = tok
            try:
                if tok.startswith('e'):
                    i = int(tok[1:])
                    e = app.controller.game.enemies[i-1]
                    txt = f"{tok}:{getattr(e,'name',tok)}"
                elif tok.startswith('m'):
                    i = int(tok[1:])
                    m = app.controller.game.player.board[i-1]
                    txt = f"{tok}:{getattr(m,'name',tok)}"
            except Exception:
                pass
            active = tok in (ctx.selected or set())
            style = "Tiny.TButton"
            b = ttk.Button(wrap, text=txt, style=style, command=(lambda t=tok: app._toggle_target_token(t)))
            b.pack(side=tk.LEFT, padx=2)
        # 确认/取消
        ready = te.is_ready()
        ttk.Button(ops, text="确定", command=app._confirm_skill, state=(tk.NORMAL if ready else tk.DISABLED), style="Tiny.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(ops, text="取消", command=app._cancel_skill, style="Tiny.TButton").pack(side=tk.LEFT)
