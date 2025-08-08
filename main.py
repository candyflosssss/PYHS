import sys
from network import Network
from game import Game
from battlefield import Battlefield
from player import Player
from network import Network

def main():
    print("=== comos ===")
    
    # 如果有命令行参数，直接使用
    if len(sys.argv) >= 2:
        if sys.argv[1] == "server":
            print("启动服务器模式...")
            Game(Network(is_server=True)).run()
        elif sys.argv[1] == "client":
            host = input("请输入服务器IP（默认127.0.0.1）: ").strip() or "127.0.0.1"
            Game(Network(is_server=False, host=host)).run()
        else:
            print("用法: python main.py server  或  python main.py client")
        return
    
    # 交互式启动
    print("请选择模式:")
    print("1. 服务器 (经典双人对战)")
    print("2. 客户端 (连接到服务器)")
    print("3. 多人游戏 (新的多人对战模式)")
    print("4. 单机测试 (测试背包和装备系统)")
    print("5. 聊天和操作记录演示")
    print("6. 交互式滚动演示 (支持鼠标滚轮)")
    print("7. 退出")
    
    while True:
        choice = input("请输入选择 (1/2/3/4/5/6/7): ").strip()
        
        if choice == "1":
            print("启动服务器模式...")
            Game(Network(is_server=True)).run()
            break
        elif choice == "2":
            host = input("请输入服务器IP（默认127.0.0.1）: ").strip() or "127.0.0.1"
            print(f"连接到服务器 {host}...")
            Game(Network(is_server=False, host=host)).run()
            break
        elif choice == "3":
            print("启动多人游戏模式...")
            from multiplayer_controller import start_multiplayer_game
            start_multiplayer_game()
            break
        elif choice == "4":
            print("启动单机测试模式...")
            test_inventory_system()
            break
        elif choice == "5":
            print("启动聊天和操作记录演示...")
            test_chat_and_logs()
            break
        elif choice == "6":
            print("启动交互式滚动演示...")
            test_interactive_scrolling()
            break
        elif choice == "7":
            print("再见!")
            break
        else:
            print("无效选择，请输入 1、2、3、4、5、6 或 7")

def test_interactive_scrolling():
    """测试交互式滚动功能"""
    try:
        from demo_interactive import demo_interactive_scrolling
        
        print("\n=== 交互式滚动功能演示 ===")
        print("这是最新的界面功能，支持:")
        print("1. 美观的Rich库界面布局")
        print("2. 键盘命令滚动聊天记录和操作记录")
        print("3. 滚动指示器和历史记录数量显示")
        print("4. 自动滚动到最新消息")
        print("5. 实时界面更新")
        
        print("\n滚动命令说明:")
        print("- up chat [行数] - 向上滚动聊天记录")
        print("- down chat [行数] - 向下滚动聊天记录")
        print("- up action [行数] - 向上滚动操作记录")
        print("- down action [行数] - 向下滚动操作记录")
        print("- reset - 重置滚动位置到最新消息")
        
        input("\n按回车键开始交互式演示...")
        
        # 运行交互式演示
        demo_interactive_scrolling()
        
        print("交互式滚动演示完成！返回主菜单...")
        
    except ImportError as e:
        print(f"演示模式需要的组件: {e}")
        print("请确保已安装 rich 库: pip install rich")
    except Exception as e:
        print(f"演示模式启动失败: {e}")
        import traceback
        traceback.print_exc()

def test_chat_and_logs():
    """测试聊天和操作记录功能"""
    try:
        from demo_enhanced import demo_enhanced_interface, interactive_enhanced_demo
        
        print("\n=== 增强界面功能演示 ===")
        print("新的增强界面包含以下功能:")
        print("1. 彩色文本支持 - 不同类型信息用不同颜色")
        print("2. 自动滚动功能 - 聊天和操作记录自动滚动")
        print("3. 一致的缩进和对齐")
        print("4. 优化的视觉效果")
        print("5. 实时消息更新")
        
        input("\n按回车键开始演示...")
        
        # 运行增强界面演示
        demo_enhanced_interface()
        
        # 询问是否进行交互式演示
        choice = input("\n是否进行交互式演示？(y/n): ")
        if choice.lower() == 'y':
            interactive_enhanced_demo()
        
        print("增强界面演示完成！返回主菜单...")
        
    except ImportError as e:
        print(f"演示模式需要的组件: {e}")
        print("请确保已安装 colorama 库: pip install colorama")
    except Exception as e:
        print(f"演示模式启动失败: {e}")
        import traceback
        traceback.print_exc()

def test_inventory_system():
    """测试背包和装备系统"""
    print("\n=== 背包和装备系统测试 ===")
    
    try:
        from player import Player
        from inventory_ui import show_inventory_menu
        from cards import Card
        from equipment_system import WeaponItem, ArmorItem
        from inventory import create_sample_items
        
        # 创建测试玩家
        player = Player("测试玩家")
        
        # 添加示例物品到背包
        items = create_sample_items()
        for item in items[:5]:  # 添加前5个物品
            player.add_to_inventory(item, 1)
        
        # 在战场上放置一些测试随从
        from battlefield import Battlefield
        
        # 创建测试随从并添加装备系统
        test_card1 = Card(3, 4)
        test_card1.name = "战士"
        test_card2 = Card(2, 3) 
        test_card2.name = "法师"
        test_card3 = Card(4, 2)
        test_card3.name = "盗贼"
        
        # 为随从添加装备系统
        from equipment_system import EquipmentSystem
        for card in [test_card1, test_card2, test_card3]:
            card.equipment = EquipmentSystem()
        
        # 模拟战场环境
        if hasattr(player, 'game') and player.game:
            player.game.battlefield.my_board = [test_card1, test_card2, test_card3]
        
        print(f"为 {player.name} 准备了测试环境：")
        print("- 背包中有多种装备和消耗品")
        print("- 战场上有3个随从：战士、法师、盗贼")
        print("\n现在可以测试背包功能了！")
        print("提示：输入 'bag' 命令可以打开背包管理")
        
        # 简化的测试循环
        while True:
            print(f"\n=== {player.name} 的状态 ===")
            print(f"生命值: {player.hp}")
            items_count = len(player.get_inventory_summary())
            print(f"背包物品: {items_count} 种")
            
            cmd = input("\n输入命令 (bag=背包管理, status=显示状态, quit=退出): ").strip().lower()
            
            if cmd == 'bag':
                # 创建临时的战场随从列表供背包界面使用
                temp_board = [test_card1, test_card2, test_card3]
                show_inventory_menu_with_board(player, temp_board)
            elif cmd == 'status':
                player.show_inventory()
            elif cmd == 'quit':
                print("测试结束！")
                break
            else:
                print("可用命令: bag, status, quit")
                
    except ImportError as e:
        print(f"测试模式需要的组件: {e}")
    except Exception as e:
        print(f"测试模式启动失败: {e}")

def show_inventory_menu_with_board(player, board):
    """为测试模式提供的背包界面"""
    from inventory_ui import show_inventory_menu
    
    # 临时为玩家设置战场信息以供背包界面使用
    class TempGame:
        def __init__(self):
            self.battlefield = TempBattlefield()
    
    class TempBattlefield:
        def __init__(self):
            self.my_board = board
            self.op_board = []
    
    # 临时设置
    temp_game = TempGame()
    player.game = temp_game
    
    try:
        show_inventory_menu(player)
    finally:
        # 清理临时设置
        player.game = None

if __name__ == "__main__":
    main()