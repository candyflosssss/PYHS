"""超轻量事件总线（同步、进程内）

用法：
- from src.core.events import publish, subscribe, unsubscribe
- 订阅后返回回调引用，保存以便取消订阅

事件命名建议：小写+下划线，如 'enemy_damaged'、'enemy_died'、'scene_changed'。
payload 结构不做强约束，推荐携带发生实体与少量上下文。
"""
from __future__ import annotations
from typing import Callable, List, DefaultDict
from collections import defaultdict


class _EventBus:
    def __init__(self) -> None:
        self._subs: DefaultDict[str, List[Callable[[str, dict], None]]] = defaultdict(list)

    def subscribe(self, event: str, cb: Callable[[str, dict], None]) -> Callable[[str, dict], None]:
        try:
            self._subs[event].append(cb)
        except Exception:
            pass
        return cb

    def unsubscribe(self, event: str, cb: Callable[[str, dict], None]) -> None:
        try:
            if event in self._subs and cb in self._subs[event]:
                self._subs[event].remove(cb)
        except Exception:
            pass

    def publish(self, event: str, payload: dict | None = None) -> None:
        try:
            listeners = list(self._subs.get(event, []))
        except Exception:
            listeners = []
        for cb in listeners:
            try:
                cb(event, payload or {})
            except Exception:
                # 防御性：单个订阅者异常不影响其他订阅者
                continue


_BUS = _EventBus()


def subscribe(event: str, cb: Callable[[str, dict], None]):
    return _BUS.subscribe(event, cb)


def unsubscribe(event: str, cb: Callable[[str, dict], None]):
    return _BUS.unsubscribe(event, cb)


def publish(event: str, payload: dict | None = None):
    return _BUS.publish(event, payload)
