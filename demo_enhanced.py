"""
增强显示系统演示 - 支持颜色、滚动和一致缩进
"""

from enhanced_display import enhanced_display, add_chat_message, add_action_log, add_system_message
import time
import random

def demo_enhanced_interface():
    """演示增强界面的所有功能"""
    
    print("=== 增强界面功能演示 ===")
    print("新功能包括:")
    print("1. 彩色文本支持（不同类型信息用不同颜色）")
    print("2. 自动滚动（聊天和操作记录超出限制时自动滚动）")
    print("3. 一致的缩进和对齐")
    print("4. 优化的布局和视觉效果")
    
    input("\n按回车键开始演示...")
    
    # 模拟完整的游戏状态
    game_state = {
        'phase': '激战中',
        'turn': 15,
        'current_player': '勇敢小战士',
        'players': {
            'player1': {
                'name': '勇敢小战士',
                'hp': 75,
                'max_hp': 100,
                'hand_count': 4,
                'board_count': 3,
                'inventory_count': 12
            },
            'player2': {
                'name': '智慧法师',
                'hp': 88,
                'max_hp': 100,
                'hand_count': 6,
                'board_count': 2,
                'inventory_count': 8
            },
            'player3': {
                'name': '敏捷盗贼',
                'hp': 45,  # 低血量显示红色
                'max_hp': 100,
                'hand_count': 5,
                'board_count': 1,
                'inventory_count': 15
            },
            'player4': {
                'name': '神圣牧师',
                'hp': 92,
                'max_hp': 100,
                'hand_count': 3,
                'board_count': 4,
                'inventory_count': 6
            }
        },
        'npc_zone': {
            'npcs': [
                {'name': '暗影龙王', 'atk': 35, 'hp': 120},
                {'name': '地狱犬', 'atk': 28, 'hp': 85},
                {'name': '邪恶术士', 'atk': 22, 'hp': 65},
            ],
            'difficulty': 4,
            'boss_present': True  # BOSS出现
        },
        'resource_zone': {
            'available_resources': [
                {'name': '传说武器', 'type': '装备'},
                {'name': '复活药剂', 'type': '消耗品'},
                {'name': '魔法卷轴', 'type': '法术'},
                {'name': '神秘宝石', 'type': '材料'},
            ],
            'next_refresh': 2
        }
    }
    
    # 阶段1：添加系统消息和初始状态
    add_system_message("多人游戏战斗开始！")
    add_system_message("当前遭遇BOSS暗影龙王！")
    add_action_log("游戏进入第15回合")
    
    # 显示初始状态
    enhanced_display.show_game(game_state, 'player1')
    input("\n第一阶段：基础界面显示（按回车继续）...")
    
    # 阶段2：模拟聊天对话
    chat_messages = [
        ("勇敢小战士", "大家小心！BOSS出现了！"),
        ("智慧法师", "我准备了群体治疗法术"),
        ("敏捷盗贼", "我血量不多了，需要支援"),
        ("神圣牧师", "马上给你治疗！"),
        ("勇敢小战士", "我来吸引BOSS注意力"),
        ("智慧法师", "好的，我准备火球术"),
    ]
    
    for player, message in chat_messages:
        add_chat_message(player, message)
        add_action_log(f"{player} 发送了聊天消息")
        time.sleep(0.5)  # 模拟实时聊天
    
    enhanced_display.show_game(game_state, 'player1')
    input("\n第二阶段：聊天系统演示（按回车继续）...")
    
    # 阶段3：模拟游戏操作
    game_actions = [
        "勇敢小战士 出了一张牌: 钢铁护盾",
        "智慧法师 对 暗影龙王 施放火球术",
        "敏捷盗贼 使用了 隐身药水",
        "神圣牧师 对 敏捷盗贼 施放治疗术",
        "暗影龙王 对全体玩家施放暗影冲击",
        "勇敢小战士 领取了资源: 传说武器",
        "智慧法师 打开了背包",
        "神圣牧师 向 地狱犬 发起攻击",
        "敏捷盗贼 结束了回合",
        "智慧法师 出了一张牌: 冰霜新星",
    ]
    
    for action in game_actions:
        add_action_log(action)
        time.sleep(0.3)
    
    # 添加更多聊天（测试滚动）
    add_chat_message("勇敢小战士", "这个BOSS太强了！")
    add_chat_message("智慧法师", "坚持住，我们快要赢了！")
    add_chat_message("神圣牧师", "[私聊→敏捷盗贼] 你的血量现在怎么样？")
    add_chat_message("敏捷盗贼", "谢谢治疗，好多了！")
    
    enhanced_display.show_game(game_state, 'player1')
    input("\n第三阶段：操作记录和滚动演示（按回车继续）...")
    
    # 阶段4：测试滚动功能
    print("\n测试自动滚动功能...")
    for i in range(10):
        add_chat_message(f"测试者{i+1}", f"这是第{i+1}条测试消息，用于测试聊天区的自动滚动功能")
        add_action_log(f"测试操作{i+1}: 这是第{i+1}条操作记录，用于测试操作记录区的自动滚动")
        if i % 3 == 0:  # 每3条消息显示一次界面
            enhanced_display.show_game(game_state, 'player1')
            time.sleep(1)
    
    enhanced_display.show_game(game_state, 'player1')
    input("\n第四阶段：滚动功能测试完成（按回车继续）...")
    
    # 最终展示
    print("\n=== 增强界面演示完成 ===")
    print("新功能总结:")
    print("✓ 彩色文本 - 不同类型信息用不同颜色区分")
    print("✓ 自动滚动 - 聊天和操作记录自动滚动显示最新内容")
    print("✓ 一致缩进 - 所有区域都有统一的对齐和格式")
    print("✓ 优化布局 - 更清晰的区域划分和视觉层次")
    print("✓ 实时更新 - 支持动态添加聊天和操作记录")

def interactive_enhanced_demo():
    """交互式增强界面演示"""
    print("\n=== 交互式增强界面演示 ===")
    print("体验新的彩色界面和滚动功能！")
    print("\n可用命令:")
    print("- chat <玩家名> <消息>: 模拟聊天消息")
    print("- action <描述>: 添加操作记录")
    print("- spam: 快速添加多条消息测试滚动")
    print("- clear: 清空聊天和操作记录")
    print("- quit: 退出演示")
    
    # 简化的游戏状态
    demo_state = {
        'phase': '演示模式',
        'turn': 1,
        'current_player': '演示玩家',
        'players': {
            'demo': {
                'name': '演示玩家',
                'hp': 100,
                'max_hp': 100,
                'hand_count': 5,
                'board_count': 2,
                'inventory_count': 8
            },
            'demo2': {
                'name': '测试伙伴',
                'hp': 85,
                'max_hp': 100,
                'hand_count': 3,
                'board_count': 1,
                'inventory_count': 6
            }
        },
        'npc_zone': {
            'npcs': [
                {'name': '训练假人', 'atk': 5, 'hp': 50},
            ],
            'difficulty': 1,
            'boss_present': False
        },
        'resource_zone': {
            'available_resources': [
                {'name': '训练剑', 'type': '武器'},
                {'name': '生命药水', 'type': '消耗品'},
            ],
            'next_refresh': 5
        }
    }
    
    add_system_message("欢迎使用交互式演示！")
    
    while True:
        enhanced_display.show_game(demo_state, 'demo')
        
        command = input("\n请输入命令 > ").strip()
        
        if not command:
            continue
        
        parts = command.split(' ', 2)
        cmd = parts[0].lower()
        
        if cmd == 'quit':
            break
        elif cmd == 'chat' and len(parts) >= 3:
            player_name = parts[1]
            message = parts[2]
            add_chat_message(player_name, message)
        elif cmd == 'action' and len(parts) >= 2:
            action_desc = ' '.join(parts[1:])
            add_action_log(action_desc)
        elif cmd == 'spam':
            print("快速添加测试消息...")
            for i in range(15):
                add_chat_message(f"玩家{i%3+1}", f"测试消息 #{i+1}")
                add_action_log(f"测试操作 #{i+1}")
            print("消息添加完成！")
        elif cmd == 'clear':
            enhanced_display.chat_history.clear()
            enhanced_display.action_log.clear()
            add_system_message("聊天和操作记录已清空")
        else:
            print("无效命令！请查看帮助信息。")

if __name__ == "__main__":
    try:
        demo_enhanced_interface()
        
        choice = input("\n是否进行交互式演示？(y/n): ")
        if choice.lower() == 'y':
            interactive_enhanced_demo()
        
    except KeyboardInterrupt:
        print("\n演示被中断")
    except Exception as e:
        print(f"演示出现错误: {e}")
    finally:
        print("演示结束！")
