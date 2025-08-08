"""
多人游戏系统演示
用于测试新的三区域游戏机制
"""

from multiplayer_game import MultiPlayerGame, GameManager
from game_display import show_multiplayer_game
import time

def demo_multiplayer_system():
    """演示多人游戏系统"""
    print("=== 多人游戏系统演示 ===\n")
    
    # 创建游戏管理器
    game_manager = GameManager()
    
    # 创建新游戏
    game_id, game = game_manager.create_game(max_players=4)
    print(f"创建游戏 ID: {game_id}")
    
    # 添加玩家
    players = [
        ("Alice", "玩家A"),
        ("Bob", "玩家B"), 
        ("Charlie", "玩家C"),
        ("Diana", "玩家D")
    ]
    
    for pid, name in players:
        success, message = game.add_player(pid, name)
        print(f"添加玩家 {name}: {message}")
    
    # 启动游戏
    success, message = game.start_game()
    print(f"启动游戏: {message}")
    
    if not success:
        return
    
    # 演示几个游戏回合
    for turn in range(3):
        print(f"\n=== 演示回合 {turn + 1} ===")
        
        # 获取游戏状态
        game_state = game.get_game_state()
        
        # 显示游戏界面
        show_multiplayer_game(game_state, "Alice")
        
        # 模拟玩家行动
        current_player = game.get_current_player()
        if current_player:
            print(f"\n{current_player.name} 的回合")
            
            # 模拟一些行动
            time.sleep(1)
            
            # 切换到下一个玩家
            game.next_turn()
        
        input("\n按回车继续下一回合...")
    
    print("\n演示完成！")

def demo_npc_system():
    """演示NPC系统"""
    print("\n=== NPC系统演示 ===")
    
    from multiplayer_game import NPCZone
    npc_zone = NPCZone()
    npc_zone.initialize()
    
    print("NPC区域状态:")
    state = npc_zone.get_state()
    for npc in state['npcs']:
        print(f"  {npc['name']}: 攻击力{npc['atk']}, 血量{npc['hp']}")
    
    # 模拟NPC回合
    print("\n执行NPC回合...")
    from player import Player
    test_players = {
        'p1': Player("测试玩家1"),
        'p2': Player("测试玩家2")
    }
    
    # 记录玩家血量变化
    for pid, player in test_players.items():
        print(f"行动前 {player.name}: {player.hp} HP")
    
    npc_zone.execute_turn(test_players)
    
    for pid, player in test_players.items():
        print(f"行动后 {player.name}: {player.hp} HP")

def demo_resource_system():
    """演示资源系统"""
    print("\n=== 资源系统演示 ===")
    
    from multiplayer_game import ResourceZone
    resource_zone = ResourceZone()
    resource_zone.initialize()
    
    print("资源区域状态:")
    state = resource_zone.get_state()
    for i, resource in enumerate(state['available_resources'], 1):
        print(f"  {i}. {resource['name']} ({resource['type']})")
    
    # 模拟资源领取
    print("\n模拟玩家领取资源...")
    resource = resource_zone.claim_resource('player1', 0)
    if resource:
        print(f"玩家1 领取了: {resource.name}")
    
    # 显示更新后的状态
    state = resource_zone.get_state()
    print(f"剩余资源: {len(state['available_resources'])} 个")

def demo_game_display():
    """演示游戏界面显示"""
    print("\n=== 界面显示演示 ===")
    
    # 创建模拟游戏状态
    mock_game_state = {
        'phase': '战斗阶段',
        'turn': 5,
        'current_player': 'Alice',
        'players': {
            'Alice': {
                'name': 'Alice',
                'hp': 25,
                'max_hp': 30,
                'hand_count': 5,
                'board_count': 2,
                'inventory_count': 8
            },
            'Bob': {
                'name': 'Bob', 
                'hp': 20,
                'max_hp': 30,
                'hand_count': 4,
                'board_count': 3,
                'inventory_count': 6
            }
        },
        'npc_zone': {
            'npcs': [
                {'name': '哥布林战士', 'atk': 2, 'hp': 3},
                {'name': '石头守卫', 'atk': 1, 'hp': 4}
            ],
            'difficulty': 2,
            'boss_present': False
        },
        'resource_zone': {
            'available_resources': [
                {'name': '铁剑', 'type': 'WeaponItem'},
                {'name': '生命药水', 'type': 'ConsumableItem'},
                {'name': '木材', 'type': 'MaterialItem'}
            ],
            'next_refresh': 2
        }
    }
    
    # 显示界面
    show_multiplayer_game(mock_game_state, 'Alice')
    
    input("\n按回车继续...")

if __name__ == "__main__":
    print("选择要演示的系统:")
    print("1. 完整多人游戏系统")
    print("2. NPC敌人系统")
    print("3. 公共资源系统") 
    print("4. 游戏界面显示")
    print("5. 全部演示")
    
    choice = input("请选择 (1-5): ").strip()
    
    if choice == "1":
        demo_multiplayer_system()
    elif choice == "2":
        demo_npc_system()
    elif choice == "3":
        demo_resource_system()
    elif choice == "4":
        demo_game_display()
    elif choice == "5":
        demo_npc_system()
        demo_resource_system()
        demo_game_display()
        demo_multiplayer_system()
    else:
        print("无效选择")
