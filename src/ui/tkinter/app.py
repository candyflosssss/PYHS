"""Tk GUI 应用主入口（GameTkApp）。

要点：
- 采用“视图 + 控制器”拆分：
	- 视图负责渲染与自身订阅（EnemiesView / AlliesView / ResourcesView / OperationsView）。
	- SelectionController 负责选中/高亮；TargetingEngine 负责技能目标会话。
- app 作为壳层：组装窗口、路由事件、少量跨区协调（日志/菜单/全局高亮重置/命令入口）。
- 资源/背包/敌人区/装备的细粒度刷新已下放到各视图；app 仅保留场景切换事件处理。
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
from . import animations as ANIM
from .views import EnemiesView, AlliesView, ResourcesView, OperationsView
from .widgets.log_pane import LogPane
from src.ui.targeting.specs import DEFAULT_SPECS, SkillTargetSpec
from src.ui.targeting.fsm import TargetingEngine
from .controllers.selection_controller import SelectionController
# Inline 选择：不使用弹窗选择器
from src.core.events import subscribe as subscribe_event, unsubscribe as unsubscribe_event
# --- new: runtime settings ---
from src import settings as S

try:
	from main import load_config, save_config, discover_packs, _pick_default_main  # type: ignore
except Exception:  # pragma: no cover
	load_config = save_config = discover_packs = _pick_default_main = None  # type: ignore


class GameTkApp:
	# ---------------------------------------------------------------------------
	# 函数索引与用途说明（阅读导引）

	# 初始化/基础
	# - __init__: 创建 Tk 根窗体、菜单与游戏区域, 初始化样式与视图, 可按 initial_scene 直接入局。
	# - _bind_views_context: 让各视图持有当前 game 引用, 由视图自行读取 zone/entity 与订阅事件。
	# - _log_exception: 统一异常落日志(或控制台)。
	# - _reset_highlights: 恢复卡片/敌人默认描边与底色, 清理残留高亮。
	# - _send: 统一命令入口, 兼容旧动词(a/eq/uneq/t/u/craft/back/end/skill等)后转发控制器。

	# 事件(来自模型/控制器)
	# - _on_event_scene_changed: 场景切换; 进入 UI 抑制窗口 -> 清理选择态 -> 播放过渡层 -> 延后重建视图。

	# 菜单/主界面
	# - _build_menu: 主菜单 UI(开始/改名/选择地图组/刷新/退出)。
	# - _menu_profile/_menu_start/_menu_rename/_menu_choose_pack/_menu_refresh_packs。
	# - _build_game: 游戏主界面布局(敌人区/资源与背包/队伍/操作栏/日志)。

	# 刷新与渲染
	# - refresh_all: 触发视图自渲染(资源/敌人/队伍/操作栏), 并更新场景标题。
	# - _render_resources: 委托 ResourcesView 渲染资源与背包(抑制期合并)。
	# - _render_operations: 委托 OperationsView 渲染所选队员可用操作(抑制期合并)。
	# - refresh_battlefield_only/_schedule_battlefield_refresh: 兼容保留的 no-op(视图自调度)。

	# 交互(统一走 SelectionController + TargetingEngine)
	# - begin_skill: 技能入口; TargetingEngine.begin -> 无需目标则直接执行。
	# - _confirm_skill/_cancel_skill/_update_target_highlights: 确认/取消以及微更新高亮。
	# - _slot_click: 卡片装备槽点击(卸下/更换/打开装备对话框)。
	# - _open_equip_dialog: 打开装备管理对话框并按返回值发送 eq 指令。

	# 工具/日志/命令
	# - _append_info/_append_log: 统一写入战斗日志(支持结构化 dict)。
	# - _selected_index/_pick_resource: 列表选择与资源拾取(局部刷新)。
	# - _run_cmd/_after_cmd: 运行控制器命令并落地日志/状态快照。

	# 生命周期
	# - _start_game: 进入游戏模式, 绑定视图上下文, 输出初始状态并全量刷新。
	# - _back_to_menu: 返回主菜单, 卸载视图并清理。
	# - run/_on_close: 进入 Tk 主循环/关闭前取消订阅与销毁窗口。
	# - run_tk: 外部启动入口函数(脚本/打包共用)。
	def __init__(self, player_name: str = "玩家", initial_scene: Optional[str] = None):
		"""构造应用与主窗口。初始化菜单/游戏界面并挂载视图与场景事件。"""
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
			'cand_enemy_border': '#FAD96B',
			'cand_enemy_bg':     '#FFF7CC',
			'cand_ally_border':  '#7EC6F6',
			'cand_ally_bg':      '#E6F4FF',
			'sel_enemy_border':  '#FF4D4F',
			'sel_enemy_bg':      '#FFE6E6',
			'sel_ally_border':   '#1E90FF',
			'sel_ally_bg':       '#D6EBFF',
		}
		# 应用运行期可配置项（主题/尺寸/边框/高亮/动画开关/日志颜色等）
		try:
			S.apply_console_theme()
			S.apply_to_tk_app(self)
		except Exception:
			pass

		# 启动事件驱动的被动系统（幂等）
		try:
			from src.systems import passives_system as PS
			PS.setup()
		except Exception:
			pass

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
		"""让各 View 直接持有 game 引用, 避免通过 app 转发."""
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
		"""记录异常到日志控件或打印, 避免 silent pass."""
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
		"""恢复所有卡片/敌人默认边框色, 防止残留高亮."""
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
		verb = parts[0].lower()
		rest = parts[1:]
		alias = {
			'attack': 'a', 'atk': 'a', 'a': 'a',
			'equip': 'eq', 'eq': 'eq',
			'unequip': 'uneq', 'uneq': 'uneq',
			'take': 't', 't': 't',
			'use': 'use', 'u': 'use',
			'craft': 'craft', 'c': 'craft',
			'end': 'end',
			'back': 'back', 'b': 'back',
			'skill': 'skill',
			'inv': 'i', 'i': 'i',
			'moveeq': 'moveeq',
			's': 's',
		}
		mapped = alias.get(verb, verb)
		mapped_cmd = ' '.join([mapped] + rest)
		try:
			out = self.controller._process_command(mapped_cmd)
			return out
		except Exception as e:
			self._log_exception(e, f'_send {mapped_cmd}')
			return [], {}





	# -------- Event handlers --------
	def _on_event_scene_changed(self, _evt: str, payload: dict):
		"""场景切换事件: 进入 UI 抑制期, 稍后全量刷新并清理选择/目标状态."""
		# 场景切换: 立即更新标题与状态; 稍作延时让死亡/伤害浮字有机会展示, 然后再全量刷新。
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
		# 立即隐藏操作弹窗等顶层 UI，确保切场景时界面被清空
		try:
			ops = (getattr(self, 'views', {}) or {}).get('ops')
			if ops and hasattr(ops, 'hide_popup'):
				ops.hide_popup(force=True)
		except Exception:
			pass
		# 杀掉所有子 UI（容器内容与订阅），播放切换动画占位
		try:
			# 在展示过渡层前确保操作弹窗已隐藏，避免闪烁
			ops = (getattr(self, 'views', {}) or {}).get('ops')
			if ops and hasattr(ops, 'hide_popup'):
				ops.hide_popup(force=True)
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
			delay_ms = int(getattr(self, '_scene_switch_delay_ms', 250))
			self.root.after(delay_ms, _do_full)
		except Exception:
			_do_full()


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
		# 样式在 settings.apply_to_tk_app 中统一配置；此处仅兜底
		try:
			from src import settings as S
			S.apply_to_tk_app(self)
		except Exception:
			try:
				self.style = ttk.Style(self.root)
				self.style.configure("Tiny.TButton", font=("Segoe UI", 8), padding=(4, 2))
				self.style.configure("Tiny.TLabel", font=("Segoe UI", 8))
				self.style.configure("TinyBold.TLabel", font=("Segoe UI", 9, "bold"))
				self.style.configure("Slot.TButton", font=("Segoe UI", 8), padding=(0, 0))
			except Exception:
				self.style = None
		ttk.Label(top, textvariable=self.scene_var, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
		ttk.Button(top, text="主菜单", command=self._back_to_menu, style="Tiny.TButton").pack(side=tk.RIGHT)

		# 顶部：战场区（左：伙伴 右：敌人）——固定 3x5 网格的容器，大色框区分敌我
		arena = ttk.Frame(parent)
		arena.pack(fill=tk.X, expand=False, padx=6, pady=(2, 2))
		arena.columnconfigure(0, weight=1, uniform='arena')
		arena.columnconfigure(1, weight=1, uniform='arena')
		# 伙伴区（左上）：蓝色外框
		ally_border = tk.Frame(
			arena,
			highlightthickness=int(getattr(self, 'ARENA_BORDER_THICKNESS', 4)),
			highlightbackground=getattr(self, 'ALLY_BORDER', '#4A90E2')
		)
		ally_border.grid(row=0, column=0, sticky='nsew', padx=(0, 3))
		ally_hdr = ttk.Label(ally_border, text="伙伴区 (点击选择 mN)", font=("Segoe UI", 10, 'bold'))
		ally_hdr.pack(anchor=tk.W, padx=6, pady=(4, 2))
		self.cards_container = ttk.Frame(ally_border)
		self.cards_container.pack(fill=tk.X, expand=False, padx=6, pady=(0, 6))
		self.card_wraps = {}
		self.selected_member_index = None
		# 敌人区（右上）：红色外框
		enemy_border = tk.Frame(
			arena,
			highlightthickness=int(getattr(self, 'ARENA_BORDER_THICKNESS', 4)),
			highlightbackground=getattr(self, 'ENEMY_BORDER', '#E74C3C')
		)
		enemy_border.grid(row=0, column=1, sticky='nsew', padx=(3, 0))
		enemy_hdr = ttk.Label(enemy_border, text="敌人区 (点击选择 eN)", font=("Segoe UI", 10, 'bold'))
		enemy_hdr.pack(anchor=tk.W, padx=6, pady=(4, 2))
		self.enemy_cards_container = ttk.Frame(enemy_border)
		self.enemy_cards_container.pack(fill=tk.X, expand=False, padx=6, pady=(0, 6))
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

		# （队伍区已移至顶部战场区）

		# 操作栏（提示）：操作已改为悬浮窗（移到友方卡片上）
		self.frm_operations = ttk.LabelFrame(body, text="操作提示")
		self.frm_operations.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(2, 4))
		self.frm_operations.columnconfigure(0, weight=1)
		# 初始占位
		ttk.Label(self.frm_operations, text="将鼠标移到友方角色卡上以显示可用技能/攻击；选择目标后可在悬浮窗内确认或取消。", foreground="#666").grid(row=0, column=0, sticky='w', padx=6, pady=6)

		# 底部：统一“战斗日志”
		bottom = ttk.Frame(body)
		bottom.grid(row=4, column=0, columnspan=2, sticky='nsew')
		bottom.columnconfigure(0, weight=1)
		# 使用封装的日志面板
		self.log_pane = LogPane(bottom, tag_colors=getattr(self, '_log_tag_colors', None))
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
					# 仅持久化到文件，不在 Tk 面板逐行显示
					if isinstance(line, dict):
						f.write(json.dumps(line, ensure_ascii=False) + "\n")
					else:
						f.write(str(line) + "\n")
			# UI 信息区只刷新 s5/s3 简报
			try:
				self._append_log({'type': 'state', 'text': self.controller._section_info(), 'meta': {'section': 's5', 'state': True}})
				self._append_log({'type': 'state', 'text': self.controller._section_history(), 'meta': {'section': 's3', 'state': True}})
			except Exception:
				pass
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
		# Tk 信息区不再逐行回显命令输出；改为统一展示 s5/s3
		# append to persistent log file (cross-platform) and log widget
		try:
			logdir = CFG.log_dir()
			os.makedirs(logdir, exist_ok=True)
			logpath = os.path.join(logdir, 'game.log')
			with open(logpath, 'a', encoding='utf-8') as f:
				for line in lines:
					# 仅写入文件，避免 UI 重复噪音
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
				# consume game structured logs (e.g., DND to_hit/damage) -> only persist to file
				try:
					logs = self.controller.game.pop_logs()
					for L in logs:
						try:
							f.write(json.dumps(L, ensure_ascii=False) + "\n")
						except Exception:
							f.write(str(L) + "\n")
				except Exception:
					pass
		except Exception as e:
			self._log_exception(e, '_after_cmd_log')
		# 仅在 UI 信息区输出 s5/s3 简报
		try:
			self._append_log({'type': 'state', 'text': self.controller._section_info(), 'meta': {'section': 's5', 'state': True}})
			self._append_log({'type': 'state', 'text': self.controller._section_history(), 'meta': {'section': 's3', 'state': True}})
		except Exception as e:
			self._log_exception(e, '_after_cmd_sections')
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
		# 启动时：仅输出 s5/s3 简报到信息区
		try:
			self._append_log({'type': 'state', 'text': self.controller._section_info(), 'meta': {'section': 's5', 'state': True}})
			self._append_log({'type': 'state', 'text': self.controller._section_history(), 'meta': {'section': 's3', 'state': True}})
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
		# 强制清理顶层 UI（操作弹窗/过渡层），不留残影
		try:
			ops = (getattr(self, 'views', {}) or {}).get('ops')
			if ops and hasattr(ops, 'hide_popup'):
				ops.hide_popup(force=True)
		except Exception:
			pass
		try:
			self._hide_scene_transition()
		except Exception:
			pass
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
			# 置顶，避免被其他顶层窗口（如 tooltip/操作弹窗）覆盖
			try:
				ov.attributes('-topmost', True)
			except Exception:
				pass
			ov.lift()
			ov.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}+{self.root.winfo_rootx()}+{self.root.winfo_rooty()}")
			frm = ttk.Frame(ov)
			frm.pack(fill=tk.BOTH, expand=True)
			lbl = ttk.Label(frm, text="正在切换场景…", font=("Segoe UI", 14, "bold"))
			lbl.place(relx=0.5, rely=0.5, anchor='center')
			setattr(self, '_scene_overlay', ov)
			# 随主窗口移动/缩放时同步覆盖层尺寸
			def _sync_overlay_geometry(_e=None):
				try:
					ov.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}+{self.root.winfo_rootx()}+{self.root.winfo_rooty()}")
				except Exception:
					pass
			try:
				bind_id = self.root.bind('<Configure>', _sync_overlay_geometry, add='+')
				setattr(self, '_scene_overlay_bind_id', bind_id)
			except Exception:
				setattr(self, '_scene_overlay_bind_id', None)
			# 使用可配置的淡入参数
			interval = int(getattr(self, '_overlay_fade_interval', 16))
			step = float(getattr(self, '_overlay_fade_step', 0.1))
			target = float(getattr(self, '_overlay_target_alpha', 0.8))
			def fade_in(a: float = 0.0):
				try:
					if a >= target:
						ov.attributes('-alpha', target)
						return
					ov.attributes('-alpha', a)
					self.root.after(interval, lambda: fade_in(a + step))
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
			# 解绑几何同步
			try:
				bid = getattr(self, '_scene_overlay_bind_id', None)
				if bid:
					self.root.unbind('<Configure>', bid)
				setattr(self, '_scene_overlay_bind_id', None)
			except Exception:
				pass
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
		# 进入抑制期，防止子视图在销毁过程中再次调度 after/render
		setattr(self, '_suspend_ui_updates', True)
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
			# 强制隐藏顶层窗口（过渡层/操作弹窗/tooltip）避免 Tcl 命令残留
			try:
				ops = (getattr(self, 'views', {}) or {}).get('ops')
				if ops and hasattr(ops, 'hide_popup'):
					ops.hide_popup(force=True)
			except Exception:
				pass
			try:
				self._hide_scene_transition()
			except Exception:
				pass
		except Exception:
			pass
		# 取消已知的 after 调度，尽量避免 destroy 时的 deletecommand 异常
		try:
			bid = getattr(self, '_scene_overlay_bind_id', None)
			if bid:
				self.root.after_cancel(bid)
		except Exception:
			pass
		# 容错调用 destroy，吞掉 TclError
		try:
			self.root.destroy()
		except Exception:
			pass


def run_tk(player_name: str = "玩家", initial_scene: Optional[str] = None):
	"""外部启动入口：创建并运行 GameTkApp。"""
	app = GameTkApp(player_name=player_name, initial_scene=initial_scene)
	app.run()

