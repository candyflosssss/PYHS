from __future__ import annotations

from typing import Optional

from ..qt_compat import QtWidgets, QtCore
from src import app_config as CFG
import json


class OperationsPopup(QtWidgets.QFrame):
    """Floating operations popup near a selected ally card.

    Features:
    - Attack button (disabled by stamina)
    - Skill buttons (from member.skills and equipment active skills)
    - Target area if targeting is active
    - Confirm/Cancel
    """

    def __init__(self, app_ctx, member_index: int):
        flag = QtCore.Qt.WindowType.Popup
        super().__init__(flags=flag)
        self.app_ctx = app_ctx
        self.member_index = member_index
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { background: white; border: 1px solid #bbb; }")
        self.setWindowTitle("操作")

        self.v = QtWidgets.QVBoxLayout(self)
        self.v.setContentsMargins(8, 8, 8, 8)
        self.v.setSpacing(6)

        # Title
        name = self._member_name()
        self.v.addWidget(QtWidgets.QLabel(name))

        # Buttons row
        row = QtWidgets.QHBoxLayout()
        self.v.addLayout(row)
        atk_btn = QtWidgets.QPushButton("攻击")
        atk_btn.clicked.connect(lambda: self._begin_skill('attack'))
        if not self._has_stamina_for('attack', cost_default=1):
            atk_btn.setDisabled(True)
        row.addWidget(atk_btn)

        # Skills
        skills = self._collect_skills()
        if skills:
            self.v.addWidget(QtWidgets.QLabel("技能:"))
            srow = QtWidgets.QHBoxLayout()
            self.v.addLayout(srow)
            for sid, label in skills:
                b = QtWidgets.QPushButton(label)
                if not self._has_stamina_for(sid, cost_default=1):
                    b.setDisabled(True)
                b.clicked.connect(lambda _=False, s=sid: self._begin_skill(s))
                srow.addWidget(b)

        # Target area
        self._target_wrap = QtWidgets.QWidget()
        self._target_lay = QtWidgets.QHBoxLayout(self._target_wrap)
        self._target_lay.setContentsMargins(0, 0, 0, 0)
        self._target_lay.setSpacing(4)
        self.v.addWidget(self._target_wrap)
        self._render_targets()

    # 装备相关操作已迁出至角色卡装备栏/对话框，此处不再提供装备区。

        # Confirm/Cancel
        ctrl = QtWidgets.QHBoxLayout()
        self.v.addLayout(ctrl)
        self.btn_ok = QtWidgets.QPushButton("确定")
        self.btn_cancel = QtWidgets.QPushButton("取消")
        self.btn_ok.clicked.connect(self._confirm)
        self.btn_cancel.clicked.connect(self._cancel)
        ctrl.addWidget(self.btn_ok)
        ctrl.addWidget(self.btn_cancel)
        self._refresh_confirm_state()

    # --- public ---
    def show_at_widget(self, anchor: QtWidgets.QWidget):
        g = anchor.mapToGlobal(anchor.rect().topRight())
        try:
            cfg = getattr(self.app_ctx, '_ops_popup_cfg', {}) or {}
            dx, dy = tuple(cfg.get('offset', [4, 0]) or [4, 0])
        except Exception:
            dx, dy = 4, 0
        self.move(g.x() + int(dx), g.y() + int(dy))
        self.show()

    # --- internals ---
    def _member_name(self) -> str:
        try:
            board = self.app_ctx.controller.game.player.board
            m = board[self.member_index - 1]
            return getattr(m, 'name', f"m{self.member_index}")
        except Exception:
            return f"m{self.member_index}"

    def _collect_skills(self):
        try:
            board = self.app_ctx.controller.game.player.board
            m = board[self.member_index - 1]
            skills = list(getattr(m, 'skills', []) or [])
            eq = getattr(m, 'equipment', None)
            for it in (getattr(eq, 'left_hand', None), getattr(eq, 'right_hand', None), getattr(eq, 'armor', None)):
                if it and getattr(it, 'active_skills', None):
                    for sid in it.active_skills:
                        if sid and sid not in skills:
                            skills.append(sid)
        except Exception:
            skills = []
        # map to (sid, label)
        catalog = self._load_skill_catalog()
        out = []
        for sk in skills:
            sid = sk.get('id') if isinstance(sk, dict) else sk
            label = None
            rec = catalog.get(sid) if sid else None
            if isinstance(sk, dict):
                label = sk.get('label') or sk.get('name')
            if rec and not label:
                label = rec.get('name_cn') or rec.get('name_en') or sid
            out.append((sid or label or str(sk), label or sid or str(sk)))
        return out

    def _load_skill_catalog(self):
        try:
            p = CFG.skills_catalog_path()
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get('skills'), list):
                return {rec.get('id'): rec for rec in data['skills'] if isinstance(rec, dict) and rec.get('id')}
        except Exception:
            return {}
        return {}

    def _has_stamina_for(self, sid: str, cost_default: int = 1) -> bool:
        try:
            from src import settings as S
            cost = int(S.get_skill_cost(sid, cost_default))
            board = self.app_ctx.controller.game.player.board
            m = board[self.member_index - 1]
            return int(getattr(m, 'stamina', 0)) >= cost
        except Exception:
            return True

    def _begin_skill(self, name: str):
        self.app_ctx.begin_skill(self.member_index, name)
        self._render_targets()
        self._refresh_confirm_state()

    def _render_targets(self):
        # clear
        while self._target_lay.count():
            item = self._target_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        te = getattr(self.app_ctx, 'target_engine', None)
        ctx = getattr(te, 'ctx', None) if te else None
        if not ctx or ctx.state not in ('Selecting','Confirmable'):
            return
        lab = QtWidgets.QLabel("目标:")
        self._target_lay.addWidget(lab)
        for tok in (ctx.candidates or []):
            btn = QtWidgets.QPushButton(tok)
            btn.setCheckable(True)
            btn.setChecked(tok in (ctx.selected or set()))
            btn.clicked.connect(lambda _=False, t=tok: self._toggle(t))
            self._target_lay.addWidget(btn)

    def _toggle(self, tok: str):
        self.app_ctx.toggle_token(tok)
        self._render_targets()
        self._refresh_confirm_state()

    def _refresh_confirm_state(self):
        te = getattr(self.app_ctx, 'target_engine', None)
        ready = te.is_ready() if te else False
        self.btn_ok.setEnabled(ready)

    def _confirm(self):
        self.app_ctx.confirm_skill()
        self.close()

    def _cancel(self):
        self.app_ctx.cancel_skill()
        self.close()

    #（移除装备弹窗与卸下入口）


