"""
交互式滚动界面演示
支持鼠标滚轮和键盘命令滚动聊天记录
"""

from interactive_display import (
    interactive_display, show_interactive_game, 
    scroll_chat_up, scroll_chat_down, scroll_actions_up, scroll_actions_down,
    add_chat_message, add_action_log, add_system_message, reset_scroll
)
from rich.console import Console
from rich.live import Live
import time
import threading

def demo_interactive_scrolling():
    """演示交互式滚动功能"""
    console = Console()
    
    console.print("[bold yellow]🖱️ 交互式滚动界面演示[/bold yellow]")
    console.print()
    console.print("新功能特点:")
    console.print("✓ 支持键盘命令滚动聊天记录和操作记录")
    console.print("✓ 显示滚动指示器和历史记录数量")
    console.print("✓ 美观的Rich界面布局")
    console.print("✓ 自动滚动到最新消息")
    console.print()
    console.print("滚动命令:")
    console.print("- [cyan]up chat[/cyan] / [cyan]down chat[/cyan] - 滚动聊天记录")
    console.print("- [cyan]up action[/cyan] / [cyan]down action[/cyan] - 滚动操作记录")
    console.print("- [cyan]reset[/cyan] - 回到最新消息")
    console.print()
    
    input("按回车键开始演示...")
    
    # 准备演示数据
    setup_demo_data()
    
    # 创建游戏状态
    game_state = create_demo_game_state()
    
    # 开始实时界面
    console.clear()
    
    with Live(show_interactive_game(game_state, 'player1'), refresh_per_second=4) as live:
        console.print("\n[bold green]交互式界面已启动！[/bold green]")
        console.print("[yellow]可用滚动命令:[/yellow]")
        console.print("- up chat [数字] - 向上滚动聊天记录")
        console.print("- down chat [数字] - 向下滚动聊天记录") 
        console.print("- up action [数字] - 向上滚动操作记录")
        console.print("- down action [数字] - 向下滚动操作记录")
        console.print("- reset - 重置滚动位置")
        console.print("- add - 添加测试消息")
        console.print("- quit - 退出演示")
        console.print()
        
        while True:
            try:
                # 更新界面
                live.update(show_interactive_game(game_state, 'player1'))
                
                # 处理用户输入
                command = console.input("[bold blue]请输入命令 >[/bold blue] ").strip().lower()
                
                if not command:
                    continue
                
                parts = command.split()
                cmd = parts[0]
                
                if cmd == 'quit':
                    break
                elif cmd == 'up' and len(parts) >= 2:
                    area = parts[1]
                    lines = int(parts[2]) if len(parts) > 2 else 1
                    if area == 'chat':
                        scroll_chat_up(lines)
                        console.print(f"[green]向上滚动聊天记录 {lines} 行[/green]")
                    elif area == 'action':
                        scroll_actions_up(lines)
                        console.print(f"[green]向上滚动操作记录 {lines} 行[/green]")
                elif cmd == 'down' and len(parts) >= 2:
                    area = parts[1]
                    lines = int(parts[2]) if len(parts) > 2 else 1
                    if area == 'chat':
                        scroll_chat_down(lines)
                        console.print(f"[green]向下滚动聊天记录 {lines} 行[/green]")
                    elif area == 'action':
                        scroll_actions_down(lines)
                        console.print(f"[green]向下滚动操作记录 {lines} 行[/green]")
                elif cmd == 'reset':
                    reset_scroll()
                    console.print("[green]已重置滚动位置到最新消息[/green]")
                elif cmd == 'add':
                    # 添加测试消息
                    timestamp = time.strftime('%H:%M:%S')
                    add_chat_message("测试玩家", f"这是 {timestamp} 的测试消息")
                    add_action_log(f"测试玩家 在 {timestamp} 执行了测试操作")
                    console.print("[green]已添加测试消息[/green]")
                else:
                    console.print("[red]无效命令！请查看帮助信息。[/red]")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]发生错误: {e}[/red]")
    
    console.print("\n[bold yellow]交互式演示结束！[/bold yellow]")

def setup_demo_data():
    """设置演示数据"""
    # 添加系统消息
    add_system_message("欢迎来到COMOS多人卡牌对战！")
    add_system_message("支持滚动浏览聊天记录和操作记录")
    
    # 添加大量聊天记录用于测试滚动
    chat_messages = [
        ("小明", "大家好！"),
        ("小红", "你好小明，准备开始游戏了吗？"),
        ("小李", "我也准备好了"),
        ("小王", "这个界面看起来很酷"),
        ("小明", "是的，支持滚动查看历史记录"),
        ("小红", "我们可以向上滚动查看之前的消息"),
        ("小李", "操作记录也可以滚动"),
        ("小王", "太棒了！"),
        ("系统", "游戏即将开始"),
        ("小明", "让我们开始吧！"),
        ("小红", "我出第一张牌"),
        ("小李", "我攻击敌人"),
        ("小王", "我使用治疗法术"),
        ("小明", "不错的配合！"),
        ("小红", "我们继续"),
        ("小李", "注意BOSS要出现了"),
        ("小王", "大家小心"),
        ("系统", "BOSS暗影龙王出现！"),
        ("小明", "准备战斗！"),
        ("小红", "我准备群体法术"),
        ("小李", "我来吸引仇恨"),
        ("小王", "我负责治疗支援"),
        ("系统", "战斗开始！"),
        ("小明", "冲啊！"),
        ("小红", "火球术！"),
    ]
    
    for player, message in chat_messages:
        add_chat_message(player, message)
    
    # 添加大量操作记录
    actions = [
        "小明 加入了游戏",
        "小红 加入了游戏", 
        "小李 加入了游戏",
        "小王 加入了游戏",
        "游戏开始",
        "小明 抽取了起始手牌",
        "小红 抽取了起始手牌",
        "小李 抽取了起始手牌", 
        "小王 抽取了起始手牌",
        "回合1开始",
        "小明 出了一张牌: 火球术",
        "小红 出了一张牌: 治疗术",
        "小李 出了一张牌: 战士随从",
        "小王 使用了技能: 圣光术",
        "回合2开始",
        "小明 攻击了 哥布林",
        "小红 治疗了 小李",
        "小李 挑战了 小王",
        "小王 领取了资源: 魔法药水",
        "回合3开始",
        "BOSS暗影龙王出现",
        "小明 对BOSS造成了15点伤害",
        "小红 为全体回复了生命值",
        "小李 使用了背包中的武器",
        "小王 施放了防护法术",
    ]
    
    for action in actions:
        add_action_log(action)

def create_demo_game_state():
    """创建演示游戏状态"""
    return {
        'phase': '激战中',
        'turn': 8,
        'current_player': '小明',
        'players': {
            'player1': {
                'name': '小明',
                'hp': 85,
                'max_hp': 100,
                'hand_count': 5,
                'board_count': 3,
                'inventory_count': 12
            },
            'player2': {
                'name': '小红',
                'hp': 92,
                'max_hp': 100,
                'hand_count': 4,
                'board_count': 2,
                'inventory_count': 8
            },
            'player3': {
                'name': '小李',
                'hp': 78,
                'max_hp': 100,
                'hand_count': 6,
                'board_count': 1,
                'inventory_count': 15
            },
            'player4': {
                'name': '小王',
                'hp': 95,
                'max_hp': 100,
                'hand_count': 3,
                'board_count': 4,
                'inventory_count': 6
            }
        },
        'npc_zone': {
            'npcs': [
                {'name': '暗影龙王', 'atk': 40, 'hp': 150},
                {'name': '邪恶法师', 'atk': 25, 'hp': 80},
            ],
            'difficulty': 5,
            'boss_present': True
        },
        'resource_zone': {
            'available_resources': [
                {'name': '传说武器', 'type': '装备'},
                {'name': '复活卷轴', 'type': '法术'},
                {'name': '神秘宝石', 'type': '材料'},
                {'name': '治疗药水', 'type': '消耗品'},
            ],
            'next_refresh': 3
        }
    }

if __name__ == "__main__":
    try:
        demo_interactive_scrolling()
    except KeyboardInterrupt:
        print("\n演示被中断")
    except Exception as e:
        print(f"演示出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("演示结束！")
