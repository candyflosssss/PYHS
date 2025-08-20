"""Resource list rendering helpers for Tkinter UI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any
from . import ui_utils as U


def render_resources(app, container: tk.Widget):
    # 清空容器
    for ch in list(container.winfo_children()):
        ch.destroy()
    app.selected_res_index = None
    try:
        s = app.controller.game.get_state()
        res = s.get('resources', [])
    except Exception:
        res = []
    if not res:
        ttk.Label(container, text="(空)", foreground="#888").pack(anchor=tk.W)
        return
    for i, r in enumerate(res, 1):
        try:
            if isinstance(r, dict):
                name = r.get('name') or r.get('title') or str(r)
                rtype = r.get('type')
            else:
                name = str(r)
                rtype = None
        except Exception:
            name = str(r)
            rtype = None
        try:
            clean = U.clean_ansi(name)
        except Exception:
            clean = name
        text = f"{clean}" + (f" ({rtype})" if rtype else "")
        btn = ttk.Button(container, text=text, width=18, command=lambda idx=i: app._pick_resource(idx), style="Tiny.TButton")
        btn.pack(side=tk.TOP, anchor=tk.W, padx=2, pady=2)
