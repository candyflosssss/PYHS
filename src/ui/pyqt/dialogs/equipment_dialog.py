from __future__ import annotations

from typing import Optional

from ..qt_compat import QtWidgets, DBOX_OK, DBOX_CANCEL  # type: ignore


class EquipmentDialog(QtWidgets.QDialog):
    """Minimal equipment selection dialog placeholder.

    Returns selected inventory index (int) or None.
    """

    def __init__(self, parent=None, inv_items: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("装备")
        self.setModal(True)
        v = QtWidgets.QVBoxLayout(self)
        self.list = QtWidgets.QListWidget()
        if inv_items:
            self.list.addItems(inv_items)
        v.addWidget(self.list)
        btns = QtWidgets.QDialogButtonBox(DBOX_OK | DBOX_CANCEL)
        v.addWidget(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

    def get_result(self) -> Optional[int]:
        ok = None
        if hasattr(self, 'exec_'):
            ok = (self.exec_() == QtWidgets.QDialog.Accepted)
        else:
            ok = (self.exec() == QtWidgets.QDialog.DialogCode.Accepted)
        if ok:
            row = self.list.currentRow()
            return (row + 1) if row >= 0 else None
        return None


