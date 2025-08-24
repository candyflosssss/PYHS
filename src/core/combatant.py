from __future__ import annotations

from src.systems.equipment_system import EquipmentSystem


class Combatant:
    """通用战斗单位父类（随从/敌人共用）

    - 统一字段：base_atk, hp, max_hp, can_attack, equipment, tags, passive, skills
    - 统一方法：get_total_attack/defense, attack/defense 属性, heal
    - 注意：take_damage 留给子类自定义返回值（随从不返回、敌人返回是否死亡）
    """

    def __init__(self, atk: int, hp: int, *, name: str | None = None, profession: str | None = None, race: str | None = None):
        self.base_atk = int(atk)
        self.hp = int(hp)
        self.max_hp = int(hp)
        self.can_attack = False
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
        if name:
            n = str(name)
            # 同时设置 display_name 与 name，兼容旧代码访问 .name
            setattr(self, 'display_name', n)
            setattr(self, 'name', n)

    def add_tag(self, tag: str):
        try:
            t = str(tag).lower()
            if t not in self.tags:
                self.tags.append(t)
        except Exception:
            pass

    def remove_tag(self, tag: str):
        try:
            t = str(tag).lower()
            if t in self.tags:
                self.tags.remove(t)
        except Exception:
            pass

    # 动态数值（含装备）
    def get_total_attack(self) -> int:
        return int(self.base_atk) + int(self.equipment.get_total_attack() if self.equipment else 0)

    def get_total_defense(self) -> int:
        return int(self.equipment.get_total_defense() if self.equipment else 0)

    @property
    def attack(self) -> int:
        return self.get_total_attack()

    @property
    def defense(self) -> int:
        return self.get_total_defense()

    def heal(self, amount: int):
        self.hp = min(self.hp + int(amount), self.max_hp)
