"""
增强的游戏界面显示系统
支持颜色、聊天记录、操作日志和清晰的布局
"""

import os
import time
from datetime import datetime
from collections import deque

class EnhancedGameDisplay:
    """增强游戏界面显示器"""
    
    def __init__(self):
        self.width = 140  # 界面总宽度
        # 使用deque实现自动滚动的历史记录
        self.chat_history = deque(maxlen=100)  # 最多保存100条聊天记录
        self.action_log = deque(maxlen=100)    # 最多保存100条操作记录
        
        self.max_chat_lines = 8   # 聊天区显示行数
        self.max_action_lines = 8 # 操作记录区显示行数
        self.max_area_lines = 8   # 游戏区域显示行数
        
        # 颜色支持检测
        self.use_colors = self._detect_color_support()
        
        # 颜色方案（如果支持的话）
        if self.use_colors:
            try:
                from colorama import init, Fore, Back, Style
                init(autoreset=True)
                self.colors = {
                    'header': Fore.CYAN + Style.BRIGHT,
                    'title': Fore.YELLOW + Style.BRIGHT,
                    'player': Fore.GREEN,
                    'npc': Fore.RED,
                    'resource': Fore.MAGENTA,
                    'chat': Fore.WHITE,
                    'action': Fore.LIGHTBLUE_EX,
                    'system': Fore.YELLOW,
                    'private': Fore.LIGHTCYAN_EX,
                    'border': Fore.LIGHTBLACK_EX,
                    'warning': Fore.RED + Style.BRIGHT,
                    'success': Fore.GREEN + Style.BRIGHT,
                    'info': Fore.BLUE,
                    'reset': Style.RESET_ALL
                }
            except ImportError:
                self.use_colors = False
                self.colors = {key: '' for key in ['header', 'title', 'player', 'npc', 'resource', 'chat', 'action', 'system', 'private', 'border', 'warning', 'success', 'info', 'reset']}
        else:
            self.colors = {key: '' for key in ['header', 'title', 'player', 'npc', 'resource', 'chat', 'action', 'system', 'private', 'border', 'warning', 'success', 'info', 'reset']}
    
    def _detect_color_support(self):
        """检测终端是否支持颜色"""
        try:
            import colorama
            return True
        except ImportError:
            return False
    
    def colorize(self, text, color_key):
        """给文本添加颜色"""
        if self.use_colors and color_key in self.colors:
            return f"{self.colors[color_key]}{text}{self.colors['reset']}"
        return text
    
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def add_chat_message(self, message):
        """添加聊天消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        self.chat_history.append(formatted_msg)
    
    def add_action_log(self, action):
        """添加操作记录"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_action = f"[{timestamp}] {action}"
        self.action_log.append(formatted_action)
    
    def add_system_message(self, message):
        """添加系统消息"""
        self.add_chat_message(self.colorize(f"[系统] {message}", 'system'))
    
    def show_game(self, game_state, current_player_id=None):
        """显示完整游戏界面（五区域布局）"""
        self.clear_screen()
        
        # 顶部标题
        self._show_header(game_state)
        
        # 主体区域（上半部分：三大游戏区域）
        self._show_main_areas(game_state)
        
        # 分隔线
        print(self.colorize("=" * self.width, 'border'))
        
        # 下半部分：聊天区 + 操作记录区
        self._show_communication_areas()
        
        # 当前玩家信息
        if current_player_id:
            self._show_current_player_info(game_state, current_player_id)
        
        # 底部操作提示
        self._show_command_help()
    
    def _show_header(self, game_state):
        """显示顶部标题区域"""
        print(self.colorize("=" * self.width, 'border'))
        title = "COMOS 多人卡牌对战"
        print(self.colorize(title.center(self.width), 'title'))
        
        phase_info = f"阶段: {game_state['phase']} | 回合: {game_state['turn']}"
        current_info = f"当前玩家: {game_state['current_player'] or '无'}"
        info_line = f"{phase_info} | {current_info}"
        print(self.colorize(info_line.center(self.width), 'header'))
        print(self.colorize("=" * self.width, 'border'))
    
    def _show_main_areas(self, game_state):
        """显示三大主要区域"""
        # 计算每个区域的宽度
        area_width = (self.width - 6) // 3  # 减去分隔符空间
        
        # 区域标题
        player_title = self.colorize("🏟️ 玩家竞技场".center(area_width), 'player')
        npc_title = self.colorize("👹 NPC敌人区".center(area_width), 'npc')
        resource_title = self.colorize("💎 公共资源区".center(area_width), 'resource')
        
        print(f"{player_title} | {npc_title} | {resource_title}")
        print(self.colorize("-" * self.width, 'border'))
        
        # 区域内容
        player_lines = self._format_player_arena(game_state.get('players', {}), area_width)
        npc_lines = self._format_npc_zone(game_state.get('npc_zone', {}), area_width)
        resource_lines = self._format_resource_zone(game_state.get('resource_zone', {}), area_width)
        
        # 确保每个区域都有相同的行数
        max_lines = max(len(player_lines), len(npc_lines), len(resource_lines), self.max_area_lines)
        
        for i in range(max_lines):
            player_text = player_lines[i] if i < len(player_lines) else ""
            npc_text = npc_lines[i] if i < len(npc_lines) else ""
            resource_text = resource_lines[i] if i < len(resource_lines) else ""
            
            # 确保每列的宽度一致
            player_text = player_text.ljust(area_width)
            npc_text = npc_text.ljust(area_width)
            resource_text = resource_text.ljust(area_width)
            
            print(f"{player_text} | {npc_text} | {resource_text}")
    
    def _format_player_arena(self, players, width):
        """格式化玩家竞技场区域"""
        lines = []
        for player_id, player_data in players.items():
            name = player_data.get('name', player_id)
            hp = player_data.get('hp', 0)
            max_hp = player_data.get('max_hp', 100)
            hand_count = player_data.get('hand_count', 0)
            board_count = player_data.get('board_count', 0)
            inventory_count = player_data.get('inventory_count', 0)
            
            # 玩家基本信息
            hp_text = f"HP:{hp}/{max_hp}"
            player_line = f"{name} {hp_text}".ljust(width)
            lines.append(self.colorize(player_line, 'player'))
            
            # 玩家状态
            status_line = f"  手牌:{hand_count} 随从:{board_count}".ljust(width)
            lines.append(status_line)
            
            inventory_line = f"  背包:{inventory_count}".ljust(width)
            lines.append(inventory_line)
            
            lines.append("")  # 空行分隔
            
        if not lines:
            lines = ["暂无玩家".ljust(width)]
            
        return lines
    
    def _format_npc_zone(self, npc_zone, width):
        """格式化NPC敌人区域"""
        lines = []
        
        difficulty = npc_zone.get('difficulty', 1)
        lines.append(f"难度等级: {difficulty}".ljust(width))
        lines.append("")
        
        npcs = npc_zone.get('npcs', [])
        if npcs:
            for npc in npcs:
                name = npc.get('name', '未知敌人')
                atk = npc.get('atk', 0)
                hp = npc.get('hp', 0)
                npc_line = f"{name} {atk}/{hp}".ljust(width)
                lines.append(self.colorize(npc_line, 'npc'))
        else:
            lines.append("暂无敌人".ljust(width))
            
        boss_present = npc_zone.get('boss_present', False)
        if boss_present:
            lines.append("")
            lines.append(self.colorize("⚠️ BOSS出现！".ljust(width), 'warning'))
            
        return lines
    
    def _format_resource_zone(self, resource_zone, width):
        """格式化公共资源区域"""
        lines = []
        
        next_refresh = resource_zone.get('next_refresh', 0)
        lines.append(f"刷新倒计时: {next_refresh}".ljust(width))
        lines.append("")
        
        resources = resource_zone.get('available_resources', [])
        if resources:
            for i, resource in enumerate(resources, 1):
                name = resource.get('name', '未知资源')
                resource_type = resource.get('type', '物品')
                resource_line = f"{i}. {name} ({resource_type})".ljust(width)
                lines.append(self.colorize(resource_line, 'resource'))
        else:
            lines.append("暂无可用资源".ljust(width))
            
        return lines
    
    def _show_communication_areas(self):
        """显示聊天和操作记录区域"""
        # 计算每个区域的宽度
        area_width = (self.width - 3) // 2  # 减去分隔符空间
        
        # 区域标题
        chat_title = self.colorize("💬 聊天记录".center(area_width), 'chat')
        action_title = self.colorize("📝 操作记录".center(area_width), 'action')
        
        print(f"{chat_title} | {action_title}")
        print(self.colorize("-" * self.width, 'border'))
        
        # 获取最近的消息
        recent_chat = list(self.chat_history)[-self.max_chat_lines:] if self.chat_history else []
        recent_actions = list(self.action_log)[-self.max_action_lines:] if self.action_log else []
        
        # 显示内容
        max_lines = max(len(recent_chat), len(recent_actions), self.max_chat_lines)
        
        for i in range(max_lines):
            chat_text = recent_chat[i] if i < len(recent_chat) else ""
            action_text = recent_actions[i] if i < len(recent_actions) else ""
            
            # 确保每列的宽度一致
            chat_text = chat_text.ljust(area_width)
            action_text = action_text.ljust(area_width)
            
            print(f"{chat_text} | {action_text}")
    
    def _show_current_player_info(self, game_state, current_player_id):
        """显示当前玩家信息"""
        print(self.colorize("-" * self.width, 'border'))
        
        players = game_state.get('players', {})
        if current_player_id in players:
            player = players[current_player_id]
            name = player.get('name', current_player_id)
            hp = player.get('hp', 0)
            max_hp = player.get('max_hp', 100)
            hand_count = player.get('hand_count', 0)
            inventory_count = player.get('inventory_count', 0)
            
            info = f"当前玩家: {name} | 生命值: {hp}/{max_hp} | 手牌: {hand_count} | 背包: {inventory_count}"
            print(self.colorize(info.center(self.width), 'info'))
        else:
            info = f"当前玩家: {current_player_id} | 状态: 等待中"
            print(self.colorize(info.center(self.width), 'info'))
        
        print(self.colorize("-" * self.width, 'border'))
    
    def _show_command_help(self):
        """显示操作提示"""
        print(self.colorize("=" * self.width, 'border'))
        help_title = "可用命令:"
        print(self.colorize(help_title.center(self.width), 'title'))
        
        commands1 = "play <卡牌编号> - 出牌 | attack <目标> - 攻击 | bag - 背包"
        commands2 = "challenge <玩家名> - 挑战玩家 | resource <编号> - 领取资源 | end - 结束回合"
        
        print(self.colorize(commands1.center(self.width), 'info'))
        print(self.colorize(commands2.center(self.width), 'info'))
        print(self.colorize("=" * self.width, 'border'))

# 创建全局实例
enhanced_display = EnhancedGameDisplay()

# 导出函数供其他模块使用
def show_enhanced_game(game_state, current_player_id=None):
    """显示增强游戏界面"""
    enhanced_display.show_game(game_state, current_player_id)

def add_chat_message(message):
    """添加聊天消息"""
    enhanced_display.add_chat_message(message)

def add_action_log(action):
    """添加操作记录"""
    enhanced_display.add_action_log(action)

def add_system_message(message):
    """添加系统消息"""
    enhanced_display.add_system_message(message)
