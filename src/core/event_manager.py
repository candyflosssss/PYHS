"""
统一事件管理器 - 减少重复的事件发布代码，提供更好的错误处理
"""

from typing import Any, Dict, List, Callable, Optional
import logging
from functools import wraps


class EventManager:
    """统一事件管理器"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._logger = logging.getLogger(__name__)
    
    def publish(self, event_name: str, payload: Dict[str, Any] = None) -> bool:
        """
        发布事件
        
        Args:
            event_name: 事件名称
            payload: 事件数据
            
        Returns:
            bool: 是否成功发布
        """
        try:
            if payload is None:
                payload = {}
            
            # 记录事件发布
            self._logger.debug(f"发布事件: {event_name} - {payload}")
            
            # 调用所有订阅者
            if event_name in self._subscribers:
                for callback in self._subscribers[event_name]:
                    try:
                        callback(event_name, payload)
                    except Exception as e:
                        self._logger.error(f"事件订阅者执行失败: {event_name} - {e}")
            
            return True
            
        except Exception as e:
            self._logger.error(f"事件发布失败: {event_name} - {e}")
            return False
    
    def subscribe(self, event_name: str, callback: Callable) -> bool:
        """
        订阅事件
        
        Args:
            event_name: 事件名称
            callback: 回调函数
            
        Returns:
            bool: 是否成功订阅
        """
        try:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)
                self._logger.debug(f"订阅事件: {event_name}")
            
            return True
            
        except Exception as e:
            self._logger.error(f"事件订阅失败: {event_name} - {e}")
            return False
    
    def unsubscribe(self, event_name: str, callback: Callable) -> bool:
        """
        取消订阅事件
        
        Args:
            event_name: 事件名称
            callback: 回调函数
            
        Returns:
            bool: 是否成功取消订阅
        """
        try:
            if event_name in self._subscribers:
                if callback in self._subscribers[event_name]:
                    self._subscribers[event_name].remove(callback)
                    self._logger.debug(f"取消订阅事件: {event_name}")
                    return True
            
            return False
            
        except Exception as e:
            self._logger.error(f"取消订阅失败: {event_name} - {e}")
            return False
    
    def clear_subscribers(self, event_name: str = None) -> bool:
        """
        清除订阅者
        
        Args:
            event_name: 事件名称，如果为None则清除所有
            
        Returns:
            bool: 是否成功清除
        """
        try:
            if event_name is None:
                self._subscribers.clear()
                self._logger.debug("清除所有事件订阅者")
            elif event_name in self._subscribers:
                self._subscribers[event_name].clear()
                self._logger.debug(f"清除事件订阅者: {event_name}")
            
            return True
            
        except Exception as e:
            self._logger.error(f"清除订阅者失败: {event_name} - {e}")
            return False
    
    def get_subscriber_count(self, event_name: str) -> int:
        """获取指定事件的订阅者数量"""
        return len(self._subscribers.get(event_name, []))
    
    def get_all_events(self) -> List[str]:
        """获取所有事件名称"""
        return list(self._subscribers.keys())


# 全局事件管理器实例
_event_manager = EventManager()


def publish_event(event_name: str, payload: Dict[str, Any] = None) -> bool:
    """全局事件发布函数"""
    return _event_manager.publish(event_name, payload)


def subscribe_event(event_name: str, callback: Callable) -> bool:
    """全局事件订阅函数"""
    return _event_manager.subscribe(event_name, callback)


def unsubscribe_event(event_name: str, callback: Callable) -> bool:
    """全局事件取消订阅函数"""
    return _event_manager.unsubscribe(event_name, callback)


def safe_publish_event(event_name: str, payload: Dict[str, Any] = None) -> None:
    """
    安全的事件发布函数，不会抛出异常
    
    Args:
        event_name: 事件名称
        payload: 事件数据
    """
    try:
        _event_manager.publish(event_name, payload)
    except Exception:
        pass
