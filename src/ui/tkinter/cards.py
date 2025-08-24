"""Character card rendering helpers for Tkinter UI.
Functions accept the main app instance as first parameter to keep a thin adapter surface.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any
from . import ui_utils as U


def create_character_card(app, parent: tk.Widget, m: Any, m_index: int, *, is_enemy: bool = False) -> ttk.Frame:
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

    # stats: vertical stack (attack, hp, AC) — 更紧凑的行距与小字体
    stats = ttk.Frame(frame)
    stats.grid(row=1, column=0, sticky='n', pady=(2, 2))
    # 先计算 AC 数值，再渲染文本，避免未定义变量
    try:
        if ac is not None:
            ac_val = int(ac)
        else:
            # 计算敏捷调整值
            dex_mod = 0
            try:
                if isinstance(attrs, dict):
                    dex_raw = attrs.get('dex', attrs.get('DEX'))
                    if dex_raw is not None:
                        dex_mod = (int(dex_raw) - 10) // 2
            except Exception:
                dex_mod = 0
            ac_val = 10 + int(eq_def) + int(dex_mod)
    except Exception:
        ac_val = 10 + int(eq_def)
    # 使用 ASCII 文本，避免表情符号在 Windows 上导致的行高扩大；并采用 Tiny.TLabel 样式（8pt）
    atk_var = tk.StringVar(value=f"ATK {total_atk}")
    hp_var = tk.StringVar(value=f"HP {cur_hp}/{max_hp}")
    ac_var = tk.StringVar(value=f"AC {ac_val}")
    ttk.Label(stats, textvariable=atk_var, foreground="#E6B800", style="Tiny.TLabel").grid(row=0, column=0, sticky='w', padx=0, pady=(0, 0))
    ttk.Label(stats, textvariable=hp_var, foreground="#27ae60" if cur_hp > 0 else "#c0392b", style="Tiny.TLabel").grid(row=1, column=0, sticky='w', padx=0, pady=(0, 0))
    ttk.Label(stats, textvariable=ac_var, foreground="#2980b9", style="Tiny.TLabel").grid(row=2, column=0, sticky='w', padx=0, pady=(0, 0))

    # 角色卡右侧装备槽：敌方显示为禁用态（可见信息不可操作），我方可操作
    eq = getattr(m, 'equipment', None)
    left_item = getattr(eq, 'left_hand', None) if eq else None
    armor_item = getattr(eq, 'armor', None) if eq else None
    right_item_raw = getattr(eq, 'right_hand', None) if eq else None
    # 若左手为双手武器，右手视为被占用
    right_item = left_item if getattr(left_item, 'is_two_handed', False) else right_item_raw

    right = ttk.Frame(frame)
    right.grid(row=0, column=1, rowspan=2, sticky='nsew')
    right.columnconfigure(0, weight=1)
    right.columnconfigure(1, weight=0)

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
        if is_enemy:
            # 敌方：禁用按钮，仅展示信息，不触发任何回调
            btn = ttk.Button(right, text=text, state=tk.DISABLED, style="Tiny.TButton")
        else:
            btn = ttk.Button(right, text=text, command=lambda: app._slot_click(m_index, slot_key, item), style="Tiny.TButton")
        btn.grid(row=r, column=1, sticky='e', pady=1, padx=(4, 2))
        U.attach_tooltip_deep(btn, lambda it=item, lb=label: tip_text_for(it, lb))
        return btn

    btn_l = make_btn(0, '左手', left_item, 'left')
    btn_a = make_btn(1, '盔甲', armor_item, 'armor')
    btn_r = make_btn(2, '右手', right_item, 'right')

    def card_tip():
        # Provide tooltip matching the semantics of the "s 5" command output when possible.
        # Try to use attributes commonly present on members/enemies to build a similar text.
        parts = []
        parts.append(f"名称: {name}")
        # Attack (show breakdown if available)
        parts.append(f"攻击: {total_atk} (基础{base_atk} + 装备{eq_atk})")
    # 卡面不显示防御数值
        parts.append(f"HP: {cur_hp}/{max_hp}")
        try:
            parts.append(f"AC: {ac if ac is not None else ac_val}")
        except Exception:
            parts.append(f"AC: {ac}")
        if True:
            # 六维在悬浮窗中用中文标签并纵向排列
            try:
                mapping = [
                    ('str', '力量'),
                    ('dex', '敏捷'),
                    ('con', '体质'),
                    ('int', '智力'),
                    ('wis', '感知'),
                    ('cha', '魅力'),
                ]
                lines = []
                for key, zh in mapping:
                    v = None
                    if isinstance(attrs, dict):
                        v = attrs.get(key, attrs.get(key.upper()))
                    if v is None:
                        lines.append(f"{zh} -")
                        continue
                    try:
                        iv = int(v)
                        mod = (iv - 10) // 2
                        lines.append(f"{zh} {iv}({mod:+d})")
                    except Exception:
                        lines.append(f"{zh} {v}")
                if lines:
                    parts.append("属性:")
                    parts.extend(lines)
            except Exception:
                if isinstance(attrs, dict) and attrs:
                    parts.append("属性:")
                    for k, v in attrs.items():
                        parts.append(f"{k.upper()} {v}")
        eq_list = []
        # 在悬浮窗中仍然列出装备名称（如果存在）
        try:
            eq = getattr(m, 'equipment', None)
            if eq:
                if getattr(eq, 'left_hand', None):
                    eq_list.append(f"左手: {getattr(eq.left_hand, 'name', '-')}")
                if getattr(eq, 'right_hand', None):
                    # 若左手为双手武器则 right_hand 可能为 None
                    eq_list.append(f"右手: {getattr(eq.right_hand, 'name', '-')}")
                if getattr(eq, 'armor', None):
                    eq_list.append(f"盔甲: {getattr(eq.armor, 'name', '-')}")
        except Exception:
            pass
        if eq_list:
            parts.append("装备: " + ", ".join(eq_list))
        # This function intentionally mirrors a typical "s 5" style multiline summary.
        return "\n".join(parts)

    # 挂载可更新引用，供事件驱动的微更新使用
    try:
        frame._atk_var = atk_var
        frame._hp_var = hp_var
        frame._ac_var = ac_var
        frame._btn_left = btn_l
        frame._btn_armor = btn_a
        frame._btn_right = btn_r
        frame._model_ref = m
        frame._is_enemy = bool(is_enemy)
    except Exception:
        pass
    U.attach_tooltip_deep(frame, card_tip)
    return frame
