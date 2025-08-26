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
from .dialogs.equipment_dialog import EquipmentDialog
from .dialogs.target_picker import TargetPickerDialog
from . import animations as ANIM
from . import cards as tk_cards
from .views import EnemiesView, AlliesView, ResourcesView, OperationsView
from .widgets.log_pane import LogPane
from src.ui.targeting.specs import DEFAULT_SPECS, SkillTargetSpec
from src.ui.targeting.fsm import TargetingEngine
from .controllers.selection_controller import SelectionController
# Inline 选择：不使用弹窗选择器
from src.core.events import subscribe as subscribe_event, unsubscribe as unsubscribe_event

try:
	from main import load_config, save_config, discover_packs, _pick_default_main  # type: ignore
except Exception:  # pragma: no cover
	load_config = save_config = discover_packs = _pick_default_main = None  # type: ignore


class GameTkApp:
	# ---------------------------------------------------------------------------
	# 函数索引与用途说明（维护导读）
	#
	# 初始化/基础：
	# - __init__: 创建 Tk 根窗体、菜单与游戏区域，挂载视图订阅，按 initial_scene 可直接入局。
	# - _bind_views_context: 让各视图持有当前 game，引导它们自行读取 zone/entity。
	# - _log_exception: 捕获并写入日志区域（或控制台），避免静默失败。
	# - _reset_highlights: 清除卡面/敌人高亮边框与背景，防止残留。
	# - _send: 统一命令入口，兼容旧别名（a/eq/uneq/t/use/end/craft 等）后转发给控制器。
	#
	# 事件（来自模型/控制器）：
	# - _on_event_scene_changed: 场景切换；进入 UI 抑制窗口，稍后全量刷新，期间清理选择/目标态。
	# - _on_event_inventory_changed: 背包/资源变化，仅刷新资源/背包区域（视图负责）。
	# - _on_enemy_zone_event: 敌人区 ObservableList 变更，合并调度一次战场轻量重绘。
	# - _on_resource_zone_event: 资源区变更，刷新资源与操作栏（可被抑制并合并）。
	# - _on_event_equipment_changed: 装备变更；刷新操作栏与受影响卡面文本，尽量避免整页刷新。
	# - _on_event_resource_changed: 资源文本/按钮更新（细粒度）。
	#
	# 菜单/主界面：
	# - _build_menu: 主菜单 UI（开始/改名/选择地图/刷新/退出）。
	# - _menu_profile: 菜单顶栏的当前玩家/场景展示文本。
	# - _menu_start: 依据配置选择并进入最近地图；若列表变更选择默认主图。
	# - _menu_rename: 修改玩家名并保存配置。
	# - _menu_choose_pack: 弹出地图组+主地图选择对话框并保存选择。
	# - _menu_refresh_packs: 重新扫描场景包。
	# - _build_game: 游戏主界面布局（敌人区/资源与背包/队伍/操作栏/日志）。
	#
	# 刷新与渲染：
	# - refresh_all: 全量刷新（资源/背包、日志、敌人/队伍卡片、操作栏），并重应用高亮。
	# - refresh_battlefield_only: 轻量刷新战场（敌人+队伍+操作栏），尽量保持微更新。
	# - _schedule_battlefield_refresh: 去抖/合并调度下一帧轻量刷新（避免短时间多次重绘）。
	# - _render_enemy_cards/_create_enemy_card: 委托 EnemiesView 渲染；必要时回落到本地卡片工厂。
	# - _render_cards/_create_character_card: 委托 AlliesView 渲染；必要时回落。
	# - _render_resources: 委托 ResourcesView 渲染资源与背包。
	# - _render_operations: 委托 OperationsView 渲染所选队员可用操作。
	#
	# 交互（逐步收敛到 SelectionController/TargetingEngine）：
	# - _select_skill: 旧路径：选择技能后高亮候选（保留兼容）。
	# - begin_skill: 统一技能入口；调用 TargetingEngine.begin，若无需目标则直接执行并清理。
	# - _confirm_skill: 执行技能/普攻命令并清理选择与目标态。
	# - _cancel_skill: 取消当前目标会话并恢复 UI。
	# - _update_target_highlights: 根据 TargetingEngine 候选/已选应用卡面高亮（微更新）。
	# - _op_attack/_op_manage_equipment/_slot_click: 旧操作入口（攻击/装备交互），逐步转交视图/控制器。
	# - _open_equip_dialog: 打开装备管理对话框。
	# - _open_target_picker: 旧的弹窗目标选择器（现使用内联 + SelectionController）。
	#
	# 工具/日志/命令：
	# - _attach_tooltip/_attach_tooltip_deep: 悬浮提示工具（控件或整棵子树）。
	# - _append_info/_append_log: 写入信息/战斗日志（结构化与文本）。
	# - _selected_index/_pick_resource: 列表选择/拾取资源的便捷函数。
	# - on_pick/on_use_or_equip/on_unequip_dialog/on_craft_quick: 快捷按钮与弹窗动作处理。
	# - _run_cmd/_after_cmd: 直接执行指令字符串并在日志/界面上反映结果。
	#
	# 生命周期：
	# - _start_game: 进入游戏模式，绑定视图上下文，输出初始状态，并刷新 UI。
	# - _back_to_menu: 返回主菜单并清理游戏视图。
	# - run/_on_close: 进入 Tk 主循环/关闭前保存与清理。
	# - run_tk: 外部启动入口函数（便于脚本/打包调用）。
	# ---------------------------------------------------------------------------
	def __init__(self, player_name: str = "玩家", initial_scene: Optional[str] = None):
		"""构造应用与主窗口。
		场景：程序启动或从 run_tk 进入；会初始化菜单与游戏界面并挂载视图与事件。
		"""
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
		"""场景切换事件：进入 UI 抑制期，稍后全量刷新并清理选择/目标状态。"""
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
			if getattr(self, 'target_engine', None):
				try:
					self.target_engine.cancel()
				except Exception:
					pass
			self.selection.clear_all()
		except Exception:
			pass
		# 杀掉所有子 UI（容器内容与订阅），播放切换动画占位
		try:
			self._show_scene_transition()
			self._teardown_children()
		except Exception:
			pass
		# 延迟再刷新，让死亡浮字短暂呈现
		def _do_full():
			try:
				# 结束抑制窗口，重建子 UI
				self._suspend_ui_updates = False
				setattr(self, '_pending_battlefield_refresh', False)
				# 重新绑定视图上下文并重建子 UI（视图自行订阅/渲染）
				try:
					self._bind_views_context()
					self._build_children()
					self._hide_scene_transition()
				except Exception:
					pass
			except Exception:
				# 容错：若失败则静默
				pass
		try:
			self.root.after(250, _do_full)
		except Exception:
			_do_full()


	def _on_event_inventory_changed(self, _evt: str, _payload: dict):
		"""背包/资源变更事件：仅刷新资源区与背包列表（由 ResourcesView 负责）。"""
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
		"""装备变更事件：刷新操作栏、背包清单，并微更新相关卡片数值文本。"""
		# 装备变化：仅刷新操作栏与受影响卡片的数值，避免整块重绘
		try:
			if getattr(self, '_suspend_ui_updates', False):
				self._pending_ops_refresh = True
				# 卡片的细节变更会在切换完成时统一刷新
				return
			card = (_payload or {}).get('owner') or (_payload or {}).get('card')
			self._render_operations()
			# 背包列表也会改变（装备/卸下），需要刷新（交由 ResourcesView）
			try:
				v = self.views.get('resources')
				if v and hasattr(v, 'render_inventory'):
					v.render_inventory()
			except Exception:
				pass
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
		"""资源区变更事件：仅重绘资源按钮容器。"""
		# 资源区改变：只刷新资源按钮
		try:
			self._render_resources()
		except Exception:
			pass

	# -------- Menu --------
	def _build_menu(self, parent: tk.Widget):
		"""构建主菜单区域：开始、改名、选地图组、刷新列表、退出等入口。"""
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
		"""返回菜单顶栏展示的当前玩家与场景标签。"""
		pack_id = self.cfg.get('last_pack', '')
		last_scene = self.cfg.get('last_scene', 'default_scene.json')
		scene_label = (pack_id + '/' if pack_id else '') + last_scene
		return f"玩家: {self.cfg.get('name','玩家')}    场景: {scene_label}"

	def _menu_start(self):
		"""从配置选择最近主地图并启动游戏场景。"""
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
		"""弹窗修改玩家名称并持久化到配置。"""
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
		"""弹出地图组/主地图选择对话框，保存所选并更新菜单展示。"""
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
		"""重新扫描可用场景包并提示完成。"""
		_ = discover_packs() if callable(discover_packs) else None
		messagebox.showinfo("提示", "场景列表已刷新")

	# -------- Gameplay UI --------
	def _build_game(self, parent: tk.Widget):
		"""构建游戏主界面布局：敌人区、资源/背包、队伍卡、操作栏与日志。"""
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
		# 选择/高亮控制器
		self.selection = SelectionController(self)

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

		# 将资源与背包容器交由 ResourcesView 托管
		try:
			res_view = self.views.get('resources')
			if res_view and hasattr(res_view, 'attach'):
				res_view.attach(self.res_buttons_container, self.list_inv)
			# 敌人视图也记录容器以便自身调度渲染
			enm_view = self.views.get('enemies')
			if enm_view and hasattr(enm_view, 'attach'):
				enm_view.attach(self.enemy_cards_container)
		except Exception:
			pass

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
		# 使用封装的日志面板
		self.log_pane = LogPane(bottom)
		self.log_pane.frame.grid(row=0, column=0, sticky='nsew', padx=(0, 0), pady=(3, 3))
		self.log_pane.bind_hover_tooltip()
		# 兼容旧引用
		self.text_log = self.log_pane.widget()

		# 为视图记录容器，便于其内部调度渲染
		try:
			al_view = self.views.get('allies')
			if al_view and hasattr(al_view, 'attach'):
				al_view.attach(self.cards_container)
		except Exception:
			pass

	# -------- Render --------
	def refresh_all(self, skip_info_log: bool = False):
		"""已废弃：刷新交由子 UI 决定；此处仅做兼容性触发，直接让视图渲染自身。"""
		if self.mode != 'game' or not self.controller:
			return
		try:
			scene = getattr(self.controller.game, 'current_scene_title', None) or self.controller.game.current_scene
			self.scene_var.set(f"场景: {scene if getattr(self.controller.game, 'current_scene_title', None) else os.path.basename(scene)}")
		except Exception:
			self.scene_var.set("场景: -")
		for key, fn in (
			('resources', lambda v: (v.render_inventory(), v.render())),
			('enemies', lambda v: v.render_all(self.enemy_cards_container)),
			('allies', lambda v: v.render_all(self.cards_container)),
			('ops', lambda v: v.render(self.frm_operations)),
		):
			try:
				v = self.views.get(key)
				if v:
					fn(v)
			except Exception:
				pass

	def _render_enemy_cards(self):
		"""渲染敌人卡片容器：优先委托 EnemiesView。"""
		# 交由视图实现
		v = self.views.get('enemies')
		return v.render_all(self.enemy_cards_container) if v else None

	def _create_enemy_card(self, parent: tk.Widget, e, e_index: int) -> ttk.Frame:
		"""创建单个敌人卡片控件（兼容旧 API；优先视图）。"""
		# 兼容旧 API：直接转给视图实现
		v = self.views.get('enemies')
		if v and hasattr(v, '_create_enemy_card'):
			return v._create_enemy_card(parent, e, e_index)
		return tk_cards.create_character_card(self, parent, e, e_index, is_enemy=True)

	def _select_skill(self, m_index: int, skill_type: str):
		"""旧技能选择路径：仅做候选高亮与弹窗选择，保留兼容。"""
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
				self.selection.clear_all()
			except Exception:
				# fallback
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
			try:
				self.selection.clear_all()
			except Exception:
				# fallback cleanup
				self.selected_skill = None
				self.selected_skill_name = None
				self.skill_target_index = None
				self.skill_target_token = None
				try:
					self.target_engine.reset()
				except Exception:
					pass
			try:
				self._render_operations()
				# 立即进行一次战场轻量刷新，确保卡片/敌人/操作栏同步
				self.refresh_battlefield_only()
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
		"""取消当前技能/目标选择并恢复操作栏与高亮。"""
		self.selected_skill = None
		self.selected_skill_name = None
		self.skill_target_index = None
		self.skill_target_token = None
		try:
			self._reset_highlights()
			self._render_operations()
		except Exception:
			pass



	def _render_cards(self):
		"""渲染我方卡片容器：优先委托 AlliesView。"""
		# 交由视图实现
		v = self.views.get('allies')
		return v.render_all(self.cards_container) if v else None

	def _create_character_card(self, parent: tk.Widget, m, m_index: int) -> ttk.Frame:
		"""创建单个我方卡片控件（兼容旧 API；优先视图）。"""
		# 兼容旧 API：直接转给视图实现
		v = self.views.get('allies')
		if v and hasattr(v, '_create_character_card'):
			return v._create_character_card(parent, m, m_index)
		return tk_cards.create_character_card(self, parent, m, m_index)

	def _render_resources(self):
		"""渲染资源与背包区域：抑制期合并，优先委托 ResourcesView。"""
		# 抑制窗口期间合并刷新，待窗口结束统一渲染
		if getattr(self, '_suspend_ui_updates', False):
			self._pending_resource_refresh = True
			return None
		# 优先交给 ResourcesView 渲染（解耦）
		try:
			v = self.views.get('resources')
			if v and hasattr(v, 'render'):
				return v.render()
		except Exception:
			pass
		# 旧回退已移除：不再调用模块函数
		return None

	def _render_operations(self):
		"""渲染操作栏：抑制期合并，优先委托 OperationsView。"""
		# 抑制窗口期间合并刷新，待窗口结束统一渲染
		if getattr(self, '_suspend_ui_updates', False):
			self._pending_ops_refresh = True
			return None
		v = self.views.get('ops')
		return v.render(self.frm_operations) if v else None

	def _op_attack(self, m_index: int):
		"""旧攻击入口：直接向控制器发送 atk 命令并追加日志。"""
		# 发起攻击，期望 controller 能处理选择目标或提示
		out = self._send(f"atk m{m_index}")
		try:
			resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
		except Exception:
			resp = out
		self._after_cmd(resp)

	def _op_manage_equipment(self, m_index: int):
		"""旧装备管理入口：打开装备对话框。"""
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
		"""卡片槽位点击：无物品则打开装备对话；有物品提供卸下/更换选项。"""
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
		"""打开装备管理对话框并根据返回结果发送装备指令。"""
		# 使用新对话框实现，拿到结果后发起装备命令
		dlg = EquipmentDialog(self, self.root, m_index, slot_key)
		res = dlg.show()
		if res is None:
			return
		token = f"m{m_index}"
		out = self._send(f"eq i{res} {token}")
		try:
			resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
		except Exception:
			resp = out
		self._after_cmd(resp)

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

	# 移除信息区 hover，统一使用日志悬浮（由 LogPane 管理）

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
			self.log_pane.append(text)
		except Exception:
			try:
				self.text_log.insert(tk.END, C.strip(str(text)) + "\n")
				self.text_log.see(tk.END)
			except Exception:
				pass

	def _selected_index(self, lb: tk.Listbox) -> Optional[int]:
		"""返回 Listbox 当前选中索引；未选中则为 None。"""
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
		# 局部刷新：资源按钮与背包列表（委托 ResourcesView）
		try:
			v = self.views.get('resources')
			if v:
				v.render()
				v.render_inventory()
		except Exception as e:
			self._log_exception(e, '_pick_resource_partial_refresh')
		# 保持当前选中高亮与卡片视图不变，避免视觉跳动


	def on_attack(self):
		"""操作栏“攻击”按钮：要求先选中队员，否则提示，然后走统一技能入口。"""
		if not self.controller:
			return
		if not self.selected_member_index:
			messagebox.showinfo("提示", "请先在底部卡片选择一名队员(mN)")
			return
		# 统一入口
		self.begin_skill(self.selected_member_index, 'attack')

	def _open_target_picker(self, mode: str, m_index: int):
		"""使用 TargetPickerDialog 选择目标，返回后设置 token 并确认执行。"""
		# 构建候选
		candidates = []  # list[(token, label)]
		if mode == 'attack':
			enemies = getattr(self.controller.game, 'enemies', []) or []
			for i, e in enumerate(enemies, start=1):
				try:
					if not getattr(e, 'can_be_attacked', True):
						continue
					hp = int(getattr(e, 'hp', 0)); mx = int(getattr(e, 'max_hp', hp))
					if hp <= 0:
						continue
					name = getattr(e, 'display_name', None) or getattr(e, 'name', f"敌人#{i}")
					candidates.append((f"e{i}", f"e{i}  {name}  HP {hp}/{mx}"))
				except Exception:
					candidates.append((f"e{i}", f"e{i}"))
		elif mode == 'heal':
			board = getattr(self.controller.game.player, 'board', []) or []
			for i, m in enumerate(board, start=1):
				try:
					if i == m_index:
						continue
					hp = int(getattr(m, 'hp', 0)); mx = int(getattr(m, 'max_hp', hp))
					if hp <= 0 or hp >= mx:
						continue
					name = getattr(m, 'display_name', None) or getattr(m, 'name', f"队员#{i}")
					candidates.append((f"m{i}", f"m{i}  {name}  HP {hp}/{mx}"))
				except Exception:
					candidates.append((f"m{i}", f"m{i}"))
		else:
			return
		if not candidates:
			messagebox.showinfo("提示", "没有可用的目标")
			return
		# 打开对话框
		dlg = TargetPickerDialog(self.root, ("选择攻击目标" if mode == 'attack' else "选择治疗目标"), candidates)
		picked = dlg.show()
		if not picked:
			return
		self.skill_target_token = picked
		# 同步直观高亮：敌人或友方
		try:
			if picked.startswith('e'):
				self.selected_enemy_index = int(picked[1:])
			elif picked.startswith('m'):
				self.selected_member_index = m_index
		except Exception:
			pass
		# 立即执行
		self._confirm_skill()

	def on_pick(self):
		"""操作栏“拾取”按钮：提示请直接点击左侧资源按钮。"""
		if not self.controller:
			return
		messagebox.showinfo("提示", "请点击右侧资源按钮进行拾取")

	def on_use_or_equip(self):
		"""使用/装备背包条目：根据当前选择解析为 eq 或 use 指令并执行。"""
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
		"""弹窗输入槽位并发送卸下装备指令。"""
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
		"""快速合成：若选中合成条目则按编号合成，否则触发通用 craft。"""
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
		"""直接运行控制器命令字符串，并统一追加到日志。"""
		if not self.controller:
			return
		out = self._send(cmd)
		try:
			resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
		except Exception:
			resp = out
		self._after_cmd(resp)

	def _after_cmd(self, out_lines: list[str]):
		"""命令执行后的统一落地：写日志文件与 UI，重置高亮与必要的局部刷新。"""
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
			self.selection.clear_all()
		except Exception:
			# fallback
			try:
				self.selected_skill = None
				self.selected_skill_name = None
				self.skill_target_index = None
				self.skill_target_token = None
				if getattr(self, 'target_engine', None):
					self.target_engine.reset()
			except Exception:
				pass
		# 命令后刷新由各子 UI 的事件驱动；app 不再强制刷新。
		# 不再合并调度战场刷新，由视图基于事件决定。

	def refresh_battlefield_only(self):
		"""已废弃：刷新交由各 View 自行决定。"""
		setattr(self, '_pending_battlefield_refresh', False)

	def _schedule_battlefield_refresh(self):
		"""已废弃：由敌人/盟友视图基于事件自行调度重渲染。"""
		setattr(self, '_pending_battlefield_refresh', True)

	# -------- Mode --------
	def _start_game(self, player_name: str, initial_scene: Optional[str]):
		"""进入游戏模式：创建控制器、绑定视图上下文、输出初始状态并全量刷新。"""
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
		"""退出游戏回到主菜单并恢复菜单展示。"""
		self.controller = None
		self.frame_game.pack_forget()
		self.frame_menu.pack(fill=tk.BOTH, expand=True)
		self.mode = 'menu'
		self.lbl_profile.config(text=self._menu_profile())

	# --- lifecycle helpers: build/teardown children ---
	def _teardown_children(self):
		"""销毁/卸载所有子 UI：敌人、我方、资源、操作、日志区域内容与订阅。"""
		try:
			for v in (getattr(self, 'views', {}) or {}).values():
				try:
					v.unmount()
				except Exception:
					pass
		except Exception:
			pass
		# 清空容器控件
		for container_attr in ('enemy_cards_container','res_buttons_container','cards_container','frm_operations'):
			w = getattr(self, container_attr, None)
			if not w:
				continue
			for ch in list(getattr(w, 'winfo_children', lambda: [])()):
				try:
					ch.destroy()
				except Exception:
					pass
		# 清空索引/状态
		self.enemy_card_wraps = {}
		self.card_wraps = {}
		self.selected_enemy_index = None
		self.selected_member_index = None
		# 清空日志面板（保留框架）
		try:
			self.log_pane.clear()
		except Exception:
			pass

	def _build_children(self):
		"""重建所有子 UI，视图自行渲染并订阅事件。"""
		# 更新标题
		try:
			scene = getattr(self.controller.game, 'current_scene_title', None) or self.controller.game.current_scene
			self.scene_var.set(f"场景: {scene if getattr(self.controller.game, 'current_scene_title', None) else os.path.basename(scene)}")
		except Exception:
			self.scene_var.set("场景: -")
		# 让视图持有 game 引用
		self._bind_views_context()
		# 视图各自渲染
		try:
			v = self.views.get('resources'); v and v.render_inventory(); v and v.render()
		except Exception:
			pass
		try:
			v = self.views.get('enemies'); v and v.render_all(self.enemy_cards_container)
		except Exception:
			pass
		try:
			v = self.views.get('allies'); v and v.render_all(self.cards_container)
		except Exception:
			pass
		try:
			v = self.views.get('ops'); v and v.render(self.frm_operations)
		except Exception:
			pass
		# 重新挂载订阅（视图内会处理去重）
		try:
			for v in (self.views or {}).values():
				v.mount()
		except Exception:
			pass

	def _show_scene_transition(self):
		"""显示场景切换覆盖层（简单淡入）。"""
		try:
			if hasattr(self, '_scene_overlay') and getattr(self, '_scene_overlay') is not None:
				return
			ov = tk.Toplevel(self.root)
			ov.wm_overrideredirect(True)
			ov.attributes('-alpha', 0.0)
			ov.lift()
			ov.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}+{self.root.winfo_rootx()}+{self.root.winfo_rooty()}")
			frm = ttk.Frame(ov)
			frm.pack(fill=tk.BOTH, expand=True)
			lbl = ttk.Label(frm, text="正在切换场景…", font=("Segoe UI", 14, "bold"))
			lbl.place(relx=0.5, rely=0.5, anchor='center')
			setattr(self, '_scene_overlay', ov)
			def fade_in(a=0.0):
				try:
					if a >= 0.8:
						ov.attributes('-alpha', 0.8)
						return
					ov.attributes('-alpha', a)
					self.root.after(16, lambda: fade_in(a + 0.1))
				except Exception:
					pass
			fade_in()
		except Exception:
			setattr(self, '_scene_overlay', None)

	def _hide_scene_transition(self):
		"""隐藏场景切换覆盖层。"""
		ov = getattr(self, '_scene_overlay', None)
		if ov is None:
			return
		try:
			ov.destroy()
		except Exception:
			pass
		setattr(self, '_scene_overlay', None)
	def run(self):
		"""启动 Tk 主循环并挂接关闭处理。"""
		self.root.minsize(980, 700)
		try:
			self.root.protocol("WM_DELETE_WINDOW", self._on_close)
		except Exception:
			pass
		self.root.mainloop()

	def _on_close(self):
		"""窗口关闭：取消事件订阅、卸载视图并销毁窗口。"""
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
	"""外部启动入口：创建并运行 GameTkApp。"""
	app = GameTkApp(player_name=player_name, initial_scene=initial_scene)
	app.run()

