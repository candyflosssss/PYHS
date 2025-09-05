from __future__ import annotations

from typing import List, Dict, Tuple
from ..qt_compat import QtWidgets, QtCore, QtGui


class TooltipBubble(QtWidgets.QFrame):
	"""轻量级悬浮气泡（ToolTip 风格），支持多段文本堆叠。

	- set_sections([{title,text}, ...]) 更新内容
	- set_max_width(w) 限制最大宽度并自动换行
	- 透明鼠标事件，不抢焦点
	"""

	def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
		super().__init__(parent, QtCore.Qt.WindowType.ToolTip | QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.NoDropShadowWindowHint)
		self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
		self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
		self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
		self._wrap = QtWidgets.QVBoxLayout(self)
		self._wrap.setContentsMargins(8, 8, 8, 8)
		self._wrap.setSpacing(6)
		self.setStyleSheet(
			"""
			QFrame { background: rgba(30,30,30,210); border: 1px solid rgba(255,255,255,60); border-radius:7px; }
			QLabel { color: #f5f5f5; font-size: 11px; }
			QLabel[role="title"] { color: #ffd666; font-weight: 700; margin-bottom: 2px; }
			QFrame[role="section"] { background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,30); border-radius:5px; padding:6px; }
			"""
		)
		self._sections: List[QtWidgets.QFrame] = []
		self._max_width: int = 280

	def set_max_width(self, w: int) -> None:
		self._max_width = max(120, int(w))
		self.setMaximumWidth(self._max_width)

	def clear(self) -> None:
		for sec in self._sections:
			sec.setParent(None)
			sec.deleteLater()
		self._sections.clear()

	def set_sections(self, items: List[Dict[str, str]]) -> None:
		self.clear()
		for it in items:
			box = QtWidgets.QFrame(self)
			box.setProperty("role", "section")
			lay = QtWidgets.QVBoxLayout(box)
			lay.setContentsMargins(6, 6, 6, 6)
			lay.setSpacing(2)
			if it.get("title"):
				t = QtWidgets.QLabel(it.get("title", ""), box)
				t.setProperty("role", "title")
				t.setWordWrap(True)
				lay.addWidget(t)
			body = QtWidgets.QLabel(it.get("text", ""), box)
			body.setWordWrap(True)
			lay.addWidget(body)
			self._wrap.addWidget(box)
			self._sections.append(box)
		self.setMaximumWidth(self._max_width)
		self.adjustSize()


class TooltipManager(QtCore.QObject):
	"""窗口级 Tooltip 管理器：支持“多气泡堆叠 + 屏幕边界约束 + 简易节流”。"""

	def __init__(self, owner: QtWidgets.QWidget) -> None:
		super().__init__(owner)
		self.owner = owner
		self._bubbles: List[TooltipBubble] = []
		self._timer = QtCore.QTimer(self)
		self._timer.setSingleShot(True)
		self._timer.timeout.connect(self.hide)
		self._last_sig: Tuple[int, Tuple[Tuple[Tuple[str,str],...], ...], str] | None = None
		self._last_ts: float = 0.0
		self._spacing: int = 6
		self._max_width: int = 280

	def _ensure_pool(self, n: int) -> None:
		while len(self._bubbles) < n:
			b = TooltipBubble()
			b.set_max_width(self._max_width)
			self._bubbles.append(b)
		for i in range(n, len(self._bubbles)):
			try:
				self._bubbles[i].hide()
			except Exception:
				pass

	def _screen_rect_at(self, pt: QtCore.QPoint) -> QtCore.QRect:
		try:
			scr = QtGui.QGuiApplication.screenAt(pt)
			if scr:
				g = scr.availableGeometry()
				return QtCore.QRect(g.left()+4, g.top()+4, g.width()-8, g.height()-8)
		except Exception:
			pass
		try:
			scr = QtGui.QGuiApplication.primaryScreen()
			if scr:
				g = scr.availableGeometry()
				return QtCore.QRect(g.left()+4, g.top()+4, g.width()-8, g.height()-8)
		except Exception:
			pass
		return QtCore.QRect(0, 0, 1920, 1080)

	def configure(self, *, spacing: int | None = None, max_width: int | None = None) -> None:
		if spacing is not None:
			self._spacing = max(0, int(spacing))
		if max_width is not None:
			self._max_width = max(120, int(max_width))
			for b in self._bubbles:
				b.set_max_width(self._max_width)

	def show_stacked_for_card(self, card: QtWidgets.QWidget, stacks: List[List[Dict[str,str]]], *, side: str = "right", offset: tuple[int,int] = (8,0)) -> None:
		import time as _t
		sig = (id(card), tuple(tuple((d.get("title",""), d.get("text","")) for d in sec) for sec in stacks), side)
		now = _t.monotonic()
		if self._last_sig == sig and (now - self._last_ts) < 0.10:
			return
		self._last_sig, self._last_ts = sig, now

		self._timer.stop()
		if not stacks:
			self.hide(); return
		self._ensure_pool(len(stacks))
		for i, sec in enumerate(stacks):
			b = self._bubbles[i]
			b.set_max_width(self._max_width)
			b.set_sections(sec)

		g = card.geometry()
		top_l = card.mapToGlobal(g.topLeft())
		top_r = card.mapToGlobal(g.topRight())
		base = top_r if side != "left" else top_l
		bound = self._screen_rect_at(base)
		dx = int(offset[0]) if isinstance(offset, (list, tuple)) and len(offset) >= 1 else 8
		dy = int(offset[1]) if isinstance(offset, (list, tuple)) and len(offset) >= 2 else 0
		cur_y = base.y() + dy
		for i, b in enumerate(self._bubbles[:len(stacks)]):
			w = b.width(); h = b.height()
			if side == "left":
				x = base.x() - dx - w
			else:
				x = base.x() + dx
			x = max(bound.left(), min(x, bound.right() - w))
			y = max(bound.top(), min(cur_y, bound.bottom() - h))
			b.move(x, y)
			b.show()
			cur_y = y + h + self._spacing

	def hide(self) -> None:
		for b in self._bubbles:
			try:
				b.hide()
			except Exception:
				pass

	def cancel_hide(self) -> None:
		self._timer.stop()

	def schedule_hide(self, ms: int) -> None:
		self._timer.start(max(0, int(ms)))


_MANAGERS: "dict[int, TooltipManager]" = {}


def get_manager(window: QtWidgets.QWidget | None) -> TooltipManager | None:
	if window is None:
		return None
	wid = int(window.winId()) if hasattr(window, 'winId') else id(window)
	mgr = _MANAGERS.get(wid)
	if mgr is None:
		mgr = TooltipManager(window)
		_MANAGERS[wid] = mgr
	return mgr

