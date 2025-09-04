from __future__ import annotations

from typing import List, Dict, Any, Optional

from ..qt_compat import QtWidgets, QtCore  # type: ignore
from ..widgets.card import CardWidget


class BattlefieldView(QtWidgets.QWidget):
    """Mirrored battlefield: allies (left) and enemies (right), 3 columns per side.

    Minimal functional parity:
    - Show allies/enemies from controller game
    - Click selection callback to app_ctx (updates selected indexes)
    - Basic highlight via stylesheets could be layered in later
    """

    COLS = 3

    def __init__(self, app_ctx):
        super().__init__()
        self.app_ctx = app_ctx
        self._allies: List[object] = []
        self._enemies: List[object] = []
        self._ally_cards: Dict[int, QtWidgets.QFrame] = {}
        self._enemy_cards: Dict[int, QtWidgets.QFrame] = {}

        self.setContentsMargins(0, 0, 0, 0)
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(4)

        # Panels
        self.grp_allies = QtWidgets.QGroupBox("伙伴区 (点击选择 mN)")
        self.grp_enemies = QtWidgets.QGroupBox("敌人区 (点击选择 eN)")
        try:
            self.grp_allies.setFlat(False)
            self.grp_enemies.setFlat(False)
            # Subtle region borders, title on the left, small radius
            self.grp_allies.setStyleSheet(
                "QGroupBox{border:1px solid #d9d9d9; border-radius:6px; font-weight:600; margin-top:8px; padding-top:12px;}"
                " QGroupBox::title{subcontrol-origin: margin; left:8px; padding:0 4px;}"
            )
            self.grp_enemies.setStyleSheet(
                "QGroupBox{border:1px solid #d9d9d9; border-radius:6px; font-weight:600; margin-top:8px; padding-top:12px;}"
                " QGroupBox::title{subcontrol-origin: margin; left:8px; padding:0 4px;}"
            )
        except Exception:
            pass
        layout.addWidget(self.grp_allies, 0, 0)
        layout.addWidget(self.grp_enemies, 0, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 0)
        layout.setColumnStretch(2, 1)
        layout.addItem(QtWidgets.QSpacerItem(6, 1), 0, 1)
        # Wrap grids with inner content widgets so the grid can keep its minimum size
        # and align to left/right without stretching columns. This keeps cards packed
        # tightly "one next to another" like Tk.
        # Qt5/Qt6 alignment enum compatibility
        try:
            AF = QtCore.Qt.AlignmentFlag  # PyQt6
        except Exception:  # PyQt5 fallback
            AF = QtCore.Qt  # type: ignore

        self._allies_container = QtWidgets.QWidget(self.grp_allies)
        self._allies_grid = QtWidgets.QGridLayout(self._allies_container)
        self._allies_grid.setContentsMargins(0, 0, 0, 0)
        self._allies_grid.setHorizontalSpacing(4)
        self._allies_grid.setVerticalSpacing(4)
        # place container into group with right alignment (mirrored allies)
        _al_v = QtWidgets.QVBoxLayout()
        _al_v.setContentsMargins(4, 4, 4, 4)
        _al_v.addWidget(self._allies_container, 0, AF.AlignRight)
        self.grp_allies.setLayout(_al_v)

        self._enemies_container = QtWidgets.QWidget(self.grp_enemies)
        self._enemies_grid = QtWidgets.QGridLayout(self._enemies_container)
        self._enemies_grid.setContentsMargins(0, 0, 0, 0)
        self._enemies_grid.setHorizontalSpacing(4)
        self._enemies_grid.setVerticalSpacing(4)
        _en_v = QtWidgets.QVBoxLayout()
        _en_v.setContentsMargins(4, 4, 4, 4)
        _en_v.addWidget(self._enemies_container, 0, AF.AlignLeft)
        self.grp_enemies.setLayout(_en_v)

    # --- public ---
    def render_from_game(self, game):
        try:
            self._allies = list(getattr(getattr(game, 'player', None), 'board', []) or [])[:15]
        except Exception:
            self._allies = []
        try:
            self._enemies = list(getattr(game, 'enemies', []) or [])[:15]
        except Exception:
            self._enemies = []
        self._render_side(False)
        self._render_side(True)

    # --- internals ---
    def _render_side(self, is_enemy: bool):
        grid = self._enemies_grid if is_enemy else self._allies_grid
        # reset card maps for this side
        if is_enemy:
            self._enemy_cards = {}
        else:
            self._ally_cards = {}
        # clear grid
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        items = self._enemies if is_enemy else self._allies
        cols = self.COLS
        for idx, tok in enumerate(items):
            row = idx // cols
            col = idx % cols
            # mirror columns for allies (right-aligned per row)
            vis_col = col if is_enemy else (cols - 1 - col)
            card = self._create_card(tok, idx + 1, is_enemy)
            grid.addWidget(card, row, vis_col)
            if is_enemy:
                self._enemy_cards[idx + 1] = card
            else:
                self._ally_cards[idx + 1] = card

        # keep compact height; no column stretch to avoid gaps
        try:
            for c in range(self.COLS):
                grid.setColumnStretch(c, 0)
        except Exception:
            pass

    def _create_card(self, token: object, index1: int, is_enemy: bool) -> QtWidgets.QFrame:
        card = CardWidget(self.app_ctx, token, index1, is_enemy=is_enemy)
        card.setFixedSize(self.app_ctx.CARD_W, self.app_ctx.CARD_H)
        # click trigger
        if hasattr(card, 'clicked') and card.clicked:
            try:
                card.clicked.connect(lambda i=index1, enemy=is_enemy, w=card: self._on_click(i, enemy, w))  # type: ignore[attr-defined]
            except Exception:
                card.mousePressEvent = lambda e, i=index1, enemy=is_enemy, w=card: self._on_click(i, enemy, w)
        else:
            card.mousePressEvent = lambda e, i=index1, enemy=is_enemy, w=card: self._on_click(i, enemy, w)
        # optional hover trigger
        try:
            trig = (getattr(self.app_ctx, '_ops_popup_cfg', {}) or {}).get('trigger', 'click')
            if str(trig).lower() == 'hover' and not is_enemy:
                def _enter(_e=None, i=index1, w=card):
                    self._on_click(i, False, w)
                def _leave(_e=None):
                    # popup auto-hides on click outside; for hover we simply do nothing
                    pass
                card.enterEvent = _enter  # type: ignore[assignment]
                card.leaveEvent = _leave  # type: ignore[assignment]
        except Exception:
            pass
        return card

    def _on_click(self, index1: int, is_enemy: bool, widget: QtWidgets.QWidget):
        if is_enemy:
            self.app_ctx.selected_enemy_index = index1
        else:
            self.app_ctx.selected_member_index = index1
        # If ally selected, open operations popup (to be implemented later)
        try:
            if not is_enemy:
                from .operations_popup import OperationsPopup  # lazy
                pop = OperationsPopup(self.app_ctx, index1)
                pop.show_at_widget(widget)
        except Exception:
            pass

    # --- highlighting ---
    def update_highlights(self):
        """Apply candidate/selected highlights based on TargetingEngine context."""
        # reset
        def style_reset(card: QtWidgets.QFrame):
            if isinstance(card, CardWidget):
                card.apply_default_style()
            else:
                card.setStyleSheet("QFrame { background: #fafafa; border: 1px solid #cfcfcf; border-radius:4px; }")
        for m in list(self._ally_cards.values()):
            style_reset(m)
        for e in list(self._enemy_cards.values()):
            style_reset(e)

        te = getattr(self.app_ctx, 'target_engine', None)
        ctx = getattr(te, 'ctx', None) if te else None
        if not ctx:
            return
        cand = set(ctx.candidates or [])
        sel = set(ctx.selected or [])
        def apply(card: QtWidgets.QFrame, border: str, bg: str):
            card.setStyleSheet(f"QFrame {{ background: {bg}; border: 2px solid {border}; }}")
        # enemies
        for idx, card in list(self._enemy_cards.items()):
            tok = f"e{idx}"
            if tok in sel:
                apply(card, self.app_ctx.HL['sel_enemy_border'], self.app_ctx.HL['sel_enemy_bg'])
            elif tok in cand:
                apply(card, self.app_ctx.HL['cand_enemy_border'], self.app_ctx.HL['cand_enemy_bg'])
        # allies
        for idx, card in list(self._ally_cards.items()):
            tok = f"m{idx}"
            if tok in sel:
                apply(card, self.app_ctx.HL['sel_ally_border'], self.app_ctx.HL['sel_ally_bg'])
            elif tok in cand:
                apply(card, self.app_ctx.HL['cand_ally_border'], self.app_ctx.HL['cand_ally_bg'])

    # --- targeted refresh & feedback ---
    def refresh_model(self, model: object, *, is_enemy: bool):
        items = self._enemies if is_enemy else self._allies
        try:
            idx = items.index(model) + 1
        except ValueError:
            return
        card = (self._enemy_cards if is_enemy else self._ally_cards).get(idx)
        if isinstance(card, CardWidget):
            card.refresh(model)

    def flash_card(self, model: object, *, is_enemy: bool, kind: str = 'damage'):
        items = self._enemies if is_enemy else self._allies
        try:
            idx = items.index(model) + 1
        except ValueError:
            return
        card = (self._enemy_cards if is_enemy else self._ally_cards).get(idx)
        if not card:
            return
        color = '#c0392b' if kind == 'damage' else '#27ae60'
        try:
            orig = card.styleSheet()
        except Exception:
            orig = ''
        card.setStyleSheet(f"QFrame {{ background: {color}; border: 2px solid #000; }}")
        try:
            QtCore.QTimer.singleShot(180, lambda: card.setStyleSheet(orig))
        except Exception:
            pass

    def _stats_text(self, token: object) -> str:
        # no-op; stats are rendered in CardWidget
        return ""


