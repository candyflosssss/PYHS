"""
通用实体定义：Enemy、ResourceItem
从旧多人模块中抽离，避免工厂与游戏模块的循环依赖。
"""

from __future__ import annotations
from typing import Callable, Optional
from src.ui import colors as C
from src.core.combatant import Combatant


class ResourceItem:
    """资源物品"""

    def __init__(self, name: str, item_type: str, effect_value: int):
        self.name = name
        self.item_type = item_type  # 'weapon', 'potion', 'armor', etc.
        self.effect_value = effect_value

    def __str__(self) -> str:  # pragma: no cover - 简单显示
        return C.resource(f"{self.name}(+{self.effect_value})")


class Enemy(Combatant):
    """敌人单位（继承 Combatant，统一接口）"""

    def __init__(
        self,
        name: str,
        attack: int,
        hp: int,
        death_effect: Optional[Callable[["GameLike"], None]] = None,
    ):
        super().__init__(attack, hp, name=name)
        # 敌人默认不使用装备，但保留 equipment/defense 接口
        self.death_effect = death_effect
        self.can_attack = True

    def __str__(self) -> str:  # pragma: no cover
        return C.enemy(f"{self.name}({self.attack}/{self.hp})")

    def take_damage(self, damage: int) -> bool:
        # 敌人默认无防御（若未来引入护甲，可用 defense 抵消）
        d = max(0, int(damage))
        self.hp -= d
        return self.hp <= 0

    def on_death(self, game: "GameLike") -> None:
        if self.death_effect:
            self.death_effect(game)


# 仅用于类型提示，避免真正引入依赖
class GameLike:  # pragma: no cover - typing helper
    resource_zone: list[ResourceItem]
    players: dict
