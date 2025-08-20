"""Operations toolbar rendering for selected member."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


def render_operations(app, container: tk.Widget):
    for ch in list(container.winfo_children()):
        ch.destroy()
    sel = getattr(app, 'selected_member_index', None)
    if not sel:
        ttk.Label(container, text="(未选择队员)", foreground="#666").grid(row=0, column=0, sticky='w', padx=6, pady=6)
        return
    ops = ttk.Frame(container)
    ops.grid(row=0, column=0, sticky='w', padx=6, pady=6)
    # 攻击/装备
    ttk.Button(ops, text="攻击 (atk)", command=lambda: app._op_attack(sel), style="Tiny.TButton").pack(side=tk.LEFT, padx=4)
    ttk.Button(ops, text="装备/管理", command=lambda: app._op_manage_equipment(sel), style="Tiny.TButton").pack(side=tk.LEFT, padx=4)
    # 角色技能（来自 m.skills）
    try:
        board = app.controller.game.player.board
        m = board[sel - 1]
        skills = list(getattr(m, 'skills', []) or [])
    except Exception:
        skills = []
    if skills:
        ttk.Label(ops, text="技能:", foreground="#555").pack(side=tk.LEFT, padx=(12, 4))
        for sk in skills:
            def _make_cmd(name=sk):
                def _run():
                    # 允许点击后进入选目标高亮流程（heal/attack 已在 app 中实现选择逻辑）
                    if name in ("basic_heal",):
                        app.selected_skill_name = name
                        app._select_skill(sel, "heal")
                    elif name in ("sweep","drain","taunt","arcane_missiles"):
                        app.selected_skill_name = name
                        # 这些技能大多目标为敌人或群体，直接发起或选敌
                        if name == 'sweep':
                            out = app._send(f"skill {name} m{sel}")
                            resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
                            app._after_cmd(resp)
                        elif name in ('drain','arcane_missiles'):
                            # 进入攻击式选择敌人
                            app._select_skill(sel, "attack")
                        elif name == 'taunt':
                            out = app._send(f"skill {name} m{sel}")
                            resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
                            app._after_cmd(resp)
                        else:
                            pass
                    else:
                        # 兜底为直接 skill name
                        out = app._send(f"skill {name} m{sel}")
                        resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
                        app._after_cmd(resp)
                return _run
            ttk.Button(ops, text=sk, command=_make_cmd(sk), style="Tiny.TButton").pack(side=tk.LEFT, padx=2)
