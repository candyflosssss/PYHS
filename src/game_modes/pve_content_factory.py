"""
PvE游戏内容工厂：创建敌人与资源。
"""

from __future__ import annotations

from src.game_modes.entities import Enemy, ResourceItem


class EnemyFactory:
    """
敌人工厂
"""

    @staticmethod
    def create_goblin() -> Enemy:
        """创建哥布林"""

        def drop_potion(game):
            if len(game.resource_zone) < len(game.players) + 3:
                potion = ResourceItem("生命药水", "potion", 3)
                game.resource_zone.append(potion)

        return Enemy("哥布林", 2, 2, drop_potion)

    @staticmethod
    def create_orc() -> Enemy:
        """创建兽人"""

        def drop_weapon(game):
            if len(game.resource_zone) < len(game.players) + 3:
                weapon = ResourceItem("战斧", "weapon", 3)
                game.resource_zone.append(weapon)

        return Enemy("兽人", 3, 3, drop_weapon)

    @staticmethod
    def create_skeleton() -> Enemy:
        """创建骷髅"""

        def drop_shield(game):
            if len(game.resource_zone) < len(game.players) + 3:
                shield = ResourceItem("骨盾", "armor", 2)
                game.resource_zone.append(shield)

        return Enemy("骷髅", 2, 1, drop_shield)

    @staticmethod
    def create_random_enemy() -> Enemy:
        """创建随机敌人"""
        import random

        enemies = [
            EnemyFactory.create_goblin,
            EnemyFactory.create_orc,
            EnemyFactory.create_skeleton,
        ]
        return random.choice(enemies)()


class ResourceFactory:
    """
资源工厂
"""

    @staticmethod
    def create_wooden_sword() -> ResourceItem:
        return ResourceItem("木剑", "weapon", 2)

    @staticmethod
    def create_iron_sword() -> ResourceItem:
        return ResourceItem("铁剑", "weapon", 3)

    @staticmethod
    def create_health_potion() -> ResourceItem:
        return ResourceItem("生命药水", "potion", 3)

    @staticmethod
    def create_mana_potion() -> ResourceItem:
        return ResourceItem("法力药水", "potion", 2)

    @staticmethod
    def create_leather_armor() -> ResourceItem:
        return ResourceItem("皮甲", "armor", 2)

    @staticmethod
    def create_random_resource() -> ResourceItem:
        import random

        resources = [
            ResourceFactory.create_wooden_sword,
            ResourceFactory.create_iron_sword,
            ResourceFactory.create_health_potion,
            ResourceFactory.create_mana_potion,
            ResourceFactory.create_leather_armor,
        ]
        return random.choice(resources)()

