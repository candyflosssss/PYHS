from __future__ import annotations

from typing import Any

from ..qt_compat import QtWidgets, QtCore, QtGui
from ..dialogs.equipment_dialog import EquipmentDialog
try:
    # 优先从全局 app 注入的 settings 读取（通过 settings.apply_to_tk_app 注入到 app_ctx）
    # 若不可用，则直接读取 settings.tk_cfg()
    from ... import settings as SETTINGS  # type: ignore
except Exception:  # pragma: no cover - 容错：未找到 settings 模块
    SETTINGS = None  # type: ignore
Signal = QtCore.pyqtSignal


class CardWidget(QtWidgets.QFrame):
    """角色卡片组件（PyQt6 版）。

    功能结构：
    - 顶部名称、ATK/AC 统计、体力胶囊、HP 条、右侧装备栏（左手/盔甲/右手）。
    - 通过 refresh(model) 刷新显示；装备栏按钮点击会弹出装备对话框（不再直接卸下）。
    - 敌人卡片禁用装备交互；盟友卡片可交互。

    输入：
    - app_ctx: 上下文（需要提供 _slot_click、若有 _stamina_cfg/_hp_bar_cfg 则用于皮肤配置）。
    - model: 角色模型（需要具备 name/display_name、equipment、hp/max_hp、stamina 等属性）。
    - index1: 1 基索引，传给 app 的命令接口。
    - is_enemy: 是否为敌方，用于禁用装备交互。

    输出：
    - 无直接返回。UI 状态根据 model 动态更新。
    """

    clicked = Signal() if 'Signal' in globals() and Signal else None  # type: ignore

    def __init__(self, app_ctx, model: Any, index1: int, *, is_enemy: bool = False):
        super().__init__()
        self.app_ctx = app_ctx
        self.model = model
        self.index1 = index1
        self.is_enemy = is_enemy
        # 仅对卡片外框应用样式，避免影响子控件
        try:
            self.setObjectName("cardRoot")
        except Exception:
            pass

        # Frame style/size (host view will set fixed size)
        shape = QtWidgets.QFrame.Shape.NoFrame
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
            # 首选 app 注入的调色板；退化到 settings.tk_cfg().stats_colors
            atk_col = (getattr(self.app_ctx, '_stats_colors', {}) or {}).get('atk')
            if not atk_col and SETTINGS:
                atk_col = (SETTINGS.tk_cfg().get('stats_colors', {}) or {}).get('atk', '#E6B800')
            if not atk_col:
                atk_col = '#E6B800'
        except Exception:
            atk_col = '#E6B800'
        self.lbl_atk.setStyleSheet(f"color:{atk_col}; font-weight:700; font-size:12px;")
        row_atk.addWidget(QtWidgets.QLabel("ATK:"))
        row_atk.addWidget(self.lbl_atk)
        row_ac = QtWidgets.QHBoxLayout()
        self.lbl_ac = QtWidgets.QLabel("0")
        try:
            ac_col = (getattr(self.app_ctx, '_stats_colors', {}) or {}).get('ac')
            if not ac_col and SETTINGS:
                ac_col = (SETTINGS.tk_cfg().get('stats_colors', {}) or {}).get('ac', '#2980b9')
            if not ac_col:
                ac_col = '#2980b9'
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
        # 标记为装备槽按钮，便于排除全卡点击
        try:
            for b in (self.btn_left, self.btn_armor, self.btn_right):
                setattr(b, "_is_equipment_slot", True)
        except Exception:
            pass
        root.addLayout(eq_col, 0, 1, 2, 1)

        # Stamina capsules (row widget to allow custom bg like Tk)
        self.stamina_row = QtWidgets.QWidget()
        self.stamina_wrap = QtWidgets.QHBoxLayout(self.stamina_row)
        self.stamina_wrap.setContentsMargins(0, 0, 0, 0)
        self.stamina_wrap.setSpacing(0)
        # Ensure left alignment consistently
        self.stamina_wrap.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self.stamina_row, 2, 0, 1, 2)

        # HP bar
        self.hp_bar = QtWidgets.QProgressBar()
        self.hp_bar.setTextVisible(True)
        try:
            # app_ctx 注入优先；否则直接从 settings 读取
            hp_cfg = getattr(self.app_ctx, '_hp_bar_cfg', None)
            if not hp_cfg and SETTINGS:
                hp_cfg = SETTINGS.tk_cfg().get('hp_bar', {}) or {}
            hp_h = int((hp_cfg or {}).get('height', 14))
            hp_bg = (hp_cfg or {}).get('bg', '#e0e0e0')
            hp_fg = (hp_cfg or {}).get('fg', '#2ecc71')
            hp_text = (hp_cfg or {}).get('text', '#ffffff')
            self.hp_bar.setFixedHeight(max(10, hp_h))
            self.hp_bar.setStyleSheet(
                (
                    f"QProgressBar{{border:0; background:{hp_bg}; border-radius:5px;}}"
                    f" QProgressBar{{ text-align:center; padding:0px; font-size:11px; color:{hp_text};}}"
                    f" QProgressBar::chunk{{background:{hp_fg}; border:0; margin:0px; border-radius:5px;}}"
                )
            )
        except Exception:
            self.hp_bar.setFixedHeight(14)
            self.hp_bar.setStyleSheet(
                (
                    "QProgressBar{border:0; background:#e0e0e0; border-radius:5px;}"
                    " QProgressBar{ text-align:center; padding:0px; font-size:11px; color:#ffffff;}"
                    " QProgressBar::chunk{background:#2ecc71; border:0; margin:0px; border-radius:5px;}"
                )
            )
        root.addWidget(self.hp_bar, 3, 0, 1, 2)

        # 绑定按钮点击逻辑
        self._wire_equipment_buttons()
        # 仅安装用于“卡片级点击”的事件过滤；不再拦截 Hover/ToolTip（交给 Qt 默认处理）。
        try:
            for w in (self, self.lbl_name, self.lbl_atk, self.lbl_ac, self.hp_bar, self.btn_left, self.btn_armor, self.btn_right):
                w.installEventFilter(self)
        except Exception:
            pass
        # 初次渲染
        self.refresh(model)

    def apply_default_style(self) -> None:
        """应用卡片默认样式（背景色 + 1px 描边 + 圆角）。

        描边/背景从 settings 注入的 app_ctx._card_cfg 读取；否则使用内置默认。
        """
        try:
            cc = getattr(self.app_ctx, '_card_cfg', {}) or {}
            bg = cc.get('bg', '#fafafa')
            stroke = cc.get('stroke_color', '#d9d9d9')
            w = int(cc.get('stroke_width', 1))
            r = int(cc.get('radius', 6))
        except Exception:
            bg, stroke, w, r = '#fafafa', '#d9d9d9', 1, 6
        # 仅选中本卡片外框，不影响子控件
        self.setStyleSheet(f"#cardRoot {{ background: {bg}; border: {max(0,w)}px solid {stroke}; border-radius:{max(0,r)}px; }}")

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
            dex_raw = getattr(m, 'dex', None)
            if dex_raw is None:
                attrs = getattr(m, 'attributes', {}) or {}
                dex_raw = attrs.get('dex', attrs.get('DEX'))
            if dex_raw is not None:
                dex_mod = (int(dex_raw) - 10) // 2
        except Exception:
            dex_mod = 0
        return int(10 + defense + dex_mod)
    def _equipment_triplet(self, m: Any):
        """返回装备三件套：左手、盔甲、右手。

        注意：不在此处处理“双手占用右手”的逻辑，保持 right 为真实右手物品。
        """
        try:
            eq = getattr(m, 'equipment', None)
            left = getattr(eq, 'left_hand', None) if eq else None
            armor = getattr(eq, 'armor', None) if eq else None
            right = getattr(eq, 'right_hand', None) if eq else None
            return left, armor, right
        except Exception:
            return None, None, None

    def _tooltip_for_item(self, item: Any, slot_name: str) -> str:
        """生成装备项的提示文本。

        输入：item 装备对象；slot_name 槽位中文名。
        输出：多行字符串，包含名称、攻击/防御、其它已知属性。
        """
        if not item:
            return f"{slot_name}: -"
        lines: list[str] = [f"{slot_name}: {getattr(item, 'name', '-')}"]
        try:
            atk = getattr(item, 'attack', None)
            if atk is not None:
                lines.append(f"攻击: {int(atk)}")
        except Exception:
            pass
        try:
            df = getattr(item, 'defense', None)
            if df is not None:
                lines.append(f"防御: {int(df)}")
        except Exception:
            pass
        # 其它可选属性
        for key, zh in [('hp', '生命'), ('ac', '护甲'), ('stamina', '体力')]:
            try:
                v = getattr(item, key, None)
                if v is not None:
                    lines.append(f"{zh}: {v}")
            except Exception:
                pass
        return "\n".join(lines)

    def _build_card_tooltip(self, m: Any) -> str:
        """构造角色卡悬浮信息（基础段）。

        包含：名称、ATK/AC、HP、属性（若有）、装备清单。
        """
        parts: list[str] = []
        try:
            parts.append(f"名称: {self._name_of(m)}")
        except Exception:
            pass
        try:
            b, eqa, tot = self._split_atk(m)
            parts.append(f"ATK: {tot} (基础{b} + 装备{eqa})")
        except Exception:
            pass
        try:
            parts.append(f"AC: {self._compute_ac(m)}")
        except Exception:
            pass
        try:
            cur_hp = int(getattr(m, 'hp', 0)); max_hp = int(getattr(m, 'max_hp', cur_hp or 1))
            parts.append(f"HP: {cur_hp}/{max_hp}")
        except Exception:
            pass
        # 属性
        try:
            attrs = getattr(m, 'attributes', {}) or {}
            mapping = [('str','力量'),('dex','敏捷'),('con','体质'),('int','智力'),('wis','感知'),('cha','魅力')]
            lines: list[str] = []
            for key, zh in mapping:
                v = attrs.get(key, attrs.get(key.upper()))
                if v is None:
                    continue
                try:
                    iv = int(v)
                    mod = (iv - 10) // 2
                    lines.append(f"{zh} {iv}({mod:+d})")
                except Exception:
                    lines.append(f"{zh} {v}")
            if lines:
                parts.append("属性:")
                parts.extend(lines)
        except Exception:
            pass
        # 装备名称列表
        try:
            eq = getattr(m, 'equipment', None)
            eq_list = []
            if eq:
                if getattr(eq, 'left_hand', None):
                    eq_list.append(f"左手: {getattr(eq.left_hand, 'name', '-')}")
                if getattr(eq, 'right_hand', None):
                    eq_list.append(f"右手: {getattr(eq.right_hand, 'name', '-')}")
                if getattr(eq, 'armor', None):
                    eq_list.append(f"盔甲: {getattr(eq.armor, 'name', '-')}")
            if eq_list:
                parts.append("装备: " + ", ".join(eq_list))
        except Exception:
            pass
        return "\n".join(parts)

    def _wire_equipment_buttons(self):
        """绑定装备栏按钮事件。

    - 敌方禁用按钮；盟友连接到 _slot_click。
        - 动态禁用（例如双手武器占用右手）在 refresh 内根据模型状态处理。
        """
        if self.is_enemy:
            for b in (self.btn_left, self.btn_armor, self.btn_right):
                b.setDisabled(True)
        else:
            self.btn_left.clicked.connect(lambda: self._slot_click('left'))
            self.btn_armor.clicked.connect(lambda: self._slot_click('armor'))
            self.btn_right.clicked.connect(lambda: self._slot_click('right'))

    def _slot_click(self, slot_key: str):
        """打开装备选择对话框并执行装备。

        输入：slot_key ∈ {'left','armor','right'}。
        行为：
        - 弹出 EquipmentDialog，右侧仅显示可装备到该槽位的物品。
        - 在对话框内点击物品即完成装备与背包扣减（对话框不会自动关闭）。
        - 关闭对话框后，刷新本卡片显示。
        """
        try:
            # 以主窗口作为父级，避免刷新战场时销毁卡片导致对话框被连带关闭
            parent = getattr(self.app_ctx, '_window_ref', None) or self
            dlg = EquipmentDialog(self.app_ctx, parent, self.index1, slot_key)
            _ = dlg.get_result()  # 结果仅作记录；装备已在对话框中即时完成
        except Exception:
            pass
        # 不论是否选择，关闭对话框后刷新自身 UI（覆盖仅卸下的情况）
        try:
            self.refresh(self.model)
        except Exception:
            pass

    # --- API ---
    def refresh(self, m: Any) -> None:
        """根据当前模型刷新卡片显示。

        包含：名称/ATK/AC、体力胶囊、HP 条、装备栏按钮文本/提示与可用状态。
        """
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
        # config from settings/app_ctx
        st_cfg = getattr(self.app_ctx, '_stamina_cfg', None)
        if not st_cfg and SETTINGS:
            st_cfg = (SETTINGS.tk_cfg().get('stamina', {}) or {})
        # 体力行背景色（从 settings 读取；未提供则透明）
        bgc = str((st_cfg or {}).get('bg', 'transparent'))
        max_caps = int((st_cfg or {}).get('max_caps', 6))
        colors = (st_cfg or {}).get('colors', {}) or {}
        col_on = colors.get('on', '#2ecc71')
        col_off = colors.get('off', '#e74c3c')
        try:
            cur = int(getattr(m, 'stamina', 0)); mx = int(getattr(m, 'stamina_max', cur or 1))
        except Exception:
            cur, mx = 0, 1
        show_n = min(mx, max_caps)
        # 是否显示体力（settings.ui.tk.stamina.enabled）
        st_enabled = bool((st_cfg or {}).get('enabled', True))
        # apply row background (transparent)
        self.stamina_row.setStyleSheet(f"QWidget{{background:{bgc}; border:0;}}")
        if st_enabled and show_n > 0:
            for i in range(show_n):
                seg = QtWidgets.QFrame()
                shape = QtWidgets.QFrame.Shape.NoFrame
                seg.setFrameShape(shape)
                seg.setFixedSize(8, 16)
                color = col_on if i < cur else col_off
                # 体力胶囊：需要 1px 描边（其余子项仍不描边）
                try:
                    sc = (st_cfg or {}).get('stroke_color', '#cfd8dc')
                    sw = int((st_cfg or {}).get('stroke_width', 1))
                except Exception:
                    sc, sw = '#cfd8dc', 1
                seg.setStyleSheet(f"QFrame {{ background: {color}; border: {max(0,sw)}px solid {sc}; border-radius:4px; }}")
                self.stamina_wrap.addWidget(seg)

        # HP bar
        try:
            cur_hp = int(getattr(m, 'hp', 0)); max_hp = int(getattr(m, 'max_hp', cur_hp or 1))
        except Exception:
            cur_hp, max_hp = 0, 1
        self.hp_bar.setMaximum(max_hp)
        self.hp_bar.setValue(cur_hp)
        self.hp_bar.setFormat(f"{cur_hp}/{max_hp}")

        # 装备栏：按钮文本/提示/禁用状态
        left, armor, right = self._equipment_triplet(m)
        # 文本显示当前装备名（无则短横），提示包含详细属性
        self.btn_left.setText((getattr(left, 'name')) if left and getattr(left, 'name', None) else '左手: -')
        self.btn_armor.setText((getattr(armor, 'name')) if armor and getattr(armor, 'name', None) else '盔甲: -')
        # 右手文本受双手武器影响：若左手为双手，则右手按钮禁用，但仍显示“当前右手装备的名称（若有）”。
        lh_two_handed = bool(getattr(left, 'is_two_handed', False)) if left else False
        # 若左手为双手，则右手显示同一把双手武器名称（但禁用）；否则显示真实右手装备
        if lh_two_handed:
            show_item = left
        else:
            show_item = right
        self.btn_right.setText((getattr(show_item, 'name')) if show_item and getattr(show_item, 'name', None) else '右手: -')

        self.btn_left.setToolTip(self._tooltip_for_item(left, '左手'))
        self.btn_armor.setToolTip(self._tooltip_for_item(armor, '盔甲'))
        # 双手武器占用右手时，提示原因
        if lh_two_handed:
            # 右手显示为左手双手武器的信息，并追加受限说明
            base_tip = self._tooltip_for_item(left, '右手') if left else '右手: -'
            self.btn_right.setToolTip(base_tip + "\n(当前持双手武器，右手被占用)")
        else:
            self.btn_right.setToolTip(self._tooltip_for_item(right, '右手'))

        # 根据敌友与双手武器状态动态禁用按钮
        if self.is_enemy:
            for b in (self.btn_left, self.btn_armor, self.btn_right):
                b.setDisabled(True)
        else:
            self.btn_left.setDisabled(False)
            self.btn_armor.setDisabled(False)
            # 左手为双手武器 -> 右手禁用
            self.btn_right.setDisabled(lh_two_handed)
        # 卡片整体与 ATK/HP/AC 的提示：回退为系统 ToolTip（静态文本，由 Qt 管理显示/隐藏）
        self._update_tooltips()

    def _update_tooltips(self) -> None:
        """更新卡片整体与局部标签的系统 ToolTip 文本。

        - 卡片整体：展示综合角色信息（名称/ATK/AC/HP/属性/装备清单）。
        - ATK 标签：展示基础与装备构成。
        - HP 条：展示当前/最大 HP。
        """
        try:
            # 卡片整体
            self.setToolTip(self._build_card_tooltip(self.model))
        except Exception:
            pass
        # ATK 细节
        try:
            b, eqa, tot = self._split_atk(self.model)
            self.lbl_atk.setToolTip(f"总攻击: {tot}\n基础: {b}\n装备: {eqa}")
        except Exception:
            try:
                self.lbl_atk.setToolTip("")
            except Exception:
                pass
        # HP 细节
        try:
            cur_hp = int(getattr(self.model, 'hp', 0)); max_hp = int(getattr(self.model, 'max_hp', cur_hp or 1))
            self.hp_bar.setToolTip(f"HP: {cur_hp}/{max_hp}")
        except Exception:
            try:
                self.hp_bar.setToolTip("")
            except Exception:
                pass

    # --- event filter: 仅用于“卡片级点击” ---
    def eventFilter(self, obj, event):  # noqa: N802 (Qt signature)
        try:
            et = getattr(QtCore.QEvent, 'Type', QtCore.QEvent)
            mpress = getattr(et, 'MouseButtonPress', 2)
            targets = (self, self.lbl_name, self.lbl_atk, self.lbl_ac, self.hp_bar, self.btn_left, self.btn_armor, self.btn_right)

            # 卡片级点击透传
            if event.type() == mpress:
                if obj in (self.btn_left, self.btn_right, self.btn_armor):
                    return False
                if hasattr(self, 'clicked') and self.clicked:
                    try:
                        self.clicked.emit()  # type: ignore[attr-defined]
                    except Exception:
                        pass
                return False

            # 其余事件（Enter/Leave/Hover/ToolTip）统一交给 Qt 默认 ToolTip 行为处理
        except Exception:
            pass
        return super().eventFilter(obj, event)



