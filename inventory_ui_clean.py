"""
背包和装备管理界面
提供玩家背包管理、装备系统和消耗品使用的图形化界面
"""

def show_inventory_menu(player):
    """显示背包管理菜单"""
    while True:
        print("\n" + "="*50)
        print(f"🎒 {player.name} 的背包管理")
        print("="*50)
        
        # 获取背包物品
        items = get_player_items(player)
        
        # 显示背包内容
        print_inventory(items)
        
        # 获取战场随从
        board = get_player_board(player)
        
        # 显示战场随从
        print_board_minions(board)
        
        # 显示操作菜单
        print_menu_options()
        
        # 处理用户选择
        choice = input("\n请选择操作 (1-5): ").strip()
        
        if choice == "1":
            view_item_details(player, items)
        elif choice == "2":
            equip_item_to_minion(player, items, board)
        elif choice == "3":
            unequip_item_from_minion(player, board)
        elif choice == "4":
            use_consumable_item(player, items)
        elif choice == "5":
            print("返回游戏...")
            break
        else:
            print("无效选择，请重试")

def get_player_items(player):
    """获取玩家背包物品"""
    if hasattr(player, 'inventory'):
        return player.inventory.get_all_items()
    return {}

def get_player_board(player):
    """获取玩家战场随从"""
    if hasattr(player, 'game') and player.game:
        battlefield = player.game.battlefield
        return battlefield.my_board if player.is_me else battlefield.op_board
    return []

def print_inventory(items):
    """显示背包内容"""
    print("\n📦 背包物品:")
    if not items:
        print("  (背包为空)")
    else:
        for i, (item_name, quantity) in enumerate(items.items(), 1):
            print(f"  {i}. {item_name} x{quantity}")

def print_board_minions(board):
    """显示战场随从"""
    print("\n🃏 战场随从:")
    if not board:
        print("  (战场上没有随从)")
    else:
        for i, card in enumerate(board, 1):
            attack = get_card_attack(card)
            hp = card.hp
            equipment_info = get_equipment_info(card)
            card_name = getattr(card, 'name', f'随从{i}')
            print(f"  {i}. {card_name} ({attack}/{hp}){equipment_info}")

def get_card_attack(card):
    """获取卡牌攻击力"""
    return card.get_total_attack() if hasattr(card, 'get_total_attack') else card.atk

def get_equipment_info(card):
    """获取装备信息字符串"""
    if not hasattr(card, 'equipment') or not card.equipment:
        return ""
    
    equipped_items = []
    if card.equipment.left_hand:
        equipped_items.append(f"左手:{card.equipment.left_hand.name}")
    if card.equipment.right_hand:
        equipped_items.append(f"右手:{card.equipment.right_hand.name}")
    if card.equipment.armor:
        equipped_items.append(f"护甲:{card.equipment.armor.name}")
    
    return f" [装备: {', '.join(equipped_items)}]" if equipped_items else ""

def print_menu_options():
    """显示菜单选项"""
    print("\n📋 操作选项:")
    print("  1. 查看物品详情")
    print("  2. 给随从装备武器/护甲")
    print("  3. 卸下随从装备")
    print("  4. 使用消耗品")
    print("  5. 返回游戏")

def view_item_details(player, items):
    """查看物品详情"""
    if not items:
        print("背包中没有物品")
        input("按回车继续...")
        return
    
    print("\n请选择要查看的物品:")
    item_list = list(items.keys())
    for i, item_name in enumerate(item_list, 1):
        print(f"  {i}. {item_name}")
    
    try:
        choice = int(input("请输入物品编号: ")) - 1
        if 0 <= choice < len(item_list):
            item_name = item_list[choice]
            item_obj = find_item_object(player, item_name)
            print_item_details(item_obj)
        else:
            print("无效的物品编号")
    except ValueError:
        print("请输入有效的数字")
    
    input("按回车继续...")

def print_item_details(item_obj):
    """打印物品详细信息"""
    if not item_obj:
        print("无法找到物品详细信息")
        return
    
    print(f"\n📄 {item_obj.name} 详情:")
    print(f"   描述: {item_obj.description}")
    print(f"   类型: {type(item_obj).__name__}")
    
    if hasattr(item_obj, 'attack_bonus'):
        print(f"   攻击力加成: +{item_obj.attack_bonus}")
    if hasattr(item_obj, 'defense_bonus'):
        print(f"   防御力加成: +{item_obj.defense_bonus}")
    if hasattr(item_obj, 'slot_type'):
        print(f"   装备位置: {item_obj.slot_type}")
    if hasattr(item_obj, 'heal_amount'):
        print(f"   治疗量: {item_obj.heal_amount}")

def equip_item_to_minion(player, items, board):
    """给随从装备物品"""
    if not items or not board:
        print("背包中没有物品或战场上没有随从")
        input("按回车继续...")
        return
    
    # 获取可装备物品
    equipment_items = get_equipment_items(player, items)
    if not equipment_items:
        print("背包中没有可装备的物品")
        input("按回车继续...")
        return
    
    # 选择装备
    print("\n🗡️ 可装备的物品:")
    for i, (item_name, item_obj) in enumerate(equipment_items, 1):
        print(f"  {i}. {format_equipment_display(item_name, item_obj)}")
    
    try:
        item_choice = int(input("选择要装备的物品编号: ")) - 1
        if 0 <= item_choice < len(equipment_items):
            item_name, item_obj = equipment_items[item_choice]
            
            # 选择随从
            card_choice = select_minion(board)
            if card_choice is not None:
                perform_equip(player, board[card_choice], item_name, item_obj)
    except ValueError:
        print("请输入有效的数字")
    
    input("按回车继续...")

def get_equipment_items(player, items):
    """获取可装备的物品列表"""
    equipment_items = []
    for item_name in items.keys():
        item_obj = find_item_object(player, item_name)
        if item_obj and hasattr(item_obj, 'slot_type'):
            equipment_items.append((item_name, item_obj))
    return equipment_items

def format_equipment_display(item_name, item_obj):
    """格式化装备显示信息"""
    slot_info = f"({item_obj.slot_type})" if hasattr(item_obj, 'slot_type') else ""
    attack_info = f"+{item_obj.attack_bonus}攻" if hasattr(item_obj, 'attack_bonus') and item_obj.attack_bonus > 0 else ""
    defense_info = f"+{item_obj.defense_bonus}防" if hasattr(item_obj, 'defense_bonus') and item_obj.defense_bonus > 0 else ""
    bonus_info = f" [{attack_info}{defense_info}]" if attack_info or defense_info else ""
    return f"{item_name}{slot_info}{bonus_info}"

def select_minion(board):
    """选择随从"""
    print("\n🃏 选择要装备的随从:")
    for i, card in enumerate(board, 1):
        card_name = getattr(card, 'name', f'随从{i}')
        print(f"  {i}. {card_name}")
    
    try:
        choice = int(input("选择随从编号: ")) - 1
        if 0 <= choice < len(board):
            return choice
    except ValueError:
        pass
    
    print("无效的随从编号")
    return None

def perform_equip(player, card, item_name, item_obj):
    """执行装备操作"""
    # 确保随从有装备系统
    if not hasattr(card, 'equipment'):
        from equipment_system import EquipmentSystem
        card.equipment = EquipmentSystem()
    
    # 尝试装备
    success = card.equipment.equip(item_obj)
    if success:
        remove_item_from_inventory(player, item_name, 1)
        card_name = getattr(card, 'name', '随从')
        print(f"✅ 成功为 {card_name} 装备了 {item_name}")
    else:
        print(f"❌ 装备失败，可能该部位已有装备或装备类型不匹配")

def unequip_item_from_minion(player, board):
    """卸下随从装备"""
    if not board:
        print("战场上没有随从")
        input("按回车继续...")
        return
    
    equipped_cards = get_equipped_cards(board)
    if not equipped_cards:
        print("没有随从装备了物品")
        input("按回车继续...")
        return
    
    # 显示有装备的随从
    print("\n🔧 有装备的随从:")
    for i, (card_idx, card, equipment_list) in enumerate(equipped_cards, 1):
        card_name = getattr(card, 'name', f'随从{card_idx+1}')
        equipment_names = [f"{slot}:{item.name}" for slot, item in equipment_list]
        print(f"  {i}. {card_name} [装备: {', '.join(equipment_names)}]")
    
    try:
        choice = int(input("选择要卸装备的随从: ")) - 1
        if 0 <= choice < len(equipped_cards):
            perform_unequip(player, equipped_cards[choice])
    except ValueError:
        print("请输入有效的数字")
    
    input("按回车继续...")

def get_equipped_cards(board):
    """获取有装备的随从列表"""
    equipped_cards = []
    for i, card in enumerate(board):
        if hasattr(card, 'equipment') and card.equipment:
            equipment_list = []
            if card.equipment.left_hand:
                equipment_list.append(('左手', card.equipment.left_hand))
            if card.equipment.right_hand:
                equipment_list.append(('右手', card.equipment.right_hand))
            if card.equipment.armor:
                equipment_list.append(('护甲', card.equipment.armor))
            
            if equipment_list:
                equipped_cards.append((i, card, equipment_list))
    return equipped_cards

def perform_unequip(player, equipped_card_data):
    """执行卸装备操作"""
    card_idx, card, equipment_list = equipped_card_data
    
    print("\n选择要卸下的装备:")
    for i, (slot, item) in enumerate(equipment_list, 1):
        print(f"  {i}. {slot}: {item.name}")
    
    try:
        equip_choice = int(input("选择装备编号: ")) - 1
        if 0 <= equip_choice < len(equipment_list):
            slot, item = equipment_list[equip_choice]
            
            success = card.equipment.unequip(slot)
            if success:
                add_item_to_inventory(player, item, 1)
                card_name = getattr(card, 'name', '随从')
                print(f"✅ 成功从 {card_name} 的{slot}卸下了 {item.name}")
            else:
                print("❌ 卸装备失败")
        else:
            print("无效的装备编号")
    except ValueError:
        print("请输入有效的数字")

def use_consumable_item(player, items):
    """使用消耗品"""
    if not items:
        print("背包中没有物品")
        input("按回车继续...")
        return
    
    consumable_items = get_consumable_items(player, items)
    if not consumable_items:
        print("背包中没有可使用的消耗品")
        input("按回车继续...")
        return
    
    print("\n🧪 可使用的消耗品:")
    for i, (item_name, item_obj) in enumerate(consumable_items, 1):
        heal_info = f"(恢复{item_obj.heal_amount}HP)" if hasattr(item_obj, 'heal_amount') else ""
        print(f"  {i}. {item_name} {heal_info}")
    
    try:
        choice = int(input("选择要使用的消耗品编号: ")) - 1
        if 0 <= choice < len(consumable_items):
            item_name, item_obj = consumable_items[choice]
            perform_use_item(player, item_name)
    except ValueError:
        print("请输入有效的数字")
    
    input("按回车继续...")

def get_consumable_items(player, items):
    """获取可使用的消耗品列表"""
    consumable_items = []
    for item_name in items.keys():
        item_obj = find_item_object(player, item_name)
        if item_obj and (hasattr(item_obj, 'effect') or 'ConsumableItem' in str(type(item_obj))):
            consumable_items.append((item_name, item_obj))
    return consumable_items

def perform_use_item(player, item_name):
    """执行使用物品操作"""
    if hasattr(player, 'use_item'):
        success = player.use_item(item_name, 1)
        if success:
            print(f"✅ 成功使用了 {item_name}")
        else:
            print(f"❌ 使用 {item_name} 失败")
    else:
        print("玩家没有使用物品的功能")

# 工具函数
def find_item_object(player, item_name):
    """查找物品对象"""
    if hasattr(player, 'inventory'):
        for slot in player.inventory.slots:
            if slot.item.name == item_name:
                return slot.item
    return None

def add_item_to_inventory(player, item, quantity):
    """添加物品到背包"""
    if hasattr(player, 'add_to_inventory'):
        return player.add_to_inventory(item, quantity)
    elif hasattr(player, 'inventory'):
        return player.inventory.add_item(item, quantity)
    return False

def remove_item_from_inventory(player, item_name, quantity):
    """从背包移除物品"""
    if hasattr(player, 'remove_from_inventory'):
        return player.remove_from_inventory(item_name, quantity)
    elif hasattr(player, 'inventory'):
        return player.inventory.remove_item(item_name, quantity)
    return False
