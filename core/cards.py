import random
from ui import colors as C
from .combatant import Combatant

class Card(Combatant):
    weight = 1  # 抽牌权重

    def __init__(self, atk, hp):
        super().__init__(atk, hp)
        self.atk = atk  # 兼容旧字段
        self.attacks = 0
        # equipment/tags/passive/skills 已在 Combatant 初始化

    def take_damage(self, damage):
        """处理卡牌受到伤害（考虑防御力）"""
        defense = self.get_total_defense()
        actual_damage = max(1, damage - defense)
        self.hp -= actual_damage

    def on_play(self, game, owner, target=None):
        pass

    def on_death(self, game, owner):
        pass

    def heal(self, amount):
        self.hp = min(self.hp + amount, self.max_hp)

    def sync_state(self):
        windfury = getattr(self, 'windfury', False)
        total_atk = self.get_total_attack()
        return f"{self.__class__.__name__},{total_atk},{self.hp},{self.max_hp},{self.attacks},{int(self.can_attack)},{int(windfury)}"

    def info(self):
        total_atk = self.get_total_attack()
        defense = self.get_total_defense()
        equipment_info = f", {self.equipment}" if str(self.equipment) != "装备: 无" else ""
        return f"攻击 {total_atk}，生命 {self.hp}/{self.max_hp}，防御 {defense}，类型 基础随从{equipment_info}"

    def __str__(self):
        total_atk = self.get_total_attack()
        name = getattr(self, 'display_name', self.__class__.__name__)
        return C.friendly(f"{name}[{total_atk}/{self.hp}]")
    
    def __repr__(self):
        return self.__str__()

class NormalCard(Card):
    weight = 1
    def __init__(self, atk, hp, *, name: str | None = None, tags=None, passive=None, skills=None):
        super().__init__(atk, hp)
        if name:
            setattr(self, 'display_name', name)
        if tags:
            try: self.tags = list(tags)
            except Exception: pass
        if passive:
            try: self.passive = dict(passive)
            except Exception: pass
        if skills:
            try: self.skills = list(skills)
            except Exception: pass

class DrawCard(Card):
    weight = 3
    def on_play(self, game, owner, target=None):
        card = game.draw(owner) if hasattr(game, 'draw') else None
        if card:
            _log(game, f"{self} 召唤后抽到 {card}")
        else:
            _log(game, f"{self} 尝试抽牌，但当前模式不支持")

    def info(self):
        return f"攻击 {self.atk}，生命 {self.hp}/{self.max_hp}，类型 抽牌随从，效果 召唤后抽一张牌"

class WindfuryCard(Card):
    weight = 3
    def __init__(self, atk, hp):
        super().__init__(atk, hp)
        self.windfury = True  # 风怒卡牌初始就有风怒属性
        
    def on_play(self, game, owner, target=None):
        _log(game, f"{self} 获得风怒，本回合可额外攻击一次")

    def info(self):
        return f"攻击 {self.atk}，生命 {self.hp}/{self.max_hp}，类型 风怒随从，效果 每回合可额外攻击一次"

class BattlecryCard(Card):
    weight = 3
    requires_target = True
    def on_play(self, game, owner, target=None):
        damage = self.get_total_attack()  # 使用总攻击力
        if target == 'enemy_hero':
            # 兼容不同游戏模式
            if hasattr(game, 'damage_enemy_hero'):
                attacker_owner = owner
                game.damage_enemy_hero(attacker_owner, damage)
                _log(game, f"{self} 使用战吼效果对敌方英雄造成 {damage} 点伤害")
            else:
                _log(game, f"{self} 的战吼准备造成 {damage} 点伤害（PvE模式）")
        elif isinstance(target, Card):
            target.take_damage(damage)
            _log(game, f"{self} 使用战吼效果对 {target} 造成 {damage} 点伤害")
        elif target is not None:
            # 兼容 PvE 的 Enemy/Boss：有 take_damage 或 hp 的对象
            if hasattr(target, 'take_damage'):
                died = target.take_damage(damage)
                _log(game, f"{self} 使用战吼效果对 {target} 造成 {damage} 点伤害")
                # 敌人死亡时从游戏移除并触发亡语
                game_ref = game
                try:
                    if died and game_ref is not None:
                        removed = False
                        if hasattr(game_ref, 'enemies') and isinstance(getattr(game_ref, 'enemies'), list):
                            if target in game_ref.enemies:
                                target.on_death(game_ref)
                                game_ref.enemies.remove(target)
                                removed = True
                        if not removed and hasattr(game_ref, 'enemy_zone') and isinstance(getattr(game_ref, 'enemy_zone'), list):
                            if target in game_ref.enemy_zone:
                                target.on_death(game_ref)
                                game_ref.enemy_zone.remove(target)
                                removed = True
                        # Boss 被击杀：结束游戏（若有 running 标志）
                        if not removed and hasattr(game_ref, 'boss') and target is getattr(game_ref, 'boss') and getattr(target, 'hp', 1) <= 0:
                            if hasattr(game_ref, 'running'):
                                game_ref.running = False
                except Exception:
                    pass
            elif hasattr(target, 'hp'):
                target.hp -= damage
                _log(game, f"{self} 使用战吼效果对目标造成 {damage} 点伤害")
        else:
            _log(game, f"{self} 战吼缺少目标")

    # 兼容旧接口：部分逻辑会直接调用 battlecry
    def battlecry(self, owner, target=None):
        game = getattr(owner, 'game', None)
        self.on_play(game, owner, target)

    def info(self):
        total_atk = self.get_total_attack()
        defense = self.get_total_defense()
        equipment_info = f", {self.equipment}" if str(self.equipment) != "装备: 无" else ""
        return f"攻击 {total_atk}，生命 {self.hp}/{self.max_hp}，防御 {defense}，类型 战吼随从，效果 召唤时对一个目标造成攻击力点伤害{equipment_info}"

class CombinedCard(Card):
    weight = 5
    requires_target = True
    def __init__(self, atk, hp):
        super().__init__(atk, hp)
        self.windfury = True  # 组合卡牌初始就有风怒属性
        
    def on_play(self, game, owner, target=None):
        card = game.draw(owner) if hasattr(game, 'draw') else None
        if card:
            _log(game, f"{self} 召唤后抽到 {card}")
        else:
            _log(game, f"{self} 尝试抽牌，但当前模式不支持")
        _log(game, f"{self} 获得风怒，本回合可额外攻击一次")
        damage = self.get_total_attack()  # 使用总攻击力
        if target == 'enemy_hero':
            # 兼容不同游戏模式
            if hasattr(game, 'damage_enemy_hero'):
                attacker_owner = owner
                game.damage_enemy_hero(attacker_owner, damage)
                _log(game, f"{self} 使用战吼效果对敌方英雄造成 {damage} 点伤害")
            else:
                _log(game, f"{self} 的战吼准备造成 {damage} 点伤害（PvE模式）")
        elif isinstance(target, Card):
            target.take_damage(damage)
            _log(game, f"{self} 使用战吼效果对 {target} 造成 {damage} 点伤害")
        elif target is not None:
            if hasattr(target, 'take_damage'):
                died = target.take_damage(damage)
                _log(game, f"{self} 使用战吼效果对 {target} 造成 {damage} 点伤害")
                game_ref = game
                try:
                    if died and game_ref is not None:
                        removed = False
                        if hasattr(game_ref, 'enemies') and isinstance(getattr(game_ref, 'enemies'), list):
                            if target in game_ref.enemies:
                                target.on_death(game_ref)
                                game_ref.enemies.remove(target)
                                removed = True
                        if not removed and hasattr(game_ref, 'enemy_zone') and isinstance(getattr(game_ref, 'enemy_zone'), list):
                            if target in game_ref.enemy_zone:
                                target.on_death(game_ref)
                                game_ref.enemy_zone.remove(target)
                                removed = True
                        if not removed and hasattr(game_ref, 'boss') and target is getattr(game_ref, 'boss') and getattr(target, 'hp', 1) <= 0:
                            if hasattr(game_ref, 'running'):
                                game_ref.running = False
                except Exception:
                    pass
            elif hasattr(target, 'hp'):
                target.hp -= damage
                _log(game, f"{self} 使用战吼效果对目标造成 {damage} 点伤害")
        else:
            _log(game, f"{self} 战吼缺少目标")

    def battlecry(self, owner, target=None):
        game = getattr(owner, 'game', None)
        self.on_play(game, owner, target)

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
            _log(game, "亡语：对敌方英雄造成2点伤害")
        else:
            _log(game, "亡语：准备造成2点伤害（PvE模式）")
    def __str__(self):
        # 统一走基类的着色显示
        return super().__str__()

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
        if self.equipment.equip(wooden_sword, game):
            _log(game, f"亡语：{self} 装备了木剑！")
        else:
            _log(game, f"亡语：装备槽冲突，无法装备木剑")
    
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

# --- 内部日志工具 ---
def _log(game, text: str):
    try:
        if game is not None and hasattr(game, 'log'):
            game.log(text)
        else:
            print(text)
    except Exception:
        print(text)