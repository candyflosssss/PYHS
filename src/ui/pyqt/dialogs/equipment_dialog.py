from __future__ import annotations

from typing import Optional, List

from ..qt_compat import QtWidgets, QtCore, QtGui  # type: ignore


class _GridCanvas(QtWidgets.QWidget):
    """带方格背景的容器，用于呈现背包网格。

    - cell: 每个格子的像素尺寸（正方形）。
    - bg: 背景填充颜色。
    - line: 网格线颜色。
    子控件（按钮）会叠加在方格背景之上。
    """
    def __init__(self, cell: int = 72, bg: str = "#f9f9fb", line: str = "#e5e7eb", parent=None):
        super().__init__(parent)
        self._cell = int(max(16, cell))
        self._bg = str(bg)
        self._line = str(line)

    def paintEvent(self, event):
        w = self.width(); h = self.height()
        p = QtGui.QPainter(self)
        try:
            p.fillRect(self.rect(), QtGui.QColor(self._bg))
            pen = QtGui.QPen(QtGui.QColor(self._line))
            pen.setWidth(1)
            p.setPen(pen)
            step = self._cell
            # 竖线
            x = 0
            while x <= w:
                p.drawLine(x, 0, x, h)
                x += step
            # 横线
            y = 0
            while y <= h:
                p.drawLine(0, y, w, y)
                y += step
        finally:
            p.end()


class EquipmentDialog(QtWidgets.QDialog):
    """装备选择对话框

    - 左侧：槽位信息与“卸下”按钮（操作后不关闭）。
    - 右侧：背包中“所有装备类物品”的滚动网格；点击即装备到合适槽位，不关闭。
    - 提示：悬浮展示名称、攻防、技能与描述。

    确定：返回最近一次点击的背包 1-based 索引；取消或未选择返回 None。
    """

    def __init__(self, app_ctx, parent, m_index: int, slot_key: str):
        super().__init__(parent)
        self.app_ctx = app_ctx
        self.m_index = m_index
        self.slot_key = slot_key  # 'left'|'right'|'armor'
        self.setWindowTitle("装备管理：点击右侧任意装备自动穿戴")
        self.setModal(True)
        # 状态
        self._index_map: List[int] = []
        self._chosen: Optional[int] = None
        self._selected_btn: Optional[QtWidgets.QPushButton] = None
        self._btn_by_idx: dict[int, QtWidgets.QPushButton] = {}
        # 左侧槽位与按钮引用
        self._lbl_lh: Optional[QtWidgets.QLabel] = None
        self._lbl_ar: Optional[QtWidgets.QLabel] = None
        self._lbl_rh: Optional[QtWidgets.QLabel] = None
        self._btn_ul: Optional[QtWidgets.QPushButton] = None
        self._btn_ua: Optional[QtWidgets.QPushButton] = None
        self._btn_ur: Optional[QtWidgets.QPushButton] = None
        # 右侧区域引用
        self._right_scroll: Optional[QtWidgets.QScrollArea] = None
        self._grid_wrap: Optional[QtWidgets.QWidget] = None
        self._grid_layout: Optional[QtWidgets.QGridLayout] = None
        # 构建 UI
        self._build_ui()

    # --- helpers ---
    def _member_and_eq(self):
        try:
            m = self.app_ctx.controller.game.player.board[self.m_index - 1]
            return m, getattr(m, 'equipment', None)
        except Exception:
            return None, None

    def _fits_slot_and_ok(self, it, eq) -> bool:
        try:
            from src.systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
        except Exception:
            WeaponItem = ArmorItem = ShieldItem = tuple()  # type: ignore
        s = self.slot_key
        if s == 'armor':
            return isinstance(it, ArmorItem)
        if s == 'left':
            if isinstance(it, ShieldItem):
                return not (eq and getattr(eq, 'left_hand', None) and getattr(eq.left_hand, 'is_two_handed', False))
            if isinstance(it, WeaponItem):
                if getattr(it, 'is_two_handed', False):
                    return True
                return getattr(it, 'slot_type', '') == 'left_hand' and not (eq and getattr(eq, 'left_hand', None) and getattr(eq.left_hand, 'is_two_handed', False))
            return False
        if s == 'right':
            if eq and getattr(eq, 'left_hand', None) and getattr(eq.left_hand, 'is_two_handed', False):
                return False
            return isinstance(it, WeaponItem) and not getattr(it, 'is_two_handed', False) and getattr(it, 'slot_type', '') == 'right_hand'
        return False

    def _fmt_tip(self, it) -> str:
        if not it:
            return "-"
        lines: List[str] = [getattr(it, 'name', str(it))]
        try:
            atk = int(getattr(it, 'attack', 0) or 0)
        except Exception:
            atk = 0
        try:
            df = int(getattr(it, 'defense', 0) or 0)
        except Exception:
            df = 0
        if atk or df:
            lines.append(f"攻击: {atk}  防御: {df}")
        try:
            acts = list(getattr(it, 'active_skills', []) or [])
            if acts:
                lines.append("主动技能: " + ", ".join(acts))
        except Exception:
            pass
        try:
            pas = dict(getattr(it, 'passives', {}) or {})
            if pas:
                lines.append("被动: " + ", ".join(f"{k}={v}" for k, v in pas.items()))
        except Exception:
            pass
        try:
            desc = getattr(it, 'description', '') or ''
            if desc:
                lines.append(desc)
        except Exception:
            pass
        return "\n".join(lines)

    def _rarity_color(self, rarity: str) -> str:
        # 优先使用 settings 中的稀有度配色
        pal = ((getattr(self.app_ctx, '_equipment_cfg', {}) or {}).get('rarity_colors', {}) or {})
        if not pal:
            pal = {
                'common': '#BDBDBD',      # 灰
                'uncommon': '#4CAF50',    # 绿
                'rare': '#2196F3',        # 蓝
                'epic': '#9C27B0',        # 紫
                'legendary': '#FF9800',   # 橙
            }
        return pal.get((rarity or 'common').lower(), '#BDBDBD')

    def _unequip(self, slot: str):
        try:
            token = f"m{self.m_index}"
            out = self.app_ctx._send(f"uneq {token} {slot}")
            # 仅刷新主窗口，不依赖父级控件存在性
            self.app_ctx.after_cmd(out)
        except Exception:
            pass
        # 不自动关闭；刷新
        self._refresh_left()
        self._refresh_right_grid()
        # 父级可能是 MainWindow；若是卡片，刷新由 after_cmd 统一处理

    def _choose(self, idx1: int, btn: QtWidgets.QPushButton):
        """点击背包物品：立即执行装备，刷新左右两侧与角色卡，窗口不关闭。"""
        self._chosen = idx1  # 记录最近选择
        # 执行装备
        try:
            controller = getattr(self.app_ctx, 'controller', None)
            game = getattr(controller, 'game', None) if controller else None
            player = getattr(game, 'player', None) if game else None
            inv = getattr(player, 'inventory', None) if player else None
            if inv and getattr(inv, 'slots', None) and 1 <= idx1 <= len(inv.slots):
                item = inv.slots[idx1 - 1].item
                name = getattr(item, 'name', None)
                # 目标随从
                member = None
                try:
                    member = player.board[self.m_index - 1]
                except Exception:
                    member = None
                if name and member is not None:
                    inv.use_item(name, 1, player=player, target=member)
                    # 全局刷新（主窗口/战场/背包）
                    try:
                        self.app_ctx.after_cmd([])
                    except Exception:
                        pass
        except Exception:
            pass
        # UI：高亮与刷新
        try:
            if self._selected_btn is not None:
                self._selected_btn.setProperty('selected', False)
                self._apply_btn_style(self._selected_btn)
        except Exception:
            pass
        self._selected_btn = btn
        try:
            btn.setProperty('selected', True)
            self._apply_btn_style(btn)
        except Exception:
            pass
        self._refresh_left()
        self._refresh_right_grid()
        # 父级刷新由 after_cmd 负责

    def get_result(self) -> Optional[int]:
        ok = (self.exec() == QtWidgets.QDialog.DialogCode.Accepted)
        return self._chosen if ok else None

    # 防止回车键在子按钮聚焦时意外触发 Accept
    def keyPressEvent(self, event) -> None:
        # 仅允许在 OK/Cancel 按钮区域获得焦点时使用回车关闭对话框
        from ..qt_compat import QtCore
        key = event.key()
        if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            fw = self.focusWidget()
            allow = isinstance(fw, QtWidgets.QDialogButtonBox) or (
                isinstance(fw, QtWidgets.QPushButton) and isinstance(fw.parent(), QtWidgets.QDialogButtonBox)
            )
            if not allow:
                event.accept()  # 吞掉回车，避免触发默认的 QDialog.Accepted
                return
        super().keyPressEvent(event)

    # --- UI ---
    def _build_ui(self) -> None:
        v = QtWidgets.QVBoxLayout(self)
        # 读取 settings 中的装备窗口配置
        cfg = getattr(self.app_ctx, '_equipment_cfg', {}) or {}
        dcfg = dict(cfg.get('dialog', {}) or {})
        gcfg = dict(cfg.get('grid', {}) or {})
        rcfg = dict(cfg.get('rarity_colors', {}) or {})
        try:
            w = int(dcfg.get('width', 640))
            h = int(dcfg.get('height', 520))
            # 缩小一半宽度（可在用户配置中直接设定更精确的值覆盖）
            self.setFixedSize(max(320, w // 2), h)
        except Exception:
            pass
        # 垂直布局：上（槽位/卸下），下（背包网格）

        # 上：槽位与卸下
        top = QtWidgets.QWidget()
        l = QtWidgets.QGridLayout(top)
        _m, eq = self._member_and_eq()

        def label_of(x):
            if not x:
                return "-"
            parts = []
            if getattr(x, 'attack', 0):
                parts.append(f"+{int(getattr(x, 'attack', 0))}攻")
            if getattr(x, 'defense', 0):
                parts.append(f"+{int(getattr(x, 'defense', 0))}防")
            flags = []
            if getattr(x, 'is_two_handed', False):
                flags.append('双手')
            flag = (" [" + ", ".join(flags) + "]") if flags else ""
            return f"{getattr(x, 'name', '-')} {' '.join(parts)}{flag}"

        lh = getattr(eq, 'left_hand', None) if eq else None
        ar = getattr(eq, 'armor', None) if eq else None
        rh = getattr(eq, 'right_hand', None) if eq else None
        # 左手
        l.addWidget(QtWidgets.QLabel("左手:"), 0, 0)
        self._lbl_lh = QtWidgets.QLabel(label_of(lh))
        self._lbl_lh.setToolTip(self._fmt_tip(lh) if lh else "左手: -")
        l.addWidget(self._lbl_lh, 0, 1)
        self._btn_ul = QtWidgets.QPushButton("卸下")
        # 防止作为对话框默认按钮触发 Accept
        try:
            self._btn_ul.setAutoDefault(False)
            self._btn_ul.setDefault(False)
            self._btn_ul.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        except Exception:
            pass
        self._btn_ul.setDisabled(lh is None)
        self._btn_ul.clicked.connect(lambda: self._unequip('left'))
        l.addWidget(self._btn_ul, 0, 2)
        # 盔甲
        l.addWidget(QtWidgets.QLabel("盔甲:"), 1, 0)
        self._lbl_ar = QtWidgets.QLabel(label_of(ar))
        self._lbl_ar.setToolTip(self._fmt_tip(ar) if ar else "盔甲: -")
        l.addWidget(self._lbl_ar, 1, 1)
        self._btn_ua = QtWidgets.QPushButton("卸下")
        try:
            self._btn_ua.setAutoDefault(False)
            self._btn_ua.setDefault(False)
            self._btn_ua.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        except Exception:
            pass
        self._btn_ua.setDisabled(ar is None)
        self._btn_ua.clicked.connect(lambda: self._unequip('armor'))
        l.addWidget(self._btn_ua, 1, 2)
        # 右手
        l.addWidget(QtWidgets.QLabel("右手:"), 2, 0)
        self._lbl_rh = QtWidgets.QLabel(label_of(rh))
        self._lbl_rh.setToolTip(self._fmt_tip(rh) if rh else "右手: -")
        l.addWidget(self._lbl_rh, 2, 1)
        self._btn_ur = QtWidgets.QPushButton("卸下")
        try:
            self._btn_ur.setAutoDefault(False)
            self._btn_ur.setDefault(False)
            self._btn_ur.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        except Exception:
            pass
        self._btn_ur.setDisabled(rh is None)
        self._btn_ur.clicked.connect(lambda: self._unequip('right'))
        l.addWidget(self._btn_ur, 2, 2)
        v.addWidget(top)

        # 下：背包网格（滚动+方格背景）
        bottom_wrap = QtWidgets.QScrollArea()
        bottom_wrap.setWidgetResizable(True)
        try:
            bottom_wrap.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        except Exception:
            pass
        try:
            bottom_wrap.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            bottom_wrap.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        except Exception:
            pass
        # 移除默认外框并清零 viewport 边距，避免首行/首列偏移
        try:
            bottom_wrap.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            bottom_wrap.setViewportMargins(0, 0, 0, 0)
        except Exception:
            pass
        self._right_scroll = bottom_wrap
        # 用自定义网格底板提供格子背景
        grid_bg = _GridCanvas(cell=int(gcfg.get('cell', 72)), bg=str(gcfg.get('bg', '#f9f9fb')), line=str(gcfg.get('line', '#e5e7eb')))
        # 清零容器自身边距，避免与绘制的格线错位
        try:
            grid_bg.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        grid_bg.setLayout(QtWidgets.QGridLayout())
        self._grid_wrap = grid_bg
        self._grid_layout = grid_bg.layout()
        try:
            # 强制网格起点为左上角
            self._grid_layout.setOriginCorner(QtCore.Qt.Corner.TopLeftCorner)
            self._grid_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        except Exception:
            pass
        # 再次确保容器与布局无边距
        try:
            self._grid_wrap.setContentsMargins(0, 0, 0, 0)
            self._grid_layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        # 记录格子规格
        try:
            self._grid_cell = int(gcfg.get('cell', 72))
            self._grid_cols = int(gcfg.get('cols', 6))
        except Exception:
            self._grid_cell, self._grid_cols = 72, 6
        # 初始实际列数（随后根据 viewport 宽度动态调整）
        self._grid_actual_cols = self._grid_cols
        try:
            bottom_wrap.viewport().installEventFilter(self)
        except Exception:
            pass
        # 初始构建网格
        self._rebuild_right_grid()
        bottom_wrap.setWidget(grid_bg)
        v.addWidget(bottom_wrap, 1)

        # 底部按钮
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        v.addWidget(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

    def _clear_layout(self, layout: QtWidgets.QLayout):
        try:
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
                elif item.layout() is not None:
                    self._clear_layout(item.layout())
        except Exception:
            pass

    def _rebuild_right_grid(self):
        """重建右侧背包网格（显示所有装备类物品，点击即时装备）。"""
        if not self._right_scroll:
            return
        wrap = self._grid_wrap
        grid = self._grid_layout
        if wrap is None:
            wrap = QtWidgets.QWidget()
            self._grid_wrap = wrap
        if grid is None:
            grid = QtWidgets.QGridLayout(wrap)
            self._grid_layout = grid
        # 清空旧内容
        self._clear_layout(grid)
        # 紧贴方格背景，取消间距并左上对齐
        try:
            if hasattr(grid, 'setOriginCorner'):
                grid.setOriginCorner(QtCore.Qt.Corner.TopLeftCorner)
            grid.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(0)
            grid.setHorizontalSpacing(0)
            grid.setVerticalSpacing(0)
        except Exception:
            pass
        try:
            self._grid_wrap.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        # 重置索引映射
        self._index_map = []
        self._btn_by_idx = {}
        # 数据源
        inv_owner = getattr(getattr(getattr(self.app_ctx, 'controller', None), 'game', None), 'player', None)
        inv = getattr(inv_owner, 'inventory', None)
        row = col = 0
        cell = int(getattr(self, '_grid_cell', 72))
        cols = int(getattr(self, '_grid_actual_cols', getattr(self, '_grid_cols', 6)))
        total = 0
        if inv is not None:
            # 展示所有“装备类”物品，不再按槽位过滤；点击后由 use_item/装备系统决定落位
            try:
                from src.systems.inventory import EquipmentItem  # 基类
            except Exception:
                EquipmentItem = tuple()  # type: ignore
            for idx, slot in enumerate(list(getattr(inv, 'slots', []) or []), 1):
                it = getattr(slot, 'item', None)
                # 仅显示装备（武器/盾牌/盔甲），隐藏消耗品/素材
                try:
                    if not isinstance(it, EquipmentItem):
                        continue
                except Exception:
                    # 基类不可用时，退化为属性判断
                    if not hasattr(it, 'slot_type'):
                        continue
                self._index_map.append(idx)
                rarity = str(getattr(it, 'rarity', 'common') or 'common').lower()
                color = self._rarity_color(rarity)
                btn = QtWidgets.QPushButton(getattr(it, 'name', f"i{idx}"))
                # 防止物品按钮触发对话框默认 Accept
                try:
                    btn.setAutoDefault(False)
                    btn.setDefault(False)
                    btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
                except Exception:
                    pass
                btn.setToolTip(self._fmt_tip(it))
                btn.setProperty('rarity_color', color)
                self._apply_btn_style(btn)
                try:
                    btn.setFixedSize(cell, cell)
                except Exception:
                    pass
                btn.clicked.connect(lambda _=False, i_idx=idx, b=btn: self._choose(i_idx, b))
                self._btn_by_idx[idx] = btn
                grid.addWidget(btn, row, col)
                col += 1
                total += 1
                if col >= cols:
                    col, row = 0, row + 1
        # 计算并设置网格底板的固定尺寸（避免出现半格）
        try:
            rows = max(1, (total + cols - 1) // cols)
            w = cols * cell
            h = rows * cell
            self._grid_wrap.setFixedSize(w, h)
        except Exception:
            pass
        self._right_scroll.setWidget(wrap)

    def eventFilter(self, obj, event):
        # 当滚动区域的可视宽度变化时，重新计算列数，避免出现半格
        try:
            if self._right_scroll and obj is self._right_scroll.viewport():
                if event.type() == QtCore.QEvent.Type.Resize:
                    vw = max(1, obj.width())
                    cell = int(getattr(self, '_grid_cell', 72))
                    max_cols = int(getattr(self, '_grid_cols', 6))
                    cols = max(1, min(max_cols, vw // cell))
                    if cols != int(getattr(self, '_grid_actual_cols', max_cols)):
                        self._grid_actual_cols = cols
                        self._rebuild_right_grid()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _refresh_right_grid(self):
        """刷新右侧网格（重建）。"""
        self._rebuild_right_grid()

    def _refresh_parent_card(self):
        """尝试刷新父级卡片（若父组件提供 refresh(model) 接口）。"""
        try:
            p = self.parent()
            if p is not None and hasattr(p, 'refresh') and hasattr(p, 'model'):
                p.refresh(p.model)
        except Exception:
            pass

    def _apply_btn_style(self, btn: QtWidgets.QPushButton):
        """应用物品按钮样式：按稀有度描边，选中态加深背景/边框。"""
        try:
            color = btn.property('rarity_color') or '#BDBDBD'
            selected = bool(btn.property('selected')) or btn.isChecked()
        except Exception:
            color, selected = '#BDBDBD', False
        if selected:
            ss = (
                f"QPushButton{{border:3px solid {color}; padding:2px; border-radius:4px; background: rgba(0,0,0,0.06);}}"
                f" QPushButton:hover{{background: rgba(0,0,0,0.08);}}"
            )
        else:
            ss = (
                f"QPushButton{{border:2px solid {color}; padding:3px; border-radius:4px;}}"
                f" QPushButton:hover{{background: rgba(0,0,0,0.04);}}"
            )
        try:
            btn.setStyleSheet(ss)
        except Exception:
            pass

    def _refresh_left(self):
        """刷新左侧槽位标签与卸下按钮禁用状态。"""
        _m, eq = self._member_and_eq()
        def label_of(x):
            if not x:
                return "-"
            parts = []
            if getattr(x, 'attack', 0):
                parts.append(f"+{int(getattr(x, 'attack', 0))}攻")
            if getattr(x, 'defense', 0):
                parts.append(f"+{int(getattr(x, 'defense', 0))}防")
            flags = []
            if getattr(x, 'is_two_handed', False):
                flags.append('双手')
            flag = (" [" + ", ".join(flags) + "]") if flags else ""
            return f"{getattr(x, 'name', '-')} {' '.join(parts)}{flag}"
        lh = getattr(eq, 'left_hand', None) if eq else None
        ar = getattr(eq, 'armor', None) if eq else None
        rh = getattr(eq, 'right_hand', None) if eq else None
        if self._lbl_lh is not None:
            self._lbl_lh.setText(label_of(lh))
            self._lbl_lh.setToolTip(self._fmt_tip(lh) if lh else "左手: -")
        if self._lbl_ar is not None:
            self._lbl_ar.setText(label_of(ar))
            self._lbl_ar.setToolTip(self._fmt_tip(ar) if ar else "盔甲: -")
        if self._lbl_rh is not None:
            self._lbl_rh.setText(label_of(rh))
            self._lbl_rh.setToolTip(self._fmt_tip(rh) if rh else "右手: -")
        if self._btn_ul is not None:
            self._btn_ul.setDisabled(lh is None)
        if self._btn_ua is not None:
            self._btn_ua.setDisabled(ar is None)
        if self._btn_ur is not None:
            self._btn_ur.setDisabled(rh is None)


