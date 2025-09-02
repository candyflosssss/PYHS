"""
基础实体类 - 统一管理攻击力、防御力、生命值等基础属性
消除各个实体类中的重复代码
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from src.systems.equipment_system import EquipmentSystem


class BaseEntity(ABC):
    """基础实体抽象类，提供通用的属性和方法"""
    
    def __init__(self, atk: int, hp: int, *, name: str | None = None, 
                 profession: str | None = None, race: str | None = None):
        self.base_atk = int(atk)
        self.hp = int(hp)
        self.max_hp = int(hp)
        self.can_attack = False
        
        # 装备系统
        self.equipment = EquipmentSystem()
        try:
            # 让装备系统能在事件中回溯归属对象
            setattr(self.equipment, 'owner', self)
        except Exception:
            pass
        
        # 可选拓展字段（默认空）
        self.tags = []          # e.g. ["healer","mage","tank"]
        self.passive = {}       # e.g. {"no_counter":true}
        self.skills = []        # e.g. [{"name":"治疗","heal":4}]
        
        # DnD 数据（可选）：{'level':1,'attrs':{'str':10,...},'ac':None,'bonuses':{}}
        self.dnd = None
        
        # 职业与种族字段（可用于分配默认技能）
        self.profession = profession
        self.race = race
        
        # 名称设置
        if name:
            n = str(name)
            # 同时设置 display_name 与 name，兼容旧代码访问 .name
            setattr(self, 'display_name', n)
            setattr(self, 'name', n)
        
        # 体力系统：由 settings.rules.stamina.base 控制回合上限
        try:
            from src import settings as S
            base = int(getattr(S, 'stamina_base')())
        except Exception:
            base = 3
        self.stamina_max = int(base)
        self.stamina = int(base)

    def add_tag(self, tag: str):
        """添加标签"""
        try:
            t = str(tag).lower()
            if t not in self.tags:
                self.tags.append(t)
        except Exception:
            pass

    def remove_tag(self, tag: str):
        """移除标签"""
        try:
            t = str(tag).lower()
            if t in self.tags:
                self.tags.remove(t)
        except Exception:
            pass

    def has_tag(self, tag: str) -> bool:
        """检查是否有指定标签"""
        try:
            return str(tag).lower() in self.tags
        except Exception:
            return False

    # 动态数值（含装备）
    def get_total_attack(self) -> int:
        """获取总攻击力（基础攻击力 + 装备加成）"""
        return int(self.base_atk) + int(self.equipment.get_total_attack() if self.equipment else 0)

    def get_total_defense(self) -> int:
        """获取总防御力（装备加成）"""
        return int(self.equipment.get_total_defense() if self.equipment else 0)

    @property
    def attack(self) -> int:
        """攻击力属性（总攻击力）"""
        return self.get_total_attack()

    @property
    def defense(self) -> int:
        """防御力属性（总防御力）"""
        return self.get_total_defense()

    def heal(self, amount: int):
        """治疗，恢复生命值"""
        prev_hp = self.hp
        self.hp = min(self.hp + int(amount), self.max_hp)
        self._publish_heal_event(amount, prev_hp, self.hp)

    def take_damage(self, damage: int) -> bool:
        """受到伤害，返回是否死亡"""
        prev_hp = self.hp
        self.hp = max(0, self.hp - int(damage))
        self._publish_damage_event(damage, prev_hp, self.hp)
        return self.hp <= 0

    def is_alive(self) -> bool:
        """检查是否存活"""
        return self.hp > 0

    def is_dead(self) -> bool:
        """检查是否死亡"""
        return self.hp <= 0

    # --- stamina helpers ---
    def refill_stamina(self):
        """回合开始回满体力"""
        self.stamina = int(self.stamina_max)
        self._publish_stamina_event('refill')

    def spend_stamina(self, amount: int) -> bool:
        """尝试消耗体力；不足则返回 False"""
        a = max(0, int(amount))
        if self.stamina < a:
            return False
        self.stamina -= a
        self._publish_stamina_event('spend', amount=a)
        return True

    def has_stamina(self, amount: int = 1) -> bool:
        """检查是否有足够的体力"""
        return self.stamina >= amount

    # --- 事件发布辅助方法 ---
    def _publish_heal_event(self, amount: int, hp_before: int, hp_after: int):
        """发布治疗事件"""
        try:
            from src.core.events import publish as publish_event
            publish_event('entity_healed', {
                'entity': self, 
                'amount': amount, 
                'hp_before': hp_before, 
                'hp_after': hp_after
            })
        except Exception:
            pass

    def _publish_damage_event(self, damage: int, hp_before: int, hp_after: int):
        """发布伤害事件"""
        try:
            from src.core.events import publish as publish_event
            publish_event('entity_damaged', {
                'entity': self, 
                'damage': damage, 
                'hp_before': hp_before, 
                'hp_after': hp_after
            })
        except Exception:
            pass

    def _publish_stamina_event(self, reason: str, **kwargs):
        """发布体力变化事件"""
        try:
            from src.core.events import publish as publish_event
            payload = {
                'owner': self, 
                'stamina': self.stamina, 
                'stamina_max': self.stamina_max, 
                'reason': reason
            }
            payload.update(kwargs)
            publish_event('stamina_changed', payload)
        except Exception:
            pass

    # --- 抽象方法 ---
    @abstractmethod
    def on_death(self, game=None):
        """死亡时的回调，子类必须实现"""
        pass

    def __str__(self):
        """字符串表示"""
        name = getattr(self, 'display_name', getattr(self, 'name', self.__class__.__name__))
        return f"{name}[{self.attack}/{self.hp}]"

    def __repr__(self):
        return self.__str__()
