from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

class EquipmentDialog:
    """Modal dialog to pick an equipment for a member and slot.
    Returns the chosen inventory index (1-based) or None.
    """
    def __init__(self, app, parent, m_index: int, slot_key: str):
        self.app = app
        self.parent = parent
        self.m_index = m_index
        self.slot_key = slot_key
        self.result: Optional[int] = None
        self._index_map: list[int] = []

    def _fits_slot_and_ok(self, it, eq) -> bool:
        try:
            from src.systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
        except Exception:
            WeaponItem = ArmorItem = ShieldItem = tuple()  # type: ignore
        slot_key = self.slot_key
        if slot_key == 'armor':
            return isinstance(it, ArmorItem)
        if slot_key == 'left':
            if isinstance(it, ShieldItem):
                return not (eq and getattr(eq, 'left_hand', None) and getattr(eq.left_hand, 'is_two_handed', False))
            if isinstance(it, WeaponItem):
                if getattr(it, 'is_two_handed', False):
                    return True
                return getattr(it, 'slot_type', '') == 'left_hand' and not (eq and getattr(eq, 'left_hand', None) and getattr(eq.left_hand, 'is_two_handed', False))
            return False
        if slot_key == 'right':
            if eq and getattr(eq, 'left_hand', None) and getattr(eq.left_hand, 'is_two_handed', False):
                return False
            return isinstance(it, WeaponItem) and not getattr(it, 'is_two_handed', False) and getattr(it, 'slot_type', '') == 'right_hand'
        return False

    def _fmt_label(self, it) -> str:
        try:
            atk = int(getattr(it, 'attack', 0) or 0)
        except Exception:
            atk = 0
        try:
            df = int(getattr(it, 'defense', 0) or 0)
        except Exception:
            df = 0
        flags = []
        if getattr(it, 'is_two_handed', False):
            flags.append('双手')
        stats = []
        if atk: stats.append(f"+{atk}攻")
        if df: stats.append(f"+{df}防")
        stat_str = (" " + " ".join(stats)) if stats else ""
        flag_str = (" [" + ", ".join(flags) + "]") if flags else ""
        return f"{getattr(it, 'name', str(it))}{stat_str}{flag_str}"

    def show(self) -> Optional[int]:
        top = tk.Toplevel(self.parent)
        top.title("选择装备")
        top.transient(self.parent)
        top.grab_set()
        self.top = top
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
        ttk.Label(frm, text=f"为 m{self.m_index} 选择装备到 [{self.slot_key}]::").pack(anchor=tk.W)
        tip_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=tip_var, foreground="#666").pack(anchor=tk.W)
        lb = tk.Listbox(frm, height=12)
        lb.pack(fill=tk.BOTH, expand=True, pady=6)
        preview_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=preview_var, foreground="#0a0").pack(anchor=tk.W, pady=(0, 4))

        inv = self.app.controller.game.player.inventory
        try:
            m = self.app.controller.game.player.board[self.m_index - 1]
            eq = getattr(m, 'equipment', None)
        except Exception:
            m = None
            eq = None

        blocked_msg = None
        if self.slot_key == 'right' and eq and getattr(eq, 'left_hand', None) and getattr(eq.left_hand, 'is_two_handed', False):
            blocked_msg = '当前持双手武器，右手不可装备'
        for idx, slot in enumerate(inv.slots, 1):
            it = slot.item
            if self._fits_slot_and_ok(it, eq):
                lb.insert(tk.END, f"i{idx}  {self._fmt_label(it)}")
                self._index_map.append(idx)
        if blocked_msg:
            tip_var.set(blocked_msg)
        elif not self._index_map:
            tip_var.set('暂无可装备的物品')

        def fmt_delta(v: int) -> str:
            return f"+{v}" if v > 0 else (f"{v}" if v < 0 else "±0")

        def update_preview(evt=None):
            if not self._index_map:
                preview_var.set("")
                return
            sel = lb.curselection()
            if not sel:
                preview_var.set("")
                return
            try:
                i_idx = self._index_map[sel[0]]
                it = inv.slots[i_idx - 1].item
                m = self.app.controller.game.player.board[self.m_index - 1]
                eq = getattr(m, 'equipment', None)
                cur_eq_atk = int(eq.get_total_attack() if eq else 0)
                cur_eq_def = int(eq.get_total_defense() if eq else 0)
                lh = getattr(eq, 'left_hand', None) if eq else None
                rh = getattr(eq, 'right_hand', None) if eq else None
                ar = getattr(eq, 'armor', None) if eq else None
                new_lh, new_rh, new_ar = lh, rh, ar
                if self.slot_key == 'armor':
                    new_ar = it
                elif self.slot_key == 'left':
                    if getattr(it, 'is_two_handed', False):
                        new_lh, new_rh = it, None
                    else:
                        new_lh = it
                elif self.slot_key == 'right':
                    new_rh = it
                def g_atk(x):
                    return int(getattr(x, 'attack', 0) or 0)
                def g_def(x):
                    return int(getattr(x, 'defense', 0) or 0)
                new_eq_atk = (g_atk(new_lh) + g_atk(new_rh))
                new_eq_def = (g_def(new_lh) + g_def(new_rh) + g_def(new_ar))
                d_atk = (new_eq_atk - cur_eq_atk)
                d_def = (new_eq_def - cur_eq_def)
                preview_var.set(f"预览: 攻 {fmt_delta(d_atk)}  防 {fmt_delta(d_def)}")
            except Exception:
                preview_var.set("")

        lb.bind('<<ListboxSelect>>', update_preview)

        def do_confirm(evt=None):
            sel = lb.curselection()
            if not sel:
                return
            self.result = self._index_map[sel[0]]
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

        lb.bind('<Double-Button-1>', do_confirm)
        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="确认装备", command=do_confirm).pack(side=tk.LEFT)
        ttk.Button(btns, text="取消", command=do_cancel).pack(side=tk.RIGHT)

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
