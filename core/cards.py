import random
from systems.equipment_system import EquipmentSystem

class Card:
    weight = 1  # 抽牌权重

    def __init__(self, atk, hp):
        self.atk = atk
        self.base_atk = atk  # 基础攻击力
        self.hp = hp
        self.max_hp = hp  # 记录最大生命值
        self.attacks = 0
        self.can_attack = False
        self.equipment = EquipmentSystem()  # 添加装备系统

    def get_total_attack(self):
        """获取总攻击力（基础+装备）"""
        return self.base_atk + self.equipment.get_total_attack()
    
    def get_total_defense(self):
        """获取总防御力"""
        return self.equipment.get_total_defense()
    
    def take_damage(self, damage):
        """处理卡牌受到伤害（考虑防御力）"""
        defense = self.get_total_defense()
        actual_damage = max(1, damage - defense)  # 至少造成1点伤害
        self.hp -= actual_damage
        if defense > 0:
            print(f"{self} 防御减免{defense}点伤害，实际受到 {actual_damage} 点伤害，当前生命值为 {self.hp}")
        else:
            print(f"{self} 受到了 {actual_damage} 点伤害，当前生命值为 {self.hp}")

    def on_play(self, game, owner, target=None):
        """出场触发（子类重写）"""
        pass

    def on_death(self, game, owner):
        """死亡触发（子类重写）"""
        pass

    def heal(self, amount):
        """处理卡牌回血"""
        self.hp = min(self.hp + amount, self.max_hp)
        print(f"{self} 恢复了 {amount} 点生命值，当前生命值为 {self.hp}")

    def sync_state(self):
        """将卡牌状态转换为字符串"""
        windfury = getattr(self, 'windfury', False)
        total_atk = self.get_total_attack()
        return f"{self.__class__.__name__},{total_atk},{self.hp},{self.max_hp},{self.attacks},{int(self.can_attack)},{int(windfury)}"

    def info(self):
        """返回卡牌的详细信息"""
        total_atk = self.get_total_attack()
        defense = self.get_total_defense()
        equipment_info = f", {self.equipment}" if str(self.equipment) != "装备: 无" else ""
        return f"攻击 {total_atk}，生命 {self.hp}/{self.max_hp}，防御 {defense}，类型 基础随从{equipment_info}"

    def __str__(self):
        total_atk = self.get_total_attack()
        return f"{self.__class__.__name__}[{total_atk}/{self.hp}]"
    
    def __repr__(self):
        return self.__str__()

class NormalCard(Card):
    weight = 1

class DrawCard(Card):
    weight = 3
    def on_play(self, game, owner, target=None):
        card = game.draw(owner) if hasattr(game, 'draw') else None
        if card:
            print(f"效果: 召唤后抽到 {card}")
        else:
            print("效果: 抽牌（PvE模式暂不支持）")

    def info(self):
        return f"攻击 {self.atk}，生命 {self.hp}/{self.max_hp}，类型 抽牌随从，效果 召唤后抽一张牌"

class WindfuryCard(Card):
    weight = 3
    def __init__(self, atk, hp):
        super().__init__(atk, hp)
        self.windfury = True  # 风怒卡牌初始就有风怒属性
        
    def on_play(self, game, owner, target=None):
        print("效果: 本回合可额外攻击一次")

    def info(self):
        return f"攻击 {self.atk}，生命 {self.hp}/{self.max_hp}，类型 风怒随从，效果 每回合可额外攻击一次"

class BattlecryCard(Card):
    weight = 3
    def on_play(self, game, owner, target=None):
        damage = self.get_total_attack()  # 使用总攻击力
        if target == 'enemy_hero':
            # 兼容不同游戏模式
            if hasattr(game, 'damage_enemy_hero'):
                attacker_owner = owner
                game.damage_enemy_hero(attacker_owner, damage)
                print(f"效果: 战吼对敌方英雄造成 {damage} 点伤害")
            else:
                print(f"效果: 战吼准备造成 {damage} 点伤害（PvE模式）")
        elif isinstance(target, Card):
            target.take_damage(damage)
            print(f"效果: 战吼对 {target} 造成 {damage} 点伤害")
        else:
            print("效果: 战吼缺少目标")

    def info(self):
        total_atk = self.get_total_attack()
        defense = self.get_total_defense()
        equipment_info = f", {self.equipment}" if str(self.equipment) != "装备: 无" else ""
        return f"攻击 {total_atk}，生命 {self.hp}/{self.max_hp}，防御 {defense}，类型 战吼随从，效果 召唤时对一个目标造成攻击力点伤害{equipment_info}"

class CombinedCard(Card):
    weight = 5
    def __init__(self, atk, hp):
        super().__init__(atk, hp)
        self.windfury = True  # 组合卡牌初始就有风怒属性
        
    def on_play(self, game, owner, target=None):
        card = game.draw(owner) if hasattr(game, 'draw') else None
        if card:
            print(f"效果: 召唤后抽到 {card}")
        else:
            print("效果: 抽牌（PvE模式暂不支持）")
        print("效果: 风怒（本回合可额外攻击一次）")
        damage = self.get_total_attack()  # 使用总攻击力
        if target == 'enemy_hero':
            # 兼容不同游戏模式
            if hasattr(game, 'damage_enemy_hero'):
                attacker_owner = owner
                game.damage_enemy_hero(attacker_owner, damage)
                print(f"效果: 战吼对敌方英雄造成 {damage} 点伤害")
            else:
                print(f"效果: 战吼准备造成 {damage} 点伤害（PvE模式）")
        elif isinstance(target, Card):
            target.take_damage(damage)
            print(f"效果: 战吼对 {target} 造成 {damage} 点伤害")
        else:
            print("效果: 战吼缺少目标")

    def info(self):
        total_atk = self.get_total_attack()
        defense = self.get_total_defense()
        equipment_info = f", {self.equipment}" if str(self.equipment) != "装备: 无" else ""
        return f"攻击 {total_atk}，生命 {self.hp}/{self.max_hp}，防御 {defense}，类型 3合一随从，效果 召唤后抽牌+风怒+战吼{equipment_info}"

class DeathrattleCard(Card):
    weight = 1
    def __init__(self, atk=2, hp=1):
        super().__init__(atk, hp)
    def on_death(self, game, owner):
        # 兼容不同游戏模式
        if hasattr(game, 'damage_enemy_hero'):
            attacker_owner = owner  # 死亡的随从的主人就是攻击者
            game.damage_enemy_hero(attacker_owner, 2)
            print("亡语：对敌方英雄造成2点伤害")
        else:
            print("亡语：准备造成2点伤害（PvE模式）")
    def __str__(self):
        return f"DeathrattleCard[{self.atk}/{self.hp}]"

    def info(self):
        return f"攻击 {self.atk}，生命 {self.hp}/{self.max_hp}，类型 亡语随从，效果 死亡时对敌方英雄造成2点伤害"


class RewardSwordCard(Card):
    """奖励木剑的随从 - 为PvE模式优化"""
    weight = 2
    def __init__(self, atk=1, hp=3):
        super().__init__(atk, hp)
    
    def on_death(self, game=None, owner=None):
        """死亡时给随机队友一把木剑装备（PvE模式适配）"""
        from systems.equipment_system import WeaponItem
        
        # 创建木剑装备
        wooden_sword = WeaponItem("木剑", "简单的木制武器", 50, attack=2)
        
        # PvE模式：装备给自己
        if self.equipment.equip(wooden_sword):
            print(f"亡语：{self} 装备了木剑！")
        else:
            print(f"亡语：装备槽冲突，无法装备木剑")
    
    def info(self):
        total_atk = self.get_total_attack()
        defense = self.get_total_defense()
        equipment_info = f", {self.equipment}" if str(self.equipment) != "装备: 无" else ""
        return f"攻击 {total_atk}，生命 {self.hp}/{self.max_hp}，防御 {defense}，类型 奖励随从，效果 死亡时自我装备木剑{equipment_info}"


card_types = [NormalCard, DrawCard, WindfuryCard, BattlecryCard, CombinedCard, DeathrattleCard, RewardSwordCard]
weights = [ct.weight for ct in card_types]

def draw_card():
    cls = random.choices(card_types, weights=weights, k=1)[0]
    atk = random.randint(1, 5)
    hp = random.randint(1, 5)
    return cls(atk, hp)