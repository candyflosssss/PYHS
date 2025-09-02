from __future__ import annotations

"""轻量存档/世界进度管理

职责：
- 维护每个玩家的世界进度（场景内已击杀的敌人与已拾取的资源不会重生）。
- 提供最小 API：加载/保存、场景键标准化、令牌生成、应用进度过滤、标记事件。

注意：本模块当前只做“敌人与资源不重生”的持久化；
后续可扩展背包/队伍快照等功能。
"""

import json
import os
from typing import Dict, Any, List

from src import app_config as CFG


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


class SaveManager:
    def __init__(self, player_name: str):
        self.player_name = str(player_name or 'player')
        self.path = self._default_save_path(self.player_name)
        self.data: Dict[str, Any] = {
            'version': 1,
            'player': {
                'name': self.player_name,
            },
            # 按场景记录：已击杀敌人与已采集资源（令牌→计数）
            'scenes': {},
            # 可选：持久背包与队伍
            # 'inventory': [ {spec}+qty ],
            # 'party': [ { token, name, base_atk, hp, max_hp, equipment:{...} } ]
        }

    # --- 路径/加载/保存 ---
    @staticmethod
    def _default_save_path(player_name: str) -> str:
        base = CFG.user_data_dir()
        safe = ''.join(ch for ch in player_name if ch.isalnum() or ch in ('_', '-')) or 'player'
        return os.path.join(base, f'save_{safe}.json')

    @classmethod
    def load(cls, player_name: str) -> 'SaveManager':
        mgr = cls(player_name)
        try:
            if os.path.isfile(mgr.path):
                with open(mgr.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    mgr.data.update(data)
        except Exception:
            # 坏档不阻断运行，使用内置默认
            pass
        return mgr

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            # 原子替换（尽力而为）
            try:
                if os.path.exists(self.path):
                    os.replace(tmp, self.path)
                else:
                    os.rename(tmp, self.path)
            except Exception:
                # 回退直接写
                with open(self.path, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            # 静默失败，不影响游戏
            pass

    # --- 场景键与令牌 ---
    @staticmethod
    def normalize_scene_key(path: str) -> str:
        try:
            return os.path.abspath(path)
        except Exception:
            return str(path or '')

    @staticmethod
    def enemy_token(enemy) -> str:
        try:
            name = getattr(enemy, 'name', None) or getattr(enemy, 'display_name', None) or str(enemy)
        except Exception:
            name = 'enemy'
        try:
            base_atk = _safe_int(getattr(enemy, 'base_atk', getattr(enemy, 'attack', 0)))
        except Exception:
            base_atk = 0
        try:
            max_hp = _safe_int(getattr(enemy, 'max_hp', getattr(enemy, 'hp', 0)))
        except Exception:
            max_hp = 0
        return f"{name}|{base_atk}|{max_hp}"

    @staticmethod
    def resource_token(res) -> str:
        try:
            name = getattr(res, 'name', None) or str(res)
        except Exception:
            name = 'resource'
        try:
            item_type = getattr(res, 'item_type', '')
        except Exception:
            item_type = ''
        try:
            val = _safe_int(getattr(res, 'effect_value', 0))
        except Exception:
            val = 0
        return f"{name}|{item_type}|{val}"

    # --- 应用进度：过滤已清除对象 ---
    def apply_scene_progress(self, scene_key: str, enemies_list: List[Any], resources_list: List[Any]) -> None:
        """根据已记录的击杀/采集计数，原地过滤掉不应再出现的敌人与资源。"""
        key = self.normalize_scene_key(scene_key)
        sc = self.data.setdefault('scenes', {}).setdefault(key, {})
        killed: Dict[str, int] = dict(sc.get('enemies_killed', {}))
        taken: Dict[str, int] = dict(sc.get('resources_collected', {}))

        # 过滤敌人：按计数“消费”
        if enemies_list:
            consumed: Dict[str, int] = {}
            remain = []
            for e in list(enemies_list):
                tok = self.enemy_token(e)
                used = consumed.get(tok, 0)
                quota = _safe_int(killed.get(tok, 0))
                if used < quota:
                    # 标记为已消耗，不加入剩余
                    consumed[tok] = used + 1
                    continue
                remain.append(e)
            # 就地替换
            try:
                enemies_list.clear(); enemies_list.extend(remain)
            except Exception:
                pass

        # 过滤资源：按计数“消费”
        if resources_list:
            consumed_r: Dict[str, int] = {}
            remain_r = []
            for r in list(resources_list):
                tok = self.resource_token(r)
                used = consumed_r.get(tok, 0)
                quota = _safe_int(taken.get(tok, 0))
                if used < quota:
                    consumed_r[tok] = used + 1
                    continue
                remain_r.append(r)
            try:
                resources_list.clear(); resources_list.extend(remain_r)
            except Exception:
                pass

    # --- 标记事件 ---
    def mark_enemy_killed(self, scene_key: str, token: str) -> None:
        key = self.normalize_scene_key(scene_key)
        sc = self.data.setdefault('scenes', {}).setdefault(key, {})
        m = sc.setdefault('enemies_killed', {})
        m[token] = _safe_int(m.get(token, 0)) + 1

    def mark_resource_collected(self, scene_key: str, token: str) -> None:
        key = self.normalize_scene_key(scene_key)
        sc = self.data.setdefault('scenes', {}).setdefault(key, {})
        m = sc.setdefault('resources_collected', {})
        m[token] = _safe_int(m.get(token, 0)) + 1

    # --- 背包快照/恢复 ---
    def snapshot_inventory(self, inventory) -> None:
        """将背包序列化到存档：[{name,type,qty,...}]。"""
        try:
            from src.systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
            from src.systems.inventory import ConsumableItem, MaterialItem, EquipmentItem
        except Exception:
            WeaponItem = ArmorItem = ShieldItem = ConsumableItem = MaterialItem = EquipmentItem = tuple()  # type: ignore

        out: List[Dict[str, Any]] = []
        try:
            for slot in getattr(inventory, 'slots', []) or []:
                it = getattr(slot, 'item', None)
                qty = _safe_int(getattr(slot, 'quantity', 0))
                if not it or qty <= 0:
                    continue
                spec: Dict[str, Any] = {
                    'name': getattr(it, 'name', '物品'),
                    'qty': qty,
                }
                # 设备系统装备
                if isinstance(it, WeaponItem):
                    spec.update({'type': 'weapon', 'attack': _safe_int(getattr(it, 'attack', 0)),
                                 'slot_type': getattr(it, 'slot_type', 'right_hand'),
                                 'two_handed': bool(getattr(it, 'is_two_handed', False)),
                                 'active_skills': list(getattr(it, 'active_skills', []) or []),
                                 'passives': dict(getattr(it, 'passives', {}) or {})})
                elif isinstance(it, ArmorItem):
                    spec.update({'type': 'armor', 'defense': _safe_int(getattr(it, 'defense', 0)),
                                 'active_skills': list(getattr(it, 'active_skills', []) or []),
                                 'passives': dict(getattr(it, 'passives', {}) or {})})
                elif isinstance(it, ShieldItem):
                    spec.update({'type': 'shield', 'defense': _safe_int(getattr(it, 'defense', 0)),
                                 'attack': _safe_int(getattr(it, 'attack', 0)),
                                 'active_skills': list(getattr(it, 'active_skills', []) or []),
                                 'passives': dict(getattr(it, 'passives', {}) or {})})
                # 消耗品/材料
                elif isinstance(it, ConsumableItem):
                    # 若能推断效果，则记录 effect 标记
                    spec.update({'type': 'consumable'})
                    # 尝试从描述推断（形如: 恢复X点生命）
                    try:
                        desc = getattr(it, 'description', '') or ''
                        if '恢复' in desc and '生命' in desc:
                            import re
                            m = re.search(r"恢复(\d+)点生命", desc)
                            if m:
                                spec['effect'] = 'heal_hp'
                                spec['value'] = _safe_int(m.group(1), 0)
                    except Exception:
                        pass
                elif isinstance(it, MaterialItem):
                    spec.update({'type': 'material'})
                elif isinstance(it, EquipmentItem):
                    spec.update({'type': 'equipment'})
                else:
                    spec.update({'type': 'item'})
                out.append(spec)
            self.data['inventory'] = out
        except Exception:
            pass

    def restore_inventory(self, inventory) -> None:
        try:
            items = self.data.get('inventory')
            if not isinstance(items, list):
                return
            # 清空并按存档重建
            try:
                inventory.clear(game=None)
            except Exception:
                try:
                    inventory.slots.clear()
                except Exception:
                    pass
            for spec in items:
                it = self._spec_to_item(spec)
                qty = _safe_int(spec.get('qty', 1), 1)
                if it is not None and qty > 0:
                    try:
                        # 使用 add_item 以触发事件
                        inventory.add_item(it, qty)
                    except Exception:
                        pass
        except Exception:
            pass

    def has_inventory(self) -> bool:
        try:
            inv = self.data.get('inventory')
            return isinstance(inv, list) and len(inv) > 0
        except Exception:
            return False

    def _spec_to_item(self, spec: Dict[str, Any]):
        try:
            from src.systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
            from src.systems.inventory import ConsumableItem, MaterialItem, EquipmentItem, Item
        except Exception:
            return None
        t = (spec or {}).get('type')
        name = (spec or {}).get('name') or '物品'
        if t == 'weapon':
            return WeaponItem(name, description=f"保存装备:{name}", durability=100,
                               attack=_safe_int(spec.get('attack', 0)),
                               slot_type=spec.get('slot_type') or 'right_hand',
                               is_two_handed=bool(spec.get('two_handed', False)),
                               active_skills=list(spec.get('active_skills', []) or []),
                               passives=dict(spec.get('passives', {}) or {}))
        if t == 'armor':
            return ArmorItem(name, description=f"保存装备:{name}", durability=100,
                              defense=_safe_int(spec.get('defense', 0)),
                              active_skills=list(spec.get('active_skills', []) or []),
                              passives=dict(spec.get('passives', {}) or {}))
        if t == 'shield':
            return ShieldItem(name, description=f"保存装备:{name}", durability=100,
                              defense=_safe_int(spec.get('defense', 0)),
                              attack=_safe_int(spec.get('attack', 0)),
                              active_skills=list(spec.get('active_skills', []) or []),
                              passives=dict(spec.get('passives', {}) or {}))
        if t == 'consumable':
            eff = spec.get('effect'); val = _safe_int(spec.get('value', 0))
            effect_fn = None
            if eff == 'heal_hp' and val > 0:
                def _eff(player, target):
                    try:
                        player.heal(val)
                    except Exception:
                        pass
                effect_fn = _eff
            return ConsumableItem(name, description=spec.get('description', ''), effect=effect_fn)
        if t == 'material':
            return MaterialItem(name, description=spec.get('description', ''))
        if t == 'equipment':
            return EquipmentItem(name, description=spec.get('description', ''))
        # 回退为普通 Item
        try:
            return Item(name)
        except Exception:
            return None

    # --- 队伍(伙伴)快照与应用（不含体力） ---
    def snapshot_party(self, board: List[Any]) -> None:
        out: List[Dict[str, Any]] = []
        try:
            from src.systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
        except Exception:
            WeaponItem = ArmorItem = ShieldItem = tuple()  # type: ignore
        for m in board or []:
            try:
                tok = self._member_token(m)
                ent = {
                    'token': tok,
                    'name': getattr(m, 'name', getattr(m, 'display_name', str(m))),
                    'base_atk': _safe_int(getattr(m, 'base_atk', getattr(m, 'attack', 0))),
                    'max_hp': _safe_int(getattr(m, 'max_hp', getattr(m, 'hp', 0))),
                    'hp': _safe_int(getattr(m, 'hp', 0)),
                }
                # 装备
                eq = getattr(m, 'equipment', None)
                if eq:
                    eq_spec: Dict[str, Any] = {}
                    for slot_name in ('left_hand', 'right_hand', 'armor'):
                        it = getattr(eq, slot_name, None)
                        if not it:
                            continue
                        if isinstance(it, WeaponItem):
                            eq_spec[slot_name] = {'type': 'weapon', 'name': it.name, 'attack': _safe_int(it.attack), 'slot_type': getattr(it, 'slot_type', 'right_hand'), 'two_handed': bool(getattr(it, 'is_two_handed', False)), 'active_skills': list(getattr(it, 'active_skills', []) or []), 'passives': dict(getattr(it, 'passives', {}) or {})}
                        elif isinstance(it, ArmorItem):
                            eq_spec[slot_name] = {'type': 'armor', 'name': it.name, 'defense': _safe_int(it.defense), 'active_skills': list(getattr(it, 'active_skills', []) or []), 'passives': dict(getattr(it, 'passives', {}) or {})}
                        elif isinstance(it, ShieldItem):
                            eq_spec[slot_name] = {'type': 'shield', 'name': it.name, 'defense': _safe_int(it.defense), 'attack': _safe_int(getattr(it, 'attack', 0)), 'active_skills': list(getattr(it, 'active_skills', []) or []), 'passives': dict(getattr(it, 'passives', {}) or {})}
                        else:
                            # 其他类型暂不保存
                            continue
                    ent['equipment'] = eq_spec
                out.append(ent)
            except Exception:
                continue
        self.data['party'] = out

    def apply_party_snapshot_to_board(self, board: List[Any]) -> None:
        saved: List[Dict[str, Any]] = list(self.data.get('party', []) or [])
        if not saved:
            return
        # 构建 token -> entries list 映射，以支持重复角色
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for ent in saved:
            tok = ent.get('token')
            if not tok:
                continue
            buckets.setdefault(tok, []).append(ent)
        # 逐个棋子应用
        for m in board or []:
            tok = self._member_token(m)
            lst = buckets.get(tok)
            if not lst:
                continue
            ent = lst.pop(0)
            # 恢复 HP（不动体力）
            try:
                mhp = _safe_int(ent.get('max_hp', getattr(m, 'max_hp', 0)))
                hpv = _safe_int(ent.get('hp', getattr(m, 'hp', 0)))
                setattr(m, 'max_hp', mhp or getattr(m, 'max_hp', mhp))
                setattr(m, 'hp', max(0, min(mhp or getattr(m, 'max_hp', 0), hpv)))
            except Exception:
                pass
            # 恢复装备
            try:
                eq_spec = ent.get('equipment') or {}
                self._apply_equipment_spec(m, eq_spec)
            except Exception:
                pass

    def _member_token(self, m) -> str:
        try:
            name = getattr(m, 'name', None) or getattr(m, 'display_name', None) or str(m)
        except Exception:
            name = 'ally'
        try:
            base_atk = _safe_int(getattr(m, 'base_atk', getattr(m, 'attack', 0)))
        except Exception:
            base_atk = 0
        try:
            max_hp = _safe_int(getattr(m, 'max_hp', getattr(m, 'hp', 0)))
        except Exception:
            max_hp = 0
        return f"{name}|{base_atk}|{max_hp}"

    def _apply_equipment_spec(self, entity, eq_spec: Dict[str, Any]) -> None:
        try:
            from src.systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
        except Exception:
            return
        eq = getattr(entity, 'equipment', None)
        if not eq:
            return
        # 先卸下所有
        try:
            for slot in ('left_hand', 'right_hand', 'armor'):
                if getattr(eq, slot, None) is not None:
                    eq.unequip(slot)
        except Exception:
            pass
        # 再按 spec 装回
        def make_item(s):
            t = (s or {}).get('type')
            n = (s or {}).get('name') or '装备'
            if t == 'weapon':
                return WeaponItem(n, description=f"保存装备:{n}", durability=100,
                                  attack=_safe_int(s.get('attack', 0)),
                                  slot_type=s.get('slot_type') or 'right_hand',
                                  is_two_handed=bool(s.get('two_handed', False)),
                                  active_skills=list(s.get('active_skills', []) or []),
                                  passives=dict(s.get('passives', {}) or {}))
            if t == 'armor':
                return ArmorItem(n, description=f"保存装备:{n}", durability=100,
                                 defense=_safe_int(s.get('defense', 0)),
                                 active_skills=list(s.get('active_skills', []) or []),
                                 passives=dict(s.get('passives', {}) or {}))
            if t == 'shield':
                return ShieldItem(n, description=f"保存装备:{n}", durability=100,
                                  defense=_safe_int(s.get('defense', 0)),
                                  attack=_safe_int(s.get('attack', 0)),
                                  active_skills=list(s.get('active_skills', []) or []),
                                  passives=dict(s.get('passives', {}) or {}))
            return None
        # 双手武器优先，以确保槽位冲突正确处理
        # 简化：直接按 slot 顺序装备，底层逻辑会处理双手覆盖
        for slot in ('armor', 'left_hand', 'right_hand'):
            spec = eq_spec.get(slot)
            if not spec:
                continue
            item = make_item(spec)
            if item is None:
                continue
            try:
                eq.equip(item)
            except Exception:
                pass
