import sys
from network import Network
from game import Game
from battlefield import Battlefield
from player import Player
from network import Network

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "server":
        Game(Network(is_server=True)).run()
    elif len(sys.argv) >= 2 and sys.argv[1] == "client":
        host = input("请输入服务器IP（默认127.0.0.1）: ").strip() or "127.0.0.1"
        Game(Network(is_server=False, host=host)).run()
    else:
        print("用法: python main.py server  或  python main.py client")