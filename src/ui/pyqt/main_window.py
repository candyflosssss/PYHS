from __future__ import annotations

from typing import Optional

from .qt_compat import QtWidgets, QtCore  # type: ignore

from .app import GameQtApp
from .views.battlefield_view import BattlefieldView
from .views.resources_view import ResourcesView
from .views.operations_view import OperationsRow
from .widgets.log_pane import LogPane
from .events_bridge import EventsBridge


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, app_ctx: GameQtApp):
        super().__init__()
        self.app_ctx = app_ctx

        self.setWindowTitle("COMOS - PyQt GUI")
        self.setMinimumSize(980, 700)

        # Central composite widget
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(6)

        # Top bar: scene title + back to menu (placeholder)
        top = QtWidgets.QHBoxLayout()
        self.lbl_scene = QtWidgets.QLabel("场景: -")
        self.btn_menu = QtWidgets.QPushButton("主菜单")
        self.btn_menu.setFixedHeight(24)
        top.addWidget(self.lbl_scene)
        top.addStretch(1)
        top.addWidget(self.btn_menu)
        vbox.addLayout(top)

        # Battlefield area
        self.battlefield = BattlefieldView(self.app_ctx)
        vbox.addWidget(self.battlefield)

        # Middle: resources (left) + inventory (right)
        mid = QtWidgets.QWidget()
        mid_layout = QtWidgets.QGridLayout(mid)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setHorizontalSpacing(6)
        mid_layout.setVerticalSpacing(6)

        # Resources panel
        self.resources = ResourcesView(self.app_ctx)
        mid_layout.addWidget(self.resources.panel, 0, 0)

        # Inventory panel
        inv_group = QtWidgets.QGroupBox("背包 / 可合成 (iN / 名称 / cN)")
        inv_v = QtWidgets.QVBoxLayout(inv_group)
        self.list_inv = QtWidgets.QListWidget()
        inv_v.addWidget(self.list_inv)
        mid_layout.addWidget(inv_group, 0, 1)
        mid_layout.setColumnStretch(0, 0)
        mid_layout.setColumnStretch(1, 1)
        vbox.addWidget(mid)

        # Actions row (back/end)
        self.ops_row = OperationsRow(self.app_ctx)
        vbox.addWidget(self.ops_row.panel)

        # Log bottom
        self.log = LogPane()
        # inject shared log tag palette if available
        try:
            pal = getattr(self.app_ctx, '_log_tag_colors', None)
            if isinstance(pal, dict) and pal:
                self.log.set_palette(pal)
        except Exception:
            pass
        vbox.addWidget(self.log.panel)

        # Wire inventory widget to resources view for rendering
        self.resources.bind_inventory(self.list_inv)

        # Start controller and first render
        self.app_ctx.start_game()
        # Register back-reference for app_ctx to reach overlay/log
        try:
            setattr(self.app_ctx, '_window_ref', self)
        except Exception:
            pass
        # mount events bridge
        self._events = EventsBridge(self.app_ctx, self)
        try:
            self._events.mount()
        except Exception:
            pass
        # Signals
        self.btn_menu.clicked.connect(self.on_back_to_menu)
        # Timer to poll and update highlights during targeting session
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        # Scene overlay (hidden by default)
        self._overlay = QtWidgets.QWidget(self)
        self._overlay.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._overlay.setStyleSheet("background: rgba(20,20,20,0.6);")
        self._overlay.hide()
        self._overlay.raise_()
        self.resizeEvent = self._wrap_resize(self.resizeEvent)

        self.refresh_all()
    

    # --- UI actions ---
    def on_back_to_menu(self):
        try:
            from .menu_window import MenuWindow
            # unmount bridge
            try:
                self._events.unmount()
            except Exception:
                pass
            menu = MenuWindow(self.app_ctx)
            menu.show()
            self.close()
        except Exception as e:
            QtWidgets.QMessageBox.information(self, "提示", f"返回主菜单失败: {e}")

    # --- render helpers ---
    def refresh_all(self):
        g = getattr(self.app_ctx.controller, 'game', None)
        if g is not None:
            title = getattr(g, 'current_scene_title', None) or getattr(g, 'current_scene', '-')
            self.lbl_scene.setText(f"场景: {title}")
            # battlefield
            self.battlefield.render_from_game(g)
            self.battlefield.update_highlights()
            # resources + inventory
            self.resources.render()
            self.resources.render_inventory()

    def _tick(self):
        # update highlights if targeting active
        try:
            te = getattr(self.app_ctx, 'target_engine', None)
            if te and te.ctx and te.ctx.state in ('Selecting','Confirmable'):
                self.battlefield.update_highlights()
        except Exception:
            pass

    # --- overlay helpers ---
    def _wrap_resize(self, orig):
        def _wrapped(event):
            try:
                self._overlay.setGeometry(self.rect())
            except Exception:
                pass
            return orig(event)
        return _wrapped

    def show_scene_overlay(self):
        try:
            self._overlay.setGeometry(self.rect())
            self._overlay.setWindowOpacity(0.0)
            self._overlay.show()
            self._overlay.raise_()
            # fade in
            try:
                self._fade_timer and self._fade_timer.stop()
            except Exception:
                pass
            self._fade_timer = QtCore.QTimer(self)
            try:
                fade_interval = int(getattr(self.app_ctx, '_overlay_fade_interval', 16))
                fade_step = float(getattr(self.app_ctx, '_overlay_fade_step', 0.1))
                target_alpha = float(getattr(self.app_ctx, '_overlay_target_alpha', 0.8))
            except Exception:
                fade_interval, fade_step, target_alpha = 16, 0.1, 0.8
            self._fade_timer.setInterval(fade_interval)
            def _tick():
                try:
                    a = float(self._overlay.windowOpacity())
                    if a >= target_alpha:
                        self._overlay.setWindowOpacity(target_alpha)
                        self._fade_timer.stop()
                        return
                    self._overlay.setWindowOpacity(a + fade_step)
                except Exception:
                    self._fade_timer.stop()
            self._fade_timer.timeout.connect(_tick)
            self._fade_timer.start()
        except Exception:
            pass

    def hide_scene_overlay(self):
        try:
            # fade out
            try:
                self._fade_out and self._fade_out.stop()
            except Exception:
                pass
            self._fade_out = QtCore.QTimer(self)
            try:
                fade_interval = int(getattr(self.app_ctx, '_overlay_fade_interval', 16))
                fade_step = float(getattr(self.app_ctx, '_overlay_fade_step', 0.1))
            except Exception:
                fade_interval, fade_step = 16, 0.1
            self._fade_out.setInterval(fade_interval)
            def _tick():
                try:
                    a = float(self._overlay.windowOpacity())
                    if a <= 0.0:
                        self._overlay.setWindowOpacity(0.0)
                        self._fade_out.stop()
                        self._overlay.hide()
                        return
                    self._overlay.setWindowOpacity(max(0.0, a - fade_step))
                except Exception:
                    self._fade_out.stop()
                    self._overlay.hide()
            self._fade_out.timeout.connect(_tick)
            self._fade_out.start()
        except Exception:
            pass


