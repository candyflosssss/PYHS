from __future__ import annotations

try:
    from .. import operations as tk_operations
except Exception:  # type: no cover
    tk_operations = None  # type: ignore


class OperationsView:
    """Owns rendering of the operations toolbar.

    Keep it thin and delegate to existing operations renderer.
    """

    def __init__(self, app):
        self.app = app

    def mount(self):
        # no event subscription here; other views ask to refresh ops
        return

    def unmount(self):
        return

    def render(self, container):
        if tk_operations is None:
            return None
        return tk_operations.render_operations(self.app, container)
