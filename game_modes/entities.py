"""
通用实体定义：Enemy、ResourceItem、Boss
从 pve_multiplayer_game 中抽离，避免工厂与游戏模块的循环依赖。
"""

from __future__ import annotations
from typing import Callable, Optional
from ui import colors as C


class ResourceItem:
    """资源物品"""

    def __init__(self, name: str, item_type: str, effect_value: int):
        self.name = name
        self.item_type = item_type  # 'weapon', 'potion', 'armor', etc.
        self.effect_value = effect_value

    def __str__(self) -> str:  # pragma: no cover - 简单显示
        return C.resource(f"{self.name}(+{self.effect_value})")


class Enemy:
    """敌人单位"""

    def __init__(
        self,
        name: str,
        attack: int,
        hp: int,
        death_effect: Optional[Callable[["GameLike"], None]] = None,
    ):
        self.name = name
        self.attack = attack
        self.hp = hp
        self.max_hp = hp
        self.death_effect = death_effect
        self.can_attack = True

    def __str__(self) -> str:  # pragma: no cover
        return C.enemy(f"{self.name}({self.attack}/{self.hp})")

    def take_damage(self, damage: int) -> bool:
        """返回是否死亡"""
        self.hp -= damage
        return self.hp <= 0

    def on_death(self, game: "GameLike") -> None:
        if self.death_effect:
            self.death_effect(game)


class Boss:
    """Boss 单位（默认不反击）"""

    def __init__(self, name: str = "终极Boss", hp: int = 100):
        self.name = name
        self.hp = hp
        self.max_hp = hp
        self.attack = 0

    def take_damage(self, damage: int) -> bool:
        self.hp -= damage
        return self.hp <= 0

    def __str__(self) -> str:  # pragma: no cover
        return C.enemy(f"{self.name}({self.hp}/{self.max_hp})")


# 仅用于类型提示，避免真正引入依赖
class GameLike:  # pragma: no cover - typing helper
    resource_zone: list[ResourceItem]
    players: dict
