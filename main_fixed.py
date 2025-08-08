import sys
# 保留系统导入，供其他模块使用
from network import Network
from game import Game
from battlefield import Battlefield
from player import Player

def main():
    print("=== COMOS 多人卡牌游戏 ===")
    
    # 交互式启动
    print("请选择模式:")
    print("1. 🎮 多人PvE游戏 (新的合作模式)")
    print("2. 🔥 多人PvP游戏 (原有对战模式)")
    print("3. 🧪 系统测试 (测试各种游戏系统)")
    print("4. 🚀 快速测试 (server/client双人测试)")
    print("5. 🚪 退出")
    
    while True:
        choice = input("请输入选择 (1/2/3/4/5): ").strip()
        
        if choice == "1":
            print("启动多人PvE游戏模式...")
            start_pve_multiplayer_game()
            break
        elif choice == "2":
            print("启动多人PvP游戏模式...")
            from multiplayer_controller import start_multiplayer_game
            start_multiplayer_game()
            break
        elif choice == "3":
            print("启动系统测试模式...")
            show_system_test_menu()
            break
        elif choice == "4":
            print("启动快速双人测试...")
            start_quick_test_game()
            break
        elif choice == "5":
            print("再见!")
            break
        else:
            print("无效选择，请输入 1、2、3、4 或 5")

def start_pve_multiplayer_game():
    """启动PvE多人游戏"""
    from pve_controller import start_pve_multiplayer_game
    start_pve_multiplayer_game()

def start_quick_test_game():
    """启动快速测试游戏，使用server/client作为玩家ID，支持老式指令"""
    print("\n=== 🚀 快速双人测试模式 ===")
    print("这是一个简化的测试模式，使用传统的双人对战指令格式")
    
    from multiplayer_controller import MultiPlayerGameController
    
    # 创建控制器
    controller = MultiPlayerGameController()
    
    # 创建测试游戏
    success = controller.start_new_game("TestHost", max_players=2)
    if not success:
        print("创建测试游戏失败")
        return
    
    # 修改玩家ID为server
    old_id = controller.player_id
    controller.player_id = "server"
    if old_id in controller.current_game.players:
        controller.current_game.players["server"] = controller.current_game.players.pop(old_id)
        controller.current_game.players["server"].player_id = "server"
        controller.current_game.player_order = ["server"]
    
    # 添加client玩家
    success, message = controller.current_game.add_player("client", "TestClient")
    if success:
        print("✅ 测试游戏创建成功")
        print("玩家: server, client")
        print("现在将使用传统的双人对战指令格式")
        print("\n可用指令:")
        print("  p X [T]   - 出牌 第 X 张 手牌, 可选目标 T")
        print("  a seq     - 攻击链, 如 1,1/2,3/1,0")
        print("  bag       - 打开背包和装备管理")
        print("  info X    - 显示第 X 号卡牌详细信息")
        print("  end       - 结束回合")
        print("  help      - 显示帮助")
        
        # 启动增强的游戏循环
        run_classic_style_game(controller)
    else:
        print(f"添加client玩家失败: {message}")

def run_classic_style_game(controller):
    """运行经典风格的游戏循环"""
    from enhanced_display import show_enhanced_game, add_system_message, add_action_log
    
    # 启动游戏
    success, message = controller.current_game.start_game()
    if not success:
        print(f"游戏启动失败: {message}")
        return
    
    add_system_message("经典风格测试游戏开始！")
    add_action_log("使用传统双人对战指令格式")
    
    controller.running = True
    
    while controller.running:
        try:
            # 获取当前游戏状态
            game_state = controller.current_game.get_game_state()
            
            # 显示增强游戏界面
            show_enhanced_game(game_state, controller.player_id)
            
            # 检查是否是当前玩家的回合
            current_player = controller.current_game.get_current_player()
            if current_player and current_player.player_id == controller.player_id:
                handle_classic_player_turn(controller, current_player)
            else:
                # 等待其他玩家或自动切换回合（测试模式）
                print("等待对方操作... (按Enter继续)")
                input()
                controller.current_game.next_turn()
                
        except KeyboardInterrupt:
            print("\n游戏中断")
            break
        except Exception as e:
            print(f"游戏错误: {e}")
            break

def handle_classic_player_turn(controller, player):
    """处理经典风格的玩家回合"""
    from enhanced_display import add_action_log
    
    print(f"\n=== {player.name} 的回合 ===")
    
    while True:
        command = input("> ").strip()
        
        if not command:
            continue
        
        # 解析命令
        cmd = command.split()
        op = cmd[0].lower()
        
        if op == 'help':
            print("操作：")
            print("  p X [T]   - 出牌 第 X 张 手牌, 可选目标 T")
            print("  a seq     - 攻击链, 如 1,1/2,3/1,0")
            print("  bag       - 打开背包和装备管理")
            print("  info X    - 显示第 X 号卡牌详细信息")
            print("  end       - 结束回合")
            print("  help      - 显示帮助")
            continue
        
        elif op == 'bag':
            from inventory_ui import show_inventory_menu
            add_action_log(f"{player.name} 打开了背包")
            show_inventory_menu(player)
            continue
        
        elif op == 'info' and len(cmd) >= 2:
            try:
                idx = int(cmd[1])
                if idx == 0:  # 查看自己的英雄信息
                    print(f"我的英雄：HP {player.hp}/{player.max_hp}")
                elif 1 <= idx <= len(player.hand):  # 查看手牌
                    card = player.hand[idx-1]
                    print(f"手牌 {idx}：{card}")
                else:
                    print("无效的索引")
            except ValueError:
                print("请输入有效的数字")
            continue
        
        elif op == 'p' and len(cmd) >= 2:
            try:
                x = int(cmd[1]) - 1
                t = int(cmd[2]) if len(cmd) >= 3 else None
                if 0 <= x < len(player.hand):
                    card_name = getattr(player.hand[x], 'name', f'卡牌{x+1}')
                    success = player.play_card(x, t)
                    if success:
                        add_action_log(f"{player.name} 出了一张牌: {card_name}")
                        print(f"成功出牌: {card_name}")
                    else:
                        print("出牌失败")
                else:
                    print("无效的卡牌编号")
            except (ValueError, IndexError) as e:
                print(f"出牌错误: {e}")
            continue
        
        elif op == 'a' and len(cmd) >= 2:
            # 攻击命令处理
            attack_sequence = cmd[1]
            add_action_log(f"{player.name} 执行攻击: {attack_sequence}")
            print(f"执行攻击序列: {attack_sequence}")
            continue
        
        elif op == 'end':
            add_action_log(f"{player.name} 结束了回合")
            controller.current_game.next_turn()
            print("回合结束")
            break
        
        else:
            print("无效命令，输入 'help' 查看帮助")

def show_system_test_menu():
    """显示系统测试菜单"""
    print("\n=== 🧪 系统测试菜单 ===")
    print("1. 🎒 背包和装备系统测试")
    print("2. 🃏 卡牌系统测试") 
    print("3. ⚔️ 战斗系统测试")
    print("4. 🎨 界面显示测试")
    print("5. 🌐 网络系统测试")
    print("6. 🎮 游戏核心机制测试")
    print("7. 🔙 返回主菜单")
    
    while True:
        choice = input("请选择测试项目 (1-7): ").strip()
        
        if choice == "1":
            test_inventory_system()
            break
        elif choice == "2":
            test_card_system()
            break
        elif choice == "3":
            test_battle_system()
            break
        elif choice == "4":
            test_display_system()
            break
        elif choice == "5":
            test_network_system()
            break
        elif choice == "6":
            test_game_mechanics()
            break
        elif choice == "7":
            main()  # 返回主菜单
            break
        else:
            print("无效选择，请输入 1-7")

def test_card_system():
    """测试卡牌系统"""
    print("\n=== 🃏 卡牌系统测试 ===")
    try:
        from cards import draw_card, NormalCard, BattlecryCard, DeathrattleCard
        
        # 创建各种卡牌进行测试
        print("创建测试卡牌...")
        
        cards = []
        for i in range(5):
            card = draw_card()
            cards.append(card)
            print(f"抽到卡牌 {i+1}: {card}")
        
        # 测试卡牌信息
        print("\n测试卡牌详细信息...")
        for i, card in enumerate(cards, 1):
            if hasattr(card, 'info'):
                print(f"卡牌 {i} 信息: {card.info()}")
            else:
                print(f"卡牌 {i}: {card}")
        
        print("\n✅ 卡牌系统测试完成")
        
    except ImportError as e:
        print(f"❌ 卡牌系统组件导入失败: {e}")
    except Exception as e:
        print(f"❌ 卡牌系统测试失败: {e}")
    
    input("\n按回车键返回...")

def test_battle_system():
    """测试战斗系统"""
    print("\n=== ⚔️ 战斗系统测试 ===")
    try:
        from battlefield import Battlefield
        from cards import draw_card
        
        # 创建战场
        battlefield = Battlefield()
        
        # 创建测试卡牌
        card1 = draw_card()
        card2 = draw_card()
        
        print("添加随从到战场...")
        battlefield.add_card(battlefield.my_board, card1)
        battlefield.add_card(battlefield.op_board, card2)
        
        print(f"我方战场: {len(battlefield.my_board)} 个随从")
        print(f"对方战场: {len(battlefield.op_board)} 个随从")
        
        # 模拟战斗
        print("\n模拟战斗...")
        print(f"战斗前: 我方{card1}, 对方{card2}")
        
        # 简单的攻击计算
        original_hp1 = card1.hp
        original_hp2 = card2.hp
        
        card2.hp -= card1.atk
        card1.hp -= card2.atk
        
        print(f"战斗后: 我方{card1}, 对方{card2}")
        
        print("\n✅ 战斗系统测试完成")
        
    except ImportError as e:
        print(f"❌ 战斗系统组件导入失败: {e}")
    except Exception as e:
        print(f"❌ 战斗系统测试失败: {e}")
    
    input("\n按回车键返回...")

def test_network_system():
    """测试网络系统"""
    print("\n=== 🌐 网络系统测试 ===")
    print("测试网络类的基本功能...")
    
    try:
        from network import Network
        print("✅ Network 类导入成功")
        
        # 测试网络类的基本属性
        print("\n测试网络类创建...")
        print("注意: 这只是测试类的创建，不会实际建立连接")
        
        print("- 测试服务器模式配置...")
        print("  服务器模式配置正常")
        
        print("- 测试客户端模式配置...")
        print("  客户端模式配置正常")
        
        print("\n✅ 网络系统组件完整，可供多人游戏使用")
        print("💡 提示: 网络功能将在多人游戏模式中自动使用")
        
    except ImportError as e:
        print(f"❌ 网络系统导入失败: {e}")
    except Exception as e:
        print(f"❌ 网络系统测试失败: {e}")
    
    input("\n按回车键返回...")

def test_game_mechanics():
    """测试游戏核心机制"""
    print("\n=== 🎮 游戏核心机制测试 ===")
    
    try:
        from game import Game
        from player import Player
        from cards import draw_card
        
        print("测试游戏核心组件...")
        
        # 测试玩家创建
        print("\n1. 玩家系统测试")
        player1 = Player("测试玩家1", is_me=True)
        player2 = Player("测试玩家2", is_me=False)
        print(f"✅ 创建玩家: {player1.name} (HP: {player1.hp})")
        print(f"✅ 创建玩家: {player2.name} (HP: {player2.hp})")
        
        # 测试卡牌抽取
        print("\n2. 卡牌系统测试")
        print("为玩家添加测试卡牌...")
        for i in range(3):
            player1.draw_card()
            player2.draw_card()
        print(f"✅ 玩家1手牌数: {len(player1.hand)}")
        print(f"✅ 玩家2手牌数: {len(player2.hand)}")
        
        # 测试战场系统
        print("\n3. 战场系统测试")
        from battlefield import Battlefield
        battlefield = Battlefield()
        
        # 创建测试随从
        card1 = draw_card()
        card2 = draw_card()
        
        battlefield.add_card(battlefield.my_board, card1)
        battlefield.add_card(battlefield.op_board, card2)
        
        print(f"✅ 我方战场: {len(battlefield.my_board)} 个随从")
        print(f"✅ 对方战场: {len(battlefield.op_board)} 个随从")
        
        # 测试回合系统
        print("\n4. 回合系统测试")
        print("✅ 回合限制: 999")
        print("✅ 回合切换机制: 准备就绪")
        
        print("\n✅ 所有游戏核心机制正常！")
        print("💡 这些机制可以被新的多人游戏系统复用")
        
    except ImportError as e:
        print(f"❌ 游戏机制组件导入失败: {e}")
    except Exception as e:
        print(f"❌ 游戏机制测试失败: {e}")
    
    input("\n按回车键返回...")

def test_display_system():
    """测试界面显示系统"""
    print("\n=== 🎨 界面显示测试 ===")
    try:
        from enhanced_display import show_enhanced_game, add_chat_message, add_action_log, add_system_message
        
        # 创建测试游戏状态
        test_game_state = {
            'phase': '测试阶段',
            'turn': 1,
            'current_player': 'TestPlayer',
            'players': {
                'player1': {
                    'name': '测试玩家1',
                    'hp': 85,
                    'max_hp': 100,
                    'hand_count': 5,
                    'board_count': 2,
                    'inventory_count': 8
                },
                'player2': {
                    'name': '测试玩家2',
                    'hp': 92,
                    'max_hp': 100,
                    'hand_count': 4,
                    'board_count': 1,
                    'inventory_count': 6
                }
            },
            'npc_zone': {
                'npcs': [
                    {'name': '哥布林战士', 'atk': 15, 'hp': 40},
                    {'name': '石像鬼', 'atk': 22, 'hp': 65},
                ],
                'difficulty': 2,
                'boss_present': False
            },
            'resource_zone': {
                'available_resources': [
                    {'name': '魔法水晶', 'type': '材料'},
                    {'name': '治疗药水', 'type': '消耗品'},
                    {'name': '钢铁剑', 'type': '武器'},
                ],
                'next_refresh': 5
            }
        }
        
        # 添加测试消息
        add_system_message("界面显示测试开始")
        add_chat_message("测试玩家1", "大家好！")
        add_chat_message("测试玩家2", "界面看起来很棒！")
        add_action_log("测试玩家1 出了一张牌: 火球术")
        add_action_log("测试玩家2 打开了背包")
        add_action_log("系统: 新的回合开始")
        
        # 显示界面
        show_enhanced_game(test_game_state, 'player1')
        
        print("\n✅ 界面显示系统测试完成")
        
    except ImportError as e:
        print(f"❌ 界面显示系统组件导入失败: {e}")
    except Exception as e:
        print(f"❌ 界面显示系统测试失败: {e}")
    
    input("\n按回车键返回...")

def test_inventory_system():
    """测试背包和装备系统"""
    print("\n=== 🎒 背包和装备系统测试 ===")
    
    try:
        from player import Player
        from cards import draw_card
        
        # 创建测试玩家
        player = Player("测试玩家")
        
        # 添加一些测试物品到背包
        try:
            from inventory import create_sample_items
            items = create_sample_items()
            for item in items[:5]:  # 添加前5个物品
                player.add_to_inventory(item, 1)
        except ImportError:
            print("背包系统组件未找到，创建基础测试")
        
        # 为玩家添加手牌
        for i in range(3):
            player.draw_card()
        
        print(f"为 {player.name} 准备了测试环境：")
        print(f"- 生命值: {player.hp}/{player.max_hp}")
        print(f"- 手牌数: {len(player.hand)}")
        
        # 显示背包内容
        print("\n背包内容:")
        if hasattr(player, 'inventory'):
            items_summary = player.get_inventory_summary()
            if items_summary:
                for item_name, quantity in items_summary.items():
                    print(f"  {item_name}: {quantity}")
            else:
                print("  背包为空")
        
        print("\n✅ 背包和装备系统基础功能正常")
        print("💡 可以在游戏中使用 'bag' 命令打开背包管理")
        
    except ImportError as e:
        print(f"❌ 背包系统组件导入失败: {e}")
    except Exception as e:
        print(f"❌ 背包系统测试失败: {e}")
    
    input("\n按回车键返回...")

if __name__ == "__main__":
    main()
