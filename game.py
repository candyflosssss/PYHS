from battlefield import Battlefield
from player import Player
from network import Network
from pve_multiplayer_game import PvEGameManager, PvEMultiplayerGame, GamePhase
import os
import time

TURN_LIMIT = 999  # 最大回合数

class Game:
    def __init__(self, network):
        self.network = network
        
        # 判断是否使用新的PvE多人模式
        self.use_pve_mode = True  # 默认使用新模式
        
        if self.use_pve_mode:
            # 新的PvE多人模式
            self.game_manager = PvEGameManager()
            self.player_id = f"player_{int(time.time() * 1000) % 10000}"
            self.current_game_id = None
            self.current_game = None
            self.is_server = network.is_server
            
            if self.is_server:
                # 服务器创建游戏
                self.current_game_id, self.current_game = self.game_manager.create_game(self.player_id)
            
        else:
            # 原有的双人模式（保留兼容）
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
        if self.use_pve_mode:
            self.run_pve_mode()
        else:
            self.run_classic_mode()
    
    def run_pve_mode(self):
        """运行PvE多人模式"""
        if self.is_server:
            self.run_server_mode()
        else:
            self.run_client_mode()
    
    def run_server_mode(self):
        """服务器模式：房主等待玩家并控制游戏开始"""
        print("=== PvE多人卡牌对战 - 服务器模式 ===")
        
        # 房主加入自己的游戏
        player_name = input("请输入你的名字: ").strip()
        if not player_name:
            player_name = "房主"
        
        success, message = self.current_game.add_player(self.player_id, player_name)
        if not success:
            print(f"加入游戏失败: {message}")
            return
        
        print(f"游戏房间已创建，ID: {self.current_game_id}")
        print("等待其他玩家加入...")
        
        # 等待玩家加入的循环
        while True:
            self.show_pve_waiting_room()
            
            command = input("输入命令 (s=开始游戏, r=刷新, q=退出): ").strip().lower()
            
            if command == 's':
                # 开始准备阶段
                success, message = self.current_game.start_preparation()
                if success:
                    print(message)
                    success, message = self.current_game.start_game()
                    if success:
                        print(message)
                        break
                    else:
                        print(f"游戏启动失败: {message}")
                else:
                    print(f"准备失败: {message}")
            
            elif command == 'r':
                continue  # 刷新显示
            
            elif command == 'q':
                return
            
            # 模拟其他玩家加入（这里应该通过网络实现）
            self.simulate_player_join()
        
        # 进入游戏主循环
        self.run_pve_game_loop()
    
    def run_client_mode(self):
        """客户端模式：加入服务器的游戏"""
        print("=== PvE多人卡牌对战 - 客户端模式 ===")
        
        game_id = input("请输入游戏房间ID: ").strip()
        try:
            game_id = int(game_id)
        except ValueError:
            print("无效的房间ID")
            return
        
        player_name = input("请输入你的名字: ").strip()
        if not player_name:
            player_name = "玩家"
        
        # 获取游戏（这里应该通过网络实现）
        game = self.game_manager.get_game(game_id)
        if not game:
            print("房间不存在")
            return
        
        success, message = game.add_player(self.player_id, player_name)
        if success:
            self.current_game_id = game_id
            self.current_game = game
            print(f"成功加入游戏: {message}")
            
            # 等待游戏开始
            while self.current_game.phase in [GamePhase.WAITING, GamePhase.PREPARATION]:
                print("等待房主开始游戏...")
                time.sleep(2)
            
            # 进入游戏主循环
            self.run_pve_game_loop()
        else:
            print(f"加入失败: {message}")
    
    def run_pve_game_loop(self):
        """PvE游戏主循环"""
        while self.current_game.running and self.current_game.phase != GamePhase.GAME_OVER:
            try:
                # 显示游戏状态
                self.show_pve_game()
                
                # 检查是否是当前玩家的回合
                current_player = self.current_game.get_current_player()
                if current_player and current_player.player_id == self.player_id:
                    self.handle_pve_player_turn(current_player)
                else:
                    # 等待其他玩家或系统回合
                    self.wait_for_turn()
                
            except KeyboardInterrupt:
                print("\n游戏中断")
                break
            except Exception as e:
                print(f"游戏错误: {e}")
                break
        
        if self.current_game.phase == GamePhase.GAME_OVER:
            print("游戏结束！")
    
    def simulate_player_join(self):
        """模拟其他玩家加入（用于测试）"""
        import random
        if random.random() < 0.3:  # 30%概率有新玩家加入
            fake_id = f"bot_{random.randint(1000, 9999)}"
            fake_name = f"玩家{random.randint(1, 100)}"
            self.current_game.add_player(fake_id, fake_name)
    
    def show_pve_waiting_room(self):
        """显示PvE等待房间"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=== 游戏房间 ===")
        print(f"房间ID: {self.current_game_id}")
        print(f"当前玩家数: {len(self.current_game.players)}")
        print("\n玩家列表:")
        for i, (pid, player) in enumerate(self.current_game.players.items(), 1):
            marker = " (房主)" if pid == self.current_game.server_player_id else ""
            print(f"  {i}. {player.name}{marker}")
        print("\n命令: s=开始游戏, r=刷新, q=退出")
    
    def show_pve_game(self):
        """显示PvE游戏界面"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        game_state = self.current_game.get_game_state()
        current_player = self.current_game.get_current_player()
        my_player = self.current_game.players.get(self.player_id)
        
        print(f"=== 回合 {game_state['turn_number']} - {game_state['phase']} ===")
        
        # 显示Boss状态
        print(f"Boss: {game_state['boss']}")
        
        # 显示敌人区
        print(f"敌人区: {game_state['enemy_zone'] if game_state['enemy_zone'] else '无敌人'}")
        
        # 显示资源区
        print(f"资源区: {game_state['resource_zone']}")
        
        print("=" * 50)
        
        # 显示所有玩家状态
        print("玩家状态:")
        for i, pid in enumerate(game_state['player_order']):
            player_data = game_state['players'][pid]
            marker = " <- 当前回合" if current_player and pid == current_player.player_id else ""
            marker += " (你)" if pid == self.player_id else ""
            print(f"  {i+1}. {player_data['name']} HP:{player_data['hp']}/{player_data['max_hp']} "
                  f"手牌:{player_data['hand_count']} 随从:{player_data['battlefield_count']}{marker}")
        
        # 显示我的详细信息
        if my_player:
            print(f"\n我的状态:")
            print(f"  生命值: {my_player.hp}/{my_player.max_hp}")
            print(f"  手牌: {my_player.hand}")
            if my_player.battlefield.my_board:
                print(f"  我的随从: {my_player.battlefield.my_board}")
            else:
                print(f"  我的随从: 无")
        
        print()
    
    def handle_pve_player_turn(self, player):
        """处理PvE模式下的玩家回合"""
        print(f"=== 你的回合 ===")
        
        while True:
            command = input("> ").strip()
            
            if not command:
                continue
            
            # 解析命令
            parts = command.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd == 'h' or cmd == 'help':
                self.show_pve_help()
                continue
            
            elif cmd == 'p' and args:
                # 出牌: p 手牌编号 [目标]
                if self.handle_pve_play_card(player, args):
                    continue  # 出牌不结束回合
            
            elif cmd == 'a' and len(args) >= 2:
                # 攻击: a 攻击者编号 目标区域 [目标编号]
                if self.handle_pve_attack(player, args):
                    continue  # 攻击不结束回合
            
            elif cmd == 'c' and len(args) >= 1:
                # 收集资源: c 资源编号
                if self.handle_pve_collect_resource(player, args[0]):
                    continue  # 收集不结束回合
            
            elif cmd == 'i' or cmd == 'info':
                # 查看信息: i [目标编号]
                self.handle_pve_info(player, args)
                continue
            
            elif cmd == 'bag':
                self.handle_bag(player)
                continue
            
            elif cmd == 'e' or cmd == 'end':
                print(f"{player.name} 结束回合")
                self.current_game.next_turn()
                break
            
            else:
                print("无效命令，输入 'h' 查看帮助")
    
    def handle_pve_play_card(self, player, args):
        """处理PvE出牌"""
        try:
            card_index = int(args[0]) - 1
            target_idx = None
            if len(args) > 1:
                target_idx = int(args[1])
            
            if 0 <= card_index < len(player.hand):
                card_name = player.hand[card_index].name if hasattr(player.hand[card_index], 'name') else f"卡牌{card_index+1}"
                player.play_card(card_index, target_idx)
                print(f"成功出牌: {card_name}")
                return True
            else:
                print("无效的卡牌编号")
        except ValueError:
            print("请输入有效的数字")
        except Exception as e:
            print(f"出牌错误: {e}")
        return False
    
    def handle_pve_attack(self, player, args):
        """处理PvE攻击"""
        try:
            attacker_index = int(args[0]) - 1
            target_zone = int(args[1])
            
            if target_zone == 0:  # 攻击敌人区
                if len(args) >= 3:
                    target_index = int(args[2])
                    if target_index == 0:  # 攻击Boss
                        success, message = self.current_game.attack_boss(self.player_id, attacker_index)
                        print(message)
                        return success
                    else:  # 攻击敌人
                        enemy_index = target_index - 1
                        success, message = self.current_game.attack_enemy(self.player_id, attacker_index, enemy_index)
                        print(message)
                        return success
                else:
                    print("攻击敌人区需要指定目标编号 (0=Boss, 1+=敌人)")
            
            elif target_zone >= 1:  # 攻击其他玩家的随从
                if len(args) >= 3:
                    target_minion = int(args[2]) - 1
                    # 找到目标玩家
                    target_player_index = target_zone - 1
                    if target_player_index < len(self.current_game.player_order):
                        target_player_id = self.current_game.player_order[target_player_index]
                        success, message = self.current_game.attack_player_minion(
                            self.player_id, attacker_index, target_player_id, target_minion)
                        print(message)
                        return success
                    else:
                        print("无效的玩家编号")
                else:
                    print("攻击玩家随从需要指定随从编号")
            
            else:
                print("无效的攻击目标")
                
        except ValueError:
            print("请输入有效的数字")
        except Exception as e:
            print(f"攻击错误: {e}")
        return False
    
    def handle_pve_collect_resource(self, player, resource_arg):
        """处理PvE收集资源"""
        try:
            resource_index = int(resource_arg) - 1
            resource = self.current_game.collect_resource(self.player_id, resource_index)
            if resource:
                print(f"成功收集资源: {resource}")
                return True
            else:
                print("收集资源失败")
        except ValueError:
            print("请输入有效的数字")
        except Exception as e:
            print(f"收集错误: {e}")
        return False
    
    def handle_pve_info(self, player, args):
        """处理PvE信息查看（保留原有的info机制）"""
        if not args:
            print("请指定要查看的目标编号")
            return
        
        try:
            idx = int(args[0])
            if idx == 0:  # 查看自己的英雄信息
                print(f"我的英雄：HP {player.hp}/{player.max_hp}")
            elif 1 <= idx <= len(player.hand):  # 查看手牌
                card = player.hand[idx-1]
                print(f"手牌 {idx}：{card.info()}")
            elif idx > 100 and idx-100 <= len(player.battlefield.my_board):  # 查看我方战场
                card = player.battlefield.my_board[idx-101]
                print(f"我方随从 {idx-100}：{card.info()}")
            else:
                print("无效的索引")
        except ValueError:
            print("请输入有效的数字")
    
    def show_pve_help(self):
        """显示PvE帮助信息"""
        help_text = """
========== PvE游戏命令帮助 ==========
--- 基本操作 ---
p <手牌编号> [目标]  - 出第N张手牌，可选目标
a <随从编号> <区域> <目标> - 攻击
  例: a 1 0 0      - 第1个随从攻击Boss
  例: a 1 0 1      - 第1个随从攻击敌人区第1个敌人
  例: a 1 2 1      - 第1个随从攻击玩家2的第1个随从
c <资源编号>        - 收集第N个资源
e/end              - 结束回合

--- 信息查看 ---
i/info <编号>       - 查看信息
  0 = 我的英雄, 1-N = 手牌, 101-N = 我的随从
bag                - 打开背包

--- 其他 ---
h/help             - 显示此帮助
=================================
"""
        print(help_text)
    
    def wait_for_turn(self):
        """等待回合"""
        print("等待其他玩家或系统回合...", end="", flush=True)
        time.sleep(1)
        print("\r" + " " * 40 + "\r", end="", flush=True)
    
    def run_classic_mode(self):
        """运行经典双人模式（保留原有逻辑）"""
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
        """经典模式玩家回合（保留原有逻辑但适配info机制）"""
        if not self.use_pve_mode:
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
                self.handle_bag(player)
                if not self.use_pve_mode:
                    self.show()  # 背包操作后刷新游戏界面
                continue

            if op == 'info' and len(cmd) >= 2:
                self.handle_classic_info(player, cmd[1])
                continue

            if op == 'p' and len(cmd) >= 2:
                try:
                    x = int(cmd[1]) - 1
                    t = int(cmd[2]) if len(cmd) >= 3 else None
                    player.play_card(x, t)
                    if not self.use_pve_mode:
                        self.show()
                except Exception as e:
                    print(f"出牌错误: {e}")
                continue

            if op == 'a' and len(cmd) >= 2:
                if player.attack(cmd[1]):
                    if not self.use_pve_mode:
                        self.battlefield.sync_state(self.network)
                        self.show()
                    return
                if not self.use_pve_mode:
                    self.battlefield.sync_state(self.network)
                    self.show()
                continue

            if op == 'end':
                if not self.use_pve_mode:
                    self.network.send("end")
                    self.turn_num += 1
                    self.is_my_turn = False
                    # 通知对方回合开始
                    self.network.send("start_turn")
                    self.show()
                break

            print("!")
    
    def handle_classic_info(self, player, idx_str):
        """处理经典模式的info命令（保留原有逻辑）"""
        try:
            idx = int(idx_str)
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
    
    def handle_bag(self, player):
        """处理背包操作（通用方法）"""
        from inventory_ui import show_inventory_menu
        show_inventory_menu(player)

    def opponent_turn(self):
        """经典模式对方回合"""
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
        """经典模式显示界面"""
        if self.use_pve_mode:
            return  # PvE模式有自己的显示方法
            
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"\nT{self.turn_num} {'你的回合' if self.is_my_turn else '对方回合'}")
        print(f"对方英雄: ({self.player_op.hp}/{self.player_op.max_hp})")
        print(f"对方战场: {self.battlefield.op_board}")
        print(f"-----------------------------")
        print(f"我方英雄: ({self.player_me.hp}/{self.player_me.max_hp})")
        print(f"我方战场: {self.battlefield.my_board}")
        print(f"手牌: {self.player_me.hand}\n")

    def draw(self, owner):
        """抽牌逻辑（经典模式）"""
        if owner == 'me':
            return self.player_me.draw_card()
        else:
            return self.player_op.draw_card()
    
    def sync_hp(self):
        """同步双方血量（经典模式）"""
        if hasattr(self, 'network'):
            # 发送格式：hp 我的血量 对方血量（从发送方视角）
            hp_msg = f"hp {self.player_me.hp} {self.player_op.hp}"
            self.network.send(hp_msg)
            print(f"DEBUG: 发送血量同步 - 我方:{self.player_me.hp} 对方:{self.player_op.hp}")
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
        if not self.use_pve_mode:
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
        if not self.use_pve_mode:
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
        """检查游戏是否结束（经典模式）"""
        if not self.use_pve_mode:
            if self.player_me.hp <= 0:
                print("你败北了！")
                self.network.send("WIN")
                exit(0)
            elif self.player_op.hp <= 0:
                print("你获胜了！")
                self.network.send("WIN")
                exit(0)
    
    def _start_turn(self):
        """回合开始逻辑（经典模式）"""
        if not self.use_pve_mode:
            # 重置我方随从的攻击状态
            for card in self.battlefield.my_board:
                card.can_attack = True
                card.attacks = 0
            print("DEBUG: 重置我方随从攻击状态")