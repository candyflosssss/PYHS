from __future__ import annotations

from ..qt_compat import QtWidgets  # type: ignore


class OperationsRow:
    def __init__(self, app_ctx):
        self.app_ctx = app_ctx
        self.panel = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(self.panel)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        btn_back = QtWidgets.QPushButton("返回上一级")
        btn_end = QtWidgets.QPushButton("结束回合 (end)")
        btn_back.clicked.connect(lambda: self._run('back'))
        btn_end.clicked.connect(lambda: self._run('end'))
        h.addWidget(btn_back)
        h.addWidget(btn_end)
        h.addStretch(1)

    def _run(self, cmd: str):
        self.app_ctx._send(cmd)


