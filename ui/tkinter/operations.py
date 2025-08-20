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
    ttk.Button(ops, text="攻击 (atk)", command=lambda: app._op_attack(sel), style="Tiny.TButton").pack(side=tk.LEFT, padx=4)
    ttk.Button(ops, text="装备/管理", command=lambda: app._op_manage_equipment(sel), style="Tiny.TButton").pack(side=tk.LEFT, padx=4)
