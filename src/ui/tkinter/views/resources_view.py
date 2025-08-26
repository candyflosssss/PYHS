from __future__ import annotations

from typing import Any, Callable, Optional

from tkinter import ttk
from .. import ui_utils as U

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
        self._res_container = None
        self._inv_listbox = None
        self.game = None

    def set_context(self, game):
        """让视图直接持有 game 引用（可选）。"""
        self.game = game

    def attach(self, res_container, inv_listbox):
        """将资源按钮容器与背包 Listbox 交给视图托管。"""
        self._res_container = res_container
        self._inv_listbox = inv_listbox

    def render(self):
        """渲染资源按钮区域。"""
        if getattr(self.app, '_suspend_ui_updates', False):
            # 若在抑制窗口，交由 app 合并标记；视图不主动冲刷
            setattr(self.app, '_pending_resource_refresh', True)
            setattr(self.app, '_pending_ops_refresh', True)
            return
        c = self._res_container
        if c is None:
            return
        # 采集资源
        try:
            s = self.app.controller.game.get_state()
            res = s.get('resources', [])
        except Exception:
            res = []

        def fmt_resource(r) -> str:
            try:
                if isinstance(r, dict):
                    name = r.get('name') or r.get('title') or str(r)
                    rtype = r.get('type')
                else:
                    name = str(r)
                    rtype = None
            except Exception:
                name = str(r)
                rtype = None
            try:
                clean = U.clean_ansi(name)
            except Exception:
                clean = name
            return f"{clean}" + (f" ({rtype})" if rtype else "")

        target_texts = [fmt_resource(r) for r in res]

        # 仅保留按钮子项
        children = [w for w in c.winfo_children() if isinstance(w, ttk.Button)]

        def ensure_placeholder(show: bool):
            for w in list(c.winfo_children()):
                if not isinstance(w, ttk.Button):
                    try:
                        w.destroy()
                    except Exception:
                        pass
            if show:
                ttk.Label(c, text="(空)", foreground="#888").pack(anchor='w')

        if not target_texts:
            for btn in children:
                try:
                    btn.destroy()
                except Exception:
                    pass
            ensure_placeholder(True)
            return

        ensure_placeholder(False)

        if len(children) < len(target_texts):
            for _ in range(len(target_texts) - len(children)):
                btn = ttk.Button(c, text="", width=18, style="Tiny.TButton")
                btn.pack(side='top', anchor='w', padx=2, pady=2)
                children.append(btn)
        elif len(children) > len(target_texts):
            for btn in children[len(target_texts):]:
                try:
                    btn.destroy()
                except Exception:
                    pass
            children = children[:len(target_texts)]

        for i, (btn, text) in enumerate(zip(children, target_texts), start=1):
            try:
                if btn.cget('text') != text:
                    btn.configure(text=text)
                btn.configure(command=(lambda idx=i: self.app._pick_resource(idx)))
            except Exception:
                pass

    def render_inventory(self):
        """仅刷新背包列表（不重绘卡片/场景）。"""
        lb = self._inv_listbox
        if lb is None:
            return
        try:
            text = self.app.controller._section_inventory() if self.app.controller else ''
            lb.delete(0, 'end')
            for line in (text or '').splitlines():
                s = (line or '').strip().rstrip()
                if not s:
                    continue
                if s.endswith('):') or s.endswith(':'):
                    continue
                lb.insert('end', s)
        except Exception:
            pass

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
            self.render()
            # 背包列表需同步刷新
            self.render_inventory()
            # 操作栏可能依赖可用物品 -> 直接请求 OperationsView 渲染
            try:
                ops = (getattr(self.app, 'views', {}) or {}).get('ops')
                if ops and hasattr(self.app, 'frm_operations'):
                    ops.render(self.app.frm_operations)
            except Exception:
                pass
        except Exception:
            pass

    def _on_res_changed(self, _evt: str, _payload: dict):
        try:
            self.render()
            # 资源变化通常伴随背包变化（拾取/使用）
            self.render_inventory()
        except Exception:
            pass

    def _on_res_zone(self, _evt: str, _payload: dict):
        try:
            self.render()
            self.render_inventory()
            # 操作栏可能依赖资源可用性
            try:
                ops = (getattr(self.app, 'views', {}) or {}).get('ops')
                if ops and hasattr(self.app, 'frm_operations'):
                    ops.render(self.app.frm_operations)
            except Exception:
                pass
        except Exception:
            pass
