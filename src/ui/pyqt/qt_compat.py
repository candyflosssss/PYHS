from __future__ import annotations

try:
    from PyQt5 import QtWidgets, QtCore, QtGui  # type: ignore
    API = 'PyQt5'
    # Dialog button flags
    DBOX_OK = QtWidgets.QDialogButtonBox.Ok
    DBOX_CANCEL = QtWidgets.QDialogButtonBox.Cancel
    DBOX_YES = QtWidgets.QDialogButtonBox.Yes
    DBOX_NO = QtWidgets.QDialogButtonBox.No
except Exception:  # pragma: no cover
    from PyQt6 import QtWidgets, QtCore, QtGui  # type: ignore
    API = 'PyQt6'
    # Dialog button flags (PyQt6 enums moved under StandardButton)
    DBOX_OK = QtWidgets.QDialogButtonBox.StandardButton.Ok
    DBOX_CANCEL = QtWidgets.QDialogButtonBox.StandardButton.Cancel
    DBOX_YES = QtWidgets.QDialogButtonBox.StandardButton.Yes
    DBOX_NO = QtWidgets.QDialogButtonBox.StandardButton.No

__all__ = ['QtWidgets', 'QtCore', 'QtGui', 'API', 'DBOX_OK', 'DBOX_CANCEL', 'DBOX_YES', 'DBOX_NO']



