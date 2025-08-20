"""Textual 外壳（带主菜单与行动板）
- 主菜单：开始游戏、修改名称、选择地图组、刷新、退出（逻辑对齐 main.py）
- 行动板：单列（队伍→敌人→资源→背包），按钮紧凑贴合文字
"""

from __future__ import annotations

import os
import re
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, Log, Label, Input
from textual.widget import Widget

from game_modes.pve_controller import SimplePvEController
from ui import colors as C
from systems.equipment_system import WeaponItem, ArmorItem, ShieldItem

try:
    from main import load_config, save_config, discover_packs, _pick_default_main  # type: ignore
except Exception:  # pragma: no cover
    load_config = save_config = discover_packs = _pick_default_main = None  # type: ignore


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _to_plain_lines(text: str) -> list[str]:
    try:
        return (ANSI_RE.sub("", text)).splitlines() or [""]
    except Exception:
        return [text]


def _clear_container(container: Widget) -> None:
    """尽力清空容器的子节点，避免 DuplicateIds。
    兼容不同 Textual 版本：先尝试 remove_children，再逐个 child.remove，最后用查询移除。
    """
    # 1) 官方 API（可能是延迟的，但先调用）
    try:
        container.remove_children()
    except Exception:
        pass
    # 2) 逐个 immediate remove
    try:
        for child in list(container.children):
            try:
                child.remove()
            except Exception:
                pass
    except Exception:
        pass
    # 3) 兜底：递归查询所有子节点并移除
    try:
        for child in list(container.query("*")):
            if child is not container:
                try:
                    child.remove()
                except Exception:
                    pass
    except Exception:
        pass


class GameTextualApp(App):
    CSS = """
    Screen { layout: vertical; }
    # 顶部与提示
    # 让按钮尽量贴文字宽度
    # 主体两栏
    .main { height: 1fr; }
    .col { padding: 0; align-horizontal: left; }
    # 标题
    .sec_title { text-style: bold; color: $accent; padding: 0 0; }
    .hint { color: $text-muted; padding: 0 0; }
    # 按钮（紧凑、贴文字）
    .item { margin: 0; padding: 0 0; min-height: 1; height: 1; width: auto; border: none; }
    .tight { padding: 0 0; margin: 0; width: auto; height: 1; }
    # 收紧整体行距
    # 尽量让 Board 中的控件贴合文本高度
    # 不用全局 Button 以免影响主菜单按钮
    #board { padding: 0; margin: 0; }
    #right { padding: 0; }
    #topbar, #hintbar { padding: 0; }
    #leftcol { layout: vertical; }
    #board { height: 1fr; padding: 0; margin: 0; }
    #char_panel_container { height: auto; padding: 0; margin: 0; }
    #board Button { padding: 0 0; margin: 0; min-height: 1; height: 1; }
    #board Label { padding: 0 0; margin: 0; }
    #info, #logs { padding: 0; }
    # 语义色
    .friendly { color: $success; }
    .enemy { color: $warning; }
    .resource { color: $accent; }
    .equip { color: $text; }
    .highlight { border: round $warning; }
    .selected { border: heavy $success; }

    /* 顶部栏/提示栏强制单行高度，避免过多留白 */
    #topbar { height: 1; min-height: 1; padding: 0; margin: 0; }
    #topbar Label { height: 1; min-height: 1; padding: 0; margin: 0; }
    #topbar Button { height: 1; min-height: 1; padding: 0; margin: 0; }
    #hintbar { height: 1; min-height: 1; padding: 0; margin: 0; }
    #hintbar Label { height: 1; min-height: 1; padding: 0; margin: 0; }

    /* 角色面板（左下角，放在 Board 末尾） */
    #char_panel { border: round $accent; padding: 0 0; margin: 0 0; width: auto; }
    #char_header { padding: 0 0; margin: 0 0; height: 1; min-height: 1; }
    #char_stats { padding: 0 0; margin: 0 0; height: 1; min-height: 1; }
    #slots { padding: 0 0; margin: 0 0; }
    .slot { padding: 0 0; margin: 0 1; height: 1; min-height: 1; width: auto; }
    """

    BINDINGS = [
        ("ctrl+c", "app.quit", "退出"),
        ("esc", "cancel_select", "取消选中"),
        ("f5", "refresh_view", "刷新视图"),
        ("f9", "toggle_logs", "切换日志"),
    ]

    def __init__(self, player_name: Optional[str] = None, initial_scene: Optional[str] = None):
        super().__init__()
        # 模式与控制器
        self.mode = "menu"  # menu|game
        self.controller: Optional[SimplePvEController] = None
        self._player_name = player_name or "玩家"
        self._pending_initial_scene = initial_scene
        # 选择状态/刷新 epoch
        self.sel_minion: Optional[int] = None
        self._epoch = 0
        # UI 部件
        self.header_title = None
        self.turn_label = None
        self.btn_menu = None
        self.btn_back = None
        self.btn_end = None
        self.hint_bar = None
        self.board = None
        self.char_container = None
        self.info_panel = None
        self.log_panel = None
        self.show_logs = True
        # 主菜单数据
        self.cfg = None
        self.packs = None
        self.menu_state = "root"  # root | choose_pack | edit_name
        self.name_input = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            self.header_title = Label("", id="scene_title")
            yield self.header_title
            self.turn_label = Label("", id="turn_label")
            yield self.turn_label
            self.btn_menu = Button("主菜单", id="btn_menu", classes="tight")
            yield self.btn_menu
            self.btn_back = Button("返回上级", id="btn_back", classes="tight")
            yield self.btn_back
            self.btn_end = Button("结束回合", id="btn_end", classes="tight", variant="success")
            yield self.btn_end
        with Horizontal(id="hintbar"):
            self.hint_bar = Label("")
            yield self.hint_bar

        with Horizontal(classes="main"):
            with Vertical(id="leftcol", classes="col"):
                self.board = ScrollableContainer(id="board")
                yield self.board
                self.char_container = Vertical(id="char_panel_container")
                yield self.char_container
            with Vertical(id="right", classes="col"):
                yield Label("信息", classes="sec_title")
                self.info_panel = Log(id="info")
                yield self.info_panel
                yield Label("日志", classes="sec_title")
                self.log_panel = Log(id="logs")
                yield self.log_panel

    def on_mount(self) -> None:
        self._enter_menu()

    # 动作
    def action_refresh_view(self) -> None:
        if self.mode == "game":
            self._refresh_all()
        else:
            self._render_menu()

    def action_cancel_select(self) -> None:
        if self.mode != "game":
            return
        self.sel_minion = None
        self._render_board()

    def action_toggle_logs(self) -> None:
        if self.mode != "game":
            return
        self.show_logs = not self.show_logs
        if self.log_panel:
            self.log_panel.display = self.show_logs

    # 状态/渲染
    def _set_scene_header(self) -> None:
        if self.mode != "game" or not self.controller:
            if self.header_title:
                self.header_title.update("主菜单")
            if self.turn_label:
                self.turn_label.update("")
            if self.btn_back:
                self.btn_back.disabled = True
            if self.btn_end:
                self.btn_end.disabled = True
            if self.hint_bar:
                # 更短提示，减小视觉占用
                self.hint_bar.update("提示: 开始游戏或设置")
            return
        title = "场景"
        try:
            raw_title = self.controller.game.current_scene_title or self.controller.game.current_scene or "场景"
            title = C.strip(str(raw_title))
        except Exception:
            pass
        if self.header_title:
            self.header_title.update(f"场景：{title}")
        if self.turn_label:
            t = getattr(self.controller.game, 'turn', '')
            self.turn_label.update(f"回合 {t}")
        if self.btn_back:
            can_back = bool(getattr(self.controller.game, 'can_navigate_back', None) and self.controller.game.can_navigate_back())
            self.btn_back.disabled = not can_back
        if self.btn_end:
            self.btn_end.disabled = False
        if self.hint_bar:
            if self.sel_minion is None:
                self.hint_bar.update("提示: 点资源=拾取；选队员后可攻击/装备")
            else:
                self.hint_bar.update("已选：点敌人=攻击；点背包=装备；Esc 取消")

    def _append_log(self, text: str) -> None:
        if not self.log_panel:
            return
        for s in _to_plain_lines(text):
            if s.strip():
                self.log_panel.write_line(s)

    def _append_info(self, text: str) -> None:
        if not self.info_panel:
            return
        for s in _to_plain_lines(text):
            if s.strip():
                self.info_panel.write_line(s)

    def _refresh_all(self) -> None:
        self._set_scene_header()
        self._render_board()
        if self.controller and self.controller.info:
            if self.info_panel:
                self.info_panel.clear()
            for i, line in enumerate(self.controller.info[-10:]):
                if i == 0:
                    if any(k in line for k in ("失败", "无效", "错误")):
                        self._append_info(C.error(line))
                    elif any(k in line for k in ("成功", "进入回合", "拾取", "使用", "攻击")):
                        self._append_info(C.success(line))
                    else:
                        self._append_info(C.warning(line))
                else:
                    self._append_info(C.dim(line))

    def _render_board(self) -> None:
        if not self.board or self.mode != "game" or not self.controller:
            return
        self._epoch += 1
        _clear_container(self.board)
        if self.char_container:
            _clear_container(self.char_container)
        # 复用控制器的区块文本，保证与 s 指令一致
        from re import match
        def mount_section(title: str, section_text: str, token_prefix: str, button_prefix: str, btn_class: str, highlight: bool = False):
            lines = [ln for ln in _to_plain_lines(section_text) if ln.strip() != ""]
            if not lines:
                return
            # 标题行
            self.board.mount(Label(lines[0], classes="sec_title tight"))
            if len(lines) == 1:
                return
            # 其余行：解析 token 列（如 "  m1  文本"）
            for ln in lines[1:]:
                m = match(r"^\s*(\w\d+)\s+(.*)$", ln)
                if m and m.group(1).lower().startswith(token_prefix):
                    token = m.group(1)
                    body = m.group(2)
                    try:
                        idx = int(token[1:])
                    except Exception:
                        idx = 0
                    btn = Button(body, id=f"{button_prefix}_{idx}__{self._epoch}", classes=f"item tight {btn_class}")
                    if button_prefix == 'm' and self.sel_minion == (idx - 1):
                        btn.add_class("selected")
                    if highlight:
                        btn.add_class("highlight")
                    self.board.mount(btn)
                else:
                    # 普通文本行
                    self.board.mount(Label(ln, classes="tight hint"))

        # 各区块
        # 玩家队伍
        try:
            mount_section("队伍", self.controller._section_player(), 'm', 'm', 'friendly', highlight=False)
        except Exception:
            pass
        # 敌人
        try:
            hl = self.sel_minion is not None
            mount_section("敌人", self.controller._section_enemy(), 'e', 'e', 'enemy', highlight=hl)
        except Exception:
            pass
        # 资源
        try:
            mount_section("资源", self.controller._section_resources(), 'r', 'r', 'resource', highlight=False)
        except Exception:
            pass
        # 背包（含可合成列表文本）
        try:
            mount_section("背包", self.controller._section_inventory(), 'i', 'i', 'equip', highlight=(self.sel_minion is not None))
        except Exception:
            pass
        # 角色面板（左下角）：显示当前选中队员(或玩家)与装备槽
        try:
            self._mount_char_panel()
        except Exception:
            pass

    def _mount_char_panel(self) -> None:
        if (not self.char_container) or (not self.controller):
            return
        game = self.controller.game
        # 目标：优先选中的队员，否则玩家
        board = getattr(game.player, 'board', [])
        target = None
        if self.sel_minion is not None and 0 <= self.sel_minion < len(board):
            target = board[self.sel_minion]
        # 名称与数值
        if target is not None:
            try:
                name = getattr(target, 'display_name', None) or target.__class__.__name__
            except Exception:
                name = '随从'
            try:
                atk = int(getattr(target, 'get_total_attack', lambda: getattr(target, 'atk', 0))())
            except Exception:
                atk = int(getattr(target, 'atk', 0))
            cur_hp = int(getattr(target, 'hp', 0))
            max_hp = int(getattr(target, 'max_hp', cur_hp))
        else:
            # 玩家摘要：总攻=队伍总和，玩家HP
            name = getattr(game.player, 'name', '玩家')
            try:
                atk = int(game.player.get_total_attack())
            except Exception:
                atk = 0
            cur_hp = int(getattr(game.player, 'hp', 0))
            max_hp = int(getattr(game.player, 'max_hp', cur_hp))
        # 容器
        self.char_container.mount(Label("角色", id="char_header", classes="sec_title tight"))
        from textual.containers import Vertical, Horizontal
        panel = Vertical(id="char_panel")
        stats = f"{name}  [攻 {atk} | HP {cur_hp}/{max_hp}]"
        panel.mount(Label(stats, id="char_stats", classes="tight"))
        # 装备槽（仅当选中目标且其具有 equipment）
        slots_row = Horizontal(id="slots")
        left_txt = "左:空"; armor_txt = "甲:空"; right_txt = "右:空"
        left_tip = armor_tip = right_tip = ""
        if target is not None:
            eq = getattr(target, 'equipment', None)
            if eq:
                if getattr(eq, 'left_hand', None):
                    lh = eq.left_hand
                    left_txt = f"左:{getattr(lh, 'name', '???')}"
                    bonus = []
                    if getattr(lh, 'attack', 0): bonus.append(f"+{lh.attack}攻")
                    if getattr(lh, 'defense', 0): bonus.append(f"+{lh.defense}防")
                    if getattr(lh, 'is_two_handed', False): bonus.append("双手")
                    left_tip = " ".join(bonus) if bonus else "无加成"
                if getattr(eq, 'armor', None):
                    ar = eq.armor
                    armor_txt = f"甲:{getattr(ar, 'name', '???')}"
                    bonus = []
                    if getattr(ar, 'attack', 0): bonus.append(f"+{ar.attack}攻")
                    if getattr(ar, 'defense', 0): bonus.append(f"+{ar.defense}防")
                    armor_tip = " ".join(bonus) if bonus else "无加成"
                if getattr(eq, 'right_hand', None):
                    rh = eq.right_hand
                    right_txt = f"右:{getattr(rh, 'name', '???')}"
                    bonus = []
                    if getattr(rh, 'attack', 0): bonus.append(f"+{rh.attack}攻")
                    if getattr(rh, 'defense', 0): bonus.append(f"+{rh.defense}防")
                    right_tip = " ".join(bonus) if bonus else "无加成"
        # 创建槽位按钮（悬浮提示）
        btn_left = Button(left_txt, classes="item tight slot", id=f"slot_left__{self._epoch}")
        btn_armor = Button(armor_txt, classes="item tight slot", id=f"slot_armor__{self._epoch}")
        btn_right = Button(right_txt, classes="item tight slot", id=f"slot_right__{self._epoch}")
        try:
            # 直接设置 tooltip（Textual 支持时会显示）
            if left_tip: btn_left.tooltip = C.strip(left_tip)
            if armor_tip: btn_armor.tooltip = C.strip(armor_tip)
            if right_tip: btn_right.tooltip = C.strip(right_tip)
        except Exception:
            pass
        # 若未选目标，则将槽位禁用
        if target is None:
            btn_left.disabled = True
            btn_armor.disabled = True
            btn_right.disabled = True
        slots_row.mount(btn_left)
        slots_row.mount(btn_armor)
        slots_row.mount(btn_right)
        panel.mount(slots_row)
        self.char_container.mount(panel)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn_menu":
            self._enter_menu()
            return
        if self.mode == "menu":
            bid_base = bid.split("__", 1)[0]
            if bid_base == "menu_start":
                self._menu_start_game()
                return
            if bid_base == "menu_edit_name":
                self.menu_state = "edit_name"
                self._render_menu()
                return
            if bid_base == "menu_choose_pack":
                self.menu_state = "choose_pack"
                self._render_menu()
                return
            if bid_base == "menu_reload":
                self._menu_load_data(force_reload=True)
                self._render_menu()
                return
            if bid_base == "menu_back":
                self.menu_state = "root"
                self._render_menu()
                return
            if bid_base == "menu_quit":
                self.exit()
                return
            if bid_base.startswith("pick_pack_"):
                try:
                    idx = int(bid_base.split("_", 2)[-1])
                    self._select_pack_by_index(idx)
                except Exception:
                    pass
                return
            if bid_base == "name_ok":
                self._apply_new_name()
                return
            if bid_base == "name_cancel":
                self.menu_state = "root"
                self._render_menu()
                return
            return
        # 游戏内按钮
        if bid == "btn_end":
            await self._do_command("end")
            return
        if bid == "btn_back":
            await self._do_command("b")
            return
        bid_base = bid.split("__", 1)[0]
        if bid_base.startswith("m_"):
            idx = int(bid_base.split("_", 1)[1]) - 1
            self.sel_minion = None if self.sel_minion == idx else idx
            self._render_board()
            return
        if bid_base.startswith("e_"):
            eidx = int(bid_base.split("_", 1)[1]) - 1
            if self.sel_minion is None:
                return
            await self._do_command(f"a m{self.sel_minion+1} e{eidx+1}")
            self.sel_minion = None
            return
        if bid_base.startswith("r_"):
            ridx = int(bid_base.split("_", 1)[1]) - 1
            await self._do_command(f"t r{ridx+1}")
            return
        if bid_base.startswith("i_"):
            iidx = int(bid_base.split("_", 1)[1]) - 1
            inv = self.controller.game.player.inventory if self.controller else None
            if not inv or not (0 <= iidx < len(inv.slots)):
                return
            it = inv.slots[iidx].item
            if self.sel_minion is not None and isinstance(it, (WeaponItem, ArmorItem, ShieldItem)):
                await self._do_command(f"eq i{iidx+1} m{self.sel_minion+1}")
                self.sel_minion = None
            return

    async def _do_command(self, cmd: str) -> None:
        try:
            if not self.controller:
                return
            out_lines, _ = self.controller._process_command(cmd)
            if out_lines:
                self._append_info("\n".join(out_lines))
            logs = getattr(self.controller.game, 'pop_logs', None)
            if callable(logs):
                for line in logs():
                    self._append_log(line)
        except Exception as e:
            self._append_info(C.error(f"指令失败: {e}"))
        finally:
            self._refresh_all()

    # 菜单/模式
    def _enter_menu(self) -> None:
        self.mode = "menu"
        if self.log_panel:
            self.log_panel.display = False
        if self.info_panel:
            self.info_panel.display = False
        self._menu_load_data()
        self._set_scene_header()
        self._render_menu()

    def _start_game(self, initial_scene: Optional[str]) -> None:
        self.mode = "game"
        self._pending_initial_scene = initial_scene
        self._ensure_controller(reset=True)
        if self.log_panel:
            self.log_panel.display = True
        if self.info_panel:
            self.info_panel.display = True
        self.sel_minion = None
        self._refresh_all()

    def _render_menu(self) -> None:
        if not self.board:
            return
        self._epoch += 1
        _clear_container(self.board)
        self.board.mount(Label("主菜单", classes="sec_title"))
        if isinstance(self.cfg, dict):
            pack_id = self.cfg.get('last_pack', '')
            scene = self.cfg.get('last_scene', 'default_scene.json')
            label = (pack_id + '/' if pack_id else '') + scene
            self.board.mount(Label(f"玩家: {self.cfg.get('name','玩家')}", classes="hint"))
            self.board.mount(Label(f"场景: {label}", classes="hint"))
        if self.menu_state == "root":
            ep = self._epoch
            self.board.mount(Button("开始游戏", id=f"menu_start__{ep}", classes="item tight"))
            self.board.mount(Button("修改玩家名称", id=f"menu_edit_name__{ep}", classes="item tight"))
            self.board.mount(Button("选择地图组", id=f"menu_choose_pack__{ep}", classes="item tight"))
            self.board.mount(Button("重新载入场景列表", id=f"menu_reload__{ep}", classes="item tight"))
            self.board.mount(Button("退出", id=f"menu_quit__{ep}", classes="item tight"))
        elif self.menu_state == "choose_pack":
            self.board.mount(Label("选择地图组", classes="sec_title"))
            pack_ids = list(self.packs.keys()) if isinstance(self.packs, dict) else []
            for i, pid in enumerate(pack_ids, 1):
                pname = self.packs[pid].get('name', pid)
                txt = f"{i}. {pname} ({'基础' if pid=='' else pid})"
                self.board.mount(Button(txt, id=f"pick_pack_{i}__{self._epoch}", classes="item tight"))
            self.board.mount(Button("返回主菜单", id=f"menu_back__{self._epoch}", classes="item tight"))
        elif self.menu_state == "edit_name":
            self.board.mount(Label("修改玩家名称", classes="sec_title"))
            self.name_input = Input(placeholder="输入新名称")
            self.board.mount(self.name_input)
            self.board.mount(Button("确定", id=f"name_ok__{self._epoch}", classes="item tight"))
            self.board.mount(Button("取消", id=f"name_cancel__{self._epoch}", classes="item tight"))

    def _ensure_controller(self, reset: bool = False) -> None:
        if self.controller is None or reset:
            self.controller = SimplePvEController(self._player_name, self._pending_initial_scene)

    # 菜单辅助
    def _menu_load_data(self, force_reload: bool = False) -> None:
        if callable(load_config) and (force_reload or self.cfg is None):
            try:
                self.cfg = load_config()
                self._player_name = self.cfg.get('name', self._player_name)
            except Exception:
                self.cfg = {'name': self._player_name, 'last_pack': '', 'last_scene': 'default_scene.json'}
        if callable(discover_packs) and (force_reload or self.packs is None):
            try:
                self.packs = discover_packs()
            except Exception:
                self.packs = {}

    def _menu_start_game(self) -> None:
        self._menu_load_data()
        pack_id = (self.cfg or {}).get('last_pack', '') if isinstance(self.cfg, dict) else ''
        scene = (self.cfg or {}).get('last_scene', 'default_scene.json') if isinstance(self.cfg, dict) else 'default_scene.json'
        pack = (self.packs or {}).get(pack_id) if isinstance(self.packs, dict) else None
        mains = (pack or {}).get('mains', [])
        if scene not in mains and mains:
            try:
                scene = _pick_default_main(mains) if callable(_pick_default_main) else mains[0]
            except Exception:
                scene = mains[0]
            if isinstance(self.cfg, dict):
                self.cfg['last_scene'] = scene
                if callable(save_config):
                    try:
                        save_config(self.cfg)
                    except Exception:
                        pass
        scene_path = (pack_id + '/' if pack_id else '') + scene
        self._start_game(initial_scene=scene_path)

    def _select_pack_by_index(self, idx: int) -> None:
        self._menu_load_data()
        pack_ids = list(self.packs.keys()) if isinstance(self.packs, dict) else []
        if not (1 <= idx <= len(pack_ids)):
            return
        pid = pack_ids[idx - 1]
        pack = self.packs[pid]
        mains = pack.get('mains', [])
        chosen = None
        if mains:
            try:
                chosen = _pick_default_main(mains) if callable(_pick_default_main) else mains[0]
            except Exception:
                chosen = mains[0]
        else:
            subs = pack.get('subs', [])
            chosen = subs[0] if subs else 'default_scene.json'
        if isinstance(self.cfg, dict):
            self.cfg['last_pack'] = pid
            self.cfg['last_scene'] = chosen
            if callable(save_config):
                try:
                    save_config(self.cfg)
                except Exception:
                    pass
        self.menu_state = "root"
        self._render_menu()

    def _apply_new_name(self) -> None:
        new_name = (self.name_input.value if self.name_input else "").strip()
        if new_name:
            self._player_name = new_name
            if isinstance(self.cfg, dict):
                self.cfg['name'] = new_name
                if callable(save_config):
                    try:
                        save_config(self.cfg)
                    except Exception:
                        pass
        self.menu_state = "root"
        self._render_menu()


def run_textual(player_name: Optional[str] = None, initial_scene: Optional[str] = None) -> None:
    GameTextualApp(player_name=player_name, initial_scene=initial_scene).run()
