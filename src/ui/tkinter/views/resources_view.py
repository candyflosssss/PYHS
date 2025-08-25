from __future__ import annotations

from typing import Any, Callable

try:
    from src.core.events import subscribe as subscribe_event, unsubscribe as unsubscribe_event
except Exception:  # pragma: no cover
    def subscribe_event(*_a, **_k):  # type: ignore
        return None
    def unsubscribe_event(*_a, **_k):  # type: ignore
        return None


class ResourcesView:
    """Owns resource/inventory related events and updates side pane.

    Subscribes to resource_changed, inventory_changed and the ObservableList
    variants (resource_added/removed/resources_*). It calls app._render_resources()
    and app._render_operations() as needed.
    """

    def __init__(self, app):
        self.app = app
        self._subs: list[tuple[str, Callable]] = []

    def mount(self):
        if self._subs:
            return
        # inventory/resource direct events
        self._subs.append(('inventory_changed', subscribe_event('inventory_changed', self._on_inv_changed)))
        self._subs.append(('resource_changed', subscribe_event('resource_changed', self._on_res_changed)))
        # zone variants for resources
        for evt in ('resource_added','resource_removed','resources_cleared','resources_reset','resources_changed'):
            self._subs.append((evt, subscribe_event(evt, self._on_res_zone)))

    def unmount(self):
        for evt, cb in (self._subs or []):
            try:
                unsubscribe_event(evt, cb)
            except Exception:
                pass
        self._subs.clear()

    def _on_inv_changed(self, _evt: str, _payload: dict):
        try:
            self.app._render_resources()
            # 背包列表需同步刷新
            self.app._refresh_inventory_only()
            # 操作栏可能依赖可用物品
            self.app._render_operations()
        except Exception:
            pass

    def _on_res_changed(self, _evt: str, _payload: dict):
        try:
            self.app._render_resources()
            # 资源变化通常伴随背包变化（拾取/使用）
            self.app._refresh_inventory_only()
        except Exception:
            pass

    def _on_res_zone(self, _evt: str, _payload: dict):
        try:
            self.app._render_resources()
            self.app._refresh_inventory_only()
            # operations may depend on resources availability
            self.app._render_operations()
        except Exception:
            pass
