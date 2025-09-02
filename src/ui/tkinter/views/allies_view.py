from __future__ import annotations


class AlliesView:
    """空实现（占位）：移除伙伴区界面逻辑，保留卡片组件供后续重设使用。

    保留 API 以兼容 app：set_context/attach/mount/unmount/render_all。
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
        # 不再订阅任何事件
        return

    def unmount(self):
        # 无订阅可取消
        return

    def render_all(self, container):
        # 清空容器与索引映射，保持 app 兼容
        try:
            for ch in list(container.winfo_children()):
                ch.destroy()
        except Exception:
            pass
        try:
            if hasattr(self.app, 'card_wraps'):
                self.app.card_wraps.clear()
        except Exception:
            pass
        return
