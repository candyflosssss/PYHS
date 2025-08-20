"""Character card rendering helpers for Tkinter UI.
Functions accept the main app instance as first parameter to keep a thin adapter surface.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any
from . import ui_utils as U


def create_character_card(app, parent: tk.Widget, m: Any, m_index: int) -> ttk.Frame:
    # 攻击值优先从常见字段获取：attack -> atk -> base_atk
    try:
        if hasattr(m, 'attack'):
            base_atk = int(getattr(m, 'attack', 0) or 0)
        elif hasattr(m, 'atk'):
            base_atk = int(getattr(m, 'atk', 0) or 0)
        else:
            base_atk = int(getattr(m, 'base_atk', 0) or 0)
    except Exception:
        base_atk = 0
    try:
        eq_atk = int(m.equipment.get_total_attack() if hasattr(m, 'equipment') and m.equipment else 0)
    except Exception:
        eq_atk = 0
    total_atk = base_atk + eq_atk
    cur_hp = int(getattr(m, 'hp', 0))
    max_hp = int(getattr(m, 'max_hp', cur_hp))
    try:
        eq_def = int(m.equipment.get_total_defense() if hasattr(m, 'equipment') and m.equipment else 0)
    except Exception:
        eq_def = 0
    # 名称优先从 display_name/name 获取
    try:
        name = getattr(m, 'display_name', None) or getattr(m, 'name', None) or m.__class__.__name__
    except Exception:
        name = '随从'

    # DND 概览
    dnd = getattr(m, 'dnd', None)
    ac = None
    attrs = None
    if isinstance(dnd, dict):
        ac = dnd.get('ac')
        attrs = dnd.get('attrs') or dnd.get('attributes')

    # Card frame: single column layout (name on top, stats vertical, equipment on right)
    frame = ttk.Frame(parent, relief='ridge', padding=4)
    frame.columnconfigure(0, weight=1)

    # name (top)
    ttk.Label(frame, text=str(name), font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky='n', pady=(2, 2))

    # stats: vertical stack (attack, hp, defense)
    stats = ttk.Frame(frame)
    stats.grid(row=1, column=0, sticky='n', pady=(2, 2))
    # 使用 ASCII 文本确保在 Windows 字体下稳定显示，缩小字体并减小行距
    ttk.Label(stats, text=f"ATK {total_atk}", foreground="#E6B800", font=("Segoe UI", 9)).pack(anchor=tk.CENTER, pady=0)
    ttk.Label(stats, text=f"HP {cur_hp}/{max_hp}", foreground="#27ae60" if cur_hp > 0 else "#c0392b", font=("Segoe UI", 9)).pack(anchor=tk.CENTER, pady=0)
    ttk.Label(stats, text=f"DEF {eq_def}", foreground="#2980b9", font=("Segoe UI", 9)).pack(anchor=tk.CENTER, pady=0)
    # AC 显示：若未提供 ac，则以 10+DEF 作为回退
    try:
        ac_val = int(ac) if ac is not None else (10 + int(eq_def))
    except Exception:
        ac_val = 10 + int(eq_def)
    ttk.Label(stats, text=f"AC {ac_val}", foreground="#8e44ad", font=("Segoe UI", 9)).pack(anchor=tk.CENTER, pady=0)
    # 六维总是显示（缺失用 -），数字显示修正值
    try:
        keys = ['str','dex','con','int','wis','cha']
        row_parts = []
        for k in keys:
            v = None
            if isinstance(attrs, dict):
                v = attrs.get(k, attrs.get(k.upper()))
            label = k.upper()
            if v is None:
                row_parts.append(f"{label} -")
                continue
            try:
                iv = int(v)
                mod = (iv - 10) // 2
                row_parts.append(f"{label} {iv}({mod:+d})")
            except Exception:
                row_parts.append(f"{label} {v}")
        ttk.Label(stats, text="  ".join(row_parts), foreground="#7f8c8d", font=("Segoe UI", 8)).pack(anchor=tk.CENTER, pady=0)
    except Exception:
        pass

    # equipment buttons (right column)
    right = ttk.Frame(frame)
    right.grid(row=0, column=1, rowspan=2, sticky='nsew')
    right.columnconfigure(0, weight=1)
    right.columnconfigure(1, weight=0)

    eq = getattr(m, 'equipment', None)
    left_item = getattr(eq, 'left_hand', None) if eq else None
    armor_item = getattr(eq, 'armor', None) if eq else None
    right_item_raw = getattr(eq, 'right_hand', None) if eq else None
    right_item = left_item if getattr(left_item, 'is_two_handed', False) else right_item_raw

    def slot_text(label, item):
        if item:
            return getattr(item, 'name', '-')
        return f"{label}: -"

    def tip_text_for(item, label):
        if not item:
            return f"{label}: 空槽"
        parts = []
        try:
            if getattr(item, 'attack', 0):
                parts.append(f"+{getattr(item, 'attack', 0)} 攻")
        except Exception:
            pass
        try:
            if getattr(item, 'defense', 0):
                parts.append(f"+{getattr(item, 'defense', 0)} 防")
        except Exception:
            pass
        if getattr(item, 'is_two_handed', False):
            parts.append('双手')
        head = getattr(item, 'name', '')
        tail = ' '.join(parts)
        return head + ("\n" + tail if tail else '')

    def make_btn(r, label, item, slot_key):
        text = slot_text(label, item)
        btn = ttk.Button(right, text=text, command=lambda: app._slot_click(m_index, slot_key, item), style="Tiny.TButton")
        btn.grid(row=r, column=1, sticky='e', pady=1, padx=(4, 2))
        U.attach_tooltip_deep(btn, lambda it=item, lb=label: tip_text_for(it, lb))
        return btn

    make_btn(0, '左手', left_item, 'left')
    make_btn(1, '盔甲', armor_item, 'armor')
    make_btn(2, '右手', right_item, 'right')

    def card_tip():
        # Provide tooltip matching the semantics of the "s 5" command output when possible.
        # Try to use attributes commonly present on members/enemies to build a similar text.
        parts = []
        parts.append(f"名称: {name}")
        # Attack (show breakdown if available)
        parts.append(f"攻击: {total_atk} (基础{base_atk} + 装备{eq_atk})")
        parts.append(f"防御: {eq_def}")
        parts.append(f"HP: {cur_hp}/{max_hp}")
        try:
            parts.append(f"AC: {ac if ac is not None else ac_val}")
        except Exception:
            parts.append(f"AC: {ac}")
        if True:
            # 和卡面一致的六维行
            try:
                keys = ['str','dex','con','int','wis','cha']
                row_parts = []
                for k in keys:
                    v = None
                    if isinstance(attrs, dict):
                        v = attrs.get(k, attrs.get(k.upper()))
                    label = k.upper()
                    if v is None:
                        row_parts.append(f"{label} -")
                        continue
                    try:
                        iv = int(v)
                        mod = (iv - 10) // 2
                        row_parts.append(f"{label} {iv}({mod:+d})")
                    except Exception:
                        row_parts.append(f"{label} {v}")
                parts.append("属性: " + "  ".join(row_parts))
            except Exception:
                if isinstance(attrs, dict) and attrs:
                    parts.append("属性: " + ", ".join([f"{k.upper()}={v}" for k,v in attrs.items()]))
        eq_list = []
        if left_item:
            eq_list.append(f"左手: {getattr(left_item, 'name', '-')}")
        if right_item_raw:
            eq_list.append(f"右手: {getattr(right_item_raw, 'name', '-')}")
        if armor_item:
            eq_list.append(f"盔甲: {getattr(armor_item, 'name', '-')}")
        if eq_list:
            parts.append("装备: " + ", ".join(eq_list))
        # This function intentionally mirrors a typical "s 5" style multiline summary.
        return "\n".join(parts)

    U.attach_tooltip_deep(frame, card_tip)
    return frame
