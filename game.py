from battlefield import Battlefield
from player import Player
from network import Network
import os

TURN_LIMIT = 999  # 最大回合数

class Game:
    def __init__(self, network):
        self.network = network
        self.battlefield = Battlefield()
        self.player_me = Player("我", is_me=True)
        self.player_op = Player("对方", is_me=False)
        # 添加对Game的引用
        self.player_me.game = self
        self.player_op.game = self
        # 添加互相引用
        self.player_me.enemy_player = self.player_op
        self.player_op.enemy_player = self.player_me
        self.turn_num = 1
        self.is_my_turn = network.is_server

    def run(self):
        for _ in range(3):
            self.player_me.draw_card()
            self.player_op.draw_card()
        self.show()

        while self.turn_num <= TURN_LIMIT:
            if self.is_my_turn:
                self.player_turn(self.player_me)
            else:
                self.opponent_turn()

    def player_turn(self, player):
        self.battlefield.sync_state(self.network)
        while True:
            cmd = input(">").split()
            if not cmd: continue
            op = cmd[0]

            if op == 'help':
                print("操作：")
                print("  p X [T]   - 出牌 第 X 张 手牌, 可选目标 T")
                print("  a seq     - 攻击链, 如 1,1/2,3/1,0")
                print("  bag       - 打开背包和装备管理")
                print("  help      - 显示帮助")
                print("  info X    - 显示第 X 号卡牌详细信息")
                print("  end       - 结束回合")
                continue

            if op == 'bag':
                # 打开背包管理界面
                from inventory_ui import show_inventory_menu
                show_inventory_menu(player)
                self.show()  # 背包操作后刷新游戏界面
                continue

            if op == 'info' and len(cmd) >= 2:
                try:
                    idx = int(cmd[1])
                    if idx == 0:  # 查看自己的英雄信息
                        print(f"我的英雄：HP {player.hp}/{player.max_hp}")
                    elif 1 <= idx <= len(player.hand):  # 查看手牌
                        card = player.hand[idx-1]
                        print(f"手牌 {idx}：{card.info()}")
                    elif idx > 100 and idx-100 <= len(self.battlefield.my_board):  # 查看我方战场
                        card = self.battlefield.my_board[idx-101]
                        print(f"我方战场 {idx-100}：{card.info()}")
                    elif idx > 200 and idx-200 <= len(self.battlefield.op_board):  # 查看敌方战场
                        card = self.battlefield.op_board[idx-201]
                        print(f"敌方战场 {idx-200}：{card.info()}")
                    else:
                        print("无效的索引")
                except ValueError:
                    print("请输入有效的数字")
                continue

            if op == 'p' and len(cmd) >= 2:
                try:
                    x = int(cmd[1]) - 1
                    t = int(cmd[2]) if len(cmd) >= 3 else None
                    player.play_card(x, t)
                    self.show()
                except Exception as e:
                    print(f"出牌错误: {e}")
                continue

            if op == 'a' and len(cmd) >= 2:
                if player.attack(cmd[1]):
                    self.battlefield.sync_state(self.network)
                    self.show()
                    return
                self.battlefield.sync_state(self.network)
                self.show()
                continue

            if op == 'end':
                self.network.send("end")
                self.turn_num += 1
                self.is_my_turn = False
                # 通知对方回合开始
                self.network.send("start_turn")
                self.show()
                break

            print("!")

    def opponent_turn(self):
        print("等待对方操作...")
        op_cmd = self.network.recv()
        self.handle_op_cmd(op_cmd)

    def handle_op_cmd(self, cmd):
        """处理对方发送的命令"""
        print(f"DEBUG: 接收到命令: '{cmd}'")  # 添加调试信息
        parts = cmd.split()
        if not parts: return
        
        op = parts[0]
        print(f"DEBUG: 命令部分: {parts}")  # 添加调试信息
        
        if op == 'p':  # 对方出牌
            idx = int(parts[1]) - 1
            t = int(parts[2]) if len(parts) >= 3 else None
            # 使用网络出牌方法，不会触发交互
            self.player_op.play_card_network(idx, t)
            self.show()
        
        elif op == 'a':  # 对方攻击
            self.player_op.attack(parts[1])
            self.show()
        
        elif op == 's':  # 对方同步状态
            self.battlefield.apply_state(cmd)
            self.show()
        
        elif op == 'end':  # 对方结束回合
            print("对方结束回合")
            self.turn_num += 1
            self.is_my_turn = True
            # 处理我方回合开始逻辑
            self._start_turn()
            self.show()
        
        elif op == 'start_turn':  # 对方通知我们回合开始
            self._start_turn()
        
        elif op == 'WIN':  # 对方赢了
            print("你输了！")
            exit(0)
        
        elif op == 'hp':  # 对方同步生命值
            # 接收到的格式：hp 发送方血量 发送方的对方血量
            # 发送方是我的对手，所以：
            # - 发送方血量 = 我看到的对方血量
            # - 发送方的对方血量 = 我看到的我方血量
            sender_hp = int(parts[1])
            sender_opponent_hp = int(parts[2])
            self.player_op.hp = sender_hp  # 发送方血量就是我的对手血量
            self.player_me.hp = sender_opponent_hp  # 发送方的对手血量就是我的血量
            print(f"DEBUG: 接收血量同步 - 对方:{sender_hp} 我方:{sender_opponent_hp}")
            self.show()

    def show(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"\nT{self.turn_num} {'你的回合' if self.is_my_turn else '对方回合'}")
        print(f"对方英雄: ({self.player_op.hp}/{self.player_op.max_hp})")
        print(f"对方战场: {self.battlefield.op_board}")
        print(f"-----------------------------")
        print(f"我方英雄: ({self.player_me.hp}/{self.player_me.max_hp})")
        print(f"我方战场: {self.battlefield.my_board}")
        print(f"手牌: {self.player_me.hand}\n")

    def draw(self, owner):
        """抽牌逻辑"""
        if owner == 'me':
            return self.player_me.draw_card()
        else:
            return self.player_op.draw_card()
    
    def sync_hp(self):
        """同步双方血量"""
        if hasattr(self, 'network'):
            # 发送格式：hp 我的血量 对方血量（从发送方视角）
            hp_msg = f"hp {self.player_me.hp} {self.player_op.hp}"
            self.network.send(hp_msg)
            print(f"DEBUG: 发送血量同步 - 我方:{self.player_me.hp} 对方:{self.player_op.hp}")
    
    def damage_enemy_hero(self, attacker_owner, damage):
        """对敌方英雄造成伤害并同步（从攻击者角度）"""
        if attacker_owner == 'me':
            # 我方攻击，对方受伤
            self.player_op.hp -= damage
            print(f"对方英雄受到 {damage} 点伤害")
        elif attacker_owner == 'op':
            # 对方攻击，我方受伤  
            self.player_me.hp -= damage
            print(f"我方英雄受到 {damage} 点伤害")
        
        # 同步血量
        self.sync_hp()
        
        # 检查游戏结束
        self._check_game_over()
    
    def damage_player(self, target_owner, damage):
        """对玩家造成伤害并同步（指定目标）"""
        if target_owner == 'me':
            self.player_me.hp -= damage
            print(f"我方英雄受到 {damage} 点伤害")
        elif target_owner == 'op':
            self.player_op.hp -= damage
            print(f"对方英雄受到 {damage} 点伤害")
        
        # 同步血量
        self.sync_hp()
        
        # 检查游戏结束
        self._check_game_over()
    
    def _check_game_over(self):
        """检查游戏是否结束"""
        if self.player_me.hp <= 0:
            print("你败北了！")
            self.network.send("WIN")
            exit(0)
        elif self.player_op.hp <= 0:
            print("你获胜了！")
            self.network.send("WIN")
            exit(0)
    
    def _start_turn(self):
        """回合开始逻辑"""
        # 重置我方随从的攻击状态
        for card in self.battlefield.my_board:
            card.can_attack = True
            card.attacks = 0
        print("DEBUG: 重置我方随从攻击状态")