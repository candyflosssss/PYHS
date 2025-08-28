from .inventory import EquipmentItem
from src.core.events import publish as publish_event
from src.ui import colors as C

class WeaponItem(EquipmentItem):
    """武器装备

    可选：
    - active_skills: [skill_id,...] 装备后可用的主动技能（会出现在操作栏）
    - passives: dict 被动效果声明（示例：{'lifesteal_on_attack_stat': 'str'}）
    """
    def __init__(self, name, description="", durability=100, attack=0, slot_type="right_hand", is_two_handed=False,
                 active_skills=None, passives=None):
        super().__init__(name, description, durability)
        self.attack = attack
        self.defense = 0
        self.slot_type = slot_type
        self.is_two_handed = is_two_handed
        self.active_skills = list(active_skills or [])
        self.passives = dict(passives or {})
    
    def __str__(self):
        if self.is_two_handed:
            return C.resource(f"{self.name}(双手武器 +{self.attack}攻)")
        return C.resource(f"{self.name}(武器 +{self.attack}攻)")

class ArmorItem(EquipmentItem):
    """防具装备

    可选：active_skills/passives，示例被动：
    - {'heal_on_damaged_stat': 'wis'}    受伤时按 WIS 调整值治疗
    - {'reflect_on_damaged': 'stamina_cost_1'}   受伤时若有体力则消耗1并反伤
    """
    def __init__(self, name, description: str = "", durability: int = 100, defense: int = 0, slot_type: str = "armor",
                 active_skills=None, passives=None):
        super().__init__(name, description, durability)
        self.attack = 0
        self.defense = defense
        self.slot_type = slot_type
        self.is_two_handed = False
        self.active_skills = list(active_skills or [])
        self.passives = dict(passives or {})

    def __str__(self):
        return C.resource(f"{self.name}(防具 +{self.defense}防)")

class ShieldItem(EquipmentItem):
    """盾牌装备（左手）"""
    def __init__(self, name, description="", durability=100, defense=0, attack=0, active_skills=None, passives=None):
        super().__init__(name, description, durability)
        self.attack = attack
        self.defense = defense
        self.slot_type = "left_hand"
        self.is_two_handed = False
        self.active_skills = list(active_skills or [])
        self.passives = dict(passives or {})
    
    def __str__(self):
        if self.attack > 0:
            return C.resource(f"{self.name}(盾牌 +{self.attack}攻 +{self.defense}防)")
        return C.resource(f"{self.name}(盾牌 +{self.defense}防)")


class EquipmentSystem:
    """装备系统"""
    def __init__(self):
        self.left_hand = None
        self.right_hand = None
        self.armor = None
    
    def _log(self, game, text: str):
        try:
            if game is not None and hasattr(game, 'log'):
                game.log(text)
            else:
                print(text)
        except Exception:
            print(text)

    def equip(self, equipment, game=None):
        """装备物品（可选传入 game，用于统一日志输出）
        - 如目标槽位已有装备，会自动将被替换的装备退回玩家背包（若可获取到 game.player）。
        - 双手武器会清空并返还双手的原有装备。
        """
        def return_item(it):
            if not it:
                return
            try:
                player = getattr(game, 'player', None)
                if player is not None and hasattr(player, 'add_item'):
                    player.add_item(it, 1)
                else:
                    # 退化为打印
                    self._log(game, f"已移除装备: {it}")
            except Exception:
                try:
                    self._log(game, f"已移除装备: {it}")
                except Exception:
                    pass

        # 盔甲
        if equipment.slot_type == "armor":
            if self.armor is not None:
                self._log(game, f"替换盔甲: {self.armor} -> {equipment}")
                return_item(self.armor)
            self.armor = equipment
            self._log(game, f"装备盔甲: {equipment}")
            try:
                publish_event('equipment_changed', {'slot': 'armor', 'item': equipment, 'owner': getattr(self, 'owner', None)})
            except Exception:
                pass
            return True

        # 双手武器
        if equipment.is_two_handed:
            # 清理双手，并返还
            if self.left_hand is not None:
                self._log(game, f"移除左手: {self.left_hand}")
                return_item(self.left_hand)
            if self.right_hand is not None:
                self._log(game, f"移除右手: {self.right_hand}")
                return_item(self.right_hand)
            self.left_hand = equipment
            self.right_hand = None
            self._log(game, f"装备双手武器: {equipment}")
            try:
                publish_event('equipment_changed', {'slot': 'both_hands', 'item': equipment, 'owner': getattr(self, 'owner', None)})
            except Exception:
                pass
            return True

        # 单手左手武器
        if equipment.slot_type == "left_hand":
            if self.left_hand and self.left_hand.is_two_handed:
                self._log(game, "无法装备，左手当前为双手武器")
                return False
            if self.left_hand is not None:
                self._log(game, f"替换左手: {self.left_hand} -> {equipment}")
                return_item(self.left_hand)
            self.left_hand = equipment
            self._log(game, f"装备左手: {equipment}")
            try:
                publish_event('equipment_changed', {'slot': 'left_hand', 'item': equipment, 'owner': getattr(self, 'owner', None)})
            except Exception:
                pass
            return True

        # 单手右手武器
        if equipment.slot_type == "right_hand":
            if self.left_hand and self.left_hand.is_two_handed:
                self._log(game, "无法装备，当前持有双手武器")
                return False
            if self.right_hand is not None:
                self._log(game, f"替换右手: {self.right_hand} -> {equipment}")
                return_item(self.right_hand)
            self.right_hand = equipment
            self._log(game, f"装备右手: {equipment}")
            try:
                publish_event('equipment_changed', {'slot': 'right_hand', 'item': equipment, 'owner': getattr(self, 'owner', None)})
            except Exception:
                pass
            return True

        # 未知槽位
        self._log(game, f"无法装备(未知槽位): {equipment}")
        return False
    
    def unequip(self, slot):
        """卸下装备，返回被卸下的物品(或 None)"""
        removed = None
        if slot == "left_hand":
            removed, self.left_hand = self.left_hand, None
        elif slot == "right_hand":
            removed, self.right_hand = self.right_hand, None
        elif slot == "armor":
            removed, self.armor = self.armor, None
        try:
            if removed:
                publish_event('equipment_changed', {'slot': slot, 'item': None, 'removed': removed, 'owner': getattr(self, 'owner', None)})
        except Exception:
            pass
        return removed
    
    def get_total_attack(self):
        """获取总攻击力"""
        total = 0
        if self.left_hand:
            total += self.left_hand.attack
        if self.right_hand:
            total += self.right_hand.attack
        return total
    
    def get_total_defense(self):
        """获取总防御力"""
        total = 0
        if self.left_hand:
            total += self.left_hand.defense
        if self.right_hand:
            total += self.right_hand.defense
        if self.armor:
            total += self.armor.defense
        return total
    
    def __str__(self):
        items = []
        if self.left_hand:
            if getattr(self.left_hand, 'is_two_handed', False):
                items.append(f"双手:{self.left_hand.name}")
            else:
                items.append(f"左手:{self.left_hand.name}")
        if self.right_hand:
            items.append(f"右手:{self.right_hand.name}")
        if self.armor:
            items.append(f"盔甲:{self.armor.name}")
        
        if not items:
            return "装备: 无"
        
        total_atk = self.get_total_attack()
        total_def = self.get_total_defense()
        return f"装备: {', '.join(items)} (总计 +{total_atk}攻 +{total_def}防)"


# 创建一些测试装备
def create_sample_equipment():
    """创建示例装备（含主动/被动示例）"""
    return {
        "wooden_sword": WeaponItem("木剑", "简单的木制武器", 50, attack=2),
        "iron_shield": ShieldItem("铁盾", "坚固的铁制盾牌", 80, defense=3),
        "leather_armor": ArmorItem("皮甲", "轻便的皮革护甲", 60, defense=2),
        "great_sword": WeaponItem("巨剑", "需要双手持握的大剑", 100, attack=5, slot_type="left_hand", is_two_handed=True),
        "steel_sword": WeaponItem("钢剑", "锋利的钢制长剑", 90, attack=4, active_skills=["precise_strike"]),
        "magic_shield": ShieldItem("魔法盾", "带有魔法增幅的盾牌", 120, defense=4, attack=1),
        "嗜血之剑": WeaponItem("嗜血之剑", "攻击时按力量调整值恢复生命", 100, attack=3, passives={"lifesteal_on_attack_stat": "str"}),
        "生命铠甲": ArmorItem("生命铠甲", "受伤时按智慧调整值恢复生命", 100, defense=3, passives={"heal_on_damaged_stat": "wis"}),
        "诅咒之铠": ArmorItem("诅咒之铠", "受伤时可消耗体力反伤", 100, defense=2, passives={"reflect_on_damaged": "stamina_cost_1"}),
    }


if __name__ == "__main__":
    # 测试装备系统
    print("=== 装备系统测试 ===")
    
    eq_system = EquipmentSystem()
    equipment = create_sample_equipment()
    
    print(f"初始状态: {eq_system}")
    
    # 装备单手武器和盾牌
    eq_system.equip(equipment["wooden_sword"])
    eq_system.equip(equipment["iron_shield"])
    eq_system.equip(equipment["leather_armor"])
    print(f"装备后: {eq_system}")
    
    print("\n尝试装备双手武器:")
    eq_system.equip(equipment["great_sword"])
    print(f"装备双手武器后: {eq_system}")
    
    print("\n尝试再装备右手武器:")
    eq_system.equip(equipment["steel_sword"])
    print(f"尝试装备右手后: {eq_system}")
