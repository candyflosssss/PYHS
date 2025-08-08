"""
PvE多人游戏测试
测试新的PvE系统功能
"""

from pve_multiplayer_game import PvEMultiplayerGame, PvEGameManager, GamePhase
from pve_content_factory import EnemyFactory, ResourceFactory, BossFactory
import time

def test_pve_game():
    """测试PvE游戏基本功能"""
    print("=== PvE游戏测试 ===")
    
    # 创建游戏管理器
    manager = PvEGameManager()
    
    # 服务器玩家创建游戏
    server_player_id = "server_player"
    game_id, game = manager.create_game(server_player_id)
    
    print(f"游戏已创建，ID: {game_id}")
    
    # 添加玩家
    success, msg = game.add_player(server_player_id, "房主")
    print(f"房主加入: {success}, {msg}")
    
    success, msg = game.add_player("player2", "玩家2")
    print(f"玩家2加入: {success}, {msg}")
    
    success, msg = game.add_player("player3", "玩家3") 
    print(f"玩家3加入: {success}, {msg}")
    
    # 显示游戏状态
    print("\n=== 等待房间状态 ===")
    state = game.get_game_state()
    print(f"阶段: {state['phase']}")
    print(f"玩家数: {len(state['players'])}")
    for pid, player_data in state['players'].items():
        print(f"  {player_data['name']} (HP: {player_data['hp']}/{player_data['max_hp']})")
    
    # 开始准备阶段
    print("\n=== 开始准备阶段 ===")
    success, msg = game.start_preparation()
    print(f"准备阶段: {success}, {msg}")
    
    # 显示准备后状态
    state = game.get_game_state()
    print(f"阶段: {state['phase']}")
    print(f"资源区: {state['resource_zone']}")
    print(f"敌人区: {state['enemy_zone']}")
    print(f"Boss: {state['boss']}")
    
    # 开始游戏
    print("\n=== 开始游戏 ===")
    success, msg = game.start_game()
    print(f"游戏开始: {success}, {msg}")
    
    # 显示游戏开始后状态
    state = game.get_game_state()
    print(f"阶段: {state['phase']}")
    print(f"回合数: {state['turn_number']}")
    print(f"当前玩家索引: {state['current_player_index']}")
    
    current_player = game.get_current_player()
    if current_player:
        print(f"当前回合玩家: {current_player.name}")
        print(f"手牌数: {len(current_player.hand)}")
    
    # 测试收集资源
    print("\n=== 测试收集资源 ===")
    if state['resource_zone']:
        resource = game.collect_resource(server_player_id, 0)
        if resource:
            print(f"成功收集资源: {resource}")
        else:
            print("收集资源失败")
    
    # 模拟一些回合
    print("\n=== 模拟回合进行 ===")
    for i in range(3):
        current_player = game.get_current_player()
        if current_player:
            print(f"回合 {i+1}: {current_player.name} 的回合")
            
            # 出一张牌（如果有的话）
            if current_player.hand:
                try:
                    current_player.play_card(0)  # 出第一张手牌
                    print(f"  {current_player.name} 出了一张牌")
                except Exception as e:
                    print(f"  出牌失败: {e}")
            
            # 结束回合
            game.next_turn()
            print(f"  {current_player.name} 结束回合")
        
        time.sleep(0.5)  # 稍作停顿
    
    print("\n=== 测试完成 ===")
    final_state = game.get_game_state()
    print(f"最终阶段: {final_state['phase']}")
    print(f"最终回合数: {final_state['turn_number']}")

def test_factories():
    """测试工厂类"""
    print("\n=== 工厂测试 ===")
    
    # 测试敌人工厂
    print("敌人:")
    goblin = EnemyFactory.create_goblin()
    orc = EnemyFactory.create_orc()
    skeleton = EnemyFactory.create_skeleton()
    print(f"  {goblin}")
    print(f"  {orc}")
    print(f"  {skeleton}")
    
    # 测试资源工厂
    print("资源:")
    sword = ResourceFactory.create_wooden_sword()
    potion = ResourceFactory.create_health_potion()
    armor = ResourceFactory.create_leather_armor()
    print(f"  {sword}")
    print(f"  {potion}")
    print(f"  {armor}")
    
    # 测试Boss工厂
    print("Boss:")
    dragon = BossFactory.create_dragon_boss()
    demon = BossFactory.create_demon_boss()
    lich = BossFactory.create_lich_boss()
    print(f"  {dragon}")
    print(f"  {demon}")
    print(f"  {lich}")

if __name__ == "__main__":
    test_factories()
    test_pve_game()
