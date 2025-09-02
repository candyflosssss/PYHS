from __future__ import annotations

from src.core.base_entity import BaseEntity


class Combatant(BaseEntity):
    """通用战斗单位父类（随从/敌人共用）

    - 继承自 BaseEntity，获得统一的属性和方法
    - 注意：take_damage 留给子类自定义返回值（随从不返回、敌人返回是否死亡）
    """

    def __init__(self, atk: int, hp: int, *, name: str | None = None, profession: str | None = None, race: str | None = None):
        super().__init__(atk, hp, name=name, profession=profession, race=race)

    def on_death(self, game=None):
        """死亡时的回调，子类必须实现"""
        pass
