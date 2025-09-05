from __future__ import annotations

from typing import Optional, Any

from .qt_compat import QtWidgets  # type: ignore

from src.game_modes.pve_controller import SimplePvEController
from src.ui.targeting.fsm import TargetingEngine
from src import settings as S
from src import settings as S


class GameQtApp:
    """Thin application wrapper mirroring Tk app responsibilities.

    - Owns controller and top-level selection/targeting state placeholders
    - Provides `_send` to normalize commands compatible with the controller
    - Hosts references used by views (e.g., selected indexes, highlight styles)
    """

    def __init__(self, player_name: str = "玩家", initial_scene: Optional[str] = None):
        self.player_name = player_name
        self.initial_scene = initial_scene

        # Controller and game
        self.controller = None  # type: Optional[SimplePvEController]

        # Selection/target state (kept compatible with Tk app naming)
        self.selected_member_index = None  # type: Optional[int]
        self.selected_enemy_index = None   # type: Optional[int]
        self.selected_skill_name = None    # type: Optional[str]

        # Card size baseline (closer to Tk app defaults)
        # Keep readable while avoiding over-wide cards breaking compact grid
        self.CARD_W = 180
        self.CARD_H = 100

        # Highlight palette defaults (will be overridden by settings)
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

        # Apply shared settings (console colors, UI dims/palettes, stamina/hp/ops configs)
        try:
            S.apply_console_theme()
            S.apply_to_tk_app(self)
        except Exception:
            pass

        # Root window
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

        # Apply shared settings (console theme + UI params same as Tk)
        try:
            S.apply_console_theme()
            S.apply_to_tk_app(self)
        except Exception:
            pass

        # Targeting engine (shared with Tk semantics)
        self.target_engine = TargetingEngine(self)

    # --- selection helpers (semantics parity) ---
    def begin_skill(self, m_index: int, name: str):
        self.selected_member_index = m_index
        self.selected_skill_name = name
        src = f"m{m_index}"
        need_exec = self.target_engine.begin(src, name)
        if need_exec:
            out = self._send(f"skill {name} {src}")
            self.after_cmd(out)
            self.clear_selection()
            return
        # else: let UI highlight candidates and show popup

    def confirm_skill(self):
        if not self.selected_member_index:
            return
        src = f"m{self.selected_member_index}"
        name = self.selected_skill_name or 'attack'
        selected = []
        if getattr(self, 'target_engine', None) and self.target_engine.is_ready():
            selected = self.target_engine.get_selected()
        if name in (None, 'attack') and selected:
            out = self._send(f"a {src} {selected[0]}")
        else:
            parts = ["skill", name or '', src] + selected
            out = self._send(" ".join([p for p in parts if p]))
        self.after_cmd(out)
        self.clear_selection()

    def cancel_skill(self):
        self.clear_selection()

    def toggle_token(self, tok: str):
        te = getattr(self, 'target_engine', None)
        if not te or not te.ctx:
            return
        if tok in te.ctx.selected:
            te.unpick(tok)
        else:
            te.pick(tok)

    def clear_selection(self):
        self.selected_skill_name = None
        self.selected_member_index = None
        self.selected_enemy_index = None
        try:
            self.target_engine.reset()
        except Exception:
            pass

    # --- equipment slot click bridge (used by CardWidget) ---
    def _slot_click(self, m_index: int, slot_key: str, item):
        # mirror tk: if no item -> open equip dialog; else ask to unequip/replace (simplified)
        from .dialogs.equipment_dialog import EquipmentDialog
        if item is None:
            # open equip picker
            try:
                text = self.controller._section_inventory() if self.controller else ''
                items = []
                for line in (text or '').splitlines():
                    s = (line or '').strip().rstrip()
                    if not s:
                        continue
                    if s.endswith('):') or s.endswith(':'):
                        continue
                    items.append(s)
            except Exception:
                items = []
            dlg = EquipmentDialog(None, items)
            idx = dlg.get_result()
            if idx is None:
                return
            token = f"m{m_index}"
            out = self._send(f"eq i{idx} {token}")
            self.after_cmd(out)
            return
        # has item -> unequip；若左手为双手武器且点击右手，映射为卸下左手（与 Tk 行为一致）
        token = f"m{m_index}"
        effective = slot_key
        try:
            board = self.controller.game.player.board if self.controller else []
            m = board[m_index - 1] if (board and 0 <= m_index - 1 < len(board)) else None
            eq = getattr(m, 'equipment', None)
            if slot_key == 'right' and eq and getattr(eq, 'left_hand', None) and getattr(eq.left_hand, 'is_two_handed', False):
                effective = 'left'
        except Exception:
            pass
        slot = {'left': 'left', 'right': 'right', 'armor': 'armor'}.get(effective, effective)
        out = self._send(f"uneq {token} {slot}")
        self.after_cmd(out)

    # --- after command ---
    def after_cmd(self, _out):
        # Refresh main window if available and keep selection highlights reasonable
        try:
            # Let main window rerender
            from .main_window import MainWindow  # local import
            # Find top window and call refresh
            for w in self.app.topLevelWidgets():
                if isinstance(w, MainWindow):
                    w.refresh_all()
                    break
        except Exception:
            pass
        # Append controller info/history to log if available
        try:
            win = getattr(self, '_window_ref', None)
            if win and hasattr(self.controller, 'info'):
                infos = list(getattr(self.controller, 'info', []) or [])
                if infos:
                    for it in infos:
                        try:
                            win.log.append(it)
                        except Exception:
                            pass
        except Exception:
            pass

    # --- scene overlay bridge (parity to Tk) ---
    def _show_scene_transition(self):
        try:
            win = getattr(self, '_window_ref', None)
            if win:
                win.show_scene_overlay()
        except Exception:
            pass

    def _hide_scene_transition(self):
        try:
            win = getattr(self, '_window_ref', None)
            if win:
                win.hide_scene_overlay()
        except Exception:
            pass

    # --- controller lifecycle ---
    def start_game(self) -> None:
        if self.controller is None:
            self.controller = SimplePvEController(player_name=self.player_name, initial_scene=self.initial_scene)

    # --- command bridge (compatible mapping) ---
    def _send(self, cmd: str) -> Any:
        if not self.controller:
            return []
        parts = (cmd or '').split()
        if not parts:
            return []
        alias = {
            'attack': 'a', 'atk': 'a', 'a': 'a',
            'equip': 'equip', 'eq': 'equip',
            'unequip': 'unequip', 'uneq': 'unequip',
            'take': 'take', 't': 'take',
            'use': 'use', 'u': 'use',
            'craft': 'craft', 'c': 'craft',
            'end': 'end',
            'back': 'back', 'b': 'back',
            'skill': 'skill',
            'inv': 'i', 'i': 'i',
            'moveeq': 'moveeq',
            's': 's',
        }
        mapped = alias.get(parts[0].lower(), parts[0].lower())
        mapped_cmd = ' '.join([mapped] + parts[1:])
        return self.controller._process_command(mapped_cmd)


