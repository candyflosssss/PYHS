"""Character card rendering helpers for Tkinter UI.
Functions accept the main app instance as first parameter to keep a thin adapter surface.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any
from . import ui_utils as U
from src import app_config as CFG
from src import settings as S
import json, os


_SKILL_CATALOG_CACHE: dict[str, dict] | None = None


def _skill_catalog() -> dict[str, dict]:
    global _SKILL_CATALOG_CACHE
    if _SKILL_CATALOG_CACHE is not None:
        return _SKILL_CATALOG_CACHE
    try:
        p = CFG.skills_catalog_path()
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get('skills'), list):
            _SKILL_CATALOG_CACHE = { rec.get('id'): rec for rec in data['skills'] if isinstance(rec, dict) and rec.get('id') }
        else:
            _SKILL_CATALOG_CACHE = {}
    except Exception:
        _SKILL_CATALOG_CACHE = {}
    return _SKILL_CATALOG_CACHE


def equipment_tooltip(item, label: str, *, is_enemy: bool | None = None, app=None) -> str:
    if not item:
        return f"{label}: 空槽"
    lines: list[str] = []
    name = getattr(item, 'name', '') or ''
    lines.append(name)
    # 描述
    desc = getattr(item, 'description', None)
    if desc:
        lines.append(str(desc))
    # 基础加成
    parts = []
    try:
        av = int(getattr(item, 'attack', 0) or 0)
        if av:
            parts.append(f"+{av} 攻")
    except Exception:
        pass
    try:
        dv = int(getattr(item, 'defense', 0) or 0)
        if dv:
            parts.append(f"+{dv} 防")
    except Exception:
        pass
    if getattr(item, 'is_two_handed', False):
        parts.append('双手')
    if parts:
        lines.append('，'.join(parts))
    # 主动技能（如果配置允许在敌方显示则显示，否则敌方隐藏）
    sks = list(getattr(item, 'active_skills', []) or [])
    show_actives = True
    try:
        if is_enemy and app is not None:
            tcfg = getattr(app, '_tooltip_cfg', {}) or {}
            if not bool(tcfg.get('enemy_show_active_skills', False)):
                show_actives = False
    except Exception:
        show_actives = True
    if sks and show_actives:
        cat = _skill_catalog()
        lines.append('主动技能:')
        for sid in sks:
            rid = str(sid)
            rec = cat.get(rid) or {}
            nm = rec.get('name_cn') or rec.get('name_en') or rid
            cost = 0
            try:
                cost = int(getattr(S, 'get_skill_cost')(rid, 1))
            except Exception:
                cost = 1
            desc = rec.get('desc')
            line = f"- {nm}（消耗体力 {cost}）"
            if desc:
                line += f"\n  {desc}"
            lines.append(line)
    # 被动
    psv = getattr(item, 'passives', None) or {}
    if isinstance(psv, dict) and psv:
        stat_map = {'str':'力量','dex':'敏捷','con':'体质','int':'智力','wis':'智慧','cha':'魅力'}
        lines.append('被动:')
        for k, v in psv.items():
            if k == 'lifesteal_on_attack_stat':
                zh = stat_map.get(str(v).lower(), str(v))
                lines.append(f"- 攻击命中后按{zh}调整值吸血")
            elif k == 'heal_on_damaged_stat':
                zh = stat_map.get(str(v).lower(), str(v))
                lines.append(f"- 受伤后按{zh}调整值治疗自身")
            elif k == 'reflect_on_damaged':
                if str(v).startswith('stamina_cost_'):
                    try:
                        n = int(str(v).split('_')[-1])
                    except Exception:
                        n = 1
                    lines.append(f"- 受伤后消耗{n}点体力进行反击")
                else:
                    lines.append("- 受伤后进行反击")
            else:
                lines.append(f"- {k}: {v}")
    return "\n".join(lines)


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
    top = ttk.Frame(frame)
    top.grid(row=0, column=0, sticky='ew', pady=(0, 0))
    top.columnconfigure(0, weight=1)
    ttk.Label(top, text=str(name), font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky='w')

    # stats: vertical stack（仅显示 ATK 与 AC；HP 改为下方血条）
    stats = ttk.Frame(frame)
    stats.grid(row=1, column=0, sticky='n', pady=(0, 0))
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
    atk_var = tk.StringVar(value=f"{total_atk}")
    hp_var = tk.StringVar(value=f"HP {cur_hp}/{max_hp}")
    ac_var = tk.StringVar(value=f"{ac_val}")
    try:
        cols = getattr(app, '_stats_colors', {}) or {}
        col_atk = cols.get('atk', '#E6B800')
        col_hp_pos = cols.get('hp_pos', '#27ae60')
        col_hp_zero = cols.get('hp_zero', '#c0392b')
        col_ac = cols.get('ac', '#2980b9')
    except Exception:
        col_atk, col_hp_pos, col_hp_zero, col_ac = "#E6B800", "#27ae60", "#c0392b", "#2980b9"
    stats.grid_columnconfigure(0, weight=0)
    # 攻击：图标 + 数字（3位预留），紧贴无空格
    atk_wrap = ttk.Frame(stats)
    ttk.Label(atk_wrap, text="⚔", font=("Segoe UI", 11), padding=0).pack(side=tk.LEFT, padx=(0,0))
    ttk.Label(atk_wrap, textvariable=atk_var, foreground=col_atk, style="Tiny.TLabel", font=("Segoe UI", 11, 'bold'), anchor='w', padding=0).pack(side=tk.LEFT, padx=(0,0))
    atk_wrap.grid(row=0, column=0, sticky='w', padx=(0, 0), pady=(0, 0))
    # 防御：图标 + 数字（3位预留），紧贴无空格
    ac_wrap = ttk.Frame(stats)
    ttk.Label(ac_wrap, text="🛡", font=("Segoe UI", 11), padding=0).pack(side=tk.LEFT, padx=(0,0))
    ttk.Label(ac_wrap, textvariable=ac_var, foreground=col_ac, style="Tiny.TLabel", font=("Segoe UI", 11, 'bold'), anchor='w', padding=0).pack(side=tk.LEFT, padx=(0,0))
    ac_wrap.grid(row=1, column=0, sticky='w', padx=(0, 0), pady=(2, 0))

    # 角色卡右侧装备槽：敌方显示为禁用态（可见信息不可操作），我方可操作
    eq = getattr(m, 'equipment', None)
    left_item = getattr(eq, 'left_hand', None) if eq else None
    armor_item = getattr(eq, 'armor', None) if eq else None
    right_item_raw = getattr(eq, 'right_hand', None) if eq else None
    # 若左手为双手武器，右手视为被占用
    right_item = left_item if getattr(left_item, 'is_two_handed', False) else right_item_raw

    # 右侧更紧凑：去除多余列与内边距，使用单列承载按钮
    right = ttk.Frame(frame, padding=(0, 0))
    right.grid(row=0, column=1, rowspan=2, sticky='n')
    right.columnconfigure(0, weight=0)

    def slot_text(label, item):
        if item:
            return getattr(item, 'name', '-')
        return f"{label}: -"

    def tip_text_for(item, label):
        return equipment_tooltip(item, label, is_enemy=is_enemy, app=app)

    def make_btn(r, label, item, slot_key):
        text = slot_text(label, item)
        if is_enemy:
            # 敌方：禁用按钮，仅展示信息，不触发任何回调
            btn = ttk.Button(right, text=text, state=tk.DISABLED, style="Slot.TButton")
        else:
            btn = ttk.Button(right, text=text, command=lambda: app._slot_click(m_index, slot_key, item), style="Slot.TButton")
        # 更紧凑的外边距与单列布局
        btn.grid(row=r, column=0, sticky='e', pady=(0, 0), padx=(0, 0))
        # 标记为装备槽按钮，AlliesView 绑定时将跳过其操作栏事件
        try:
            setattr(btn, '_is_equipment_slot', True)
        except Exception:
            pass
        U.attach_tooltip_deep(btn, lambda it=item, lb=label: tip_text_for(it, lb))
        return btn

    btn_l = make_btn(0, '左手', left_item, 'left')
    btn_a = make_btn(1, '盔甲', armor_item, 'armor')
    btn_r = make_btn(2, '右手', right_item, 'right')

    # stamina row: now placed below equipment area (new row 2 spanning both columns)
    try:
        st_cfg = getattr(app, '_stamina_cfg', {}) or {}
        if st_cfg.get('enabled', True):
            # 体力条使用与卡片不同的背景色，提升可辨识度
            # 仅展示圆角体力胶囊，不显示文字与数值
            bgc_card = None
            try:
                bgc_card = frame.cget('background')
            except Exception:
                bgc_card = None
            bgc = (st_cfg.get('bg') or '#f2f3f5')
            st_row = tk.Frame(frame, bg=bgc)
            st_row.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(2, 0))
            # 仅一列：胶囊容器
            st_row.columnconfigure(0, weight=1)
            caps = []
            max_caps = max(1, int(st_cfg.get('max_caps', 6)))
            col_on = ((st_cfg.get('colors') or {}).get('on') or '#2ecc71')
            col_off = ((st_cfg.get('colors') or {}).get('off') or '#e74c3c')
            cur = int(getattr(m, 'stamina', 0)); mx = int(getattr(m, 'stamina_max', cur or 1))
            show_n = min(mx, max_caps)
            cap_wrap = tk.Frame(st_row, bg=bgc)
            cap_wrap.grid(row=0, column=0, sticky='w')
            for i in range(show_n):
                # 使用圆头直线绘制更平滑的圆角长条
                c = tk.Canvas(cap_wrap, width=8, height=16, highlightthickness=0, bg=bgc)
                fill = col_on if i < cur else col_off
                # 垂直线，宽度代表条的粗细，capstyle=ROUND 形成上下圆角
                c.create_line(4, 2, 4, 14, fill=fill, width=4, capstyle=tk.ROUND)
                c.pack(side=tk.LEFT, padx=0)
                caps.append(c)
            frame._st_caps = caps
            frame._st_colors = (col_on, col_off)
    except Exception:
        pass

    # HP bar row: placed below stamina row (new row 3)
    try:
        hp_cfg = getattr(app, '_hp_bar_cfg', {}) or {}
        h = int(hp_cfg.get('height', 12))
        bg = hp_cfg.get('bg', '#e5e7eb')
        fg = hp_cfg.get('fg', '#e74c3c')
        tx = hp_cfg.get('text', '#ffffff')
        fs = int(hp_cfg.get('font_size', 10))
        oc = hp_cfg.get('text_outline', '#000000')
        hp_row = tk.Frame(frame, bg=bg)
        hp_row.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(2, 0))
        # 背景底条
        hp_canvas = tk.Canvas(hp_row, height=h, highlightthickness=0, bg=bg)
        hp_canvas.pack(fill=tk.X, expand=True)
        # 画前景填充（按比例）并覆盖文本
        def _draw_hp_bar(cur:int, mx:int):
            hp_canvas.delete('all')
            width = max(1, int(hp_canvas.winfo_width() or 1))
            ratio = 0 if mx <= 0 else max(0.0, min(1.0, float(cur)/float(mx)))
            fill_w = int(width * ratio)
            hp_canvas.create_rectangle(0, 0, width, h, fill=bg, outline=bg, width=0)
            if fill_w > 0:
                hp_canvas.create_rectangle(0, 0, fill_w, h, fill=fg, outline=fg, width=0)
            # 覆盖文本（描边）
            cx, cy = width//2, h//2
            try:
                # 细描边：四向偏移
                for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
                    hp_canvas.create_text(cx+dx, cy+dy, text=f"{cur}/{mx}", fill=oc, font=("Segoe UI", fs, 'bold'))
            except Exception:
                pass
            hp_canvas.create_text(cx, cy, text=f"{cur}/{mx}", fill=tx, font=("Segoe UI", fs, 'bold'))
        # 初始绘制需要在布局完成后获取宽度
        def _after_map_draw():
            _draw_hp_bar(cur_hp, max_hp)
        try:
            hp_canvas.bind('<Configure>', lambda _e: _draw_hp_bar(int(getattr(frame, '_hp_cur', cur_hp)), int(getattr(frame, '_hp_max', max_hp))))
        except Exception:
            pass
        frame._hp_canvas = hp_canvas
        frame._hp_cur = cur_hp
        frame._hp_max = max_hp
        # 延迟一次绘制
        try:
            frame.after(0, _after_map_draw)
        except Exception:
            pass
    except Exception:
        pass

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
