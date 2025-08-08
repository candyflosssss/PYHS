"""
聊天和操作记录功能演示
"""

from game_display_enhanced import display, add_chat_message, add_action_log, add_system_message
import time

def demo_chat_and_logs():
    """演示聊天和操作记录功能"""
    
    # 模拟游戏状态
    game_state = {
        'phase': '游戏中',
        'turn': 3,
        'current_player': '小明',
        'players': {
            'player1': {
                'name': '小明',
                'hp': 85,
                'max_hp': 100,
                'hand_count': 5,
                'board_count': 2,
                'inventory_count': 8
            },
            'player2': {
                'name': '小红',
                'hp': 92,
                'max_hp': 100,
                'hand_count': 4,
                'board_count': 1,
                'inventory_count': 6
            },
            'player3': {
                'name': '小李',
                'hp': 78,
                'max_hp': 100,
                'hand_count': 6,
                'board_count': 3,
                'inventory_count': 4
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
    
    print("=== 聊天和操作记录功能演示 ===")
    
    # 添加一些系统消息
    add_system_message("欢迎来到COMOS多人卡牌对战！")
    add_system_message("游戏已开始，祝你游戏愉快！")
    
    # 添加一些聊天消息
    add_chat_message("小明", "大家好！")
    add_chat_message("小红", "你好小明~")
    add_chat_message("小李", "这个游戏看起来很有趣")
    add_chat_message("小明", "是的，我们一起合作对付NPC吧")
    add_chat_message("小红", "好主意！我有治疗法术")
    
    # 添加一些操作记录
    add_action_log("小明 出了一张牌: 火球术")
    add_action_log("小红 打开了背包")
    add_action_log("小李 向 哥布林战士 发起攻击")
    add_action_log("小明 领取了资源: 魔法水晶")
    add_action_log("小红 结束了回合")
    
    # 显示界面
    display.show_game(game_state, 'player1')
    
    print("\n演示完成！新界面包含了:")
    print("1. 三大游戏区域 (玩家竞技场、NPC敌人区、公共资源区)")
    print("2. 聊天区域 (显示玩家交流消息)")
    print("3. 操作记录区 (显示游戏动作历史)")
    print("4. 当前玩家信息和操作提示")

def interactive_demo():
    """交互式演示"""
    print("\n=== 交互式聊天演示 ===")
    print("可以尝试以下命令:")
    print("- chat <消息>: 发送聊天消息")
    print("- action <动作>: 添加操作记录")
    print("- quit: 退出演示")
    
    # 简化的游戏状态
    simple_state = {
        'phase': '演示模式',
        'turn': 1,
        'current_player': '测试玩家',
        'players': {
            'demo': {
                'name': '测试玩家',
                'hp': 100,
                'max_hp': 100,
                'hand_count': 3,
                'board_count': 1,
                'inventory_count': 5
            }
        },
        'npc_zone': {
            'npcs': [{'name': '测试怪物', 'atk': 10, 'hp': 30}],
            'difficulty': 1,
            'boss_present': False
        },
        'resource_zone': {
            'available_resources': [{'name': '测试资源', 'type': '测试'}],
            'next_refresh': 3
        }
    }
    
    while True:
        display.show_game(simple_state, 'demo')
        
        command = input("\n请输入命令 > ").strip()
        
        if not command:
            continue
        
        parts = command.split(' ', 1)
        cmd = parts[0].lower()
        
        if cmd == 'quit':
            break
        elif cmd == 'chat' and len(parts) > 1:
            add_chat_message("测试玩家", parts[1])
        elif cmd == 'action' and len(parts) > 1:
            add_action_log(f"测试玩家 {parts[1]}")
        else:
            print("无效命令，请输入 'chat <消息>' 或 'action <动作>' 或 'quit'")

if __name__ == "__main__":
    demo_chat_and_logs()
    
    choice = input("\n是否进行交互式演示？(y/n): ")
    if choice.lower() == 'y':
        interactive_demo()
    
    print("演示结束！")
