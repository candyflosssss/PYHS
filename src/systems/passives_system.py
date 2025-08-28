"""
事件驱动的被动系统：集中订阅战斗事件，根据装备声明的 passives 触发效果。

支持示例：
- lifesteal_on_attack_stat: 按指定属性调整值在攻击命中后为攻击者治疗（如 'str'/'wis'）
- heal_on_damaged_stat: 受伤后按指定属性调整值自疗（如 'wis'）
- reflect_on_damaged: 受伤后若有体力则消耗1反弹同等伤害到攻击者

用法：在游戏初始化后调用 setup() 一次（UI 或控制器启动时）。
"""
from __future__ import annotations

from typing import Dict

try:
    from src.core.events import subscribe as subscribe_event
except Exception:  # pragma: no cover
    def subscribe_event(*_a, **_k):  # type: ignore
        return None


_SUBS = []
_READY = False


def _get_attr(entity, key: str) -> int:
    try:
        k = str(key).lower()
        dnd = getattr(entity, 'dnd', None)
        if isinstance(dnd, dict):
            attrs = dnd.get('attrs') or dnd.get('attributes') or {}
            v = attrs.get(k, attrs.get(k.upper()))
            if v is not None:
                return int(v)
    except Exception:
        pass
    return 10


def _iter_equipped_items(owner):
    eq = getattr(owner, 'equipment', None)
    for it in (getattr(eq, 'left_hand', None), getattr(eq, 'right_hand', None), getattr(eq, 'armor', None)):
        if it:
            yield it


def _on_attack_resolved(_evt: str, payload: Dict):
    attacker = (payload or {}).get('attacker')
    damage = int((payload or {}).get('damage', 0))
    if not attacker or damage <= 0:
        return
    # lifesteal_on_attack_stat
    try:
        stat = None
        for it in _iter_equipped_items(attacker):
            v = getattr(it, 'passives', {}).get('lifesteal_on_attack_stat')
            if v:
                stat = str(v).lower(); break
        if stat:
            mod = (_get_attr(attacker, stat) - 10) // 2
            heal_amt = max(0, int(mod))
            if heal_amt > 0:
                prev = getattr(attacker, 'hp', 0)
                try:
                    attacker.heal(heal_amt)
                except Exception:
                    setattr(attacker, 'hp', min(getattr(attacker, 'hp', 0) + heal_amt, getattr(attacker, 'max_hp', getattr(attacker, 'hp', 0) + heal_amt)))
                game = getattr(getattr(attacker, 'equipment', None), 'owner', None)
                # 无法可靠取得 game 实例，这里仅依赖攻击流程已记录日志；跳过额外日志以简化。
    except Exception:
        pass


def _on_counter_resolved(_evt: str, payload: Dict):
    defender = (payload or {}).get('defender')
    attacker = (payload or {}).get('attacker')
    damage = int((payload or {}).get('damage', 0))
    if not defender or damage <= 0:
        return
    # heal_on_damaged_stat
    try:
        stat = None
        for it in _iter_equipped_items(defender):
            v = getattr(it, 'passives', {}).get('heal_on_damaged_stat')
            if v:
                stat = str(v).lower(); break
        if stat:
            mod = (_get_attr(defender, stat) - 10) // 2
            amt = max(0, int(mod))
            if amt > 0:
                try:
                    defender.heal(amt)
                except Exception:
                    setattr(defender, 'hp', min(getattr(defender, 'hp', 0) + amt, getattr(defender, 'max_hp', getattr(defender, 'hp', 0) + amt)))
    except Exception:
        pass
    # reflect_on_damaged
    try:
        do_reflect = False
        for it in _iter_equipped_items(defender):
            if getattr(it, 'passives', {}).get('reflect_on_damaged'):
                do_reflect = True; break
        if do_reflect and attacker and getattr(defender, 'stamina', 0) > 0:
            if getattr(defender, 'spend_stamina', None) and defender.spend_stamina(1):
                try:
                    prev = getattr(attacker, 'hp', 0)
                    dead = attacker.take_damage(damage)
                    # 由主流程处理死亡与清场切换；被动系统不负责。
                except Exception:
                    pass
    except Exception:
        pass


def setup():
    global _READY
    if _READY:
        return
    try:
        _SUBS.append(('attack_resolved', subscribe_event('attack_resolved', _on_attack_resolved)))
        _SUBS.append(('counter_resolved', subscribe_event('counter_resolved', _on_counter_resolved)))
        _READY = True
    except Exception:
        pass
