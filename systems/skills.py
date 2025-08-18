"""技能/被动判定辅助
- 基于随从的 `tags/passive/skills` 字段提供常用语义判断与数值推导。
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


def _get(obj, name: str, default=None):
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def has_tag(unit, tag: str) -> bool:
    tags = _get(unit, 'tags', []) or []
    try:
        return tag in [str(t).lower() for t in tags]
    except Exception:
        return False


def get_passive(unit, key: str, default=None):
    p = _get(unit, 'passive', {}) or {}
    try:
        return p.get(key, default)
    except Exception:
        return default


def is_healer(unit) -> bool:
    if has_tag(unit, 'healer'):
        return True
    # 兼容 skills 列表中含 heal 字段
    skills = _get(unit, 'skills', []) or []
    try:
        for s in skills:
            if isinstance(s, dict) and ('heal' in s or str(s.get('name','')).find('治疗') >= 0):
                return True
    except Exception:
        pass
    return False


def get_heal_amount(unit, base_attack: int | None = None) -> int:
    """治疗量由当前攻击力决定，忽略技能里的固定 heal 数值。
    兼容旧签名：base_attack 参数将被忽略。
    """
    try:
        return max(0, int(getattr(unit, 'attack', 0)))
    except Exception:
        return 0


def should_counter(attacker, defender) -> bool:
    """是否触发反击：
    - 进攻方带 no_counter 被动时不反击
    - 防守方攻击力<=0 不反击
    - 否则允许反击
    """
    if get_passive(attacker, 'no_counter', False):
        return False
    try:
        if getattr(defender, 'attack', 0) <= 0:
            return False
    except Exception:
        return True
    return True
