"""
新的多人游戏主控制器
整合三区域游戏机制 + 聊天和操作记录 + 颜色支持 + 滚动功能
"""

from multiplayer_game import GameManager, MultiPlayerGame
from interactive_display import (
    show_interactive_game, add_chat_message, add_action_log, add_system_message,
    scroll_chat_up, scroll_chat_down, scroll_actions_up, scroll_actions_down, reset_scroll
)
import threading
import time

class MultiPlayerGameController:
    """多人游戏控制器"""
    
    def __init__(self):
        self.game_manager = GameManager()
        self.current_game_id = None
        self.current_game = None
        self.player_id = None
        self.running = False
    
    def start_new_game(self, player_name, max_players=4):
        """创建并加入新游戏"""
        # 创建游戏
        game_id, game = self.game_manager.create_game(max_players)
        
        # 生成玩家ID
        self.player_id = f"player_{int(time.time() * 1000) % 10000}"
        
        # 加入游戏
        success, message = game.add_player(self.player_id, player_name)
        
        if success:
            self.current_game_id = game_id
            self.current_game = game
            print(f"成功创建游戏 {game_id}: {message}")
            return True
        else:
            print(f"创建游戏失败: {message}")
            return False
    
    def join_game(self, game_id, player_name):
        """加入现有游戏"""
        game = self.game_manager.get_game(game_id)
        if not game:
            print("游戏不存在")
            return False
        
        # 生成玩家ID
        self.player_id = f"player_{int(time.time() * 1000) % 10000}"
        
        # 加入游戏
        success, message = game.add_player(self.player_id, player_name)
        
        if success:
            self.current_game_id = game_id
            self.current_game = game
            print(f"成功加入游戏: {message}")
            return True
        else:
            print(f"加入游戏失败: {message}")
            return False
    
    def run_game_loop(self):
        """运行游戏主循环"""
        if not self.current_game:
            print("没有活跃的游戏")
            return
        
        self.running = True
        
        # 启动游戏
        if len(self.current_game.players) >= 2:
            success, message = self.current_game.start_game()
            if not success:
                print(f"游戏启动失败: {message}")
                return
            else:
                add_system_message("游戏开始！")
                add_action_log("多人游戏正式开始")
        
        print("进入游戏循环...")
        
        while self.running:
            try:
                # 获取当前游戏状态
                game_state = self.current_game.get_game_state()
                
                # 显示游戏界面（包含聊天和操作记录）
                layout = show_interactive_game(game_state, self.player_id)
                from rich.console import Console
                Console().print(layout)
                
                # 检查是否是当前玩家的回合
                current_player = self.current_game.get_current_player()
                if current_player and current_player.player_id == self.player_id:
                    self.handle_player_turn(current_player)
                else:
                    # 等待其他玩家
                    self.wait_for_turn()
                
            except KeyboardInterrupt:
                print("\n游戏中断")
                break
            except Exception as e:
                print(f"游戏错误: {e}")
                break
                break
        
        self.cleanup()
    
    def handle_player_turn(self, player):
        """处理当前玩家回合"""
        print(f"\n=== 你的回合 ===")
        
        while True:
            command = input("> ").strip()
            
            if not command:
                continue
            
            # 解析命令
            parts = command.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd == 'help':
                self.show_help()
                continue
            
            elif cmd == 'play' and args:
                if self.handle_play_card(player, args[0]):
                    break
            
            elif cmd == 'attack' and args:
                if self.handle_attack(player, args[0]):
                    break
            
            elif cmd == 'bag':
                self.handle_bag(player)
                continue
            
            elif cmd == 'challenge' and args:
                self.handle_challenge(player, args[0])
                continue
            
            elif cmd == 'resource' and args:
                if self.handle_resource(player, args[0]):
                    break
            
            elif cmd == 'say' and args:
                # 聊天命令
                message = " ".join(args)
                self.handle_chat(player, message)
                continue
            
            elif cmd == 'whisper' and len(args) >= 2:
                # 私聊命令
                target_player = args[0]
                message = " ".join(args[1:])
                self.handle_whisper(player, target_player, message)
                continue
            
            elif cmd == 'up' and len(args) >= 1:
                # 向上滚动命令
                area = args[0]
                lines = int(args[1]) if len(args) > 1 else 1
                if area == 'chat':
                    scroll_chat_up(lines)
                    print(f"向上滚动聊天记录 {lines} 行")
                elif area == 'action':
                    scroll_actions_up(lines)
                    print(f"向上滚动操作记录 {lines} 行")
                continue
            
            elif cmd == 'down' and len(args) >= 1:
                # 向下滚动命令
                area = args[0]
                lines = int(args[1]) if len(args) > 1 else 1
                if area == 'chat':
                    scroll_chat_down(lines)
                    print(f"向下滚动聊天记录 {lines} 行")
                elif area == 'action':
                    scroll_actions_down(lines)
                    print(f"向下滚动操作记录 {lines} 行")
                continue
            
            elif cmd == 'reset':
                # 重置滚动位置
                reset_scroll()
                print("已重置滚动位置到最新消息")
                continue
            
            elif cmd == 'end':
                add_action_log(f"{player.name} 结束了回合")
                self.current_game.next_turn()
                break
            
            else:
                print("无效命令，输入 'help' 查看帮助")
    
    def handle_play_card(self, player, card_index):
        """处理出牌"""
        try:
            index = int(card_index) - 1
            if 0 <= index < len(player.hand):
                card_name = player.hand[index].name if hasattr(player.hand[index], 'name') else f"卡牌{index+1}"
                success = player.play_card(index)
                if success:
                    add_action_log(f"{player.name} 出了一张牌: {card_name}")
                    print(f"成功出牌: {card_name}")
                    return True
                else:
                    print("出牌失败")
            else:
                print("无效的卡牌编号")
        except ValueError:
            print("请输入有效的数字")
        return False
    
    def handle_attack(self, player, target):
        """处理攻击"""
        # 这里可以实现攻击逻辑
        add_action_log(f"{player.name} 攻击了 {target}")
        print(f"攻击目标: {target}")
        return True
    
    def handle_bag(self, player):
        """处理背包操作"""
        from inventory_ui import show_inventory_menu
        add_action_log(f"{player.name} 打开了背包")
        show_inventory_menu(player)
    
    def handle_challenge(self, player, target_name):
        """处理挑战其他玩家"""
        # 查找目标玩家
        target_player = None
        for pid, p in self.current_game.players.items():
            if p.name.lower() == target_name.lower():
                target_player = p
                break
        
        if target_player:
            success = self.current_game.player_arena.challenge_player(
                self.player_id, target_player.player_id
            )
            if success:
                add_action_log(f"{player.name} 向 {target_name} 发起挑战")
                add_system_message(f"{player.name} 向 {target_name} 发起了挑战！")
                print(f"已向 {target_name} 发起挑战")
            else:
                print("挑战发起失败")
        else:
            print(f"找不到玩家: {target_name}")
    
    def handle_resource(self, player, resource_index):
        """处理领取资源"""
        try:
            index = int(resource_index) - 1
            resource = self.current_game.resource_zone.claim_resource(self.player_id, index)
            if resource:
                player.add_to_inventory(resource, 1)
                add_action_log(f"{player.name} 领取了资源: {resource.name}")
                print(f"成功领取资源: {resource.name}")
                return True
            else:
                print("领取资源失败")
        except ValueError:
            print("请输入有效的数字")
        return False
    
    def handle_chat(self, player, message):
        """处理聊天消息"""
        if len(message.strip()) > 0:
            add_chat_message(player.name, message)
            print(f"[聊天] {player.name}: {message}")
        else:
            print("消息不能为空")
    
    def handle_whisper(self, player, target_name, message):
        """处理私聊消息"""
        # 查找目标玩家
        target_player = None
        for pid, p in self.current_game.players.items():
            if p.name.lower() == target_name.lower():
                target_player = p
                break
        
        if target_player:
            if len(message.strip()) > 0:
                # 在聊天区显示私聊消息（格式特殊化）
                whisper_msg = f"[私聊→{target_name}] {message}"
                add_chat_message(player.name, whisper_msg)
                print(f"[私聊] 对 {target_name}: {message}")
            else:
                print("私聊消息不能为空")
        else:
            print(f"找不到玩家: {target_name}")
    
    def wait_for_turn(self):
        """等待回合"""
        print("等待其他玩家操作...", end="", flush=True)
        time.sleep(2)  # 简单的等待，实际应该用网络同步
        print("\r" + " " * 30 + "\r", end="", flush=True)
    
    def show_help(self):
        """显示帮助信息"""
        help_text = """
========== 游戏命令帮助 ==========
--- 游戏操作 ---
play <编号>       - 出第N张手牌
attack <目标>     - 攻击指定目标
bag              - 打开背包管理
challenge <玩家>  - 挑战其他玩家
resource <编号>   - 领取第N个资源
end              - 结束当前回合

--- 聊天交流 ---
say <消息>       - 发送公开聊天消息
whisper <玩家> <消息> - 发送私聊消息

--- 滚动浏览 ---
up chat [行数]    - 向上滚动聊天记录
down chat [行数]  - 向下滚动聊天记录
up action [行数]  - 向上滚动操作记录
down action [行数] - 向下滚动操作记录
reset            - 重置滚动位置到最新消息

--- 其他 ---
help             - 显示此帮助
quit             - 退出游戏
=================================
"""
        print(help_text)
    
    def cleanup(self):
        """清理资源"""
        if self.current_game and self.player_id:
            self.current_game.remove_player(self.player_id)
        self.running = False

def start_multiplayer_game():
    """启动多人游戏的主函数"""
    controller = MultiPlayerGameController()
    
    print("=== COMOS 多人卡牌对战 ===")
    print("1. 创建新游戏")
    print("2. 加入游戏") 
    print("3. 返回")
    
    choice = input("请选择 (1-3): ").strip()
    
    if choice == "1":
        player_name = input("请输入你的名字: ").strip()
        if not player_name:
            player_name = "玩家"
        
        max_players = input("最大玩家数 (2-8, 默认4): ").strip()
        try:
            max_players = int(max_players)
            if max_players < 2 or max_players > 8:
                max_players = 4
        except:
            max_players = 4
        
        if controller.start_new_game(player_name, max_players):
            controller.run_game_loop()
    
    elif choice == "2":
        game_id = input("请输入游戏ID: ").strip()
        player_name = input("请输入你的名字: ").strip()
        
        if not player_name:
            player_name = "玩家"
        
        try:
            game_id = int(game_id)
            if controller.join_game(game_id, player_name):
                controller.run_game_loop()
        except ValueError:
            print("无效的游戏ID")
    
    elif choice == "3":
        return
    else:
        print("无效选择")

if __name__ == "__main__":
    start_multiplayer_game()
