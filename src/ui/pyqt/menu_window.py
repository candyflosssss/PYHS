from __future__ import annotations

import os
import json
from typing import Optional

from .qt_compat import QtWidgets, DBOX_OK, DBOX_CANCEL
from src import app_config as CFG

try:
    from main import load_config, save_config, discover_packs, _pick_default_main  # type: ignore
except Exception:  # pragma: no cover
    def load_config():  # type: ignore
        return {"name": "玩家", "last_pack": "", "last_scene": "default_scene.json"}
    def save_config(_cfg: dict):  # type: ignore
        pass
    def discover_packs():  # type: ignore
        return {}
    def _pick_default_main(mains):  # type: ignore
        return mains[0] if mains else 'default_scene.json'


class MenuWindow(QtWidgets.QMainWindow):
    def __init__(self, app_ctx, on_start_game=None):
        super().__init__()
        self.app_ctx = app_ctx
        self.on_start_game = on_start_game
        self.setWindowTitle("COMOS PvE - 主菜单")
        self.setMinimumSize(640, 420)

        self.cfg = load_config()

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(10)

        title = QtWidgets.QLabel("COMOS PvE - 主菜单")
        title.setStyleSheet("font-size:16px; font-weight:700;")
        v.addWidget(title)

        self.lbl_profile = QtWidgets.QLabel("")
        v.addWidget(self.lbl_profile)

        # Preview panel
        prev_group = QtWidgets.QGroupBox("地图组/主地图预览")
        pv = QtWidgets.QVBoxLayout(prev_group)
        self.lbl_pack = QtWidgets.QLabel("-")
        self.lbl_scene = QtWidgets.QLabel("-")
        self.lbl_desc = QtWidgets.QLabel("")
        self.lbl_desc.setWordWrap(True)
        pv.addWidget(self.lbl_pack)
        pv.addWidget(self.lbl_scene)
        pv.addWidget(self.lbl_desc)
        v.addWidget(prev_group)

        btns = QtWidgets.QVBoxLayout()
        v.addLayout(btns)

        b_start = QtWidgets.QPushButton("🎮 开始游戏")
        b_save = QtWidgets.QPushButton("📁 选择存档")
        b_rename = QtWidgets.QPushButton("✏️ 修改玩家名称")
        b_pack = QtWidgets.QPushButton("🗺️ 选择地图组")
        b_reload = QtWidgets.QPushButton("🔄 重新载入场景列表")
        b_exit = QtWidgets.QPushButton("🚪 退出")
        for b in (b_start, b_save, b_rename, b_pack, b_reload, b_exit):
            b.setFixedHeight(32)
            btns.addWidget(b)

        b_start.clicked.connect(self._menu_start)
        b_save.clicked.connect(self._menu_choose_save)
        b_rename.clicked.connect(self._menu_rename)
        b_pack.clicked.connect(self._menu_choose_pack)
        b_reload.clicked.connect(self._menu_refresh_packs)
        b_exit.clicked.connect(self.close)

        self._update_profile()
        try:
            self._update_preview()
        except Exception:
            pass

    # --- helpers ---
    def _profile_text(self) -> str:
        pack_id = self.cfg.get('last_pack', '')
        last_scene = self.cfg.get('last_scene', 'default_scene.json')
        scene_label = (pack_id + '/' if pack_id else '') + last_scene
        return f"玩家: {self.cfg.get('name','玩家')}    场景: {scene_label}"

    def _update_profile(self):
        self.lbl_profile.setText(self._profile_text())

    def _menu_start(self):
        packs = discover_packs() or {}
        pid = self.cfg.get('last_pack', '')
        pack = packs.get(pid) or packs.get('') or {}
        mains = pack.get('mains', []) if isinstance(pack, dict) else []
        if mains and self.cfg.get('last_scene') not in mains:
            self.cfg['last_scene'] = _pick_default_main(mains)
            save_config(self.cfg)
        start_scene = (pid + '/' if pid else '') + self.cfg.get('last_scene', 'default_scene.json')
        # prepare ctx and open game window
        self.app_ctx.player_name = self.cfg.get('name', '玩家')
        self.app_ctx.initial_scene = start_scene
        self.app_ctx.start_game()
        from .main_window import MainWindow
        win = MainWindow(self.app_ctx)
        # persist references to avoid GC
        try:
            self._next_win = win  # type: ignore[attr-defined]
            setattr(self.app_ctx, '_last_main_window', win)
        except Exception:
            pass
        win.show()
        self.close()

    def _menu_rename(self):
        new_name, ok = QtWidgets.QInputDialog.getText(self, "修改名称", "请输入新名称:", text=self.cfg.get('name','玩家'))
        if ok and new_name:
            self.cfg['name'] = new_name.strip()
            save_config(self.cfg)
            self._update_profile()

    def _list_saves(self):
        items = []
        try:
            udir = CFG.user_data_dir()
            for fn in os.listdir(udir):
                if not (fn.startswith('save_') and fn.endswith('.json')):
                    continue
                path = os.path.join(udir, fn)
                name = None
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        name = (data.get('player') or {}).get('name')
                except Exception:
                    pass
                if not name:
                    base = os.path.splitext(fn)[0]
                    name = base.replace('save_', '')
                label = f"{name}  ({fn})"
                items.append({'name': name, 'path': path, 'label': label})
        except Exception:
            pass
        return items

    def _menu_choose_save(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("选择存档")
        v = QtWidgets.QVBoxLayout(dlg)
        v.addWidget(QtWidgets.QLabel("可用存档"))
        lb = QtWidgets.QListWidget()
        v.addWidget(lb)
        items = self._list_saves()
        for it in items:
            lb.addItem(it['label'])
        btns = QtWidgets.QDialogButtonBox(DBOX_OK | DBOX_CANCEL)
        v.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        accepted = (dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted)
        if accepted:
            row = lb.currentRow()
            if row >= 0:
                ch = items[row]
                self.cfg['name'] = ch['name']
                save_config(self.cfg)
                QtWidgets.QMessageBox.information(self, "提示", f"已切换到存档: {ch['name']}")
                self._update_profile()

    def _menu_choose_pack(self):
        packs = discover_packs() or {}
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("选择地图组")
        grid = QtWidgets.QGridLayout(dlg)
        grid.addWidget(QtWidgets.QLabel("地图组"), 0, 0)
        grid.addWidget(QtWidgets.QLabel("主地图"), 0, 1)
        lbp = QtWidgets.QListWidget(); lbs = QtWidgets.QListWidget()
        grid.addWidget(lbp, 1, 0); grid.addWidget(lbs, 1, 1)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)

        pack_ids = []
        for pid, meta in packs.items():
            name = (meta.get('name') if isinstance(meta, dict) else None) or (pid or '基础')
            lbp.addItem(f"{name} ({pid or 'base'})")
            pack_ids.append(pid)

        def on_pick_pack():
            lbs.clear()
            row = lbp.currentRow()
            if row < 0:
                return
            pid = pack_ids[row]
            meta = packs.get(pid) or {}
            mains = meta.get('mains', []) if isinstance(meta, dict) else []
            for s in mains:
                lbs.addItem(s)
            # preview pack info
            try:
                name = (meta.get('name') if isinstance(meta, dict) else None) or (pid or '基础')
                self.lbl_pack.setText(f"地图组: {name} ({pid or 'base'})")
                self.lbl_scene.setText("主地图: -")
                self.lbl_desc.setText(self._read_pack_desc(meta))
            except Exception:
                pass
        lbp.currentRowChanged.connect(lambda _=0: on_pick_pack())
        on_pick_pack()

        btns = QtWidgets.QDialogButtonBox(DBOX_OK | DBOX_CANCEL)
        grid.addWidget(btns, 2, 0, 1, 2)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        accepted = (dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted)
        if accepted:
            r = lbp.currentRow()
            if r < 0:
                QtWidgets.QMessageBox.information(self, "提示", "请先选择地图组")
                return
            pid = pack_ids[r]
            meta = packs.get(pid) or {}
            mains = meta.get('mains', []) if isinstance(meta, dict) else []
            if not mains:
                QtWidgets.QMessageBox.information(self, "提示", "该地图组没有主地图")
                return
            sr = lbs.currentRow()
            if sr >= 0:
                chosen = mains[sr]
            else:
                chosen = _pick_default_main(mains)
            self.cfg['last_pack'] = pid
            self.cfg['last_scene'] = chosen
            save_config(self.cfg)
            self._update_profile()
            try:
                self._update_preview()
            except Exception:
                pass

    def _menu_refresh_packs(self):
        _ = discover_packs()
        QtWidgets.QMessageBox.information(self, "提示", "场景列表已刷新")

    def _update_preview(self):
        packs = discover_packs() or {}
        pid = self.cfg.get('last_pack', '')
        meta = packs.get(pid) or {}
        name = (meta.get('name') if isinstance(meta, dict) else None) or (pid or '基础')
        self.lbl_pack.setText(f"地图组: {name} ({pid or 'base'})")
        scene = self.cfg.get('last_scene', 'default_scene.json')
        self.lbl_scene.setText(f"主地图: {scene}")
        self.lbl_desc.setText(self._read_pack_desc(meta))

    def _read_pack_desc(self, meta: dict) -> str:
        try:
            desc = meta.get('desc') or meta.get('description')
            if desc:
                return str(desc)
        except Exception:
            pass
        return ""


