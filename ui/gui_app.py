"""Tkinter GUI for COMOS PvE (menu + gameplay)
- Menu: start game, rename, choose pack, refresh, quit
- Gameplay: enemies as cards at top (centered), resources as buttons, info, logs; bottom shows team cards with ATK/DEF/HP and equipment slots
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional

from game_modes.pve_controller import SimplePvEController
from ui import colors as C

try:
    from main import load_config, save_config, discover_packs, _pick_default_main  # type: ignore
except Exception:  # pragma: no cover
    load_config = save_config = discover_packs = _pick_default_main = None  # type: ignore


class GameTkApp:
    def __init__(self, player_name: str = "玩家", initial_scene: Optional[str] = None):
        self.mode = "menu"
        self.cfg = (load_config() if callable(load_config) else {"name": player_name, "last_pack": "", "last_scene": "default_scene.json"})
        if player_name and self.cfg.get("name") != player_name:
            self.cfg["name"] = player_name
            if callable(save_config):
                try:
                    save_config(self.cfg)
                except Exception:
                    pass
        self._pending_scene = initial_scene
        self.controller: Optional[SimplePvEController] = None

        self.root = tk.Tk()
        self.root.title("COMOS - Tk GUI")

        # Containers
        self.frame_menu = ttk.Frame(self.root)
        self.frame_game = ttk.Frame(self.root)
        self.frame_menu.pack(fill=tk.BOTH, expand=True)

        self._build_menu(self.frame_menu)
        self._build_game(self.frame_game)

    # -------- Menu --------
    def _build_menu(self, parent: tk.Widget):
        wrapper = ttk.Frame(parent, padding=10)
        wrapper.pack(fill=tk.BOTH, expand=True)
        ttk.Label(wrapper, text="COMOS PvE - 主菜单", font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        self.lbl_profile = ttk.Label(wrapper, text=self._menu_profile(), foreground="#555")
        self.lbl_profile.pack(anchor=tk.W, pady=(4, 10))

        btns = ttk.Frame(wrapper)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="🎮 开始游戏", command=self._menu_start).pack(fill=tk.X)
        ttk.Button(btns, text="✏️ 修改玩家名称", command=self._menu_rename).pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btns, text="🗺️ 选择地图组", command=self._menu_choose_pack).pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btns, text="🔄 重新载入场景列表", command=self._menu_refresh_packs).pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btns, text="🚪 退出", command=self.root.destroy).pack(fill=tk.X, pady=(12, 0))

    def _menu_profile(self) -> str:
        pack_id = self.cfg.get('last_pack', '')
        last_scene = self.cfg.get('last_scene', 'default_scene.json')
        scene_label = (pack_id + '/' if pack_id else '') + last_scene
        return f"玩家: {self.cfg.get('name','玩家')}    场景: {scene_label}"

    def _menu_start(self):
        packs = discover_packs() if callable(discover_packs) else {}
        pid = self.cfg.get('last_pack', '')
        pack = (packs or {}).get(pid) or (packs or {}).get('') or {}
        mains = pack.get('mains', []) if isinstance(pack, dict) else []
        if mains and self.cfg.get('last_scene') not in mains:
            self.cfg['last_scene'] = _pick_default_main(mains) if callable(_pick_default_main) else mains[0]
            if callable(save_config):
                try:
                    save_config(self.cfg)
                except Exception:
                    pass
        start_scene = (pid + '/' if pid else '') + self.cfg.get('last_scene', 'default_scene.json')
        self._start_game(self.cfg.get('name', '玩家'), start_scene)

    def _menu_rename(self):
        new_name = simpledialog.askstring("修改名称", "请输入新名称:", parent=self.root)
        if new_name:
            self.cfg['name'] = new_name.strip()
            if callable(save_config):
                try:
                    save_config(self.cfg)
                except Exception:
                    pass
            self.lbl_profile.config(text=self._menu_profile())

    def _menu_choose_pack(self):
        packs = discover_packs() if callable(discover_packs) else {}
        win = tk.Toplevel(self.root)
        win.title("选择地图组")
        win.transient(self.root)
        win.grab_set()
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="地图组").grid(row=0, column=0, sticky='w')
        ttk.Label(frm, text="主地图").grid(row=0, column=1, sticky='w', padx=(10, 0))
        lbp = tk.Listbox(frm, height=12, exportselection=False)
        lbs = tk.Listbox(frm, height=12, exportselection=False)
        lbp.grid(row=1, column=0, sticky='nsew')
        lbs.grid(row=1, column=1, sticky='nsew', padx=(10, 0))
        frm.grid_rowconfigure(1, weight=1)
        frm.grid_columnconfigure(0, weight=1)
        frm.grid_columnconfigure(1, weight=1)

        pack_ids: list[str] = []
        for pid, meta in (packs or {}).items():
            name = (meta.get('name') if isinstance(meta, dict) else None) or (pid or '基础')
            lbp.insert(tk.END, f"{name} ({pid or 'base'})")
            pack_ids.append(pid)

        def on_pick_pack(_evt=None):
            lbs.delete(0, tk.END)
            sel = lbp.curselection()
            if not sel:
                return
            pid = pack_ids[sel[0]]
            meta = (packs or {}).get(pid) or {}
            mains = meta.get('mains', []) if isinstance(meta, dict) else []
            for s in mains:
                lbs.insert(tk.END, s)

        def on_confirm():
            sel = lbp.curselection()
            if not sel:
                messagebox.showinfo("提示", "请先选择地图组")
                return
            pid = pack_ids[sel[0]]
            meta = (packs or {}).get(pid) or {}
            mains = meta.get('mains', []) if isinstance(meta, dict) else []
            if not mains:
                messagebox.showinfo("提示", "该地图组没有主地图")
                return
            isel = lbs.curselection()
            if isel:
                chosen = mains[isel[0]]
            else:
                chosen = _pick_default_main(mains) if callable(_pick_default_main) else mains[0]
            self.cfg['last_pack'] = pid
            self.cfg['last_scene'] = chosen
            if callable(save_config):
                try:
                    save_config(self.cfg)
                except Exception:
                    pass
            self.lbl_profile.config(text=self._menu_profile())
            win.destroy()

        lbp.bind("<<ListboxSelect>>", on_pick_pack)
        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btns, text="确定", command=on_confirm).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side=tk.RIGHT, expand=True, fill=tk.X)

    def _menu_refresh_packs(self):
        _ = discover_packs() if callable(discover_packs) else None
        messagebox.showinfo("提示", "场景列表已刷新")

    # -------- Gameplay UI --------
    def _build_game(self, parent: tk.Widget):
        # 顶部标题
        self.scene_var = tk.StringVar(value="场景: -")
        top = ttk.Frame(parent)
        top.pack(fill=tk.X, padx=6, pady=(6, 2))
        ttk.Label(top, textvariable=self.scene_var, font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        ttk.Button(top, text="主菜单", command=self._back_to_menu).pack(side=tk.RIGHT)

        # 顶部：敌人卡片
        frm_enemy_cards = ttk.LabelFrame(parent, text="敌人 (点击选择 eN)")
        frm_enemy_cards.pack(fill=tk.X, expand=False, padx=6, pady=(2, 2))
        self.enemy_cards_container = ttk.Frame(frm_enemy_cards)
        self.enemy_cards_container.pack(fill=tk.X, expand=False, padx=6, pady=6)
        self.enemy_card_wraps: dict[int, tk.Widget] = {}
        self.selected_enemy_index: Optional[int] = None

        # 中部主体
        body = ttk.Frame(parent)
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 6))
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        body.rowconfigure(2, weight=0)
        body.rowconfigure(3, weight=0)
        body.columnconfigure(0, weight=1, uniform='col')
        body.columnconfigure(1, weight=1, uniform='col')

        # 敌人列表
        frm_enemy = ttk.LabelFrame(body, text="敌人 (选择 eN)")
        frm_enemy.grid(row=0, column=0, sticky='nsew', padx=(0, 3), pady=(0, 3))
        self.list_enemy = tk.Listbox(frm_enemy, activestyle='dotbox')
        sb_enemy = ttk.Scrollbar(frm_enemy, orient='vertical', command=self.list_enemy.yview)
        self.list_enemy.configure(yscrollcommand=sb_enemy.set)
        self.list_enemy.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        sb_enemy.pack(side=tk.RIGHT, fill=tk.Y)

        # 资源按钮区
        frm_res = ttk.LabelFrame(body, text="资源 (点击拾取)")
        frm_res.grid(row=0, column=1, sticky='nsew', padx=(3, 0), pady=(0, 3))
        self.res_buttons_container = ttk.Frame(frm_res)
        self.res_buttons_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.selected_res_index: Optional[int] = None

        # 背包
        frm_inv = ttk.LabelFrame(body, text="背包 / 可合成 (iN / 名称 / cN)")
        frm_inv.grid(row=1, column=0, sticky='nsew', padx=(0, 3), pady=(3, 3))
        self.list_inv = tk.Listbox(frm_inv, activestyle='dotbox')
        sb_inv = ttk.Scrollbar(frm_inv, orient='vertical', command=self.list_inv.yview)
        self.list_inv.configure(yscrollcommand=sb_inv.set)
        self.list_inv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        sb_inv.pack(side=tk.RIGHT, fill=tk.Y)

        # 信息
        frm_info = ttk.LabelFrame(body, text="信息 / 状态")
        frm_info.grid(row=1, column=1, sticky='nsew', padx=(3, 0), pady=(3, 3))
        self.text_info = tk.Text(frm_info, height=10, wrap='word')
        sb_info = ttk.Scrollbar(frm_info, orient='vertical', command=self.text_info.yview)
        self.text_info.configure(yscrollcommand=sb_info.set)
        self.text_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        sb_info.pack(side=tk.RIGHT, fill=tk.Y)

        # 操作
        actions = ttk.Frame(body)
        actions.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(2, 2))
        for i in range(6):
            actions.columnconfigure(i, weight=1)
        ttk.Button(actions, text="攻击 (a)", command=self.on_attack).grid(row=0, column=0, padx=2, sticky='ew')
        ttk.Button(actions, text="拾取 (t)", command=self.on_pick).grid(row=0, column=1, padx=2, sticky='ew')
        ttk.Button(actions, text="使用/装备 (u/eq)", command=self.on_use_or_equip).grid(row=0, column=2, padx=2, sticky='ew')
        ttk.Button(actions, text="卸下 (uneq)", command=self.on_unequip_dialog).grid(row=0, column=3, padx=2, sticky='ew')
        ttk.Button(actions, text="合成 (craft)", command=self.on_craft_quick).grid(row=0, column=4, padx=2, sticky='ew')
        ttk.Button(actions, text="结束回合 (end)", command=lambda: self._run_cmd('end')).grid(row=0, column=5, padx=2, sticky='ew')

        # 队伍卡片
        frm_cards = ttk.LabelFrame(body, text="队伍 (点击选择 mN)")
        frm_cards.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(2, 4))
        self.cards_container = ttk.Frame(frm_cards)
        self.cards_container.pack(fill=tk.X, expand=False, padx=6, pady=6)
        self.card_wraps: dict[int, tk.Widget] = {}
        self.selected_member_index: Optional[int] = None

        # 日志
        frm_log = ttk.LabelFrame(body, text="日志")
        frm_log.grid(row=5, column=0, columnspan=2, sticky='nsew')
        self.text_log = tk.Text(frm_log, height=6, wrap='word')
        sb_log = ttk.Scrollbar(frm_log, orient='vertical', command=self.text_log.yview)
        self.text_log.configure(yscrollcommand=sb_log.set)
        self.text_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        sb_log.pack(side=tk.RIGHT, fill=tk.Y)

    # -------- Render --------
    def refresh_all(self):
        if self.mode != 'game' or not self.controller:
            return
        try:
            scene = getattr(self.controller.game, 'current_scene_title', None) or self.controller.game.current_scene
            if scene:
                if getattr(self.controller.game, 'current_scene_title', None):
                    self.scene_var.set(f"场景: {scene}")
                else:
                    self.scene_var.set(f"场景: {os.path.basename(scene)}")
        except Exception:
            self.scene_var.set("场景: -")

        # 列表区
        def fill(lb: tk.Listbox, text: str):
            lb.delete(0, tk.END)
            for line in (text or '').splitlines():
                s = C.strip(line).rstrip()
                if not s:
                    continue
                if s.endswith('):') or s.endswith(':'):
                    continue
                lb.insert(tk.END, s)
        fill(self.list_enemy, self.controller._section_enemy())
        fill(self.list_inv, self.controller._section_inventory())
        self._render_resources()

        # 信息与日志
        self.text_info.delete('1.0', tk.END)
        for line in (self.controller._section_info() or '').splitlines():
            self._append_info(line)
        try:
            logs = self.controller.game.pop_logs()
            for line in logs:
                self._append_log(line)
        except Exception:
            pass

        # 卡片
        self._render_enemy_cards()
        self._render_cards()

    def _render_enemy_cards(self):
        for w in list(self.enemy_cards_container.winfo_children()):
            w.destroy()
        self.enemy_card_wraps.clear()
        enemies = getattr(self.controller.game, 'enemies', None) or getattr(self.controller.game, 'enemy_zone', []) or []
        if not enemies:
            ttk.Label(self.enemy_cards_container, text="(无敌人)", foreground="#888").pack(anchor=tk.CENTER, pady=(2, 4))
            return
        max_per_row = 6
        members = list(enemies)[:12]
        rows = [members[:max_per_row], members[max_per_row:]]
        for r_idx, row_members in enumerate(rows):
            if not row_members:
                continue
            row_f = ttk.Frame(self.enemy_cards_container)
            row_f.grid(row=r_idx, column=0, sticky='ew', pady=(2, 2))
            for c in (0, max_per_row + 1):
                row_f.grid_columnconfigure(c, weight=1)
            k = len(row_members)
            start = 1 + (max_per_row - k) // 2
            for j, e in enumerate(row_members):
                e_index = r_idx * max_per_row + j + 1
                wrap = tk.Frame(row_f, highlightthickness=2, highlightbackground="#cccccc")
                inner = self._create_enemy_card(wrap, e, e_index)
                inner.pack(fill=tk.BOTH, expand=True)
                col = start + j
                wrap.grid(row=0, column=col, padx=4, sticky='n')
                def bind_all(w):
                    w.bind('<Button-1>', lambda _e, idx=e_index: self._on_enemy_card_click(idx))
                    for ch in getattr(w, 'winfo_children', lambda: [])():
                        bind_all(ch)
                bind_all(wrap)
                self.enemy_card_wraps[e_index] = wrap

    def _create_enemy_card(self, parent: tk.Widget, e, e_index: int) -> ttk.Frame:
        name = getattr(e, 'name', f'敌人#{e_index}')
        atk = int(getattr(e, 'attack', 0) or 0)
        hp = int(getattr(e, 'hp', 0) or 0)
        mhp = int(getattr(e, 'max_hp', hp) or hp)
        dfn = int(getattr(e, 'defense', 0) or 0)
        frame = ttk.Frame(parent, relief='ridge', padding=6)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=str(name), font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky='n', pady=(2, 0))
        bottom = ttk.Frame(frame)
        bottom.grid(row=1, column=0, sticky='sew', pady=(8, 0))
        for c in range(3):
            bottom.columnconfigure(c, weight=1)
        ttk.Label(bottom, text=f"ATK {atk}", foreground="#d35400").grid(row=0, column=0, sticky='s')
        ttk.Label(bottom, text=f"DEF {dfn}", foreground="#2980b9").grid(row=0, column=1, sticky='s')
        ttk.Label(bottom, text=f"HP {hp}/{mhp}", foreground="#27ae60" if hp > 0 else "#c0392b").grid(row=0, column=2, sticky='s')
        self._attach_tooltip(frame, lambda: f"名称: {name}\n攻击: {atk}\n防御: {dfn}\nHP: {hp}/{mhp}")
        return frame

    def _select_skill(self, m_index: int, skill_type: str):
        # 选择技能后高亮可用目标
        self.selected_skill = skill_type
        if skill_type == "attack":
            # 高亮可攻击敌人
            for idx, wrap in self.enemy_card_wraps.items():
                e = getattr(self.controller.game, 'enemies', [])[idx-1] if hasattr(self.controller.game, 'enemies') else None
                can_attack = getattr(e, 'can_be_attacked', True)
                color = "#ffecb3" if can_attack else "#cccccc"
                wrap.configure(highlightbackground=color)
        elif skill_type == "heal":
            # 高亮可治疗队友（HP未满且不是自己）
            for idx, wrap in self.card_wraps.items():
                m = getattr(self.controller.game.player, 'board', [])[idx-1] if hasattr(self.controller.game.player, 'board') else None
                can_heal = m and getattr(m, 'hp', 0) < getattr(m, 'max_hp', 0) and idx != m_index
                color = "#b3e5fc" if can_heal else "#cccccc"
                wrap.configure(highlightbackground=color)
        # 技能选择后，点击目标执行技能
        self.skill_target_index = None

    def _on_enemy_card_click(self, idx: int):
        # 技能选择后点击敌人执行攻击
        if hasattr(self, 'selected_skill') and self.selected_skill == "attack":
            m_idx = self.selected_member_index or 1
            e_token = f"e{idx}"
            m_token = f"m{m_idx}"
            out, _ = self.controller._process_command(f"a {m_token} {e_token}")
            self._after_cmd(out)
            self.selected_skill = None
            return
        prev = getattr(self, 'selected_enemy_index', None)
        if prev and prev in getattr(self, 'enemy_card_wraps', {}):
            try:
                self.enemy_card_wraps[prev].configure(highlightbackground="#cccccc")
            except Exception:
                pass
        self.selected_enemy_index = idx
        try:
            w = self.enemy_card_wraps.get(idx)
            if w:
                w.configure(highlightbackground="#FF6347")
        except Exception:
            pass

    def _on_card_click(self, idx: int):
        # 技能选择后点击队友执行治疗
        if hasattr(self, 'selected_skill') and self.selected_skill == "heal":
            m_idx = self.selected_member_index or 1
            tgt_token = f"m{idx}"
            out, _ = self.controller._process_command(f"heal m{m_idx} {tgt_token}")
            self._after_cmd(out)
            self.selected_skill = None
            return
        prev = getattr(self, 'selected_member_index', None)
        if prev and prev in getattr(self, 'card_wraps', {}):
            try:
                self.card_wraps[prev].configure(highlightbackground="#cccccc")
            except Exception:
                pass
        self.selected_member_index = idx
        try:
            w = self.card_wraps.get(idx)
            if w:
                w.configure(highlightbackground="#1E90FF")
        except Exception:
            pass

    def _render_cards(self):
        for w in list(self.cards_container.winfo_children()):
            w.destroy()
        self.card_wraps.clear()
        game = getattr(self.controller, 'game', None)
        if not game:
            return
        board = getattr(game.player, 'board', [])
        if not board:
            ttk.Label(self.cards_container, text="(队伍为空)", foreground="#888").pack(anchor=tk.CENTER, pady=(2, 6))
            return
        members = list(board)[:10]
        max_per_row = 5
        rows = [members[:max_per_row], members[max_per_row:]]
        for r_idx, row_members in enumerate(rows):
            if not row_members:
                continue
            row_f = ttk.Frame(self.cards_container)
            row_f.grid(row=r_idx, column=0, sticky='ew', pady=(2, 2))
            for c in (0, max_per_row + 1):
                row_f.grid_columnconfigure(c, weight=1)
            k = len(row_members)
            start = 1 + (max_per_row - k) // 2
            for j, m in enumerate(row_members):
                m_index = r_idx * max_per_row + j + 1
                wrap = tk.Frame(row_f, highlightthickness=2, highlightbackground="#cccccc")
                inner = self._create_character_card(wrap, m, m_index)
                inner.pack(fill=tk.BOTH, expand=True)
                col = start + j
                wrap.grid(row=0, column=col, padx=4, sticky='n')
                def bind_all(w):
                    w.bind('<Button-1>', lambda _e, idx=m_index: self._on_card_click(idx))
                    for ch in getattr(w, 'winfo_children', lambda: [])():
                        bind_all(ch)
                bind_all(wrap)
                self.card_wraps[m_index] = wrap

    def _create_character_card(self, parent: tk.Widget, m, m_index: int) -> ttk.Frame:
        # 获取属性
        try:
            base_atk = int(getattr(m, 'base_atk', getattr(m, 'atk', 0)))
        except Exception:
            base_atk = int(getattr(m, 'atk', 0))
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
        try:
            name = getattr(m, 'display_name', None) or m.__class__.__name__
        except Exception:
            name = '随从'
        job = '冒险者'
        try:
            tags = getattr(m, 'tags', None)
            if isinstance(tags, (list, tuple)) and tags:
                job = str(tags[0])
        except Exception:
            pass
        # 行动点
        ap = getattr(m, 'action_point', 1)
        ap_max = getattr(m, 'action_point_max', 1)
        ap_color = '#2ecc71' if ap > 0 else '#e74c3c'
        # 可攻/已攻
        can_attack = bool(getattr(m, 'can_attack', False))
        status_txt = "·可攻" if can_attack else "·已攻"
        status_fg = "#2ecc71" if can_attack else "#bdc3c7"
        # 紧凑卡片布局
        frame = ttk.Frame(parent, relief='ridge', padding=2)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        # 左侧（行动点+职业+状态）
        left = ttk.Frame(frame)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 2))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        # 行动点
        ap_label = tk.Label(left, text=f"AP:{ap}/{ap_max}", fg=ap_color, font=("Segoe UI", 8, "bold"), bg="#f8f8f8")
        ap_label.place(x=2, y=2)
        # 中文职业居中
        ttk.Label(left, text=str(job), font=("微软雅黑", 9, "bold"), foreground="#555").pack(anchor=tk.CENTER, pady=(2, 0))
        # 名称
        ttk.Label(left, text=str(name), font=("Segoe UI", 9)).pack(anchor=tk.CENTER, pady=(0, 0))
        # 可攻/已攻
        ttk.Label(left, text=status_txt, foreground=status_fg, font=("Segoe UI", 8)).pack(anchor=tk.CENTER, pady=(0, 2))
        # HP/ATK/DEF
        stats = ttk.Frame(left)
        stats.pack(anchor=tk.CENTER, pady=(2, 0))
        ttk.Label(stats, text=f"HP {cur_hp}/{max_hp}", foreground="#27ae60" if cur_hp > 0 else "#c0392b", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=2)
        ttk.Label(stats, text=f"ATK {total_atk}", foreground="#d35400", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=2)
        ttk.Label(stats, text=f"DEF {eq_def}", foreground="#2980b9", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=2)
        # 右侧（装备槽按钮缩小）
        right = ttk.Frame(frame)
        right.grid(row=0, column=1, sticky='nsew')
        eq = getattr(m, 'equipment', None)
        left_item = getattr(eq, 'left_hand', None) if eq else None
        armor_item = getattr(eq, 'armor', None) if eq else None
        right_item_raw = getattr(eq, 'right_hand', None) if eq else None
        right_item = left_item if getattr(left_item, 'is_two_handed', False) else right_item_raw
        def slot_text(label, item):
            return f"{label}:" + (getattr(item, 'name', '-') if item else '-')
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
            extra = []
            if getattr(item, 'is_two_handed', False):
                extra.append('双手')
            head = getattr(item, 'name', '')
            tail = ' '.join(parts + extra)
            return head + ("\n" + tail if tail else '')
        def make_btn(r, label, item, slot_key):
            text = slot_text(label, item)
            btn = ttk.Button(right, text=text, width=8, command=lambda: self._slot_click(m_index, slot_key, item))
            btn.grid(row=r, column=0, sticky='ew', pady=1)
            self._attach_tooltip(btn, lambda it=item, lb=label: tip_text_for(it, lb))
            return btn
        make_btn(0, '左手', left_item, 'left')
        make_btn(1, '盔甲', armor_item, 'armor')
        make_btn(2, '右手', right_item, 'right')
        # 悬浮区域覆盖整个卡片
        def card_tip():
            parts = [f"名称: {name}", f"职业: {job}", f"HP: {cur_hp}/{max_hp}"]
            parts.append(f"攻击: {total_atk} (基础{base_atk} + 装备{eq_atk})")
            parts.append(f"防御: {eq_def}")
            eq_list = []
            if left_item:
                eq_list.append(f"左手: {getattr(left_item, 'name', '-')}")
            if right_item_raw:
                eq_list.append(f"右手: {getattr(right_item_raw, 'name', '-')}")
            if armor_item:
                eq_list.append(f"盔甲: {getattr(armor_item, 'name', '-')}")
            if eq_list:
                parts.append("装备: " + ", ".join(eq_list))
            return "\n".join(parts)
        self._attach_tooltip(frame, card_tip)
        # 技能栏（卡片下方）
        skill_bar = ttk.Frame(parent)
        skill_bar.pack(fill=tk.X, pady=(1, 0))
        skills = []
        # 默认攻击
        skills.append({"name": "攻击", "type": "attack", "enabled": can_attack and ap > 0})
        # 牧师有治疗
        if job == "牧师":
            skills.append({"name": "治疗", "type": "heal", "enabled": ap > 0})
        for idx, sk in enumerate(skills):
            btn = ttk.Button(skill_bar, text=sk["name"], width=6, state=tk.NORMAL if sk["enabled"] else tk.DISABLED,
                             command=lambda t=sk["type"]: self._select_skill(m_index, t))
            btn.pack(side=tk.LEFT, padx=2)
        return frame

    def _render_resources(self):
        # 清空并重建资源按钮
        for ch in list(self.res_buttons_container.winfo_children()):
            ch.destroy()
        self.selected_res_index = None
        try:
            s = self.controller.game.get_state()
            res = s.get('resources', [])
        except Exception:
            res = []
        if not res:
            ttk.Label(self.res_buttons_container, text="(空)", foreground="#888").pack(anchor=tk.W)
            return
        for i, r in enumerate(res, 1):
            text = f"r{i}  {r}"
            btn = ttk.Button(self.res_buttons_container, text=text, width=10, command=lambda idx=i: self._pick_resource(idx))
            btn.pack(side=tk.LEFT, padx=2, pady=2)
        # 不再有滚动框

    # -------- Equip/Actions --------
    def _slot_click(self, m_index: int, slot_key: str, item):
        if item is None:
            self._open_equip_dialog(m_index, slot_key)
            return
        choice = messagebox.askyesnocancel(
            "装备操作",
            f"槽位[{slot_key}] 当前为 {getattr(item, 'name', '装备')}\n是 否：卸下；否：更换；取消：关闭",
            icon='question'
        )
        if choice is True:
            effective = slot_key
            try:
                board = self.controller.game.player.board
                m = board[m_index - 1]
                eq = getattr(m, 'equipment', None)
                if slot_key == 'right' and eq and getattr(eq, 'left_hand', None) and getattr(eq.left_hand, 'is_two_handed', False):
                    effective = 'left'
            except Exception:
                pass
            slot = {'left': 'left', 'right': 'right', 'armor': 'armor'}.get(effective, effective)
            token = f"m{m_index}"
            out, _ = self.controller._process_command(f"uneq {token} {slot}")
            self._after_cmd(out)
        elif choice is False:
            self._open_equip_dialog(m_index, slot_key)
        else:
            return

    def _open_equip_dialog(self, m_index: int, slot_key: str):
        top = tk.Toplevel(self.root)
        top.title("选择装备")
        top.transient(self.root)
        top.grab_set()
        frm = ttk.Frame(top, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text=f"为 m{m_index} 选择装备到 [{slot_key}]:").pack(anchor=tk.W)
        tip_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=tip_var, foreground="#666").pack(anchor=tk.W)
        lb = tk.Listbox(frm, height=12)
        lb.pack(fill=tk.BOTH, expand=True, pady=6)
        preview_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=preview_var, foreground="#0a0").pack(anchor=tk.W, pady=(0, 4))

        try:
            from systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
        except Exception:
            WeaponItem = ArmorItem = ShieldItem = tuple()  # type: ignore
        inv = self.controller.game.player.inventory
        index_map: list[int] = []
        try:
            m = self.controller.game.player.board[m_index - 1]
            eq = getattr(m, 'equipment', None)
        except Exception:
            m = None
            eq = None

        def fits_slot_and_ok(it) -> bool:
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

        blocked_msg = None
        if slot_key == 'right' and eq and getattr(eq, 'left_hand', None) and getattr(eq.left_hand, 'is_two_handed', False):
            blocked_msg = '当前持双手武器，右手不可装备'
        for idx, slot in enumerate(inv.slots, 1):
            it = slot.item
            if fits_slot_and_ok(it):
                atk = int(getattr(it, 'attack', 0) or 0)
                dfn = int(getattr(it, 'defense', 0) or 0)
                flags = []
                if getattr(it, 'is_two_handed', False):
                    flags.append('双手')
                stats = []
                if atk: stats.append(f"+{atk}攻")
                if dfn: stats.append(f"+{dfn}防")
                stat_str = (" " + " ".join(stats)) if stats else ""
                flag_str = (" [" + ", ".join(flags) + "]") if flags else ""
                label = f"{getattr(it, 'name', str(it))}{stat_str}{flag_str}"
                lb.insert(tk.END, f"i{idx}  {label}")
                index_map.append(idx)
        if blocked_msg:
            tip_var.set(blocked_msg)
        elif not index_map:
            tip_var.set('暂无可装备的物品')

        def fmt_delta(v: int) -> str:
            return f"+{v}" if v > 0 else (f"{v}" if v < 0 else "±0")

        def update_preview(evt=None):
            if not index_map:
                preview_var.set("")
                return
            sel = lb.curselection()
            if not sel:
                preview_var.set("")
                return
            try:
                i_idx = index_map[sel[0]]
                it = inv.slots[i_idx - 1].item
                m = self.controller.game.player.board[m_index - 1]
                eq = getattr(m, 'equipment', None)
                cur_eq_atk = int(eq.get_total_attack() if eq else 0)
                cur_eq_def = int(eq.get_total_defense() if eq else 0)
                lh = getattr(eq, 'left_hand', None) if eq else None
                rh = getattr(eq, 'right_hand', None) if eq else None
                ar = getattr(eq, 'armor', None) if eq else None
                new_lh, new_rh, new_ar = lh, rh, ar
                if slot_key == 'armor':
                    new_ar = it
                elif slot_key == 'left':
                    if getattr(it, 'is_two_handed', False):
                        new_lh, new_rh = it, None
                    else:
                        new_lh = it
                elif slot_key == 'right':
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
                messagebox.showinfo("提示", "请选择一件装备")
                return
            i_idx = index_map[sel[0]]
            token = f"m{m_index}"
            out, _ = self.controller._process_command(f"eq i{i_idx} {token}")
            self._after_cmd(out)
            try:
                top.destroy()
            except Exception:
                pass

        def do_cancel():
            try:
                top.destroy()
            except Exception:
                pass

        lb.bind('<Double-Button-1>', do_confirm)
        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="确认装备", command=do_confirm).pack(side=tk.LEFT)
        ttk.Button(btns, text="取消", command=do_cancel).pack(side=tk.RIGHT)

    def _attach_tooltip(self, widget: tk.Widget, text_provider):
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

    # -------- Actions --------
    def _append_info(self, text: str):
        self.text_info.insert(tk.END, C.strip(text) + "\n")
        self.text_info.see(tk.END)

    def _append_log(self, text: str):
        self.text_log.insert(tk.END, C.strip(text) + "\n")
        self.text_log.see(tk.END)

    def _selected_index(self, lb: tk.Listbox) -> Optional[int]:
        sel = lb.curselection()
        if not sel:
            return None
        return sel[0]

    def _pick_resource(self, idx: int):
        out, _ = self.controller._process_command(f"t r{idx}")
        self._after_cmd(out)

    def on_attack(self):
        if not self.controller:
            return
        if not self.selected_member_index:
            messagebox.showinfo("提示", "请先在底部卡片选择一名队员(mN)")
            return
        if self.selected_enemy_index:
            e_token = f"e{self.selected_enemy_index}"
        else:
            e_idx = self._selected_index(self.list_enemy)
            if e_idx is None:
                messagebox.showinfo("提示", "请在顶部卡片或左上列表选择一个敌人(eN)")
                return
            e_token = self.list_enemy.get(e_idx).split()[0]
        m_token = f"m{self.selected_member_index}"
        out, _ = self.controller._process_command(f"a {m_token} {e_token}")
        self._after_cmd(out)

    def on_pick(self):
        if not self.controller:
            return
        messagebox.showinfo("提示", "请点击右侧资源按钮进行拾取")

    def on_use_or_equip(self):
        if not self.controller:
            return
        idx = self._selected_index(self.list_inv)
        if idx is None:
            messagebox.showinfo("提示", "请选择背包条目(iN 或物品名行)")
            return
        raw = self.list_inv.get(idx)
        parts = raw.split()
        token = parts[0]
        tgt_m = None
        if self.selected_member_index:
            tgt_m = f"m{self.selected_member_index}"
        if token.startswith('i') and token[1:].isdigit():
            if not tgt_m:
                messagebox.showinfo("提示", "装备需先在底部卡片选择目标(mN)")
                return
            out, _ = self.controller._process_command(f"eq {token} {tgt_m}")
        else:
            name = raw if not token.startswith('i') else ' '.join(parts[1:])
            cmd = f"use {name}"
            if tgt_m:
                cmd += f" {tgt_m}"
            out, _ = self.controller._process_command(cmd)
        self._after_cmd(out)

    def on_unequip_dialog(self):
        if not self.controller:
            return
        if not self.selected_member_index:
            messagebox.showinfo("提示", "请先在底部卡片选择一名队员")
            return
        m_token = f"m{self.selected_member_index}"
        slot = simpledialog.askstring("卸下装备", "输入槽位: left|right|armor", parent=self.root)
        if not slot:
            return
        out, _ = self.controller._process_command(f"uneq {m_token} {slot}")
        self._after_cmd(out)

    def on_craft_quick(self):
        if not self.controller:
            return
        idx = self._selected_index(self.list_inv)
        if idx is None:
            out, _ = self.controller._process_command("craft")
            self._after_cmd(out)
            return
        raw = self.list_inv.get(idx).strip()
        if raw.startswith('c') and raw[1:].split()[0].isdigit():
            n = raw[1:].split()[0]
            out, _ = self.controller._process_command(f"c{n}")
        else:
            out, _ = self.controller._process_command("craft")
        self._after_cmd(out)

    def _run_cmd(self, cmd: str):
        if not self.controller:
            return
        out, _ = self.controller._process_command(cmd)
        self._after_cmd(out)

    def _after_cmd(self, out_lines: list[str]):
        self.text_info.delete('1.0', tk.END)
        for line in out_lines or []:
            self._append_info(line)
        self.refresh_all()

    # -------- Mode --------
    def _start_game(self, player_name: str, initial_scene: Optional[str]):
        self.controller = SimplePvEController(player_name=player_name, initial_scene=initial_scene)
        self.frame_menu.pack_forget()
        self.frame_game.pack(fill=tk.BOTH, expand=True)
        self.mode = 'game'
        full = self.controller._render_full_view()
        self.text_info.delete('1.0', tk.END)
        for line in full.splitlines():
            self._append_info(line)
        self.refresh_all()
        try:
            base = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'PYHS')
            os.makedirs(base, exist_ok=True)
            path = os.path.join(base, 'scene_runtime.txt')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"player_name: {player_name}\n")
                f.write(f"initial_scene: {initial_scene}\n")
                try:
                    f.write(f"current_scene: {self.controller.game.current_scene}\n")
                except Exception:
                    f.write("current_scene: <error>\n")
                try:
                    f.write(f"current_scene_title: {self.controller.game.current_scene_title}\n")
                except Exception:
                    f.write("current_scene_title: <error>\n")
                try:
                    f.write("--- full view ---\n")
                    f.write(self.controller._render_full_view() + "\n")
                except Exception:
                    f.write("<could not render full view>\n")
                try:
                    logs = self.controller.game.pop_logs()
                    f.write("--- logs ---\n")
                    for L in logs:
                        f.write(str(L) + "\n")
                except Exception:
                    pass
        except Exception:
            pass

    def _back_to_menu(self):
        self.controller = None
        self.frame_game.pack_forget()
        self.frame_menu.pack(fill=tk.BOTH, expand=True)
        self.mode = 'menu'
        self.lbl_profile.config(text=self._menu_profile())

    def run(self):
        self.root.minsize(980, 700)
        self.root.mainloop()


def run_tk(player_name: str = "玩家", initial_scene: Optional[str] = None):
    app = GameTkApp(player_name=player_name, initial_scene=initial_scene)
    app.run()
