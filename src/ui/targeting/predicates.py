"""Predicate library for filtering candidates.
"""
from __future__ import annotations
from typing import Any

def _get_attr_from_entity(entity, name: str, default: int = 10) -> int:
    try:
        dnd = getattr(entity, 'dnd', None)
        if isinstance(dnd, dict):
            attrs = dnd.get('attrs') or dnd.get('attributes') or {}
            v = attrs.get(name) or attrs.get(name.upper())
            return int(v if v is not None else default)
    except Exception:
        pass
    return int(default)

def is_alive(app, src_token: str, tgt_token: str) -> bool:
    try:
        obj = _resolve_token(app, tgt_token)
        return getattr(obj, 'hp', 1) > 0
    except Exception:
        return False

def can_be_attacked(app, src_token: str, tgt_token: str) -> bool:
    try:
        obj = _resolve_token(app, tgt_token)
        return bool(getattr(obj, 'can_be_attacked', True)) and getattr(obj, 'hp', 1) > 0
    except Exception:
        return False

def is_wounded(app, src_token: str, tgt_token: str) -> bool:
    try:
        obj = _resolve_token(app, tgt_token)
        hp = int(getattr(obj, 'hp', 0))
        mx = int(getattr(obj, 'max_hp', hp))
        return hp > 0 and hp < mx
    except Exception:
        return False

def not_self(app, src_token: str, tgt_token: str) -> bool:
    try:
        return src_token != tgt_token
    except Exception:
        return True

def is_heavily_wounded(app, src_token: str, tgt_token: str) -> bool:
    """目标生命≤30%最大值"""
    try:
        obj = _resolve_token(app, tgt_token)
        hp = int(getattr(obj, 'hp', 0)); mx = int(getattr(obj, 'max_hp', hp or 1))
        return hp > 0 and hp * 10 <= mx * 3
    except Exception:
        return False

def has_shield(app, src_token: str, tgt_token: str) -> bool:
    try:
        obj = _resolve_token(app, tgt_token)
        eq = getattr(obj, 'equipment', None)
        if not eq:
            return False
        lh = getattr(eq, 'left_hand', None)
        if lh is None:
            return False
        try:
            from src.systems.equipment_system import ShieldItem
            return isinstance(lh, ShieldItem)
        except Exception:
            return bool(getattr(lh, 'defense', 0)) and (getattr(lh, 'slot_type', '') == 'left_hand') and (not getattr(lh, 'is_two_handed', False))
    except Exception:
        return False

def is_mage_like(app, src_token: str, tgt_token: str) -> bool:
    try:
        obj = _resolve_token(app, tgt_token)
        tags = [str(t).lower() for t in (getattr(obj, 'tags', []) or [])]
        if 'mage' in tags or 'wizard' in tags:
            return True
        return _get_attr_from_entity(obj, 'int', 10) >= 12
    except Exception:
        return False

def dual_wielding(app, src_token: str, tgt_token: str) -> bool:
    try:
        obj = _resolve_token(app, tgt_token)
        eq = getattr(obj, 'equipment', None)
        if not eq:
            return False
        return bool(getattr(eq, 'left_hand', None) and getattr(eq, 'right_hand', None) and not getattr(eq.left_hand, 'is_two_handed', False))
    except Exception:
        return False

def src_int_gte_tgt_int(app, src_token: str, tgt_token: str) -> bool:
    try:
        s = _resolve_token(app, src_token)
        t = _resolve_token(app, tgt_token)
        return _get_attr_from_entity(s, 'int') >= _get_attr_from_entity(t, 'int')
    except Exception:
        return False

def _resolve_token(app, token: str) -> Any:
    if token.startswith('e'):
        i = int(token[1:]) - 1
        return app.controller.game.enemies[i]
    if token.startswith('m'):
        i = int(token[1:]) - 1
        return app.controller.game.player.board[i]
    raise ValueError('bad token')

PREDICATE_MAP = {
    'is_alive': is_alive,
    'can_be_attacked': can_be_attacked,
    'is_wounded': is_wounded,
    'not_self': not_self,
    'is_heavily_wounded': is_heavily_wounded,
    'has_shield': has_shield,
    'is_mage_like': is_mage_like,
    'dual_wielding': dual_wielding,
    'src_int_gte_tgt_int': src_int_gte_tgt_int,
}
