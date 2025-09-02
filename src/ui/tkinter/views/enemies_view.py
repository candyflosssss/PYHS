from __future__ import annotations


class EnemiesView:
    """空实现（占位）：移除敌人区界面逻辑，保留公共 API 以保证应用可运行。

    当前不渲染任何卡片，也不订阅事件。
    """

    def __init__(self, app):
        self.app = app
        self.game = None
        self._container = None

    def set_context(self, game):
        self.game = game

    def attach(self, container):
        self._container = container

    def mount(self):
        return

    def unmount(self):
        return

    def render_all(self, container):
        # 清空容器与索引映射，保持 app 兼容
        try:
            for ch in list(container.winfo_children()):
                ch.destroy()
        except Exception:
            pass
        try:
            if hasattr(self.app, 'enemy_card_wraps'):
                self.app.enemy_card_wraps.clear()
        except Exception:
            pass
        return
