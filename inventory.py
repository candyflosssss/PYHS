class Item:
    """物品基类"""
    def __init__(self, name, item_type="普通", max_stack=1, description=""):
        self.name = name
        self.item_type = item_type  # 物品类型：装备、消耗品、材料等
        self.max_stack = max_stack  # 最大堆叠数量
        self.description = description
    
    def __str__(self):
        return f"{self.name}({self.item_type})"
    
    def __repr__(self):
        return self.__str__()
    
    def __eq__(self, other):
        """判断两个物品是否相同（用于堆叠判断）"""
        if not isinstance(other, Item):
            return False
        return (self.name == other.name and 
                self.item_type == other.item_type and
                self.max_stack == other.max_stack)


class ItemStack:
    """物品堆叠类"""
    def __init__(self, item, quantity=1):
        self.item = item
        self.quantity = min(quantity, item.max_stack)
    
    def can_add(self, other_item, quantity=1):
        """检查是否可以添加物品到这个堆叠中"""
        return (self.item == other_item and 
                self.quantity + quantity <= self.item.max_stack)
    
    def add(self, quantity=1):
        """添加物品到堆叠中，返回实际添加的数量"""
        max_add = self.item.max_stack - self.quantity
        actual_add = min(quantity, max_add)
        self.quantity += actual_add
        return actual_add
    
    def remove(self, quantity=1):
        """从堆叠中移除物品，返回实际移除的数量"""
        actual_remove = min(quantity, self.quantity)
        self.quantity -= actual_remove
        return actual_remove
    
    def is_empty(self):
        """检查堆叠是否为空"""
        return self.quantity <= 0
    
    def is_full(self):
        """检查堆叠是否已满"""
        return self.quantity >= self.item.max_stack
    
    def split(self, quantity):
        """分割堆叠，返回新的堆叠"""
        if quantity >= self.quantity:
            # 如果要分割的数量大于等于当前数量，返回整个堆叠
            new_stack = ItemStack(self.item, self.quantity)
            self.quantity = 0
            return new_stack
        else:
            # 分割部分数量
            self.quantity -= quantity
            return ItemStack(self.item, quantity)
    
    def __str__(self):
        if self.quantity == 1:
            return str(self.item)
        return f"{self.item} x{self.quantity}"
    
    def __repr__(self):
        return self.__str__()


class Inventory:
    """背包类"""
    def __init__(self, max_slots=20):
        self.max_slots = max_slots
        self.slots = []  # 存储ItemStack对象的列表
    
    def add_item(self, item, quantity=1):
        """添加物品到背包，返回实际添加的数量"""
        remaining_quantity = quantity
        
        # 首先尝试添加到现有的堆叠中
        for slot in self.slots:
            if slot.can_add(item, remaining_quantity):
                added = slot.add(remaining_quantity)
                remaining_quantity -= added
                if remaining_quantity <= 0:
                    break
        
        # 如果还有剩余物品，创建新的堆叠
        while remaining_quantity > 0 and len(self.slots) < self.max_slots:
            stack_size = min(remaining_quantity, item.max_stack)
            new_stack = ItemStack(item, stack_size)
            self.slots.append(new_stack)
            remaining_quantity -= stack_size
        
        added_total = quantity - remaining_quantity
        if added_total > 0:
            print(f"添加到背包: {item.name} x{added_total}")
        if remaining_quantity > 0:
            print(f"背包空间不足，无法添加: {item.name} x{remaining_quantity}")
        
        return added_total
    
    def remove_item(self, item_name, quantity=1):
        """从背包中移除指定物品，返回实际移除的数量"""
        remaining_quantity = quantity
        slots_to_remove = []
        
        for i, slot in enumerate(self.slots):
            if slot.item.name == item_name:
                removed = slot.remove(remaining_quantity)
                remaining_quantity -= removed
                
                if slot.is_empty():
                    slots_to_remove.append(i)
                
                if remaining_quantity <= 0:
                    break
        
        # 移除空的槽位（从后往前移除避免索引问题）
        for i in reversed(slots_to_remove):
            del self.slots[i]
        
        removed_total = quantity - remaining_quantity
        if removed_total > 0:
            print(f"从背包移除: {item_name} x{removed_total}")
        
        return removed_total
    
    def get_item_count(self, item_name):
        """获取指定物品的总数量"""
        total = 0
        for slot in self.slots:
            if slot.item.name == item_name:
                total += slot.quantity
        return total
    
    def has_item(self, item_name, quantity=1):
        """检查是否有足够数量的指定物品"""
        return self.get_item_count(item_name) >= quantity
    
    def get_all_items(self):
        """获取背包中所有物品的字典，键为物品名称，值为数量"""
        items = {}
        for slot in self.slots:
            item_name = slot.item.name
            if item_name in items:
                items[item_name] += slot.quantity
            else:
                items[item_name] = slot.quantity
        return items
    
    def is_full(self):
        """检查背包是否已满"""
        return len(self.slots) >= self.max_slots
    
    def get_empty_slots(self):
        """获取空槽位数量"""
        return self.max_slots - len(self.slots)
    
    def clear(self):
        """清空背包"""
        self.slots.clear()
        print("背包已清空")
    
    def sort_items(self):
        """按物品类型和名称排序"""
        self.slots.sort(key=lambda slot: (slot.item.item_type, slot.item.name))
    
    def __str__(self):
        if not self.slots:
            return f"背包 ({len(self.slots)}/{self.max_slots}): 空"
        
        items_str = ", ".join(str(slot) for slot in self.slots)
        return f"背包 ({len(self.slots)}/{self.max_slots}): {items_str}"
    
    def display(self):
        """详细显示背包内容"""
        print(f"=== 背包内容 ({len(self.slots)}/{self.max_slots}) ===")
        if not self.slots:
            print("背包为空")
            return
        
        for i, slot in enumerate(self.slots, 1):
            print(f"{i}. {slot}")
            if slot.item.description:
                print(f"   描述: {slot.item.description}")


# 预定义一些常见物品类型
class EquipmentItem(Item):
    """装备物品（不可堆叠）"""
    def __init__(self, name, description="", durability=100):
        super().__init__(name, "装备", max_stack=1, description=description)
        self.durability = durability
        self.max_durability = durability


class ConsumableItem(Item):
    """消耗品物品（可堆叠）"""
    def __init__(self, name, description="", max_stack=10, effect=None):
        super().__init__(name, "消耗品", max_stack=max_stack, description=description)
        self.effect = effect  # 使用效果函数


class MaterialItem(Item):
    """材料物品（高度堆叠）"""
    def __init__(self, name, description="", max_stack=99):
        super().__init__(name, "材料", max_stack=max_stack, description=description)


# 示例物品
def create_sample_items():
    """创建一些示例物品"""
    return {
        "iron_sword": EquipmentItem("铁剑", "一把普通的铁制长剑", 80),
        "health_potion": ConsumableItem("生命药水", "恢复50点生命值", 5),
        "wood": MaterialItem("木材", "建造用的基础材料"),
        "stone": MaterialItem("石头", "坚硬的建造材料"),
        "bread": ConsumableItem("面包", "简单的食物，恢复少量生命值", 10)
    }


if __name__ == "__main__":
    # 测试代码
    print("=== 背包系统测试 ===")
    
    # 创建背包
    inventory = Inventory(10)
    
    # 创建测试物品
    items = create_sample_items()
    
    # 测试添加物品
    inventory.add_item(items["health_potion"], 3)
    inventory.add_item(items["wood"], 25)
    inventory.add_item(items["iron_sword"], 1)
    inventory.add_item(items["health_potion"], 4)  # 应该堆叠
    inventory.add_item(items["stone"], 15)
    
    # 显示背包
    inventory.display()
    
    print("\n=== 测试物品操作 ===")
    print(f"木材数量: {inventory.get_item_count('木材')}")
    print(f"是否有5个生命药水: {inventory.has_item('生命药水', 5)}")
    
    # 移除物品
    inventory.remove_item("木材", 10)
    inventory.remove_item("生命药水", 2)
    
    print("\n移除物品后:")
    inventory.display()
