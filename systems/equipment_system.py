from .inventory import EquipmentItem

class WeaponItem(EquipmentItem):
    """武器装备"""
    def __init__(self, name, description="", durability=100, attack=0, slot_type="right_hand", is_two_handed=False):
        super().__init__(name, description, durability)
        self.attack = attack
        self.defense = 0
        self.slot_type = slot_type
        self.is_two_handed = is_two_handed
    
    def __str__(self):
        if self.is_two_handed:
            return f"{self.name}(双手武器 +{self.attack}攻)"
        return f"{self.name}(武器 +{self.attack}攻)"

class ArmorItem(EquipmentItem):
    """防具装备"""
    def __init__(self, name, description="", durability=100, defense=0, slot_type="armor"):
        super().__init__(name, description, durability)
        self.attack = 0
        self.defense = defense
        self.slot_type = slot_type
        self.is_two_handed = False
    
    def __str__(self):
        return f"{self.name}(防具 +{self.defense}防)"

class ShieldItem(EquipmentItem):
    """盾牌装备"""
    def __init__(self, name, description="", durability=100, defense=0, attack=0):
        super().__init__(name, description, durability)
        self.attack = attack
        self.defense = defense
        self.slot_type = "left_hand"
        self.is_two_handed = False
    
    def __str__(self):
        if self.attack > 0:
            return f"{self.name}(盾牌 +{self.attack}攻 +{self.defense}防)"
        return f"{self.name}(盾牌 +{self.defense}防)"


class EquipmentSystem:
    """装备系统"""
    def __init__(self):
        self.left_hand = None
        self.right_hand = None
        self.armor = None
    
    def equip(self, equipment):
        """装备物品"""
        if equipment.slot_type == "armor":
            self.armor = equipment
            print(f"装备盔甲: {equipment}")
        elif equipment.is_two_handed:
            # 双手武器，清空双手槽位
            self.left_hand = equipment
            self.right_hand = None
            print(f"装备双手武器: {equipment}")
        elif equipment.slot_type == "left_hand":
            if self.left_hand and self.left_hand.is_two_handed:
                print("无法装备，左手持有双手武器")
                return False
            self.left_hand = equipment
            print(f"装备左手: {equipment}")
        elif equipment.slot_type == "right_hand":
            if self.left_hand and self.left_hand.is_two_handed:
                print("无法装备，持有双手武器")
                return False
            self.right_hand = equipment
            print(f"装备右手: {equipment}")
        return True
    
    def unequip(self, slot):
        """卸下装备"""
        if slot == "left_hand":
            self.left_hand = None
        elif slot == "right_hand":
            self.right_hand = None
        elif slot == "armor":
            self.armor = None
    
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
    """创建示例装备"""
    return {
        "wooden_sword": WeaponItem("木剑", "简单的木制武器", 50, attack=2),
        "iron_shield": ShieldItem("铁盾", "坚固的铁制盾牌", 80, defense=3),
        "leather_armor": ArmorItem("皮甲", "轻便的皮革护甲", 60, defense=2),
        "great_sword": WeaponItem("巨剑", "需要双手持握的大剑", 100, attack=5, slot_type="left_hand", is_two_handed=True),
        "steel_sword": WeaponItem("钢剑", "锋利的钢制长剑", 90, attack=4),
        "magic_shield": ShieldItem("魔法盾", "带有魔法增幅的盾牌", 120, defense=4, attack=1)
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
