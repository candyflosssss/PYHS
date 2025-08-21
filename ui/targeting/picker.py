"""Unified Target Picker UI (single or multi select).
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import List, Tuple, Optional

class TargetPicker:
    def __init__(self, app, mode: str, candidates: List[Tuple[str,str]]):
        self.app = app
        self.mode = mode  # 'single' | 'multi'
        self.candidates = candidates
        self.top: Optional[tk.Toplevel] = None
        self.lb: Optional[tk.Listbox] = None

    def show(self, title: str = '选择目标'):
        if self.top:
            try:
                self.top.destroy()
            except Exception:
                pass
        top = tk.Toplevel(self.app.root)
        top.title(title)
        top.transient(self.app.root)
        top.grab_set()
        self.top = top
        frm = ttk.Frame(top, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)
        lb = tk.Listbox(frm, height=min(12, max(4, len(self.candidates))))
        for _, label in self.candidates:
            lb.insert(tk.END, label)
        lb.pack(fill=tk.BOTH, expand=True)
        self.lb = lb
        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(8, 0))
        ok = ttk.Button(btns, text='确定', command=self._ok)
        ok.pack(side=tk.LEFT, expand=True, fill=tk.X)
        cc = ttk.Button(btns, text='取消', command=self._cancel)
        cc.pack(side=tk.RIGHT, expand=True, fill=tk.X)
        lb.bind('<Double-Button-1>', lambda _e: self._ok())
        top.bind('<Escape>', lambda _e: self._cancel())
        lb.select_set(0)

    def _ok(self):
        if not self.lb:
            return
        sel = self.lb.curselection()
        if not sel:
            return
        idx = sel[0]
        token = self.candidates[idx][0]
        try:
            if getattr(self.app, 'target_engine', None):
                self.app.target_engine.pick(token)
        except Exception:
            pass
        try:
            self.app._confirm_skill()
        except Exception:
            pass
        self._cancel()

    def _cancel(self):
        if self.top:
            try:
                self.top.destroy()
            except Exception:
                pass
            self.top = None
