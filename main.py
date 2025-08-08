import sys

def main():
    print("=== COMOS PvE 合作卡牌游戏 ===")
    
    # 交互式启动
    print("请选择模式:")
    print("1. 🎮 启动PvE合作游戏")
    print("2. 🚪 退出")
    
    while True:
        choice = input("请输入选择 (1/2): ").strip()
        
        if choice == "1":
            print("启动PvE合作游戏模式...")
            start_pve_multiplayer_game()
            break
        elif choice == "2":
            print("再见!")
            break
        else:
            print("无效选择，请输入 1 或 2")

def start_pve_multiplayer_game():
    """启动PvE多人游戏"""
    from game_modes.pve_controller import start_pve_multiplayer_game as pve_start
    pve_start()

if __name__ == "__main__":
    main()
