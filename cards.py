import random

class Card:
    weight = 1  # 抽牌权重

    def __init__(self, atk, hp):
        self.atk = atk
        self.hp = hp
        self.max_hp = hp  # 记录最大生命值
        self.attacks = 0
        self.can_attack = False

    def on_play(self, game, owner, target=None):
        """出场触发（子类重写）"""
        pass

    def on_death(self, game, owner):
        """死亡触发（子类重写）"""
        pass

    def take_damage(self, damage):
        """处理卡牌受到伤害"""
        self.hp -= damage
        print(f"{self} 受到了 {damage} 点伤害，当前生命值为 {self.hp}")

    def heal(self, amount):
        """处理卡牌回血"""
        self.hp = min(self.hp + amount, self.max_hp)
        print(f"{self} 恢复了 {amount} 点生命值，当前生命值为 {self.hp}")

    def sync_state(self):
        """将卡牌状态转换为字符串"""
        return f"{self.__class__.__name__},{self.atk},{self.hp},{self.max_hp},{self.attacks},{int(self.can_attack)}"

    def info(self):
        """返回卡牌的详细信息"""
        return f"攻击 {self.atk}，生命 {self.hp}/{self.max_hp}，类型 基础随从，无特殊效果"

    def __str__(self):
        return f"{self.__class__.__name__}[{self.atk}/{self.hp}]"
    
    def __repr__(self):
        return self.__str__()

class NormalCard(Card):
    weight = 1

class DrawCard(Card):
    weight = 3
    def on_play(self, game, owner, target=None):
        card = game.draw(owner)
        print(f"效果: 召唤后抽到 {card}")

    def info(self):
        return f"攻击 {self.atk}，生命 {self.hp}，类型 抽牌随从，效果 召唤后抽一张牌"

class WindfuryCard(Card):
    weight = 3
    def on_play(self, game, owner, target=None):
        self.windfury = True
        print("效果: 本回合可额外攻击一次")

    def info(self):
        return f"攻击 {self.atk}，生命 {self.hp}，类型 风怒随从，效果 每回合可额外攻击一次"

class BattlecryCard(Card):
    weight = 3
    def on_play(self, game, owner, target=None):
        if target == 'enemy_hero':
            if owner == 'me':
                game.player_op.hp -= self.atk
                print(f"效果: 战吼对敌方英雄造成 {self.atk} 点伤害")
            else:
                game.player_me.hp -= self.atk
                print(f"效果: 战吼对我方英雄造成 {self.atk} 点伤害")
        elif isinstance(target, Card):
            target.hp -= self.atk
            print(f"效果: 战吼对 {target} 造成 {self.atk} 点伤害")
        else:
            print("效果: 战吼缺少目标")

    def info(self):
        return f"攻击 {self.atk}，生命 {self.hp}，类型 战吼随从，效果 召唤时对一个目标造成攻击力点伤害"

class CombinedCard(Card):
    weight = 5
    def on_play(self, game, owner, target=None):
        card = game.draw(owner)
        print(f"效果: 召唤后抽到 {card}")
        self.windfury = True
        print("效果: 风怒（本回合可额外攻击一次）")
        if target == 'enemy_hero':
            if owner == 'me':
                game.player_op.hp -= self.atk
            else:
                game.player_me.hp -= self.atk
            print(f"效果: 战吼对敌方英雄造成 {self.atk} 点伤害")
        elif isinstance(target, Card):
            target.hp -= self.atk
            print(f"效果: 战吼对 {target} 造成 {self.atk} 点伤害")
        else:
            print("效果: 战吼缺少目标")

class DeathrattleCard(Card):
    weight = 1
    def __init__(self, atk=2, hp=1):
        super().__init__(atk, hp)
    def on_death(self, game, owner):
        if owner == 'me':
            game.player_op.hp -= 2
            print("亡语：对敌方英雄造成2点伤害")
        else:
            game.player_me.hp -= 2
            print("亡语：对我方英雄造成2点伤害")
    def __str__(self):
        return f"DeathrattleCard[{self.atk}/{self.hp}]"

    def info(self):
        return f"攻击 {self.atk}，生命 {self.hp}，类型 亡语随从，效果 死亡时对敌方英雄造成2点伤害"

card_types = [NormalCard, DrawCard, WindfuryCard, BattlecryCard, CombinedCard, DeathrattleCard]
weights = [ct.weight for ct in card_types]

def draw_card():
    cls = random.choices(card_types, weights=weights, k=1)[0]
    atk = random.randint(1, 5)
    hp = random.randint(1, 5)
    return cls(atk, hp)