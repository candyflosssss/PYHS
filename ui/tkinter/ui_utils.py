"""UI helper utilities for Tkinter UI moved from `yyy/ui/ui_utils.py`.
This file keeps tooltip helpers and text cleaning local to the tkinter package.
"""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Callable

_ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
_r_prefix = re.compile(r'^[rR]\s*\d+\s*[·:\-\s]*')


def clean_ansi(name: str) -> str:
    try:
        s = _ansi_escape.sub('', str(name))
        s = _r_prefix.sub('', s)
        return s.strip()
    except Exception:
        return str(name)


def attach_tooltip(widget: tk.Widget, text_provider: Callable[[], str] | str):
    tip = {'win': None}

    def show(_evt=None):
        try:
            text = text_provider() if callable(text_provider) else str(text_provider)
            if not text or tip['win'] is not None:
                return
            x = widget.winfo_rootx() + 10
            y = widget.winfo_rooty() + widget.winfo_height() + 6
            tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            lbl = ttk.Label(tw, text=text, relief='solid', borderwidth=1, padding=6, background='#ffffe0')
            lbl.pack()
            tip['win'] = tw
        except Exception:
            pass

    def hide(_evt=None):
        w = tip.get('win')
        if w is not None:
            try:
                w.destroy()
            except Exception:
                pass
            tip['win'] = None

    widget.bind('<Enter>', show)
    widget.bind('<Leave>', hide)


def attach_tooltip_deep(root_widget: tk.Widget, text_provider: Callable[[], str] | str):
    tip = {'win': None}

    def show(_evt=None):
        try:
            text = text_provider() if callable(text_provider) else str(text_provider)
            if not text:
                return
            if tip['win'] is None:
                x = root_widget.winfo_rootx() + 10
                y = root_widget.winfo_rooty() + root_widget.winfo_height() + 6
                tw = tk.Toplevel(root_widget)
                tw.wm_overrideredirect(True)
                tw.wm_geometry(f"+{x}+{y}")
                lbl = ttk.Label(tw, text=text, relief='solid', borderwidth=1, padding=6, background='#ffffe0')
                lbl.pack()
                tip['win'] = tw
                # 周期性巡检，兜底隐藏（防止未触发 Leave/Motion 时残留）
                def tick():
                    try:
                        if tip['win'] is None:
                            return
                        rx, ry = root_widget.winfo_rootx(), root_widget.winfo_rooty()
                        rw, rh = root_widget.winfo_width(), root_widget.winfo_height()
                        px, py = root_widget.winfo_pointerx(), root_widget.winfo_pointery()
                        inside = (rx <= px <= rx + rw) and (ry <= py <= ry + rh)
                        if (not inside) or (not root_widget.winfo_ismapped()):
                            hide_if_outside()
                            return
                    except Exception:
                        hide_if_outside()
                        return
                    # 继续下一次巡检
                    try:
                        root_widget.after(120, tick)
                    except Exception:
                        pass
                try:
                    root_widget.after(120, tick)
                except Exception:
                    pass
        except Exception:
            pass

    def hide_if_outside(_evt=None):
        try:
            rx, ry = root_widget.winfo_rootx(), root_widget.winfo_rooty()
            rw, rh = root_widget.winfo_width(), root_widget.winfo_height()
            px, py = root_widget.winfo_pointerx(), root_widget.winfo_pointery()
            inside = (rx <= px <= rx + rw) and (ry <= py <= ry + rh)
            if not inside and tip['win'] is not None:
                w = tip.get('win')
                if w is not None:
                    try:
                        w.destroy()
                    except Exception:
                        pass
                    tip['win'] = None
        except Exception:
            w = tip.get('win')
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass
                tip['win'] = None

    def bind_recursive(w: tk.Widget):
        try:
            w.bind('<Enter>', show, add='+')
            w.bind('<Leave>', hide_if_outside, add='+')
            w.bind('<Motion>', hide_if_outside, add='+')
        except Exception:
            pass
        for ch in getattr(w, 'winfo_children', lambda: [])():
            bind_recursive(ch)

    bind_recursive(root_widget)

    # 当顶层窗口失焦/离开/销毁时强制隐藏
    try:
        top = root_widget.winfo_toplevel()
        top.bind('<FocusOut>', lambda e: hide_if_outside(), add='+')
        top.bind('<Leave>', lambda e: hide_if_outside(), add='+')
        root_widget.bind('<Destroy>', lambda e: hide_if_outside(), add='+')
    except Exception:
        pass
