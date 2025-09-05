from __future__ import annotations

# 统一的 Qt 入口：强制使用 PyQt6（不再支持 PyQt5 回退）。
from PyQt6 import QtWidgets, QtCore, QtGui  # type: ignore
API = 'PyQt6'
# Dialog button flags (PyQt6 enums moved under StandardButton)
DBOX_OK = QtWidgets.QDialogButtonBox.StandardButton.Ok
DBOX_CANCEL = QtWidgets.QDialogButtonBox.StandardButton.Cancel
DBOX_YES = QtWidgets.QDialogButtonBox.StandardButton.Yes
DBOX_NO = QtWidgets.QDialogButtonBox.StandardButton.No

__all__ = ['QtWidgets', 'QtCore', 'QtGui', 'API', 'DBOX_OK', 'DBOX_CANCEL', 'DBOX_YES', 'DBOX_NO']



