"""
PvE多人游戏启动器
独立的PvE游戏启动和控制逻辑
"""

from pve_multiplayer_game import PvEGameManager, PvEMultiplayerGame, GamePhase
import time
import os

class PvEGameController:
    """PvE游戏控制器"""
    
    def __init__(self):
        self.game_manager = PvEGameManager()
        self.current_game_id = None
        self.current_game = None
        self.player_id = f"player_{int(time.time() * 1000) % 10000}"
        self.is_server = False
    
    def start_server_mode(self):
        """启动服务器模式（房主）"""
        print("=== PvE多人卡牌对战 - 服务器模式 ===")
        
        # 房主加入自己的游戏
        player_name = input("请输入你的名字: ").strip()
        if not player_name:
            player_name = "房主"
        
        # 创建游戏
        self.current_game_id, self.current_game = self.game_manager.create_game(self.player_id)
        success, message = self.current_game.add_player(self.player_id, player_name)
        
        if not success:
            print(f"加入游戏失败: {message}")
            return
        
        self.is_server = True
        print(f"游戏房间已创建，ID: {self.current_game_id}")
        
        # 等待玩家加入的循环
        while True:
            self.show_waiting_room()
            
            command = input("输入命令 (s=开始游戏, r=刷新, q=退出): ").strip().lower()
            
            if command == 's':
                if len(self.current_game.players) >= 1:
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
                else:
                    print("至少需要1个玩家才能开始游戏")
            
            elif command == 'r':
                continue  # 刷新显示
            
            elif command == 'q':
                return
            
            # 模拟其他玩家加入（这里应该通过网络实现）
            self.simulate_player_join()
        
        # 进入游戏主循环
        self.run_game_loop()
    
    def start_client_mode(self):
        """启动客户端模式"""
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
        
        # 获取游戏
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
            self.run_game_loop()
        else:
            print(f"加入失败: {message}")
    
    def simulate_player_join(self):
        """模拟其他玩家加入（用于测试）"""
        import random
        if random.random() < 0.2:  # 20%概率有新玩家加入
            fake_id = f"bot_{random.randint(1000, 9999)}"
            fake_name = f"玩家{random.randint(1, 100)}"
            self.current_game.add_player(fake_id, fake_name)
    
    def show_waiting_room(self):
        """显示等待房间"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=== 游戏房间 ===")
        print(f"房间ID: {self.current_game_id}")
        print(f"当前玩家数: {len(self.current_game.players)}")
        print("\n玩家列表:")
        for i, (pid, player) in enumerate(self.current_game.players.items(), 1):
            marker = " (房主)" if pid == self.current_game.server_player_id else ""
            print(f"  {i}. {player.name}{marker}")
        print("\n命令: s=开始游戏, r=刷新, q=退出")
    
    def run_game_loop(self):
        """游戏主循环"""
        while self.current_game.running and self.current_game.phase != GamePhase.GAME_OVER:
            try:
                # 显示游戏状态
                self.show_game_state()
                
                # 检查是否是当前玩家的回合
                current_player = self.current_game.get_current_player()
                if current_player and current_player.player_id == self.player_id:
                    self.handle_player_turn(current_player)
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
        
        # 清理
        if self.current_game and self.player_id:
            self.current_game.remove_player(self.player_id)
    
    def show_game_state(self):
        """显示游戏状态"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        game_state = self.current_game.get_game_state()
        current_player = self.current_game.get_current_player()
        my_player = self.current_game.players.get(self.player_id)
        
        print(f"=== 回合 {game_state['turn_number']} - {game_state['phase']} ===")
        
        # 显示Boss状态
        print(f"🏆 Boss: {game_state['boss']}")
        
        # 显示敌人区
        if game_state['enemy_zone']:
            print(f"👹 敌人区: {', '.join(game_state['enemy_zone'])}")
        else:
            print("👹 敌人区: 无敌人 (可攻击Boss)")
        
        # 显示资源区
        if game_state['resource_zone']:
            print(f"💎 资源区:")
            for i, resource in enumerate(game_state['resource_zone'], 1):
                print(f"  {i}. {resource}")
        else:
            print("💎 资源区: 无可用资源")
        
        print("=" * 60)
        
        # 显示所有玩家状态
        print("🏟️ 玩家状态:")
        for i, pid in enumerate(game_state['player_order']):
            player_data = game_state['players'][pid]
            marker = " <- 当前回合" if current_player and pid == current_player.player_id else ""
            marker += " (你)" if pid == self.player_id else ""
            print(f"  {i+1}. {player_data['name']} HP:{player_data['hp']}/{player_data['max_hp']} "
                  f"手牌:{player_data['hand_count']} 随从:{player_data['battlefield_count']}{marker}")
        
        # 显示我的详细信息
        if my_player:
            print(f"\n📋 我的详细状态:")
            print(f"  生命值: {my_player.hp}/{my_player.max_hp}")
            print(f"  手牌 ({len(my_player.hand)}):")
            for i, card in enumerate(my_player.hand, 1):
                print(f"    {i}. {card}")
            
            if my_player.battlefield.my_board:
                print(f"  我的随从 ({len(my_player.battlefield.my_board)}):")
                for i, minion in enumerate(my_player.battlefield.my_board, 1):
                    attack_status = "可攻击" if minion.can_attack else "已攻击"
                    print(f"    {i}. {minion} ({attack_status})")
            else:
                print(f"  我的随从: 无")
        
        print()
    
    def handle_player_turn(self, player):
        """处理玩家回合"""
        print(f"=== 你的回合 ({player.name}) ===")
        
        while True:
            command = input("> ").strip()
            
            if not command:
                continue
            
            # 解析命令
            parts = command.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd in ['h', 'help']:
                self.show_help()
                continue
            
            elif cmd == 'p' and args:
                # 出牌: p 手牌编号 [目标]
                if self.handle_play_card(player, args):
                    continue  # 出牌不结束回合
            
            elif cmd == 'a' and len(args) >= 2:
                # 攻击: a 随从编号 区域 [目标编号]
                if self.handle_attack(player, args):
                    continue  # 攻击不结束回合
            
            elif cmd == 'c' and len(args) >= 1:
                # 收集资源: c 资源编号
                if self.handle_collect_resource(player, args[0]):
                    continue  # 收集不结束回合
            
            elif cmd in ['i', 'info']:
                # 查看信息: i [目标编号]
                self.handle_info(player, args)
                continue
            
            elif cmd == 'bag':
                self.handle_bag(player)
                continue
            
            elif cmd in ['e', 'end']:
                print(f"{player.name} 结束回合")
                self.current_game.next_turn()
                break
            
            else:
                print("无效命令，输入 'h' 查看帮助")
    
    def handle_play_card(self, player, args):
        """处理出牌"""
        try:
            card_index = int(args[0]) - 1
            target_idx = None
            if len(args) > 1:
                target_idx = int(args[1])
            
            if 0 <= card_index < len(player.hand):
                card_name = player.hand[card_index].name if hasattr(player.hand[card_index], 'name') else f"卡牌{card_index+1}"
                player.play_card(card_index, target_idx)
                print(f"✅ 成功出牌: {card_name}")
                return True
            else:
                print("❌ 无效的卡牌编号")
        except ValueError:
            print("❌ 请输入有效的数字")
        except Exception as e:
            print(f"❌ 出牌错误: {e}")
        return False
    
    def handle_attack(self, player, args):
        """处理攻击"""
        try:
            attacker_index = int(args[0]) - 1
            target_zone = int(args[1])
            
            if target_zone == 0:  # 攻击敌人区
                if len(args) >= 3:
                    target_index = int(args[2])
                    if target_index == 0:  # 攻击Boss
                        success, message = self.current_game.attack_boss(self.player_id, attacker_index)
                        print(f"{'✅' if success else '❌'} {message}")
                        return success
                    else:  # 攻击敌人
                        enemy_index = target_index - 1
                        success, message = self.current_game.attack_enemy(self.player_id, attacker_index, enemy_index)
                        print(f"{'✅' if success else '❌'} {message}")
                        return success
                else:
                    print("❌ 攻击敌人区需要指定目标编号 (0=Boss, 1+=敌人)")
            
            elif target_zone >= 1:  # 攻击其他玩家的随从
                if len(args) >= 3:
                    target_minion = int(args[2]) - 1
                    # 找到目标玩家
                    target_player_index = target_zone - 1
                    if target_player_index < len(self.current_game.player_order):
                        target_player_id = self.current_game.player_order[target_player_index]
                        success, message = self.current_game.attack_player_minion(
                            self.player_id, attacker_index, target_player_id, target_minion)
                        print(f"{'✅' if success else '❌'} {message}")
                        return success
                    else:
                        print("❌ 无效的玩家编号")
                else:
                    print("❌ 攻击玩家随从需要指定随从编号")
            
            else:
                print("❌ 无效的攻击目标")
                
        except ValueError:
            print("❌ 请输入有效的数字")
        except Exception as e:
            print(f"❌ 攻击错误: {e}")
        return False
    
    def handle_collect_resource(self, player, resource_arg):
        """处理收集资源"""
        try:
            resource_index = int(resource_arg) - 1
            resource = self.current_game.collect_resource(self.player_id, resource_index)
            if resource:
                print(f"✅ 成功收集资源: {resource}")
                return True
            else:
                print("❌ 收集资源失败")
        except ValueError:
            print("❌ 请输入有效的数字")
        except Exception as e:
            print(f"❌ 收集错误: {e}")
        return False
    
    def handle_info(self, player, args):
        """处理信息查看"""
        if not args:
            print("请指定要查看的目标编号")
            return
        
        try:
            idx = int(args[0])
            if idx == 0:  # 查看自己的英雄信息
                print(f"🦸 我的英雄：HP {player.hp}/{player.max_hp}")
            elif 1 <= idx <= len(player.hand):  # 查看手牌
                card = player.hand[idx-1]
                print(f"🃏 手牌 {idx}：{card.info()}")
            elif idx > 100 and idx-100 <= len(player.battlefield.my_board):  # 查看我方战场
                card = player.battlefield.my_board[idx-101]
                print(f"⚔️ 我方随从 {idx-100}：{card.info()}")
            else:
                print("❌ 无效的索引")
        except ValueError:
            print("❌ 请输入有效的数字")
    
    def handle_bag(self, player):
        """处理背包操作"""
        from inventory_ui import show_inventory_menu
        show_inventory_menu(player)
    
    def show_help(self):
        """显示帮助信息"""
        help_text = """
========== PvE游戏命令帮助 ==========
--- 基本操作 ---
p <手牌编号> [目标]    - 出第N张手牌，可选目标
a <随从编号> <区域> <目标> - 攻击
  例: a 1 0 0        - 第1个随从攻击Boss
  例: a 1 0 1        - 第1个随从攻击敌人区第1个敌人
  例: a 1 2 1        - 第1个随从攻击玩家2的第1个随从
c <资源编号>          - 收集第N个资源
e/end                - 结束回合

--- 信息查看 ---
i/info <编号>         - 查看信息
  0 = 我的英雄, 1-N = 手牌, 101-N = 我的随从
bag                  - 打开背包

--- 其他 ---
h/help               - 显示此帮助
=================================
"""
        print(help_text)
    
    def wait_for_turn(self):
        """等待回合"""
        print("⏳ 等待其他玩家或系统回合...")
        time.sleep(2)

def start_pve_multiplayer_game():
    """启动PvE多人游戏的主函数"""
    controller = PvEGameController()
    
    print("\n=== 🎮 多人PvE卡牌对战 ===")
    print("这是一个合作模式，所有玩家一起对抗NPC敌人和Boss")
    print("1. 创建游戏房间 (作为房主)")
    print("2. 加入游戏房间")
    print("3. 返回主菜单")
    
    choice = input("请选择 (1-3): ").strip()
    
    if choice == "1":
        controller.start_server_mode()
    elif choice == "2":
        controller.start_client_mode()
    elif choice == "3":
        return
    else:
        print("无效选择")
