from __future__ import annotations
from typing import Callable, Iterable, Iterator, Generic, TypeVar, Optional
from src.core.events import publish as publish_event

T = TypeVar('T')

class ObservableList(Generic[T]):
    """一个带事件的列表代理。常用方法（append/remove/pop/clear/extend/insert）会发布事件。
    事件字段：on_add/on_remove/on_clear/on_reset/on_change（可选，统一变更通知）
    """
    def __init__(self,
                 initial: Optional[Iterable[T]] = None,
                 *,
                 on_add: Optional[str] = None,
                 on_remove: Optional[str] = None,
                 on_clear: Optional[str] = None,
                 on_reset: Optional[str] = None,
                 on_change: Optional[str] = None,
                 to_payload: Optional[Callable[[T], dict | str]] = None):
        self._data: list[T] = list(initial) if initial is not None else []
        self._on_add = on_add
        self._on_remove = on_remove
        self._on_clear = on_clear
        self._on_reset = on_reset
        self._on_change = on_change
        self._to_payload = to_payload or (lambda x: x)

    # --- 事件帮助 ---
    def _emit(self, evt: Optional[str], payload: dict | None = None):
        if not evt:
            return
        try:
            publish_event(evt, payload or {})
        except Exception:
            pass
        if self._on_change and evt != self._on_change:
            try:
                publish_event(self._on_change, payload or {})
            except Exception:
                pass

    # --- 列表接口 ---
    def append(self, item: T):
        self._data.append(item)
        self._emit(self._on_add, {'item': self._to_payload(item)})
        return None

    def extend(self, items: Iterable[T]):
        for it in items:
            self.append(it)
        return None

    def insert(self, index: int, item: T):
        self._data.insert(index, item)
        self._emit(self._on_add, {'item': self._to_payload(item), 'index': index})
        return None

    def remove(self, item: T):
        self._data.remove(item)
        self._emit(self._on_remove, {'item': self._to_payload(item)})
        return None

    def pop(self, index: int = -1) -> T:
        it = self._data.pop(index)
        self._emit(self._on_remove, {'item': self._to_payload(it), 'index': index})
        return it

    def clear(self):
        if not self._data:
            return None
        self._data.clear()
        self._emit(self._on_clear, {})
        return None

    def reset(self, items: Iterable[T]):
        self._data = list(items)
        self._emit(self._on_reset, {'size': len(self._data)})
        return None

    # --- 魔法方法代理 ---
    def __iter__(self) -> Iterator[T]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, idx):
        return self._data[idx]

    def __setitem__(self, idx, value):
        self._data[idx] = value
        self._emit(self._on_change, {'index': idx})

    def __delitem__(self, idx):
        it = self._data[idx]
        del self._data[idx]
        self._emit(self._on_remove, {'item': self._to_payload(it), 'index': idx})

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def to_list(self) -> list[T]:
        return list(self._data)
