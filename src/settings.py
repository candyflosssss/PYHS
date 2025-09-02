"""运行时配置（UI/动画/时间/规则）。

- 从 `app_config.user_config_path()` 指向的 JSON 读取用户配置并与此处默认值“深度合并”。
	- 也就是说：用户 JSON 里写什么就覆盖什么；没写的键继续用这里的默认。
- 提供便捷函数获取嵌套配置（ui_cfg/anim_cfg/tk_cfg/rules_cfg），避免在业务处硬编码常量。
- `apply_to_tk_app(app)` 会把常用 UI 参数注入到 Tk App（如卡片尺寸、边框、调色板、
	过场动画时间、体力显示配置、ttk 样式），做到“改 setting 即改 UI 行为”。

如何修改（最常见场景）：
- 想调颜色：在用户 JSON 写入 ui.tk.highlight/ui.tk.stats_colors/ui.tk.log.tags/ui.animations.colors 等键。
- 想调动画快慢：改 ui.animations 下的 interval_ms/steps 或直接把 ui.animations.enabled 设为 False 关闭。
- 想调字体与按钮间距：改 ui.styles 下对应样式（如 Tiny.TButton/Tiny.TLabel/Slot.TButton）。
- 想改卡片尺寸、边框粗细：改 ui.tk.card.width/height 与 ui.tk.border.*。
- 想改体力显示开关与颜色：改 ui.tk.stamina.*（此处仅影响显示，不改变规则）。
- 想改规则（体力上限/消耗）：改 rules.stamina.base、rules.skill_costs；若不写某个技能的消耗，默认 1。

注意：你不需要拷贝本文件到用户配置；只需在用户 JSON 写上需要覆盖的那几个键即可。
示例（user_config.json）：
{
	"ui": {
		"animations": { "enabled": false },
		"styles": { "Tiny.TButton": { "font": ["Microsoft YaHei", 9], "padding": [6, 3] } }
	},
	"rules": { "stamina": { "base": 4 }, "skill_costs": { "attack": 2, "sweep": 2 } }
}
"""
from __future__ import annotations

from typing import Any, Dict
import copy
import json
import os

from . import app_config as CFG


# ---- 默认配置（可在用户配置中覆盖） ----
DEFAULTS: Dict[str, Any] = {
	"console": {
		# 控制台配色主题（仅影响命令行/日志的着色，不影响 Tk 界面）
		"theme": "default",  # 可选: default | mono | high-contrast
	},
	"ui": {
		"tk": {
			"debug": {
				"anchors": { "show": True, "color": "#99ccff", "text": "#333333" }
			},
			"arena": {
				# 顶部战场区外框颜色与粗细
				"ally_border": "#4A90E2",
				"enemy_border": "#E74C3C",
				"thickness": 4
			},
			"border": {
				# 各种高亮边框粗细（像素）
				"default": 3,
				"selected_enemy": 3,
				"selected_member": 3,
			},
			# 选中/候选高亮配色
			"highlight": {
				"cand_enemy_border": "#FAD96B",
				"cand_enemy_bg": "#FFF7CC",
				"cand_ally_border": "#7EC6F6",
				"cand_ally_bg": "#E6F4FF",
				"sel_enemy_border": "#FF4D4F",
				"sel_enemy_bg": "#FFE6E6",
				"sel_ally_border": "#1E90FF",
				"sel_ally_bg": "#D6EBFF",
			},
			"overlay": {
				# 场景切换时的遮罩渐入
				"target_alpha": 0.8,
				"fade_interval_ms": 16,
				"fade_step": 0.1,
			},
			"scene_transition": {
				# 切换前延迟重建视图（留时间显示死亡/浮字）
				"delay_ms": 1500,
			},
			"tooltip": {
				# 悬浮提示刷新的轮询间隔（越小越灵敏）
				"tick_ms": 120,
				# 是否在敌方的装备提示中展示主动技能列表
				"enemy_show_active_skills": False
			},
			# 操作弹窗配置（攻击/技能列表）
			"ops_popup": {
				"trigger": "click",       # click | hover
				"hide_delay_ms": 300,       # 仅 hover 下有效
				"offset": [4, 0]            # 相对卡片右侧的位移 (dx, dy)
			},
			"stats_colors": {
				# 角色卡上 ATK/HP/AC 的文字颜色
				"atk": "#E6B800",
				"hp_pos": "#27ae60",
				"hp_zero": "#c0392b",
				"ac": "#2980b9",
			},
			"card": {
				# 卡片默认尺寸（尽量紧凑；体力行存在时视图层会保证最小高度不被裁切）
				"width": 160,
				"height": 120
			},
			"stamina": {
				# 体力显示（角色卡左上角的胶囊/条）
				"enabled": True,
				"max_caps": 20,            # UI 最多绘制的胶囊数量上限（不影响规则）
				"bg": "#f2f3f5",           # 体力条背景色（与卡片背景区分开）
				"colors": {
					"on": "#2ecc71",       # 可用体力颜色（绿）
					"off": "#e74c3c"       # 已消耗体力颜色（红）
				},
				"shape": "capsule",       # 形状占位（暂不区分，统一用小竖条表示）
			},
			"hp_bar": {
				# 血量条（显示在体力条下方）
				"height": 12,
				"bg": "#e5e7eb",
				"fg": "#e74c3c",          # 血条填充色（红）
				"text": "#ffffff"          # 覆盖文字颜色
			},
			"log": {
				"tags": {
					"info": "#222",
					"success": "#27ae60",
					"warning": "#E67E22",
					"error": "#d9534f",
					"state": "#666666",
					"attack": "#c0392b",
					"heal": "#27ae60",
					"crit": "#8E44AD",
					"miss": "#95A5A6",
					"block": "#2C3E50",
				}
			},
		},
		"animations": {
			"enabled": True,  # 全局开关（False 时不触发动画），如需彻底关闭浮字/闪烁/抖动等，改为 False 即可
			"colors": {
				"damage": "#c0392b",
				"heal": "#27ae60",
			},
			"shake": {"enabled": True, "amplitude": 5, "cycles": 8, "interval_ms": 18},
			"flash": {"repeats": 3, "interval_ms": 110},
			"fade_out": {"steps": 16, "interval_ms": 45, "delay_before_ms": 200},
			"float_text": {"dy": 30, "steps": 18, "interval_ms": 36, "font_size": 27},
		},
		# 常用 ttk 样式集中于此，方便统一调整字体与间距
		"styles": {
			# 小号紧凑按钮（操作栏等处）
			"Tiny.TButton": { "font": ["Segoe UI", 8], "padding": [4, 2] },
			# 小号标签
			"Tiny.TLabel": { "font": ["Segoe UI", 8] },
			# 小号粗体标签（卡片名/标题等）
			"TinyBold.TLabel": { "font": ["Segoe UI", 9, "bold"] },
			# 卡片槽位按钮（更紧凑）
			"Slot.TButton": { "font": ["Segoe UI", 8], "padding": [0, 0] }
		}
	},
	"rules": {
		# 玩法规则：体力	及各技能的默认消耗
		"stamina": {
			"base": 3,              # 默认体力上限（每回合开始回满）
			"refill": "full",      # 回合开始的恢复策略（目前仅支持 full）
			"growth_per_depth": 0   # 探索深度带来的成长（预留，暂不使用）
		},
		"skill_costs": {
			"attack": 1,            # 普通攻击的体力消耗
			"sweep": 1,
			"basic_heal": 1,
			"drain": 1,
			"taunt": 1,
			"arcane_missiles": 1
			# 其他未列出的技能默认 1（可在用户配置中覆盖）
		}
	}
}


_CACHED: Dict[str, Any] | None = None


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
	for k, v in (src or {}).items():
		if isinstance(v, dict) and isinstance(dst.get(k), dict):
			_deep_merge(dst[k], v)
		else:
			dst[k] = v
	return dst


def _load_file() -> Dict[str, Any]:
	path = CFG.user_config_path()
	try:
		if os.path.exists(path):
			with open(path, "r", encoding="utf-8") as f:
				data = json.load(f)
				return data if isinstance(data, dict) else {}
	except Exception:
		return {}
	return {}


def get_settings() -> Dict[str, Any]:
	global _CACHED
	if _CACHED is not None:
		return _CACHED
	data = _load_file()
	merged = copy.deepcopy(DEFAULTS)
	if isinstance(data, dict):
		# new settings live under `ui` and `console`; accept at root for forward compat
		root_ui = data.get("ui") if isinstance(data.get("ui"), dict) else {}
		root_console = data.get("console") if isinstance(data.get("console"), dict) else {}
		# Build a small map to merge into defaults
		ext: Dict[str, Any] = {}
		if root_ui:
			ext["ui"] = root_ui
		if root_console:
			ext["console"] = root_console
		_deep_merge(merged, ext)
	_CACHED = merged
	return merged


def reload() -> None:
	global _CACHED
	_CACHED = None


def ui_cfg() -> Dict[str, Any]:
	return get_settings().get("ui", {})


def anim_cfg() -> Dict[str, Any]:
	return ui_cfg().get("animations", {})


def tk_cfg() -> Dict[str, Any]:
	return ui_cfg().get("tk", {})


def rules_cfg() -> Dict[str, Any]:
	"""返回玩法规则配置（含体力与技能消耗）。"""
	return get_settings().get("rules", {})


def stamina_base() -> int:
	try:
		return int((rules_cfg().get("stamina") or {}).get("base", 3))
	except Exception:
		return 3


def get_skill_cost(name: str, default: int = 1) -> int:
	"""查询技能体力消耗；未定义则返回默认值。"""
	try:
		costs = rules_cfg().get("skill_costs", {}) or {}
		v = costs.get(str(name), None)
		return int(v) if v is not None else int(default)
	except Exception:
		return int(default)


def apply_console_theme() -> None:
	"""Apply console color theme to src.ui.colors if available."""
	try:
		from .ui import colors as C
		theme = get_settings().get("console", {}).get("theme", "default")
		C.set_theme(theme)
	except Exception:
		pass


def apply_to_tk_app(app) -> None:
	"""Apply Tk related settings to GameTkApp instance.

	Sets dimensions, borders, highlight palette, animation toggles, and stores
	stats/log palettes on `app` for views/widgets to use.
	"""
	cfg_tk = tk_cfg()
	borders = cfg_tk.get("border", {})
	cards = cfg_tk.get("card", {})
	arena = cfg_tk.get("arena", {})
	palette = cfg_tk.get("highlight", {})
	stats_colors = cfg_tk.get("stats_colors", {})
	log_tags = ((cfg_tk.get("log") or {}).get("tags") or {})

	try:
		app.CARD_W = int(cards.get("width", getattr(app, "CARD_W", 180)))
		app.CARD_H = int(cards.get("height", getattr(app, "CARD_H", 80)))
	except Exception:
		pass
	# arena border colors/thickness
	try:
		app.ARENA_BORDER_THICKNESS = int(arena.get("thickness", getattr(app, "ARENA_BORDER_THICKNESS", 4)))
		app.ALLY_BORDER = arena.get("ally_border", getattr(app, "ALLY_BORDER", "#4A90E2"))
		app.ENEMY_BORDER = arena.get("enemy_border", getattr(app, "ENEMY_BORDER", "#E74C3C"))
	except Exception:
		pass
	try:
		app._border_default = int(borders.get("default", getattr(app, "_border_default", 3)))
		app._border_selected_enemy = int(borders.get("selected_enemy", getattr(app, "_border_selected_enemy", 3)))
		app._border_selected_member = int(borders.get("selected_member", getattr(app, "_border_selected_member", 3)))
	except Exception:
		pass
	try:
		app.HL = { **getattr(app, "HL", {}), **palette }
	except Exception:
		pass
	# expose stats colors for card rendering
	try:
		app._stats_colors = { **{"atk": "#E6B800", "hp_pos": "#27ae60", "hp_zero": "#c0392b", "ac": "#2980b9"}, **stats_colors }
	except Exception:
		pass
	# expose log tag palette for LogPane
	try:
		app._log_tag_colors = log_tags
	except Exception:
		pass
	# expose stamina palette for card rendering
	try:
		st = (cfg_tk.get("stamina") or {})
		app._stamina_cfg = {
			"enabled": bool(st.get("enabled", True)),
			"max_caps": int(st.get("max_caps", 6)),
			"bg": st.get("bg", "#f2f3f5"),
			"colors": {
				"on": (st.get("colors", {}) or {}).get("on", "#2ecc71"),
				"off": (st.get("colors", {}) or {}).get("off", "#e74c3c"),
			}
		}
	except Exception:
		pass
	# expose hp bar config
	try:
		app._hp_bar_cfg = {
			"height": int(cfg_tk.get("hp_bar", {}).get("height", 12)),
			"bg": cfg_tk.get("hp_bar", {}).get("bg", "#e5e7eb"),
			"fg": cfg_tk.get("hp_bar", {}).get("fg", "#e74c3c"),
			"text": cfg_tk.get("hp_bar", {}).get("text", "#ffffff"),
		}
	except Exception:
		pass
	# expose tooltip & ops popup configs
	try:
		app._tooltip_cfg = cfg_tk.get("tooltip", {}) or {}
		app._ops_popup_cfg = cfg_tk.get("ops_popup", {}) or {"trigger":"click","hide_delay_ms":300,"offset":[4,0]}
	except Exception:
		pass
	# animation shake toggle compatibility with existing flag
	try:
		sh = anim_cfg().get("shake", {})
		app._no_shake = not bool(sh.get("enabled", False))
	except Exception:
		pass
	# store overlay/transition numbers for use in app methods
	try:
		ov = cfg_tk.get("overlay", {})
		app._overlay_target_alpha = float(ov.get("target_alpha", 0.8))
		app._overlay_fade_interval = int(ov.get("fade_interval_ms", 16))
		app._overlay_fade_step = float(ov.get("fade_step", 0.1))
	except Exception:
		pass
	# debug: anchors visualization flags/colors
	try:
		dbg = (cfg_tk.get("debug") or {})
		anc = (dbg.get("anchors") or {})
		app._debug_show_anchors = bool(anc.get("show", False))
		app._debug_anchor_color = anc.get("color", "#99ccff")
		app._debug_anchor_text = anc.get("text", "#333333")
	except Exception:
		pass
	try:
		app._scene_switch_delay_ms = int(cfg_tk.get("scene_transition", {}).get("delay_ms", 250))
	except Exception:
		pass
	# emit ttk styles from config if Style is available
	try:
		from tkinter import ttk  # type: ignore
		styles = (ui_cfg().get("styles") or {})
		if styles:
			app.style = ttk.Style(app.root)
			for name, spec in styles.items():
				kw = {}
				f = spec.get("font")
				if isinstance(f, (list, tuple)):
					kw["font"] = tuple(f)
				p = spec.get("padding")
				if isinstance(p, (list, tuple)):
					kw["padding"] = tuple(p)
				if kw:
					app.style.configure(name, **kw)
	except Exception:
		pass
