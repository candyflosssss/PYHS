from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Optional, Tuple

class TargetPickerDialog:
    """A simple modal dialog to pick a target token (eN/mN) for an action.
    Provide candidates as (token, label).
    """

    def __init__(self, parent: tk.Widget, title: str, candidates: List[Tuple[str, str]]):
        self.parent = parent
        self.title = title
        self.candidates = candidates
        self.result: Optional[str] = None

    def show(self) -> Optional[str]:
        top = tk.Toplevel(self.parent)
        top.title(self.title)
        top.transient(self.parent)
        top.grab_set()
        self.top = top
        # initial position near cursor
        try:
            self.parent.update_idletasks()
            sw, sh = self.parent.winfo_screenwidth(), self.parent.winfo_screenheight()
            px, py = self.parent.winfo_pointerx(), self.parent.winfo_pointery()
            x, y = max(0, px + 12), max(0, py + 12)
            top.geometry(f"+{x}+{y}")
        except Exception:
            pass

        frm = ttk.Frame(top, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text=self.title).pack(anchor=tk.W)
        lb = tk.Listbox(frm, height=min(10, len(self.candidates)))
        for _, label in self.candidates:
            lb.insert(tk.END, label)
        lb.pack(fill=tk.BOTH, expand=True, pady=6)
        lb.select_set(0)
        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X)

        def do_ok(evt=None):
            sel = lb.curselection()
            if not sel:
                return
            self.result = self.candidates[sel[0]][0]
            try:
                top.destroy()
            except Exception:
                pass

        def do_cancel():
            self.result = None
            try:
                top.destroy()
            except Exception:
                pass

        lb.bind('<Double-Button-1>', do_ok)
        ttk.Button(btns, text="确定", command=do_ok).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(btns, text="取消", command=do_cancel).pack(side=tk.RIGHT, expand=True, fill=tk.X)

        # second positioning with clipping
        try:
            top.update_idletasks()
            w, h = top.winfo_width(), top.winfo_height()
            sw, sh = self.parent.winfo_screenwidth(), self.parent.winfo_screenheight()
            px, py = self.parent.winfo_pointerx(), self.parent.winfo_pointery()
            x = min(max(0, px + 12), max(0, sw - w))
            y = min(max(0, py + 12), max(0, sh - h))
            top.geometry(f"+{x}+{y}")
        except Exception:
            pass

        self.parent.wait_window(top)
        return self.result
