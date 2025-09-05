from __future__ import annotations

"""PyQt 浮动 Tooltip 管理器（避免 QToolTip 在跨控件移动时提前隐藏）。

- 使用无焦点、无边框、ToolTip 窗口类型的 QFrame 配合 QLabel 自绘显示。
- 作用域为窗口级（container），在窗口内跨卡片/按钮移动时不抖动。
- 提供宽限隐藏（grace ms），离开后延迟收起；进入新目标时取消隐藏。
"""

from typing import Optional

from ..qt_compat import QtWidgets, QtCore, QtGui


class _FloatingTooltip(QtWidgets.QFrame):
    def __init__(self, parent=None, *, bg="#FFFFE1", fg="#111111"):
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.WindowType.ToolTip
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        # label
        self._label = QtWidgets.QLabel("", self)
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.addWidget(self._label)
        # style
        self.setStyleSheet(
            f"QFrame{{background:{bg}; color:{fg}; border:1px solid #A6A6A6; border-radius:4px;}}"
            f" QLabel{{color:{fg}; font-size:11px;}}"
        )

    def set_text(self, text: str) -> None:
        self._label.setText(text)
        self._label.adjustSize()
        self.adjustSize()

    def show_at(self, gpos: QtCore.QPoint) -> None:
        self.move(gpos)
        self.show()


class TooltipManager(QtCore.QObject):
    """窗口级 Tooltip 管理器。

    用法：
    - show_text(gpos, text): 在全局坐标显示文本。
    - hide_later(ms): 延迟隐藏；cancel_hide() 可取消。
    - close(): 立即隐藏。
    """

    def __init__(self, window: QtWidgets.QWidget, *, grace_ms: int = 150, bg: str = "#FFFFE1", fg: str = "#111111"):
        super().__init__(window)
        self._win = window
        self._grace_ms = int(grace_ms)
        self._bg = str(bg)
        self._fg = str(fg)
        self._tip: Optional[_FloatingTooltip] = None
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)

    def _ensure(self) -> _FloatingTooltip:
        if self._tip is None:
            self._tip = _FloatingTooltip(self._win, bg=self._bg, fg=self._fg)
        return self._tip

    def show_text(self, gpos: QtCore.QPoint, text: str) -> None:
        self.cancel_hide()
        tip = self._ensure()
        tip.set_text(text)
        tip.show_at(gpos)

    def hide_later(self, ms: Optional[int] = None) -> None:
        self._timer.start(int(self._grace_ms if ms is None else ms))

    def cancel_hide(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass

    def close(self) -> None:
        if self._tip is not None:
            try:
                self._tip.hide()
            except Exception:
                pass
