"""Full GameTkApp implementation migrated from `ui.gui_app`.

This module lives in the `ui.tkinter` package and therefore uses
relative imports for other UI helpers.
"""
from __future__ import annotations

import os
from src import app_config as CFG
import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional

from src.game_modes.pve_controller import SimplePvEController
from .. import colors as C
from . import ui_utils as U
from . import animations as ANIM
from . import cards as tk_cards
from . import resources as tk_resources
from . import operations as tk_operations
from .views import EnemiesView, AlliesView, ResourcesView, OperationsView
from src.ui.targeting.specs import DEFAULT_SPECS, SkillTargetSpec
from src.ui.targeting.fsm import TargetingEngine
# Inline 选择：不使用弹窗选择器
from src.core.events import subscribe as subscribe_event, unsubscribe as unsubscribe_event

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
		# 选中描边粗细（保持常量，避免选中时布局跳动）
		self._border_default = 3
		self._border_selected_enemy = 3
		self._border_selected_member = 3
		# 固定卡面尺寸与禁用抖动（避免视觉“抖动”）
		self.CARD_W = 180
		self.CARD_H = 80
		self._no_shake = True
		# 高亮风格（可调色）：候选与选中分别有描边与浅底色
		self._wrap_bg_default = self.root.cget('bg')
		self.HL = {
			'cand_enemy_border': '#FAD96B',  # 候选敌人描边（亮黄）
			'cand_enemy_bg':     '#FFF7CC',  # 候选敌人底色（浅黄）
			'cand_ally_border':  '#7EC6F6',  # 候选友方描边（亮蓝）
			'cand_ally_bg':      '#E6F4FF',  # 候选友方底色（浅蓝）
			'sel_enemy_border':  '#FF4D4F',  # 选中敌人描边（醒目红）
			'sel_enemy_bg':      '#FFE6E6',  # 选中敌人底色（淡红）
			'sel_ally_border':   '#1E90FF',  # 选中友方描边（深蓝）
			'sel_ally_bg':       '#D6EBFF',  # 选中友方底色（淡蓝）
		}

		# Containers
		self.frame_menu = ttk.Frame(self.root)
		self.frame_game = ttk.Frame(self.root)
		self.frame_menu.pack(fill=tk.BOTH, expand=True)

		self._build_menu(self.frame_menu)
		self._build_game(self.frame_game)

		# UI 更新抑制/合并标记（场景切换时启用，合并多次刷新请求）
		self._suspend_ui_updates = False
		self._pending_battlefield_refresh = False
		self._pending_resource_refresh = False
		self._pending_ops_refresh = False

		# 订阅核心事件（场景变更）+ 挂载视图单例订阅其自有事件
		self._event_handlers = []
		try:
			self._event_handlers.append(('scene_changed', subscribe_event('scene_changed', self._on_event_scene_changed)))
		except Exception:
			pass
		# 视图单例：分别订阅其关注的事件
		self.views = {
			'enemies': EnemiesView(self),
			'allies': AlliesView(self),
			'resources': ResourcesView(self),
			'ops': OperationsView(self),
		}
		for v in self.views.values():
			try:
				v.mount()
			except Exception:
				pass

		# 若传入了 initial_scene，则自动进入游戏（避免用户还需手动点击“开始游戏”）
		try:
			if self._pending_scene:
				# 使用 cfg 中 name（已同步）作为玩家名
				self._start_game(self.cfg.get('name', player_name), self._pending_scene)
		except Exception:
			# 不应阻塞 UI 初始化
			pass

	# ---- helpers ----

	def _bind_views_context(self):
		"""让各 View 直接持有 game 引用，避免通过 app 转发。"""
		try:
			g = self.controller.game if (self.controller and hasattr(self.controller, 'game')) else None
		except Exception:
			g = None
		for key in ('enemies', 'allies', 'resources', 'ops'):
			v = (self.views or {}).get(key)
			if v and hasattr(v, 'set_context'):
				try:
					v.set_context(g)
				except Exception:
					pass

	def _log_exception(self, exc: Exception, context: str = ""):
		"""记录异常到日志控件或打印，避免 silent pass。"""
		try:
			msg = f"ERROR{('['+context+']') if context else ''}: {exc}"
			if hasattr(self, 'text_log'):
				try:
					self._append_log(msg)
				except Exception:
					print(msg)
			else:
				print(msg)
		except Exception:
			print('ERROR while logging exception', exc)

	def _reset_highlights(self):
		"""恢复所有卡片/敌人默认边框色，防止残留高亮。"""
		try:
			for w in list(getattr(self, 'enemy_card_wraps', {}).values()):
				try:
					w.configure(highlightbackground="#cccccc", highlightthickness=self._border_default, background=self._wrap_bg_default)
				except Exception:
					pass
			for w in list(getattr(self, 'card_wraps', {}).values()):
				try:
					w.configure(highlightbackground="#cccccc", highlightthickness=self._border_default, background=self._wrap_bg_default)
				except Exception:
					pass
		except Exception as e:
			self._log_exception(e, '_reset_highlights')

	def _send(self, cmd: str):
		"""Normalize higher-level command names to controller tokens and send.

		This preserves backward compatibility with existing controller verbs.
		"""
		if not self.controller:
			return [], {}
		parts = cmd.split()
		if not parts:
			return [], {}
		verb = parts[0]
		rest = parts[1:]
		m = {
			'attack': 'a', 'atk': 'a', 'a': 'a',
			'heal': 'heal',
			'equip': 'eq', 'eq': 'eq',
			'unequip': 'uneq', 'uneq': 'uneq',
			'pick': 't', 'take': 't', 't': 't',
			'use': 'use',
			'end': 'end', 'back': 'back',
			'craft': 'craft'
		}
		mapped = m.get(verb, verb)
		# craft with number -> cN
		if mapped == 'craft':
			if rest:
				mapped_cmd = f"c{rest[0]}"
			else:
				mapped_cmd = 'craft'
		else:
			mapped_cmd = ' '.join([mapped] + rest)
		try:
			out = self.controller._process_command(mapped_cmd)
			return out
		except Exception as e:
			self._log_exception(e, f'_send {mapped_cmd}')
			return [], {}

	# -------- Event handlers --------
	def _on_event_scene_changed(self, _evt: str, payload: dict):
		# 场景切换：立即更新标题与状态；稍作延时让死亡/伤害浮字有机会展示，然后再全量刷新。
		try:
			# 进入抑制窗口：期间的 UI 刷新请求被合并，待窗口结束后一次性处理
			self._suspend_ui_updates = True
			label = payload.get('scene_title') or payload.get('scene_path')
			if label:
				self.scene_var.set(f"场景: {label}")
			self._append_log({'type': 'info', 'text': f"进入场景: {label}"})
		except Exception:
			pass
		# 清理选择态与目标态，避免跨场景残留
		try:
			self.selected_enemy_index = None
			self.selected_member_index = None
			self.selected_skill = None
			self.skill_target_token = None
			if getattr(self, 'target_engine', None):
				# 统一重置目标引擎，避免跨场景阻塞点击
				try:
					self.target_engine.cancel()
				except Exception:
					pass
				try:
					self.target_engine.reset()
				except Exception:
					pass
		except Exception:
			pass
		# 延迟再刷新，让死亡浮字短暂呈现
		def _do_full():
			try:
				# 结束抑制窗口，执行一次全量刷新
				self._suspend_ui_updates = False
				setattr(self, '_pending_battlefield_refresh', False)
				# 重新绑定视图上下文，确保直接持有最新的 game/scene 引用
				try:
					self._bind_views_context()
				except Exception:
					pass
				self.refresh_all(skip_info_log=True)
			except Exception:
				# 容错：退化为局部刷新
				try:
					self.refresh_battlefield_only()
				except Exception:
					pass
			# 处理抑制期间积累的资源/操作栏刷新请求
			try:
				if getattr(self, '_pending_resource_refresh', False):
					self._pending_resource_refresh = False
					self._render_resources()
			except Exception:
				pass
			try:
				if getattr(self, '_pending_ops_refresh', False):
					self._pending_ops_refresh = False
					self._render_operations()
			except Exception:
				pass
			# 下一帧再更新一次操作栏/日志，避免 I/O 卡顿
			try:
				self.root.after(0, lambda: (
					self._render_operations(),
					self._after_cmd(self.controller._render_full_view() if self.controller else [])
				))
			except Exception:
				pass
		try:
			self.root.after(250, _do_full)
		except Exception:
			_do_full()


	def _on_event_inventory_changed(self, _evt: str, _payload: dict):
		# 背包/资源变化：只刷新资源/背包区域
		try:
			if getattr(self, '_suspend_ui_updates', False):
				self._pending_resource_refresh = True
				return
			self._render_resources()
		except Exception:
			pass

	def _on_enemy_zone_event(self, _evt: str, _payload: dict):
		"""敌人区的 ObservableList 事件：添加/移除/清空/重置/变化。统一做轻量战场重绘（去重调度）。"""
		try:
			self._schedule_battlefield_refresh()
		except Exception:
			pass

	def _on_resource_zone_event(self, _evt: str, _payload: dict):
		"""资源区的 ObservableList 事件：仅重绘资源按钮容器。"""
		try:
			if getattr(self, '_suspend_ui_updates', False):
				self._pending_resource_refresh = True
				self._pending_ops_refresh = True
				return
			self._render_resources()
			# 操作栏可能受资源使用影响（例如药水可用性），一并刷新
			self._render_operations()
		except Exception:
			pass

	def _on_event_equipment_changed(self, _evt: str, _payload: dict):
		# 装备变化：仅刷新操作栏与受影响卡片的数值，避免整块重绘
		try:
			if getattr(self, '_suspend_ui_updates', False):
				self._pending_ops_refresh = True
				# 卡片的细节变更会在切换完成时统一刷新
				return
			card = (_payload or {}).get('owner') or (_payload or {}).get('card')
			self._render_operations()
			# 背包列表也会改变（装备/卸下），需要刷新
			self._refresh_inventory_only()
			if not card:
				return
			# 更新对应卡片
			for idx, wrap in (getattr(self, 'card_wraps', {}) or {}).items():
				inner = next((ch for ch in wrap.winfo_children() if hasattr(ch, '_model_ref')), None)
				if inner is None or getattr(inner, '_model_ref', None) is not card:
					continue
				try:
					atk = int(getattr(card, 'get_total_attack')() if hasattr(card, 'get_total_attack') else getattr(card, 'attack', 0))
					defv = int(getattr(card, 'get_total_defense')() if hasattr(card, 'get_total_defense') else getattr(card, 'defense', 0))
					cur = int(getattr(card, 'hp', 0)); mx = int(getattr(card, 'max_hp', cur))
					inner._atk_var.set(f"ATK {atk}")
					inner._ac_var.set(f"AC {10 + defv}")
					inner._hp_var.set(f"HP {cur}/{mx}")
					# 同步装备按钮文字与提示（不重建控件，避免闪烁）
					try:
						eq = getattr(card, 'equipment', None)
						lh = getattr(eq, 'left_hand', None) if eq else None
						rh_raw = getattr(eq, 'right_hand', None) if eq else None
						ar = getattr(eq, 'armor', None) if eq else None
						# 双手武器占用右手显示
						rh = lh if getattr(lh, 'is_two_handed', False) else rh_raw
						def _slot_text(label, item):
							return (getattr(item, 'name', '-')) if item else f"{label}: -"
						def _tip_text(item, label):
							if not item:
								return f"{label}: 空槽"
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
							head = getattr(item, 'name', '')
							tail = ' '.join(parts)
							return head + (("\n" + tail) if tail else '')
						# 更新文字
						if hasattr(inner, '_btn_left') and inner._btn_left:
							inner._btn_left.config(text=_slot_text('左手', lh))
						if hasattr(inner, '_btn_right') and inner._btn_right:
							inner._btn_right.config(text=_slot_text('右手', rh))
						if hasattr(inner, '_btn_armor') and inner._btn_armor:
							inner._btn_armor.config(text=_slot_text('盔甲', ar))
						# 重新绑定提示：先解绑，后绑定最新文本
						def _rebind_tip(btn, provider):
							try:
								btn.unbind('<Enter>'); btn.unbind('<Leave>'); btn.unbind('<Motion>')
							except Exception:
								pass
							try:
								U.attach_tooltip_deep(btn, provider)
							except Exception:
								pass
						if hasattr(inner, '_btn_left') and inner._btn_left:
							_rebind_tip(inner._btn_left, lambda it=lambda: getattr(getattr(card, 'equipment', None), 'left_hand', None): _tip_text(it(), '左手'))
						if hasattr(inner, '_btn_right') and inner._btn_right:
							_rebind_tip(inner._btn_right, lambda it=lambda: (getattr(getattr(card, 'equipment', None), 'left_hand', None) if getattr(getattr(getattr(card, 'equipment', None), 'left_hand', None), 'is_two_handed', False) else getattr(getattr(card, 'equipment', None), 'right_hand', None)): _tip_text(it(), '右手'))
						if hasattr(inner, '_btn_armor') and inner._btn_armor:
							_rebind_tip(inner._btn_armor, lambda it=lambda: getattr(getattr(card, 'equipment', None), 'armor', None): _tip_text(it(), '盔甲'))
					except Exception:
						pass
				except Exception:
					pass
				break
		except Exception:
			pass


	def _on_event_resource_changed(self, _evt: str, _payload: dict):
		# 资源区改变：只刷新资源按钮
		try:
			self._render_resources()
		except Exception:
			pass

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
		# 更紧凑的默认样式
		try:
			self.style = ttk.Style(self.root)
			self.style.configure("Tiny.TButton", font=("Segoe UI", 8), padding=(4, 2))
			self.style.configure("Tiny.TLabel", font=("Segoe UI", 8))
			self.style.configure("TinyBold.TLabel", font=("Segoe UI", 9, "bold"))
			# 更紧凑的卡片槽按钮样式
			self.style.configure("Slot.TButton", font=("Segoe UI", 8), padding=(0, 0))
		except Exception:
			self.style = None
		ttk.Label(top, textvariable=self.scene_var, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
		ttk.Button(top, text="主菜单", command=self._back_to_menu, style="Tiny.TButton").pack(side=tk.RIGHT)

		# 顶部：敌人卡片
		frm_enemy_cards = ttk.LabelFrame(parent, text="敌人 (点击选择 eN)")
		frm_enemy_cards.pack(fill=tk.X, expand=False, padx=6, pady=(2, 2))
		self.enemy_cards_container = ttk.Frame(frm_enemy_cards)
		self.enemy_cards_container.pack(fill=tk.X, expand=False, padx=4, pady=4)
		self.enemy_card_wraps = {}
		self.selected_enemy_index = None
		# 技能/目标选择状态
		self.selected_skill = None            # 模式：'attack'/'heal'/...
		self.selected_skill_name = None       # 技能名字，例如 'attack'|'basic_heal'|'drain'
		self.skill_target_index = None        # 目标索引（整数）
		self.skill_target_token = None        # 目标 token: eN/mN
		# 统一目标选择引擎
		self.target_engine = TargetingEngine(self)

		# 中部主体（资源与背包并排，底部统一“战斗日志”）
		body = ttk.Frame(parent)
		body.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 6))
		body.rowconfigure(0, weight=1)
		body.rowconfigure(1, weight=0)
		body.rowconfigure(2, weight=0)
		body.rowconfigure(3, weight=1)
		# 让底部信息/日志行可伸展
		body.rowconfigure(4, weight=1)
		# 左列（资源）尽量使用最小宽度，右列（背包/主区）扩展
		body.columnconfigure(0, weight=0, uniform='col')
		body.columnconfigure(1, weight=1, uniform='col')

		# 资源按钮区（左）
		frm_res = ttk.LabelFrame(body, text="资源 (点击拾取)")
		frm_res.grid(row=0, column=0, sticky='nsew', padx=(0, 3), pady=(0, 3))
		self.res_buttons_container = ttk.Frame(frm_res)
		# 垂直排列并尽量不占用过宽空间
		# 使用 pack 的垂直排列，让按钮沿列堆叠并保持窄宽度
		self.res_buttons_container.pack(fill=tk.Y, expand=False, padx=6, pady=6)
		self.selected_res_index = None

		# 背包（右）
		frm_inv = ttk.LabelFrame(body, text="背包 / 可合成 (iN / 名称 / cN)")
		frm_inv.grid(row=0, column=1, sticky='nsew', padx=(3, 0), pady=(0, 3))
		self.list_inv = tk.Listbox(frm_inv, activestyle='dotbox')
		sb_inv = ttk.Scrollbar(frm_inv, orient='vertical', command=self.list_inv.yview)
		self.list_inv.configure(yscrollcommand=sb_inv.set)
		self.list_inv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
		sb_inv.pack(side=tk.RIGHT, fill=tk.Y)

		# 操作（仅保留结束回合）
		actions = ttk.Frame(body)
		actions.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(2, 2))
		for i in range(6):
			actions.columnconfigure(i, weight=1)
		# 返回上一级：切换到上一张地图（若可用），而不是返回主菜单
		ttk.Button(actions, text="返回上一级", command=lambda: self._run_cmd('back'), style="Tiny.TButton").grid(row=0, column=0, padx=2, sticky='w')
		ttk.Button(actions, text="结束回合 (end)", command=lambda: self._run_cmd('end'), style="Tiny.TButton").grid(row=0, column=1, padx=2, sticky='w')

		# 队伍卡片
		frm_cards = ttk.LabelFrame(body, text="队伍 (点击选择 mN)")
		frm_cards.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(2, 4))
		self.cards_container = ttk.Frame(frm_cards)
		self.cards_container.pack(fill=tk.X, expand=False, padx=4, pady=4)
		self.card_wraps = {}
		self.selected_member_index = None

		# 操作栏：在队伍下方显示所选英雄的可用操作（攻击/装备/卸下/替换）
		self.frm_operations = ttk.LabelFrame(body, text="操作栏")
		self.frm_operations.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(2, 4))
		self.frm_operations.columnconfigure(0, weight=1)
		# 初始占位
		ttk.Label(self.frm_operations, text="(未选择队员)", foreground="#666").grid(row=0, column=0, sticky='w', padx=6, pady=6)

		# 底部：统一“战斗日志”
		bottom = ttk.Frame(body)
		bottom.grid(row=4, column=0, columnspan=2, sticky='nsew')
		bottom.columnconfigure(0, weight=1)

		frm_log = ttk.LabelFrame(bottom, text="战斗日志")
		frm_log.grid(row=0, column=0, sticky='nsew', padx=(0, 0), pady=(3, 3))
		self.text_log = tk.Text(frm_log, height=10, wrap='word')
		sb_log = ttk.Scrollbar(frm_log, orient='vertical', command=self.text_log.yview)
		self.text_log.configure(yscrollcommand=sb_log.set)
		self.text_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
		sb_log.pack(side=tk.RIGHT, fill=tk.Y)
		# 日志语义颜色标签
		try:
			# 基础
			self.text_log.tag_configure('info', foreground='#222')
			self.text_log.tag_configure('success', foreground='#27ae60')
			self.text_log.tag_configure('warning', foreground='#E67E22')
			self.text_log.tag_configure('error', foreground='#d9534f', underline=True)
			self.text_log.tag_configure('state', foreground="#666")
			# 战斗语义
			self.text_log.tag_configure('attack', foreground='#c0392b', font=("Segoe UI", 8, 'bold'))
			self.text_log.tag_configure('heal', foreground='#27ae60', font=("Segoe UI", 8, 'bold'))
			self.text_log.tag_configure('crit', foreground='#8E44AD', font=("Segoe UI", 8, 'bold'))
			self.text_log.tag_configure('miss', foreground='#95A5A6', font=("Segoe UI", 8, 'italic'))
			self.text_log.tag_configure('block', foreground='#2C3E50', font=("Segoe UI", 8))
		except Exception:
			pass
		try:
			self.text_log.bind('<Motion>', self._on_log_motion)
		except Exception:
			pass

	# -------- Render --------
	def refresh_all(self, skip_info_log: bool = False):
		if self.mode != 'game' or not self.controller:
			return
		# 校验或重置选择态，防止幽灵高亮
		if getattr(self, 'selected_enemy_index', None) not in getattr(self, 'enemy_card_wraps', {}):
			self.selected_enemy_index = None
		if getattr(self, 'selected_member_index', None) not in getattr(self, 'card_wraps', {}):
			self.selected_member_index = None
		# 场景标题
		try:
			scene = getattr(self.controller.game, 'current_scene_title', None) or self.controller.game.current_scene
			if scene:
				if getattr(self.controller.game, 'current_scene_title', None):
					self.scene_var.set(f"场景: {scene}")
				else:
					self.scene_var.set(f"场景: {os.path.basename(scene)}")
		except Exception:
			self.scene_var.set("场景: -")

		# 列表区：背包与资源
		self._refresh_inventory_only()
		self._render_resources()

		# 统一日志：状态快照 + 结构化事件
		if not skip_info_log:
			for line in (self.controller._section_info() or '').splitlines():
				self._append_log({'type': 'state', 'text': line, 'meta': {'state': True}})
			try:
				logs = self.controller.game.pop_logs()
				for line in logs:
					self._append_log(line)
			except Exception:
				pass

		# 卡片
		self._render_enemy_cards()
		self._render_cards()
		# 操作栏也需要同步刷新
		try:
			self._render_operations()
		except Exception:
			pass
		# 重新应用选择与技能目标高亮，避免刷新导致失焦
		try:
			if self.selected_enemy_index and self.selected_enemy_index in self.enemy_card_wraps:
				self.enemy_card_wraps[self.selected_enemy_index].configure(highlightbackground=self.HL['sel_enemy_border'], background=self.HL['sel_enemy_bg'], highlightthickness=self._border_selected_enemy)
			if self.selected_member_index and self.selected_member_index in self.card_wraps:
				self.card_wraps[self.selected_member_index].configure(highlightbackground=self.HL['sel_ally_border'], background=self.HL['sel_ally_bg'], highlightthickness=self._border_selected_member)
			# 技能模式底色
			if getattr(self, 'selected_skill', None) == 'attack':
				for idx, wrap in self.enemy_card_wraps.items():
					wrap.configure(highlightbackground=self.HL['cand_enemy_border'], background=self.HL['cand_enemy_bg'])
			if getattr(self, 'selected_skill', None) == 'heal':
				for idx, wrap in self.card_wraps.items():
					wrap.configure(highlightbackground=self.HL['cand_ally_border'], background=self.HL['cand_ally_bg'])
			# 已选择具体目标则加强高亮
			if getattr(self, 'skill_target_token', None):
				tok = self.skill_target_token
				if isinstance(tok, str) and len(tok) >= 2:
					try:
						if tok[0] == 'e':
							i = int(tok[1:])
							if i in self.enemy_card_wraps:
								self.enemy_card_wraps[i].configure(highlightbackground=self.HL['sel_enemy_border'], background=self.HL['sel_enemy_bg'], highlightthickness=self._border_selected_enemy)
						elif tok[0] == 'm':
							i = int(tok[1:])
							if i in self.card_wraps:
								self.card_wraps[i].configure(highlightbackground=self.HL['sel_ally_border'], background=self.HL['sel_ally_bg'], highlightthickness=self._border_selected_member)
					except Exception:
						pass
		except Exception:
			pass

	def _render_enemy_cards(self):
		# 交由视图实现
		v = self.views.get('enemies')
		return v.render_all(self.enemy_cards_container) if v else None

	def _create_enemy_card(self, parent: tk.Widget, e, e_index: int) -> ttk.Frame:
		# 兼容旧 API：直接转给视图实现
		v = self.views.get('enemies')
		if v and hasattr(v, '_create_enemy_card'):
			return v._create_enemy_card(parent, e, e_index)
		return tk_cards.create_character_card(self, parent, e, e_index, is_enemy=True)

	def _select_skill(self, m_index: int, skill_type: str):
		# 选择技能后高亮可用目标（不立即执行）
		self.selected_skill = skill_type
		self.skill_target_index = None
		self.skill_target_token = None
		if skill_type == "attack":
			# 高亮可攻击敌人
			for idx, wrap in self.enemy_card_wraps.items():
				e = getattr(self.controller.game, 'enemies', [])[idx-1] if hasattr(self.controller.game, 'enemies') else None
				can_attack = getattr(e, 'can_be_attacked', True)
				if can_attack:
					wrap.configure(highlightbackground=self.HL['cand_enemy_border'], background=self.HL['cand_enemy_bg'])
				else:
					wrap.configure(highlightbackground="#cccccc", background=self._wrap_bg_default)
		elif skill_type == "heal":
			# 高亮可治疗队友（HP未满且不是自己）
			for idx, wrap in self.card_wraps.items():
				m = getattr(self.controller.game.player, 'board', [])[idx-1] if hasattr(self.controller.game.player, 'board') else None
				can_heal = m and getattr(m, 'hp', 0) < getattr(m, 'max_hp', 0) and idx != m_index
				if can_heal:
					wrap.configure(highlightbackground=self.HL['cand_ally_border'], background=self.HL['cand_ally_bg'])
				else:
					wrap.configure(highlightbackground="#cccccc", background=self._wrap_bg_default)
		# 展示确认/取消
		try:
			self._render_operations()
		except Exception:
			pass
		# 同时弹出统一目标选择器，避免混乱
		try:
			self._open_target_picker(skill_type, m_index)
		except Exception:
			pass

	def begin_skill(self, m_index: int, name: str):
		"""统一技能入口：根据 skill_specs 决定目标要求并引导 UI。
		使用 TargetingEngine 与默认规格 DEFAULT_SPECS。
		"""
		self.selected_member_index = m_index
		self.selected_skill_name = name
		src = f"m{m_index}"
		need_exec = self.target_engine.begin(src, name)
		if need_exec:
			# 无需目标（self/aoe），直接执行
			out = self._send(f"skill {name} {src}")
			try:
				resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
			except Exception:
				resp = out
			self._after_cmd(resp)
			# 立即清理目标会话与技能选择，避免阻塞后续点击
			try:
				self.selected_skill = None
				self.selected_skill_name = None
				self.skill_target_index = None
				self.skill_target_token = None
				self._reset_highlights()
				if getattr(self, 'target_engine', None):
					self.target_engine.reset()
			except Exception:
				pass
			# AOE 常伴随多名敌人死亡/移除，主动刷新战场一次，保证 UI 与事件对齐
			try:
				self.refresh_battlefield_only()
			except Exception:
				pass
			return
		# 在主界面进行目标选择：高亮候选，并在操作栏渲染内联候选按钮
		self._update_target_highlights()
		try:
			self._render_operations()
		except Exception:
			pass

	def _confirm_skill(self):
		"""执行已选择的技能（或普通攻击）并清理状态。"""
		try:
			if not self.selected_member_index:
				return
			name = getattr(self, 'selected_skill_name', None)
			src = f"m{self.selected_member_index}"
			# 优先从 TargetingEngine 读取选择
			selected = []
			try:
				if getattr(self, 'target_engine', None) and self.target_engine.is_ready():
					selected = self.target_engine.get_selected()
			except Exception:
				selected = []
			# 兼容旧路径（例如 on_attack 直接设置的 token）
			if not selected and getattr(self, 'skill_target_token', None):
				selected = [self.skill_target_token]
			# attack/heal 的直达命令
			if name in (None, 'attack') and selected:
				out = self._send(f"a {src} {selected[0]}")
			elif name == 'basic_heal' and selected:
				# 走通用技能通道，控制器实现为 skill basic_heal mN mK
				out = self._send(" ".join(["skill", "basic_heal", src, selected[0]]))
			else:
				# 通用 skill
				if selected:
					out = self._send(" ".join(["skill", name or "", src] + selected).strip())
				else:
					out = self._send(f"skill {name} {src}")
			try:
				resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
			except Exception:
				resp = out
			self._after_cmd(resp)
		finally:
			self.selected_skill = None
			self.selected_skill_name = None
			self.skill_target_index = None
			self.skill_target_token = None
			try:
				self.target_engine.reset()
			except Exception:
				pass
			try:
				self._reset_highlights()
				self._render_operations()
				# 立即进行一次战场轻量刷新，确保卡片/敌人/操作栏同步
				self.refresh_battlefield_only()
			except Exception:
				pass

	def _toggle_target_token(self, token: str):
		"""在主界面点击候选或卡片时切换选择，并局部更新高亮与操作栏。"""
		try:
			if not getattr(self, 'target_engine', None) or not getattr(self.target_engine, 'ctx', None):
				return
			ctx = self.target_engine.ctx
			if token in (ctx.selected or set()):
				self.target_engine.unpick(token)
			else:
				self.target_engine.pick(token)
			self._update_target_highlights()
			self._render_operations()
		except Exception:
			pass

	def _update_target_highlights(self):
		"""根据 TargetingEngine 的候选/已选，在卡片与敌人卡上应用高亮，不触发整页刷新。"""
		try:
			self._reset_highlights()
			ctx = getattr(self, 'target_engine', None) and self.target_engine.ctx
			if not ctx:
				return
			cands = set(ctx.candidates or [])
			sel = set(ctx.selected or [])
			# 敌人卡
			for idx, wrap in (self.enemy_card_wraps or {}).items():
				tok = f"e{idx}"
				if tok in sel:
					wrap.configure(highlightbackground=self.HL['sel_enemy_border'], background=self.HL['sel_enemy_bg'], highlightthickness=self._border_selected_enemy)
				elif tok in cands:
					wrap.configure(highlightbackground=self.HL['cand_enemy_border'], background=self.HL['cand_enemy_bg'])
			# 我方卡
			for idx, wrap in (self.card_wraps or {}).items():
				tok = f"m{idx}"
				if tok in sel:
					wrap.configure(highlightbackground=self.HL['sel_ally_border'], background=self.HL['sel_ally_bg'], highlightthickness=self._border_selected_member)
				elif tok in cands:
					wrap.configure(highlightbackground=self.HL['cand_ally_border'], background=self.HL['cand_ally_bg'])
		except Exception:
			pass
			try:
				self._render_operations()
			except Exception:
				pass

	def _cancel_skill(self):
		self.selected_skill = None
		self.selected_skill_name = None
		self.skill_target_index = None
		self.skill_target_token = None
		try:
			self._reset_highlights()
			self._render_operations()
		except Exception:
			pass

	def _on_enemy_card_click(self, idx: int):
		# 若处于目标选择会话，走内联切换；否则保留旧行为
		try:
			if getattr(self, 'target_engine', None) and getattr(self.target_engine, 'ctx', None):
				self._toggle_target_token(f"e{idx}")
				return
		except Exception:
			pass
		prev = getattr(self, 'selected_enemy_index', None)
		if prev and prev in getattr(self, 'enemy_card_wraps', {}):
			try:
				self.enemy_card_wraps[prev].configure(highlightbackground="#cccccc", highlightthickness=self._border_default, background=self._wrap_bg_default)
			except Exception:
				pass
		self.selected_enemy_index = idx
		try:
			w = self.enemy_card_wraps.get(idx)
			if w:
				w.configure(highlightbackground=self.HL['sel_enemy_border'], background=self.HL['sel_enemy_bg'], highlightthickness=self._border_selected_enemy)
		except Exception:
			pass

	def _on_card_click(self, idx: int):
		# 若处于目标选择会话，走内联切换；否则保留旧行为
		try:
			if getattr(self, 'target_engine', None) and getattr(self.target_engine, 'ctx', None):
				self._toggle_target_token(f"m{idx}")
				return
		except Exception:
			pass
		prev = getattr(self, 'selected_member_index', None)
		if prev and prev in getattr(self, 'card_wraps', {}):
			try:
				self.card_wraps[prev].configure(highlightbackground="#cccccc", highlightthickness=self._border_default, background=self._wrap_bg_default)
			except Exception:
				pass
		self.selected_member_index = idx
		try:
			w = self.card_wraps.get(idx)
			if w:
				w.configure(highlightbackground=self.HL['sel_ally_border'], background=self.HL['sel_ally_bg'], highlightthickness=self._border_selected_member)
		except Exception:
			pass
		# 更新操作栏
		try:
			self._render_operations()
		except Exception:
			pass

	def _render_cards(self):
		# 交由视图实现
		v = self.views.get('allies')
		return v.render_all(self.cards_container) if v else None

	def _create_character_card(self, parent: tk.Widget, m, m_index: int) -> ttk.Frame:
		# 兼容旧 API：直接转给视图实现
		v = self.views.get('allies')
		if v and hasattr(v, '_create_character_card'):
			return v._create_character_card(parent, m, m_index)
		return tk_cards.create_character_card(self, parent, m, m_index)

	def _render_resources(self):
		# 抑制窗口期间合并刷新，待窗口结束统一渲染
		if getattr(self, '_suspend_ui_updates', False):
			self._pending_resource_refresh = True
			return None
		return tk_resources.render_resources(self, self.res_buttons_container)

	def _render_operations(self):
		# 抑制窗口期间合并刷新，待窗口结束统一渲染
		if getattr(self, '_suspend_ui_updates', False):
			self._pending_ops_refresh = True
			return None
		v = self.views.get('ops')
		return v.render(self.frm_operations) if v else tk_operations.render_operations(self, self.frm_operations)

	def _op_attack(self, m_index: int):
		# 发起攻击，期望 controller 能处理选择目标或提示
		out = self._send(f"atk m{m_index}")
		try:
			resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
		except Exception:
			resp = out
		self._after_cmd(resp)

	def _op_manage_equipment(self, m_index: int):
		# 简单触发打开第一个槽的装备对话作为入口
		try:
			board = self.controller.game.player.board
			m = board[m_index - 1]
			eq = getattr(m, 'equipment', None)
			first_slot = 'left' if True else 'right'
			self._open_equip_dialog(m_index, first_slot)
		except Exception:
			pass

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
			out = self._send(f"uneq {token} {slot}")
			try:
				resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
			except Exception:
				resp = out
			self._after_cmd(resp)
		elif choice is False:
			self._open_equip_dialog(m_index, slot_key)
		else:
			return

	def _open_equip_dialog(self, m_index: int, slot_key: str):
		top = tk.Toplevel(self.root)
		top.title("选择装备")
		top.transient(self.root)
		top.grab_set()
		# 将对话框定位到鼠标附近，并确保不越界
		try:
			self.root.update_idletasks()
			sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
			px, py = self.root.winfo_pointerx(), self.root.winfo_pointery()
			# 先设置到偏移位置，再在内容布局后精确回调一次
			x, y = max(0, px + 12), max(0, py + 12)
			top.geometry(f"+{x}+{y}")
		except Exception:
			pass
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
			from src.systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
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
			out = self._send(f"eq i{i_idx} {token}")
			try:
				resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
			except Exception:
				resp = out
			self._after_cmd(resp)
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

		# 第二次定位：计算窗口尺寸后做边界裁剪，防止出屏幕
		try:
			top.update_idletasks()
			w, h = top.winfo_width(), top.winfo_height()
			sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
			px, py = self.root.winfo_pointerx(), self.root.winfo_pointery()
			x = min(max(0, px + 12), max(0, sw - w))
			y = min(max(0, py + 12), max(0, sh - h))
			top.geometry(f"+{x}+{y}")
		except Exception:
			pass

	def _attach_tooltip(self, widget: tk.Widget, text_provider):
		"""保留原版：仅绑定到单个控件。"""
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

	def _attach_tooltip_deep(self, root_widget: tk.Widget, text_provider):
		"""改进版：将提示绑定到 root_widget 及其所有后代，
		并在离开整个卡片区域时才隐藏，避免被文字/子控件挡住或闪烁。
		"""
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
			except Exception:
				pass

		def hide_if_outside(_evt=None):
			try:
				# 指针位置不在 root_widget 矩形内时隐藏
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
				# 兜底直接隐藏
				w = tip.get('win')
				if w is not None:
					try:
						w.destroy()
					except Exception:
						pass
					tip['win'] = None

		# 绑定根与所有后代
		def bind_recursive(w: tk.Widget):
			try:
				w.bind('<Enter>', show, add='+')
				w.bind('<Leave>', hide_if_outside, add='+')
				# 在移动时也检查以便在从上往下扫掠时及时隐藏
				w.bind('<Motion>', hide_if_outside, add='+')
			except Exception:
				pass
			for ch in getattr(w, 'winfo_children', lambda: [])():
				bind_recursive(ch)

		bind_recursive(root_widget)

	def _on_log_motion(self, event):
		"""Show a small tooltip with meta info when hovering over a log line that has meta."""
		try:
			if not hasattr(self, '_log_meta'):
				return
			idx = self.text_log.index(f"@{event.x},{event.y}")
			line_no = idx.split('.')[0]
			key = f"{line_no}.0"
			meta = self._log_meta.get(key)
			# hide previous if same
			if getattr(self, '_log_tooltip_key', None) == key and getattr(self, '_log_tooltip', None):
				return
			# destroy old
			if getattr(self, '_log_tooltip', None):
				try:
					self._log_tooltip.destroy()
				except Exception:
					pass
				self._log_tooltip = None
				self._log_tooltip_key = None
			if not meta:
				return
			# create tooltip
			text = json.dumps(meta, ensure_ascii=False, indent=1)
			x = self.text_log.winfo_rootx() + event.x + 12
			y = self.text_log.winfo_rooty() + event.y + 12
			try:
				tw = tk.Toplevel(self.text_log)
				tw.wm_overrideredirect(True)
				tw.wm_geometry(f"+{x}+{y}")
				lbl = ttk.Label(tw, text=text, relief='solid', borderwidth=1, padding=6, background='#ffffe0')
				lbl.pack()
				self._log_tooltip = tw
				self._log_tooltip_key = key
			except Exception:
				self._log_tooltip = None
				self._log_tooltip_key = None
		except Exception:
			pass

	# 移除信息区 hover，统一使用日志悬浮

	# -------- Actions --------
	def _append_info(self, text_or_entry):
		"""兼容旧信息区 API：改为统一追加到战斗日志。"""
		try:
			if isinstance(text_or_entry, dict):
				self._append_log(text_or_entry)
			else:
				self._append_log({'type': 'info', 'text': str(text_or_entry), 'meta': {}})
		except Exception:
			pass

	def _append_log(self, text: str):
		"""Accept either a string or a structured log dict and render it.
		If dict, expected keys: type, text, meta
		"""
		try:
			if isinstance(text, dict):
				typ = (text.get('type', 'info') or 'info').lower()
				txt = text.get('text', '')
				meta = text.get('meta', {}) or {}
			else:
				typ = 'info'
				txt = str(text)
				meta = {}
			clean = C.strip(str(txt))
			start = self.text_log.index(tk.END)
			self.text_log.insert(tk.END, clean + "\n")
			end = self.text_log.index(tk.END)
			# apply semantic coloring tags
			try:
				palette = {
					'info': 'info', 'success': 'success', 'warning': 'warning', 'error': 'error', 'state': 'state',
					'attack': 'attack', 'damage': 'attack', 'heal': 'heal', 'crit': 'crit', 'miss': 'miss', 'block': 'block',
				}
				self.text_log.tag_add(palette.get(typ, 'info'), start, end)
			except Exception:
				pass
			# store meta as JSON-like string on the tag for tooltip retrieval
			try:
				self.text_log.tag_config(start, underline=False)
				# attach a simple mapping from index to meta via a dict on the widget
				if not hasattr(self, '_log_meta'):
					self._log_meta = {}
				self._log_meta[start] = meta
			except Exception:
				pass
			self.text_log.see(tk.END)
		except Exception:
			# fallback to simple insert
			try:
				self.text_log.insert(tk.END, C.strip(str(text)) + "\n")
				self.text_log.see(tk.END)
			except Exception:
				pass

	def _selected_index(self, lb: tk.Listbox) -> Optional[int]:
		sel = lb.curselection()
		if not sel:
			return None
		return sel[0]

	def _pick_resource(self, idx: int):
		"""轻量拾取资源：仅更新资源/背包与日志，不触发整页刷新。"""
		out = self._send(f"t r{idx}")
		try:
			resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
		except Exception:
			resp = out
		# 仅附加日志/信息，不清空，不重绘整页
		try:
			import os as _os
			_logdir = CFG.log_dir()
			_os.makedirs(_logdir, exist_ok=True)
			_logpath = _os.path.join(_logdir, 'game.log')
			with open(_logpath, 'a', encoding='utf-8') as f:
				for line in resp or []:
					# support structured log dicts
					if isinstance(line, dict):
						disp = line.get('text', '')
						self._append_info(disp)
						self._append_log(line)
						f.write(json.dumps(line, ensure_ascii=False) + "\n")
					else:
						self._append_info(line)
						self._append_log(line)
						f.write(str(line) + "\n")
		except Exception as e:
			self._log_exception(e, '_pick_resource_log')
		# 局部刷新：资源按钮与背包列表
		try:
			self._render_resources()
			self._refresh_inventory_only()
		except Exception as e:
			self._log_exception(e, '_pick_resource_partial_refresh')
		# 保持当前选中高亮与卡片视图不变，避免视觉跳动

	def _refresh_inventory_only(self):
		"""仅刷新背包列表，避免触发卡片与场景的重绘。"""
		try:
			text = self.controller._section_inventory()
			lb = self.list_inv
			lb.delete(0, tk.END)
			for line in (text or '').splitlines():
				s = C.strip(line).rstrip()
				if not s:
					continue
				# 跳过标题与分组行
				if s.endswith('):') or s.endswith(':'):
					continue
				lb.insert(tk.END, s)
		except Exception as e:
			self._log_exception(e, '_refresh_inventory_only')

	def on_attack(self):
		if not self.controller:
			return
		if not self.selected_member_index:
			messagebox.showinfo("提示", "请先在底部卡片选择一名队员(mN)")
			return
		# 统一入口
		self.begin_skill(self.selected_member_index, 'attack')

	def _open_target_picker(self, mode: str, m_index: int):
		"""统一目标选择器：弹窗列出可用目标，确认后设置 skill_target 并调用确认。
		mode: 'attack' | 'heal'
		"""
		# 收集候选
		candidates = []  # list[(token, label)]
		if mode == 'attack':
			enemies = getattr(self.controller.game, 'enemies', []) or []
			for i, e in enumerate(enemies, start=1):
				try:
					if not getattr(e, 'can_be_attacked', True):
						continue
					name = getattr(e, 'display_name', None) or getattr(e, 'name', f'敌人#{i}')
					hp = int(getattr(e, 'hp', 0))
					mx = int(getattr(e, 'max_hp', hp))
					if hp <= 0:
						continue
					candidates.append((f"e{i}", f"e{i}  {name}  HP {hp}/{mx}"))
				except Exception:
					candidates.append((f"e{i}", f"e{i}"))
		elif mode == 'heal':
			board = getattr(self.controller.game.player, 'board', []) or []
			for i, m in enumerate(board, start=1):
				try:
					if i == m_index:
						continue
					hp = int(getattr(m, 'hp', 0))
					mx = int(getattr(m, 'max_hp', hp))
					if hp >= mx:
						continue
					if hp <= 0:
						continue
					name = getattr(m, 'display_name', None) or getattr(m, 'name', f'队员#{i}')
					candidates.append((f"m{i}", f"m{i}  {name}  HP {hp}/{mx}"))
				except Exception:
					candidates.append((f"m{i}", f"m{i}"))
		else:
			return
		if not candidates:
			messagebox.showinfo("提示", "没有可用的目标")
			return
		# 弹窗
		try:
			if getattr(self, '_target_picker', None):
				try:
					self._target_picker.destroy()
				except Exception:
					pass
				self._target_picker = None
		except Exception:
			pass
		top = tk.Toplevel(self.root)
		top.title("选择目标")
		top.transient(self.root)
		top.grab_set()
		self._target_picker = top
		frm = ttk.Frame(top, padding=10)
		frm.pack(fill=tk.BOTH, expand=True)
		lbl = ttk.Label(frm, text=("选择攻击目标" if mode == 'attack' else "选择治疗目标"))
		lbl.pack(anchor=tk.W)
		lb = tk.Listbox(frm, height=min(10, len(candidates)))
		for _, label in candidates:
			lb.insert(tk.END, label)
		lb.pack(fill=tk.BOTH, expand=True, pady=6)
		lb.select_set(0)
		btns = ttk.Frame(frm)
		btns.pack(fill=tk.X)
		def do_ok(evt=None):
			sel = lb.curselection()
			if not sel:
				return
			idx = sel[0]
			tok = candidates[idx][0]
			self.skill_target_token = tok
			# 同步 card wrap 的直观高亮（若能映射）
			try:
				if tok.startswith('e'):
					self.selected_enemy_index = int(tok[1:])
				elif tok.startswith('m'):
					self.selected_member_index = m_index
			except Exception:
				pass
			try:
				top.destroy()
				self._target_picker = None
			except Exception:
				pass
			# 立即执行（会根据当前 selected_skill_name 走攻击/治疗/通用技能分支）
			self._confirm_skill()
		def do_cancel():
			try:
				top.destroy()
				self._target_picker = None
			except Exception:
				pass
		ok = ttk.Button(btns, text="确定", command=do_ok)
		ok.pack(side=tk.LEFT, expand=True, fill=tk.X)
		cc = ttk.Button(btns, text="取消", command=do_cancel)
		cc.pack(side=tk.RIGHT, expand=True, fill=tk.X)
		lb.bind('<Double-Button-1>', do_ok)

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
			out = self._send(f"eq {token} {tgt_m}")
			try:
				resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
			except Exception:
				resp = out
		else:
			name = raw if not token.startswith('i') else ' '.join(parts[1:])
			cmd = f"use {name}"
			if tgt_m:
				cmd += f" {tgt_m}"
			out = self._send(cmd)
			try:
				resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
			except Exception:
				resp = out
		self._after_cmd(resp)

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
		out = self._send(f"uneq {m_token} {slot}")
		try:
			resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
		except Exception:
			resp = out
		self._after_cmd(resp)

	def on_craft_quick(self):
		if not self.controller:
			return
		idx = self._selected_index(self.list_inv)
		if idx is None:
			out = self._send("craft")
			try:
				resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
			except Exception:
				resp = out
			self._after_cmd(resp)
			return
		raw = self.list_inv.get(idx).strip()
		if raw.startswith('c') and raw[1:].split()[0].isdigit():
			n = raw[1:].split()[0]
			out = self._send(f"c{n}")
			try:
				resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
			except Exception:
				resp = out
		else:
			out = self._send("craft")
		try:
			resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
		except Exception:
			resp = out
		self._after_cmd(resp)

	def _run_cmd(self, cmd: str):
		if not self.controller:
			return
		out = self._send(cmd)
		try:
			resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
		except Exception:
			resp = out
		self._after_cmd(resp)

	def _after_cmd(self, out_lines: list[str]):
		# 规范化输入：支持字符串/列表/元组，避免把字符串当可迭代逐字符写入导致卡顿
		try:
			if isinstance(out_lines, str):
				lines = out_lines.splitlines() or [out_lines]
			elif isinstance(out_lines, (list, tuple)):
				lines = list(out_lines)
			elif out_lines is None:
				lines = []
			else:
				lines = [str(out_lines)]
		except Exception:
			lines = []
		# 统一：将“状态快照”作为 state 行追加到战斗日志
		try:
			for line in lines:
				if isinstance(line, dict):
					self._append_log({'type': 'state', 'text': line.get('text', ''), 'meta': {'state': True}})
				else:
					self._append_log({'type': 'state', 'text': str(line), 'meta': {'state': True}})
		except Exception as e:
			self._log_exception(e, '_after_cmd_info')
		# append to persistent log file (cross-platform) and log widget
		try:
			logdir = CFG.log_dir()
			os.makedirs(logdir, exist_ok=True)
			logpath = os.path.join(logdir, 'game.log')
			with open(logpath, 'a', encoding='utf-8') as f:
				for line in lines:
					try:
						self._append_log(line)
					except Exception:
						pass
					# write structured logs as JSON for better persistence
					try:
						if isinstance(line, dict):
							f.write(json.dumps(line, ensure_ascii=False) + "\n")
						else:
							f.write(str(line) + "\n")
					except Exception:
						try:
							f.write(str(line) + "\n")
						except Exception:
							pass
				# consume game structured logs (e.g., DND to_hit/damage) and render to both panes
				try:
					logs = self.controller.game.pop_logs()
					for L in logs:
						self._append_log(L)
						try:
							f.write(json.dumps(L, ensure_ascii=False) + "\n")
						except Exception:
							f.write(str(L) + "\n")
				except Exception:
					pass
		except Exception as e:
			self._log_exception(e, '_after_cmd_log')
		# 保证恢复默认高亮
		try:
			self._reset_highlights()
		except Exception as e:
			self._log_exception(e, '_after_cmd_reset')
		# 清理可能残留的目标选择/技能状态，避免下一次点击被阻塞
		try:
			self.selected_skill = None
			self.selected_skill_name = None
			self.skill_target_index = None
			self.skill_target_token = None
			if getattr(self, 'target_engine', None):
				self.target_engine.reset()
		except Exception:
			pass
		# 命令后不再强制重绘战场，交给事件驱动；
		# 但为避免遗漏（例如某些路径未发事件），兜底刷新资源/背包/操作栏
		try:
			# 资源与背包区域
			self._render_resources()
			self._refresh_inventory_only()
			# 操作栏以反映技能/物品可用性
			self._render_operations()
		except Exception:
			pass
		# 某些无目标技能（如横扫）可能未及时触发 zone 事件，安排一次轻量战场刷新
		try:
			self._schedule_battlefield_refresh()
		except Exception:
			pass

	def refresh_battlefield_only(self):
		"""仅刷新敌人与我方卡片以及操作栏，尽量保留资源/背包与日志区域不变。
		并在重绘后恢复选中/技能候选高亮，避免失焦。
		"""
		if self.mode != 'game' or not self.controller:
			return
		# 清除调度标记
		setattr(self, '_pending_battlefield_refresh', False)
		# 仅卡片
		self._render_enemy_cards()
		self._render_cards()
		# 若索引已变化(死亡/移除)，清理失效的选中状态，避免残留导致操作栏/高亮不一致
		try:
			if getattr(self, 'selected_enemy_index', None) not in getattr(self, 'enemy_card_wraps', {}):
				self.selected_enemy_index = None
			if getattr(self, 'selected_member_index', None) not in getattr(self, 'card_wraps', {}):
				self.selected_member_index = None
		except Exception:
			pass
		# 目标选择会话的重验证，避免因死亡/阵列变化导致的残留
		try:
			if getattr(self, 'target_engine', None):
				self.target_engine.revalidate()
				self._update_target_highlights()
		except Exception:
			pass
		# 恢复高亮（非目标模式的选中）
		try:
			if self.selected_enemy_index and self.selected_enemy_index in self.enemy_card_wraps:
				self.enemy_card_wraps[self.selected_enemy_index].configure(highlightbackground=self.HL['sel_enemy_border'], background=self.HL['sel_enemy_bg'], highlightthickness=self._border_selected_enemy)
			if self.selected_member_index and self.selected_member_index in self.card_wraps:
				self.card_wraps[self.selected_member_index].configure(highlightbackground=self.HL['sel_ally_border'], background=self.HL['sel_ally_bg'], highlightthickness=self._border_selected_member)
			# 技能模式底色
			if getattr(self, 'selected_skill', None) == 'attack':
				for idx, wrap in self.enemy_card_wraps.items():
					wrap.configure(highlightbackground=self.HL['cand_enemy_border'], background=self.HL['cand_enemy_bg'])
			if getattr(self, 'selected_skill', None) == 'heal':
				for idx, wrap in self.card_wraps.items():
					wrap.configure(highlightbackground=self.HL['cand_ally_border'], background=self.HL['cand_ally_bg'])
			# 已选具体目标高亮
			if getattr(self, 'skill_target_token', None):
				try:
					tok = self.skill_target_token
					if tok.startswith('e'):
						i = int(tok[1:])
						if i in self.enemy_card_wraps:
							self.enemy_card_wraps[i].configure(highlightbackground=self.HL['sel_enemy_border'], background=self.HL['sel_enemy_bg'], highlightthickness=self._border_selected_enemy)
					elif tok.startswith('m'):
						i = int(tok[1:])
						if i in self.card_wraps:
							self.card_wraps[i].configure(highlightbackground=self.HL['sel_ally_border'], background=self.HL['sel_ally_bg'], highlightthickness=self._border_selected_member)
				except Exception:
					pass
		except Exception:
			pass
		# 操作栏
		try:
			self._render_operations()
		except Exception:
			pass

	def _schedule_battlefield_refresh(self):
		"""合并多次小范围移除导致的索引错位，在下一帧进行一次战场轻量重绘。"""
		try:
			if getattr(self, '_pending_battlefield_refresh', False):
				return
			setattr(self, '_pending_battlefield_refresh', True)
			# 场景切换抑制期：不立即调度，待抑制结束时由 refresh_all 统一处理
			if getattr(self, '_suspend_ui_updates', False):
				return
			self.root.after(0, self.refresh_battlefield_only)
		except Exception:
			# 若调度失败，直接执行一次兜底刷新
			try:
				self.refresh_battlefield_only()
			except Exception:
				pass

	# -------- Mode --------
	def _start_game(self, player_name: str, initial_scene: Optional[str]):
		self.controller = SimplePvEController(player_name=player_name, initial_scene=initial_scene)
		self.frame_menu.pack_forget()
		self.frame_game.pack(fill=tk.BOTH, expand=True)
		self.mode = 'game'
		# 让视图持有 game 引用（直接绑定场景/实体），减少 app 层转发
		try:
			self._bind_views_context()
		except Exception:
			pass
		# 输出初始状态快照到战斗日志（替代历史的 text_info 面板）
		try:
			full = self.controller._render_full_view()
			for line in (full or '').splitlines():
				self._append_log({'type': 'state', 'text': line, 'meta': {'state': True}})
		except Exception:
			pass
		self.refresh_all(skip_info_log=True)
		try:
			path = os.path.join(CFG.user_data_dir(), 'scene_runtime.txt')
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
		try:
			self.root.protocol("WM_DELETE_WINDOW", self._on_close)
		except Exception:
			pass
		self.root.mainloop()

	def _on_close(self):
		# 取消订阅并关闭
		try:
			# unmount views first
			for v in (getattr(self, 'views', {}) or {}).values():
				try:
					v.unmount()
				except Exception:
					pass
			for evt, cb in getattr(self, '_event_handlers', []) or []:
				try:
					unsubscribe_event(evt, cb)
				except Exception:
					pass
		except Exception:
			pass
		self.root.destroy()


def run_tk(player_name: str = "玩家", initial_scene: Optional[str] = None):
	app = GameTkApp(player_name=player_name, initial_scene=initial_scene)
	app.run()

