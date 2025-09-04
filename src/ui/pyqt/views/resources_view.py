from __future__ import annotations

from typing import Optional

from ..qt_compat import QtWidgets  # type: ignore

from src import app_config as CFG


class ResourcesView:
    def __init__(self, app_ctx):
        self.app_ctx = app_ctx
        self.panel = QtWidgets.QGroupBox("资源 (点击拾取)")
        v = QtWidgets.QVBoxLayout(self.panel)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)
        self._container = QtWidgets.QWidget()
        self._vlist = QtWidgets.QVBoxLayout(self._container)
        self._vlist.setContentsMargins(0, 0, 0, 0)
        self._vlist.setSpacing(4)
        v.addWidget(self._container)
        self._inv: Optional[QtWidgets.QListWidget] = None

    def bind_inventory(self, inv: QtWidgets.QListWidget) -> None:
        self._inv = inv

    def render(self) -> None:
        g = getattr(self.app_ctx.controller, 'game', None)
        if not g:
            return
        try:
            state = g.get_state()
            resources = state.get('resources', [])
        except Exception:
            resources = []

        # Clear existing buttons
        while self._vlist.count():
            item = self._vlist.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if not resources:
            lbl = QtWidgets.QLabel("(空)")
            lbl.setStyleSheet("color:#888;")
            self._vlist.addWidget(lbl)
            self._vlist.addStretch(1)
            return

        for i, r in enumerate(resources, start=1):
            name = self._fmt_res_text(r)
            btn = QtWidgets.QPushButton(name)
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda _=False, idx=i: self._pick_resource(idx))
            self._vlist.addWidget(btn)
        self._vlist.addStretch(1)

    def render_inventory(self) -> None:
        if not self._inv:
            return
        try:
            text = self.app_ctx.controller._section_inventory()
        except Exception:
            text = ''
        self._inv.clear()
        for line in (text or '').splitlines():
            s = (line or '').strip().rstrip()
            if not s:
                continue
            if s.endswith('):') or s.endswith(':'):
                continue
            self._inv.addItem(s)

    def _pick_resource(self, idx: int) -> None:
        self.app_ctx._send(f"t r{idx}")
        # partial refresh
        self.render()
        self.render_inventory()

    def _fmt_res_text(self, r) -> str:
        try:
            if isinstance(r, dict):
                name = r.get('name') or r.get('title') or str(r)
                rtype = r.get('type')
            else:
                name = str(r)
                rtype = None
        except Exception:
            name, rtype = str(r), None
        return f"{name}" + (f" ({rtype})" if rtype else "")


