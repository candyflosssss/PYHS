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
    print("1. 服务器 (先启动这个等待连接)")
    print("2. 客户端 (连接到服务器)")
    print("3. 退出")
    
    while True:
        choice = input("请输入选择 (1/2/3): ").strip()
        
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
            print("再见!")
            break
        else:
            print("无效选择，请输入 1、2 或 3")

if __name__ == "__main__":
    main()