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


def compute_ac_for_model(app, m: Any, *, is_enemy: bool = False) -> int:
    """Compute AC consistently for both allies and enemies.

    Priority:
    1) If model has dnd['ac'], use it.
    2) Else 10 + defense (from equipment or model total) + DEX mod (if dnd attrs present).

    Notes:
    - Allies typically have equipment with get_total_defense(); enemies may expose
      get_total_defense() or a plain 'defense' attribute.
    - If attrs missing, DEX mod falls back to 0.
    """
    # 1) explicit dnd.ac
    try:
        dnd = getattr(m, 'dnd', None)
        if isinstance(dnd, dict) and dnd.get('ac') is not None:
            return int(dnd.get('ac'))
    except Exception:
        pass
    # 2) base 10 + defense + dex_mod
    base = 10
    defense = 0
    # defense from equipment or model
    try:
        if hasattr(m, 'equipment') and getattr(m, 'equipment') is not None:
            eq = m.equipment
            if hasattr(eq, 'get_total_defense') and callable(eq.get_total_defense):
                defense = int(eq.get_total_defense())
            else:
                defense = int(getattr(eq, 'defense', 0) or 0)
        elif hasattr(m, 'get_total_defense') and callable(getattr(m, 'get_total_defense')):
            defense = int(m.get_total_defense())
        else:
            defense = int(getattr(m, 'defense', 0) or 0)
    except Exception:
        defense = 0
    # dex modifier if available in dnd attrs
    dex_mod = 0
    try:
        attrs = (getattr(m, 'dnd', None) or {}).get('attrs') or (getattr(m, 'dnd', None) or {}).get('attributes')
        if isinstance(attrs, dict):
            dex_raw = attrs.get('dex', attrs.get('DEX'))
            if dex_raw is not None:
                dex_mod = (int(dex_raw) - 10) // 2
    except Exception:
        dex_mod = 0
    try:
        return int(base + defense + dex_mod)
    except Exception:
        return 10 + int(defense)


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
    # 攻击值拆分：优先 base_atk + 装备攻，避免把总攻(attack/get_total_attack)再叠加一次
    def _split_atk(model: Any) -> tuple[int, int, int]:
        try:
            base = int(getattr(model, 'base_atk', getattr(model, 'atk', 0)) or 0)
        except Exception:
            base = 0
        try:
            eq = int(model.equipment.get_total_attack() if hasattr(model, 'equipment') and getattr(model, 'equipment') else 0)
        except Exception:
            eq = 0
        return base, eq, base + eq
    base_atk, eq_atk, total_atk = _split_atk(m)
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
    # 攻击：使用文本“攻”避免 emoji 在 Windows 上造成行高/对齐问题
    atk_wrap = ttk.Frame(stats)
    ttk.Label(atk_wrap, text="攻", font=("Segoe UI", 10, 'bold'), padding=0).pack(side=tk.LEFT, padx=(0,0))
    ttk.Label(atk_wrap, textvariable=atk_var, foreground=col_atk, style="Tiny.TLabel", font=("Segoe UI", 11, 'bold'), anchor='w', padding=0).pack(side=tk.LEFT, padx=(4,0))
    atk_wrap.grid(row=0, column=0, sticky='w', padx=(0, 0), pady=(0, 0))
    # 防御：改用文本“AC”，避免 emoji 在 Windows 上引发布局抖动
    ac_wrap = ttk.Frame(stats)
    ttk.Label(ac_wrap, text="AC", font=("Segoe UI", 10, 'bold'), padding=0).pack(side=tk.LEFT, padx=(0,0))
    ttk.Label(ac_wrap, textvariable=ac_var, foreground=col_ac, style="Tiny.TLabel", font=("Segoe UI", 11, 'bold'), anchor='w', padding=0).pack(side=tk.LEFT, padx=(4,0))
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
    right.grid(row=0, column=1, rowspan=2, sticky='ne', padx=(4,0))
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
            # 点击时即时读取当前装备，避免捕获旧 item
            def _on_click():
                try:
                    cur_m = getattr(frame, '_model_ref', None) or m
                    eq = getattr(cur_m, 'equipment', None)
                    cur_item = None
                    if slot_key == 'left':
                        cur_item = getattr(eq, 'left_hand', None) if eq else None
                    elif slot_key == 'right':
                        # 双手武器占用右手
                        lh = getattr(eq, 'left_hand', None) if eq else None
                        if lh is not None and getattr(lh, 'is_two_handed', False):
                            cur_item = lh
                        else:
                            cur_item = getattr(eq, 'right_hand', None) if eq else None
                    elif slot_key == 'armor':
                        cur_item = getattr(eq, 'armor', None) if eq else None
                except Exception:
                    cur_item = item
                return app._slot_click(m_index, slot_key, cur_item)
            btn = ttk.Button(right, text=text, command=_on_click, style="Slot.TButton")
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
            # 暴露引用用于后续刷新
            frame._st_caps = caps
            frame._st_colors = (col_on, col_off)
            frame._st_cap_wrap = cap_wrap
            frame._st_row = st_row
            frame._st_max_caps = max_caps
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
        # 动态读取最新数据，避免悬浮窗展示旧数值
        try:
            cur_m = getattr(frame, '_model_ref', None) or m
        except Exception:
            cur_m = m
        try:
            nm = getattr(cur_m, 'display_name', None) or getattr(cur_m, 'name', None) or name
        except Exception:
            nm = name
        b, eqa, tot = 0, 0, 0
        try:
            b, eqa, tot = (lambda: (int(getattr(cur_m, 'base_atk', getattr(cur_m, 'atk', 0)) or 0), int(getattr(cur_m, 'equipment').get_total_attack()) if getattr(cur_m, 'equipment', None) else 0, 0))()
            tot = b + eqa
        except Exception:
            try:
                tot = int(getattr(cur_m, 'get_total_attack')() if hasattr(cur_m, 'get_total_attack') else getattr(cur_m, 'attack', 0))
            except Exception:
                tot = 0
        try:
            curhp = int(getattr(cur_m, 'hp', 0)); mxhp = int(getattr(cur_m, 'max_hp', curhp))
        except Exception:
            curhp = max_hp; mxhp = max_hp
        try:
            ac_now = compute_ac_for_model(app, cur_m, is_enemy=bool(getattr(frame, '_is_enemy', False)))
        except Exception:
            ac_now = ac_val
        parts = [f"名称: {nm}", f"攻击: {tot} (基础{b} + 装备{eqa})", f"HP: {curhp}/{mxhp}", f"AC: {ac_now}"]
        # 属性（若存在）
        try:
            cur_attrs = None
            dnd_now = getattr(cur_m, 'dnd', None)
            if isinstance(dnd_now, dict):
                cur_attrs = dnd_now.get('attrs') or dnd_now.get('attributes')
            mapping = [('str','力量'),('dex','敏捷'),('con','体质'),('int','智力'),('wis','感知'),('cha','魅力')]
            if isinstance(cur_attrs, dict):
                lines = []
                for key, zh in mapping:
                    v = cur_attrs.get(key, cur_attrs.get(key.upper()))
                    if v is None:
                        lines.append(f"{zh} -")
                    else:
                        try:
                            iv = int(v); mod = (iv - 10) // 2
                            lines.append(f"{zh} {iv}({mod:+d})")
                        except Exception:
                            lines.append(f"{zh} {v}")
                if lines:
                    parts.append("属性:"); parts.extend(lines)
        except Exception:
            pass
        # 装备名称
        try:
            eq = getattr(cur_m, 'equipment', None)
            eq_list = []
            if eq:
                if getattr(eq, 'left_hand', None):
                    eq_list.append(f"左手: {getattr(eq.left_hand, 'name', '-')}")
                if getattr(eq, 'right_hand', None):
                    eq_list.append(f"右手: {getattr(eq.right_hand, 'name', '-')}")
                if getattr(eq, 'armor', None):
                    eq_list.append(f"盔甲: {getattr(eq.armor, 'name', '-')}")
            if eq_list:
                parts.append("装备: " + ", ".join(eq_list))
        except Exception:
            pass
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


def refresh_character_card(app, frame: ttk.Frame):
    """轻量刷新已创建的角色卡：攻击、AC、HP条、装备槽文本。
    要求 frame 上挂有 _model_ref/_atk_var/_ac_var/_hp_canvas/_hp_cur/_hp_max/_btn_left/_btn_right/_btn_armor。
    """
    try:
        m = getattr(frame, '_model_ref', None)
        if not m:
            return
        # 攻击合计（仅 base_atk + 装备攻，避免把总攻再叠加）
        try:
            base_atk = int(getattr(m, 'base_atk', getattr(m, 'atk', 0)) or 0)
        except Exception:
            base_atk = 0
        try:
            eq_atk = int(m.equipment.get_total_attack() if hasattr(m, 'equipment') and m.equipment else 0)
        except Exception:
            eq_atk = 0
        total_atk = base_atk + eq_atk
        try:
            frame._atk_var.set(str(total_atk))
        except Exception:
            pass
        # AC
        try:
            ac_val = compute_ac_for_model(app, m, is_enemy=bool(getattr(frame, '_is_enemy', False)))
            frame._ac_var.set(str(ac_val))
        except Exception:
            pass
    # HP 数值与血条
        try:
            cur_hp = int(getattr(m, 'hp', 0))
            max_hp = int(getattr(m, 'max_hp', cur_hp))
            frame._hp_cur = cur_hp
            frame._hp_max = max_hp
            # 触发一次重绘
            canvas = getattr(frame, '_hp_canvas', None)
            if canvas:
                try:
                    w = max(1, int(canvas.winfo_width() or 1))
                except Exception:
                    w = 1
                try:
                    # 重写一次与创建时相同的绘制逻辑（缩减版）
                    hcfg = getattr(app, '_hp_bar_cfg', {}) or {}
                    h = int(hcfg.get('height', 12)); bg = hcfg.get('bg', '#e5e7eb'); fg = hcfg.get('fg', '#e74c3c'); tx = hcfg.get('text', '#ffffff'); fs = int(hcfg.get('font_size', 10)); oc = hcfg.get('text_outline', '#000000')
                    canvas.delete('all')
                    ratio = 0 if max_hp <= 0 else max(0.0, min(1.0, float(cur_hp)/float(max_hp)))
                    fill_w = int(w * ratio)
                    canvas.create_rectangle(0, 0, w, h, fill=bg, outline=bg, width=0)
                    if fill_w > 0:
                        canvas.create_rectangle(0, 0, fill_w, h, fill=fg, outline=fg, width=0)
                    cx, cy = w//2, h//2
                    for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
                        canvas.create_text(cx+dx, cy+dy, text=f"{cur_hp}/{max_hp}", fill=oc, font=("Segoe UI", fs, 'bold'))
                    canvas.create_text(cx, cy, text=f"{cur_hp}/{max_hp}", fill=tx, font=("Segoe UI", fs, 'bold'))
                except Exception:
                    pass
        except Exception:
            pass
        # 体力胶囊：根据当前体力重新上色/必要时重建数量
        try:
            st_cfg = getattr(app, '_stamina_cfg', {}) or {}
            if st_cfg.get('enabled', True):
                cur = int(getattr(m, 'stamina', 0)); mx = int(getattr(m, 'stamina_max', cur or 1))
                max_caps = int(getattr(frame, '_st_max_caps', st_cfg.get('max_caps', 6)))
                show_n = min(mx, max_caps)
                caps = list(getattr(frame, '_st_caps', []) or [])
                cap_wrap = getattr(frame, '_st_cap_wrap', None)
                colors = getattr(frame, '_st_colors', ('#2ecc71', '#e74c3c'))
                col_on, col_off = colors[0], colors[1]
                # 如数量不符则重建
                if cap_wrap is not None and len(caps) != show_n:
                    try:
                        for ch in list(cap_wrap.winfo_children()):
                            ch.destroy()
                    except Exception:
                        pass
                    caps = []
                    for i in range(show_n):
                        c = tk.Canvas(cap_wrap, width=8, height=16, highlightthickness=0, bg=getattr(cap_wrap, 'bg', '#f2f3f5'))
                        c.create_line(4, 2, 4, 14, fill=(col_on if i < cur else col_off), width=4, capstyle=tk.ROUND)
                        c.pack(side=tk.LEFT, padx=0)
                        caps.append(c)
                    frame._st_caps = caps
                else:
                    # 数量一致：仅重绘颜色
                    for i, c in enumerate(caps):
                        try:
                            c.delete('all')
                            c.create_line(4, 2, 4, 14, fill=(col_on if i < cur else col_off), width=4, capstyle=tk.ROUND)
                        except Exception:
                            pass
        except Exception:
            pass
        # 装备槽文本
        try:
            eq = getattr(m, 'equipment', None)
            left_item = getattr(eq, 'left_hand', None) if eq else None
            armor_item = getattr(eq, 'armor', None) if eq else None
            right_item_raw = getattr(eq, 'right_hand', None) if eq else None
            right_item = left_item if getattr(left_item, 'is_two_handed', False) else right_item_raw
            if hasattr(frame, '_btn_left') and frame._btn_left:
                frame._btn_left.config(text=(getattr(left_item, 'name', '-') if left_item else '左手: -'))
            if hasattr(frame, '_btn_armor') and frame._btn_armor:
                frame._btn_armor.config(text=(getattr(armor_item, 'name', '-') if armor_item else '盔甲: -'))
            if hasattr(frame, '_btn_right') and frame._btn_right:
                frame._btn_right.config(text=(getattr(right_item, 'name', '-') if right_item else '右手: -'))
        except Exception:
            pass
    except Exception:
        pass
