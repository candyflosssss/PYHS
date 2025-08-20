"""Resource list rendering helpers for Tkinter UI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any
from . import ui_utils as U


def render_resources(app, container: tk.Widget):
    """最小化刷新资源按钮：尽可能复用已有按钮，避免整块销毁/重建。"""
    # 目标资源文本列表
    try:
        s = app.controller.game.get_state()
        res = s.get('resources', [])
    except Exception:
        res = []

    def fmt_resource(r) -> str:
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
        return f"{clean}" + (f" ({rtype})" if rtype else "")

    target_texts = [fmt_resource(r) for r in res]

    # 收集当前按钮
    children = [w for w in container.winfo_children() if isinstance(w, ttk.Button)]

    # 若完全为空且无资源，显示占位；否则清掉占位
    def ensure_placeholder(show: bool):
        # 移除所有非按钮子项（可能是之前的占位标签）
        for w in list(container.winfo_children()):
            if not isinstance(w, ttk.Button):
                w.destroy()
        if show:
            ttk.Label(container, text="(空)", foreground="#888").pack(anchor=tk.W)

    if not target_texts:
        # 无资源：如已有按钮则移除，仅保留占位
        for btn in children:
            btn.destroy()
        ensure_placeholder(True)
        return

    # 有资源：保证没有占位并按需增删改按钮
    ensure_placeholder(False)

    # 扩充或裁剪按钮数量
    if len(children) < len(target_texts):
        for _ in range(len(target_texts) - len(children)):
            btn = ttk.Button(container, text="", width=18, style="Tiny.TButton")
            btn.pack(side=tk.TOP, anchor=tk.W, padx=2, pady=2)
            children.append(btn)
    elif len(children) > len(target_texts):
        # 从末尾移除多余
        for btn in children[len(target_texts):]:
            btn.destroy()
        children = children[:len(target_texts)]

    # 更新文本与命令（仅当变化时）
    for i, (btn, text) in enumerate(zip(children, target_texts), start=1):
        try:
            if btn.cget('text') != text:
                btn.configure(text=text)
            # 重新绑定命令以确保索引正确
            btn.configure(command=(lambda idx=i: app._pick_resource(idx)))
        except Exception:
            pass
