from __future__ import annotations

from typing import Any

from ..qt_compat import QtWidgets, QtCore

try:
    Signal = QtCore.pyqtSignal  # PyQt5/6
except Exception:  # pragma: no cover
    Signal = None  # type: ignore


class CardWidget(QtWidgets.QFrame):
    """Character card widget replicating Tk card layout.

    - name (top), stats (ATK/AC), stamina capsules, HP bar, equipment slots (left/right/armor)
    - exposes refresh(model) to update visuals
    - on ally: equipment buttons enabled with click callbacks; on enemy: disabled
    """

    clicked = Signal() if 'Signal' in globals() and Signal else None  # type: ignore

    def __init__(self, app_ctx, model: Any, index1: int, *, is_enemy: bool = False):
        super().__init__()
        self.app_ctx = app_ctx
        self.model = model
        self.index1 = index1
        self.is_enemy = is_enemy

        # Frame style/size (host view will set fixed size)
        try:
            shape = QtWidgets.QFrame.Shape.NoFrame  # PyQt6
        except Exception:
            shape = QtWidgets.QFrame.NoFrame  # PyQt5
        self.setFrameShape(shape)
        self.apply_default_style()

        # Layout
        root = QtWidgets.QGridLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setHorizontalSpacing(8)
        root.setVerticalSpacing(6)
        try:
            # Make left (info) and right (equipment) columns take half width each
            root.setColumnStretch(0, 1)
            root.setColumnStretch(1, 1)
        except Exception:
            pass

        # Name
        self.lbl_name = QtWidgets.QLabel(self._name_of(model))
        self.lbl_name.setStyleSheet("font-weight:700; font-size:13px;")
        self.lbl_name.setMinimumHeight(20)
        root.addWidget(self.lbl_name, 0, 0, 1, 1)

        # Stats (ATK/AC)
        stats = QtWidgets.QVBoxLayout()
        row_atk = QtWidgets.QHBoxLayout()
        self.lbl_atk = QtWidgets.QLabel("0")
        try:
            atk_col = (getattr(self.app_ctx, '_stats_colors', {}) or {}).get('atk', '#E6B800')
        except Exception:
            atk_col = '#E6B800'
        self.lbl_atk.setStyleSheet(f"color:{atk_col}; font-weight:700; font-size:12px;")
        row_atk.addWidget(QtWidgets.QLabel("ATK:"))
        row_atk.addWidget(self.lbl_atk)
        row_ac = QtWidgets.QHBoxLayout()
        self.lbl_ac = QtWidgets.QLabel("0")
        try:
            ac_col = (getattr(self.app_ctx, '_stats_colors', {}) or {}).get('ac', '#2980b9')
        except Exception:
            ac_col = '#2980b9'
        self.lbl_ac.setStyleSheet(f"color:{ac_col}; font-weight:700; font-size:12px;")
        row_ac.addWidget(QtWidgets.QLabel("AC:"))
        row_ac.addWidget(self.lbl_ac)
        stats.addLayout(row_atk)
        stats.addLayout(row_ac)
        root.addLayout(stats, 1, 0, 1, 1)

        # Equipment column (right)
        eq_col = QtWidgets.QVBoxLayout()
        self.btn_left = QtWidgets.QPushButton("左手")
        self.btn_armor = QtWidgets.QPushButton("盔甲")
        self.btn_right = QtWidgets.QPushButton("右手")
        for b in (self.btn_left, self.btn_armor, self.btn_right):
            b.setFixedHeight(22)
            b.setStyleSheet("QPushButton{font-size:11px; padding:2px 6px;}")
            eq_col.addWidget(b)
        root.addLayout(eq_col, 0, 1, 2, 1)

        # Stamina capsules (row widget to allow custom bg like Tk)
        self.stamina_row = QtWidgets.QWidget()
        self.stamina_wrap = QtWidgets.QHBoxLayout(self.stamina_row)
        self.stamina_wrap.setContentsMargins(0, 0, 0, 0)
        self.stamina_wrap.setSpacing(0)
        # Ensure left alignment consistently
        try:
            self.stamina_wrap.setAlignment(getattr(QtCore.Qt, 'AlignmentFlag', QtCore.Qt).AlignLeft)
        except Exception:
            try:
                self.stamina_wrap.setAlignment(QtCore.Qt.AlignLeft)
            except Exception:
                pass
        root.addWidget(self.stamina_row, 2, 0, 1, 2)

        # HP bar
        self.hp_bar = QtWidgets.QProgressBar()
        self.hp_bar.setTextVisible(True)
        try:
            hp_cfg = getattr(self.app_ctx, '_hp_bar_cfg', {}) or {}
            hp_h = int(hp_cfg.get('height', 14))
            hp_bg = hp_cfg.get('bg', '#e0e0e0')
            hp_fg = hp_cfg.get('fg', '#2ecc71')
            self.hp_bar.setFixedHeight(max(10, hp_h))
            self.hp_bar.setStyleSheet(
                f"QProgressBar{{border:0; background:{hp_bg}; border-radius:5px;"
                " text-align:center; padding:0px; font-size:11px;}"
                f" QProgressBar::chunk{{background:{hp_fg}; border:0; margin:0px; border-radius:5px;}}"
            )
        except Exception:
            self.hp_bar.setFixedHeight(14)
            self.hp_bar.setStyleSheet(
                "QProgressBar{border:0; background:#e0e0e0; border-radius:5px;"
                " text-align:center; padding:0px; font-size:11px;}"
                " QProgressBar::chunk{background:#2ecc71; border:0; margin:0px; border-radius:5px;}"
            )
        root.addWidget(self.hp_bar, 3, 0, 1, 2)

        # Configure buttons and clicks
        self._wire_equipment_buttons()
        try:
            self.installEventFilter(self)
            for w in (self.lbl_name, self.lbl_atk, self.lbl_ac, self.hp_bar):
                w.installEventFilter(self)
        except Exception:
            pass

        # Populate initial values
        self.refresh(model)

    def apply_default_style(self) -> None:
        # Remove extra stroke on base card; keep subtle rounded corners
        self.setStyleSheet("QFrame { background: #fafafa; border: 0; border-radius:4px; }")

    # --- helpers ---
    def _name_of(self, m: Any) -> str:
        try:
            return getattr(m, 'display_name', None) or getattr(m, 'name', None) or m.__class__.__name__
        except Exception:
            return '随从'

    def _split_atk(self, m: Any) -> tuple[int, int, int]:
        try:
            base = int(getattr(m, 'base_atk', getattr(m, 'atk', 0)) or 0)
        except Exception:
            base = 0
        try:
            eq = int(getattr(getattr(m, 'equipment', None), 'get_total_attack', lambda: 0)())
        except Exception:
            eq = 0
        return base, eq, base + eq

    def _compute_ac(self, m: Any) -> int:
        # 10 + defense + dex_mod
        defense = 0
        try:
            eq = getattr(m, 'equipment', None)
            if eq and hasattr(eq, 'get_total_defense'):
                defense = int(eq.get_total_defense())
            else:
                defense = int(getattr(m, 'defense', 0) or 0)
        except Exception:
            defense = 0
        dex_mod = 0
        try:
            dnd = getattr(m, 'dnd', None)
            attrs = (dnd or {}).get('attrs') or (dnd or {}).get('attributes') if isinstance(dnd, dict) else None
            if isinstance(attrs, dict):
                dex_raw = attrs.get('dex', attrs.get('DEX'))
                if dex_raw is not None:
                    dex_mod = (int(dex_raw) - 10) // 2
        except Exception:
            dex_mod = 0
        return int(10 + defense + dex_mod)

    def _equipment_triplet(self, m: Any):
        eq = getattr(m, 'equipment', None)
        left = getattr(eq, 'left_hand', None) if eq else None
        armor = getattr(eq, 'armor', None) if eq else None
        right_raw = getattr(eq, 'right_hand', None) if eq else None
        right = left if getattr(left, 'is_two_handed', False) else right_raw
        return left, armor, right

    def _tooltip_for_item(self, item, label: str) -> str:
        if not item:
            return f"{label}: 空槽"
        name = getattr(item, 'name', '-')
        parts = [name]
        try:
            atk = int(getattr(item, 'attack', 0) or 0)
            if atk:
                parts.append(f"+{atk} 攻")
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
        return "，".join(parts)

    def _wire_equipment_buttons(self):
        # enable/disable based on ally/enemy
        if self.is_enemy:
            for b in (self.btn_left, self.btn_armor, self.btn_right):
                b.setDisabled(True)
        else:
            self.btn_left.clicked.connect(lambda: self._slot_click('left'))
            self.btn_armor.clicked.connect(lambda: self._slot_click('armor'))
            self.btn_right.clicked.connect(lambda: self._slot_click('right'))

    def _slot_click(self, slot_key: str):
        # Read current item and delegate to app ctx slot click
        left, armor, right = self._equipment_triplet(self.model)
        item = {'left': left, 'armor': armor, 'right': right}.get(slot_key)
        try:
            if hasattr(self.app_ctx, '_slot_click'):
                self.app_ctx._slot_click(self.index1, slot_key, item)
        finally:
            # After command, main window will refresh, ensure local refresh as well
            self.refresh(self.model)

    # --- API ---
    def refresh(self, m: Any) -> None:
        self.model = m
        self.lbl_name.setText(self._name_of(m))
        base, eq, tot = self._split_atk(m)
        self.lbl_atk.setText(str(tot))
        self.lbl_ac.setText(str(self._compute_ac(m)))
        # stamina capsules (Tk semantics: bg row + rounded thin vertical bars)
        while self.stamina_wrap.count():
            item = self.stamina_wrap.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        # config from app_ctx like Tk (_stamina_cfg)
        st_cfg = getattr(self.app_ctx, '_stamina_cfg', {}) or {}
        # Remove extra background fill; keep row transparent for a cleaner look
        bgc = 'transparent'
        max_caps = int(st_cfg.get('max_caps', 6))
        colors = st_cfg.get('colors', {}) or {}
        col_on = colors.get('on', '#2ecc71')
        col_off = colors.get('off', '#e74c3c')
        try:
            cur = int(getattr(m, 'stamina', 0)); mx = int(getattr(m, 'stamina_max', cur or 1))
        except Exception:
            cur, mx = 0, 1
        show_n = min(mx, max_caps)
        # apply row background (transparent)
        self.stamina_row.setStyleSheet(f"QWidget{{background:{bgc}; border:0;}}")
        for i in range(show_n):
            seg = QtWidgets.QFrame()
            try:
                shape = QtWidgets.QFrame.Shape.NoFrame
            except Exception:
                shape = QtWidgets.QFrame.NoFrame
            seg.setFrameShape(shape)
            seg.setFixedSize(8, 16)
            color = col_on if i < cur else col_off
            seg.setStyleSheet(f"QFrame {{ background: {color}; border: 0; border-radius:4px; }}")
            self.stamina_wrap.addWidget(seg)

        # HP bar
        try:
            cur_hp = int(getattr(m, 'hp', 0)); max_hp = int(getattr(m, 'max_hp', cur_hp or 1))
        except Exception:
            cur_hp, max_hp = 0, 1
        self.hp_bar.setMaximum(max_hp)
        self.hp_bar.setValue(cur_hp)
        self.hp_bar.setFormat(f"{cur_hp}/{max_hp}")

        # Equipment buttons text and tooltip
        left, armor, right = self._equipment_triplet(m)
        # Keep button labels short to avoid crowding; put details in tooltip
        self.btn_left.setToolTip(self._tooltip_for_item(left, '左手'))
        self.btn_armor.setToolTip(self._tooltip_for_item(armor, '盔甲'))
        self.btn_right.setToolTip(self._tooltip_for_item(right, '右手'))

    # --- event filter to emit card-level click ---
    def eventFilter(self, obj, event):  # noqa: N802 (Qt signature)
        try:
            et = getattr(QtCore.QEvent, 'Type', QtCore.QEvent)
            mpress = getattr(et, 'MouseButtonPress', 2)
            if event.type() == mpress:
                # ignore equipment button clicks
                if obj in (self.btn_left, self.btn_right, self.btn_armor):
                    return False
                if hasattr(self, 'clicked') and self.clicked:
                    try:
                        self.clicked.emit()  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    return False
        except Exception:
            pass
        return super().eventFilter(obj, event)



