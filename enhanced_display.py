"""
增强的游戏界面显示系统
支持颜色、滚动和一致缩进的五区域布局
"""

import os
import time
from datetime import datetime
from colorama import init, Fore, Back, Style
from collections import deque

# 初始化colorama
init(autoreset=True)

class ColoredGameDisplay:
    """支持颜色和滚动的增强游戏界面显示器"""
    
    def __init__(self):
        self.width = 140  # 界面总宽度
        
        # 使用deque实现自动滚动的历史记录
        self.chat_history = deque(maxlen=100)  # 最多保存100条聊天记录
        self.action_log = deque(maxlen=100)    # 最多保存100条操作记录
        
        self.max_chat_lines = 8   # 聊天区显示行数
        self.max_action_lines = 8 # 操作记录区显示行数
        self.max_area_lines = 8   # 游戏区域显示行数
        
        # 颜色方案
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
    
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def show_game(self, game_state, current_player_id=None, chat_messages=None, recent_actions=None):
        """显示完整游戏界面（五区域布局）"""
        self.clear_screen()
        
        # 更新聊天和操作记录
        if chat_messages:
            for msg in chat_messages:
                self.chat_history.append(msg)
        
        if recent_actions:
            for action in recent_actions:
                self.action_log.append(action)
        
        # 显示界面各部分
        self._show_header(game_state)
        self._show_main_areas(game_state)
        self._show_separator("主游戏区域")
        self._show_communication_areas()
        
        if current_player_id:
            self._show_current_player_info(game_state, current_player_id)
        
        self._show_command_help()
    
    def _show_header(self, game_state):
        """显示顶部标题区域"""
        border = self.colors['border'] + "=" * self.width + self.colors['reset']
        print(border)
        
        title = self.colors['title'] + "COMOS 多人卡牌对战" + self.colors['reset']
        print(title.center(self.width + len(self.colors['title']) + len(self.colors['reset'])))
        
        # 游戏状态信息
        phase_info = f"阶段: {self.colors['info']}{game_state['phase']}{self.colors['reset']}"
        turn_info = f"回合: {self.colors['info']}{game_state['turn']}{self.colors['reset']}"
        current_info = f"当前玩家: {self.colors['player']}{game_state['current_player'] or '无'}{self.colors['reset']}"
        time_info = f"时间: {self.colors['info']}{datetime.now().strftime('%H:%M:%S')}{self.colors['reset']}"
        
        info_line = f"{phase_info} | {turn_info} | {current_info} | {time_info}"
        # 计算纯文本长度（不包含颜色代码）
        plain_text_length = len(f"阶段: {game_state['phase']} | 回合: {game_state['turn']} | 当前玩家: {game_state['current_player'] or '无'} | 时间: {datetime.now().strftime('%H:%M:%S')}")
        padding = (self.width - plain_text_length) // 2
        print(" " * padding + info_line)
        
        print(border)
    
    def _show_main_areas(self, game_state):
        """显示三大主要游戏区域"""
        area_width = (self.width - 8) // 3  # 每个区域宽度，减去分隔符空间
        
        print()
        # 区域标题行
        player_title = f"{self.colors['player']}🏟️ 玩家竞技场{self.colors['reset']}"
        npc_title = f"{self.colors['npc']}👹 NPC敌人区{self.colors['reset']}"
        resource_title = f"{self.colors['resource']}💎 公共资源区{self.colors['reset']}"
        
        self._print_three_columns(
            self._center_colored_text(player_title, area_width),
            self._center_colored_text(npc_title, area_width),
            self._center_colored_text(resource_title, area_width),
            area_width
        )
        
        separator = self.colors['border'] + "-" * self.width + self.colors['reset']
        print(separator)
        
        # 区域内容
        self._show_game_area_contents(game_state, area_width)
    
    def _show_game_area_contents(self, game_state, area_width):
        """显示游戏区域内容"""
        # 准备各区域的内容行
        player_lines = self._prepare_player_area_lines(game_state['players'], area_width)
        npc_lines = self._prepare_npc_area_lines(game_state['npc_zone'], area_width)
        resource_lines = self._prepare_resource_area_lines(game_state['resource_zone'], area_width)
        
        # 确保所有区域行数相同
        max_lines = max(len(player_lines), len(npc_lines), len(resource_lines), self.max_area_lines)
        
        # 填充空行使所有区域高度一致
        while len(player_lines) < max_lines:
            player_lines.append("")
        while len(npc_lines) < max_lines:
            npc_lines.append("")
        while len(resource_lines) < max_lines:
            resource_lines.append("")
        
        # 逐行显示
        for i in range(max_lines):
            self._print_three_columns(
                self._format_area_content(player_lines[i], area_width),
                self._format_area_content(npc_lines[i], area_width),
                self._format_area_content(resource_lines[i], area_width),
                area_width
            )
    
    def _show_communication_areas(self):
        """显示聊天区和操作记录区"""
        # 计算两个区域的宽度
        chat_width = (self.width - 3) // 2
        action_width = self.width - chat_width - 3
        
        # 区域标题
        chat_title = f"{self.colors['chat']}💬 聊天区{self.colors['reset']}"
        action_title = f"{self.colors['action']}📜 操作记录{self.colors['reset']}"
        
        self._print_two_columns(
            self._center_colored_text(chat_title, chat_width),
            self._center_colored_text(action_title, action_width),
            chat_width
        )
        
        separator = self.colors['border'] + "-" * self.width + self.colors['reset']
        print(separator)
        
        # 准备聊天和操作记录内容
        chat_lines = self._prepare_chat_lines(chat_width)
        action_lines = self._prepare_action_lines(action_width)
        
        # 确保两个区域行数相同
        max_lines = max(len(chat_lines), len(action_lines), self.max_chat_lines)
        
        while len(chat_lines) < max_lines:
            chat_lines.append("")
        while len(action_lines) < max_lines:
            action_lines.append("")
        
        # 逐行显示
        for i in range(max_lines):
            self._print_two_columns(
                self._format_area_content(chat_lines[i], chat_width),
                self._format_area_content(action_lines[i], action_width),
                chat_width
            )
    
    def _prepare_chat_lines(self, width):
        """准备聊天区域内容行"""
        lines = []
        
        if not self.chat_history:
            empty_msg = f"{self.colors['border']}暂无聊天消息{self.colors['reset']}"
            lines.append(empty_msg)
            return lines
        
        # 只显示最近的聊天消息（自动滚动）
        recent_chats = list(self.chat_history)[-self.max_chat_lines:]
        
        for chat in recent_chats:
            time_str = chat.get('time', '00:00')
            player_name = chat.get('player', '系统')
            message = chat.get('message', '')
            
            # 根据消息类型选择颜色
            if player_name == '系统':
                color = self.colors['system']
            elif '[私聊' in message:
                color = self.colors['private']
            else:
                color = self.colors['chat']
            
            # 限制玩家名长度
            if len(player_name) > 8:
                player_name = player_name[:8] + "."
            
            # 处理长消息
            available_width = width - 15  # 为时间和玩家名留空间
            if len(message) > available_width:
                message = message[:available_width-3] + "..."
            
            # 格式化聊天行
            time_part = f"{self.colors['border']}[{time_str}]{self.colors['reset']}"
            name_part = f"{color}{player_name}:{self.colors['reset']}"
            message_part = f"{color}{message}{self.colors['reset']}"
            
            chat_line = f"{time_part} {name_part} {message_part}"
            lines.append(chat_line)
        
        return lines
    
    def _prepare_action_lines(self, width):
        """准备操作记录内容行"""
        lines = []
        
        if not self.action_log:
            empty_msg = f"{self.colors['border']}暂无操作记录{self.colors['reset']}"
            lines.append(empty_msg)
            return lines
        
        # 只显示最近的操作记录（自动滚动）
        recent_actions = list(self.action_log)[-self.max_action_lines:]
        
        for action in recent_actions:
            time_str = action.get('time', '00:00')
            action_text = action.get('action', '')
            
            # 处理长操作记录
            available_width = width - 10  # 为时间留空间
            if len(action_text) > available_width:
                action_text = action_text[:available_width-3] + "..."
            
            # 格式化操作行
            time_part = f"{self.colors['border']}[{time_str}]{self.colors['reset']}"
            action_part = f"{self.colors['action']}{action_text}{self.colors['reset']}"
            
            action_line = f"{time_part} {action_part}"
            lines.append(action_line)
        
        return lines
    
    def _prepare_player_area_lines(self, players, width):
        """准备玩家区域内容行"""
        lines = []
        
        if not players:
            empty_msg = f"{self.colors['border']}等待玩家加入...{self.colors['reset']}"
            lines.append(empty_msg)
            return lines
        
        for pid, player in players.items():
            # 玩家基础信息
            name = player['name'][:10] if len(player['name']) > 10 else player['name']
            
            # 生命值颜色（根据百分比）
            hp_percent = player['hp'] / player['max_hp']
            if hp_percent > 0.7:
                hp_color = self.colors['success']
            elif hp_percent > 0.3:
                hp_color = self.colors['info']
            else:
                hp_color = self.colors['warning']
            
            # 玩家信息行
            name_line = f"{self.colors['player']}{name}{self.colors['reset']}"
            hp_line = f"  {hp_color}HP: {player['hp']}/{player['max_hp']}{self.colors['reset']}"
            hand_line = f"  手牌: {self.colors['info']}{player['hand_count']}{self.colors['reset']} | 随从: {self.colors['info']}{player['board_count']}{self.colors['reset']}"
            bag_line = f"  背包: {self.colors['info']}{player['inventory_count']}{self.colors['reset']} 件物品"
            
            lines.extend([name_line, hp_line, hand_line, bag_line, ""])  # 空行分隔
        
        return lines
    
    def _prepare_npc_area_lines(self, npc_zone, width):
        """准备NPC区域内容行"""
        lines = []
        
        difficulty = npc_zone.get('difficulty', 1)
        boss_present = npc_zone.get('boss_present', False)
        npcs = npc_zone.get('npcs', [])
        
        # 难度信息
        diff_line = f"难度等级: {self.colors['warning']}{difficulty}{self.colors['reset']}"
        lines.append(diff_line)
        
        # BOSS提示
        if boss_present:
            boss_line = f"{self.colors['warning']}*** BOSS已出现! ***{self.colors['reset']}"
            lines.append(boss_line)
        
        lines.append("")  # 空行
        
        # NPC列表
        if not npcs:
            empty_line = f"{self.colors['border']}暂无敌人{self.colors['reset']}"
            lines.append(empty_line)
        else:
            for npc in npcs:
                npc_name = npc['name'][:12] if len(npc['name']) > 12 else npc['name']
                name_line = f"{self.colors['npc']}{npc_name}{self.colors['reset']}"
                stats_line = f"  攻: {self.colors['warning']}{npc['atk']}{self.colors['reset']} | 血: {self.colors['warning']}{npc['hp']}{self.colors['reset']}"
                
                lines.extend([name_line, stats_line, ""])
        
        return lines
    
    def _prepare_resource_area_lines(self, resource_zone, width):
        """准备资源区域内容行"""
        lines = []
        
        resources = resource_zone.get('available_resources', [])
        next_refresh = resource_zone.get('next_refresh', 0)
        
        # 刷新倒计时
        refresh_line = f"刷新倒计时: {self.colors['info']}{next_refresh}{self.colors['reset']} 回合"
        lines.append(refresh_line)
        lines.append("")  # 空行
        
        # 资源列表
        if not resources:
            empty_line = f"{self.colors['border']}暂无可用资源{self.colors['reset']}"
            lines.append(empty_line)
        else:
            for i, resource in enumerate(resources, 1):
                resource_name = resource['name'][:12] if len(resource['name']) > 12 else resource['name']
                resource_type = resource['type'][:8] if len(resource['type']) > 8 else resource['type']
                
                name_line = f"{self.colors['info']}{i}.{self.colors['reset']} {self.colors['resource']}{resource_name}{self.colors['reset']}"
                type_line = f"   ({self.colors['border']}{resource_type}{self.colors['reset']})"
                
                lines.extend([name_line, type_line, ""])
        
        return lines
    
    def _show_current_player_info(self, game_state, current_player_id):
        """显示当前玩家详细信息"""
        if current_player_id not in game_state['players']:
            return
        
        player = game_state['players'][current_player_id]
        
        print()
        separator = self.colors['border'] + "-" * self.width + self.colors['reset']
        print(separator)
        
        info_parts = [
            f"当前玩家: {self.colors['player']}{player['name']}{self.colors['reset']}",
            f"生命值: {self.colors['success']}{player['hp']}/{player['max_hp']}{self.colors['reset']}",
            f"手牌: {self.colors['info']}{player['hand_count']}{self.colors['reset']}",
            f"背包: {self.colors['info']}{player['inventory_count']}{self.colors['reset']}"
        ]
        
        info_line = " | ".join(info_parts)
        # 计算纯文本长度
        plain_text = f"当前玩家: {player['name']} | 生命值: {player['hp']}/{player['max_hp']} | 手牌: {player['hand_count']} | 背包: {player['inventory_count']}"
        padding = (self.width - len(plain_text)) // 2
        print(" " * padding + info_line)
        
        print(separator)
    
    def _show_command_help(self):
        """显示操作提示"""
        print()
        border = self.colors['border'] + "=" * self.width + self.colors['reset']
        print(border)
        
        commands = [
            f"{self.colors['info']}游戏命令:{self.colors['reset']} play <编号> | attack <目标> | bag | challenge <玩家> | resource <编号> | end",
            f"{self.colors['chat']}聊天命令:{self.colors['reset']} say <消息> | whisper <玩家> <消息>",
            f"{self.colors['border']}其他命令:{self.colors['reset']} help | status | quit"
        ]
        
        for cmd in commands:
            # 计算纯文本长度用于居中
            plain_cmd = cmd.replace(self.colors['info'], '').replace(self.colors['chat'], '').replace(self.colors['border'], '').replace(self.colors['reset'], '')
            padding = (self.width - len(plain_cmd)) // 2
            print(" " * padding + cmd)
        
        print(border)
    
    def _show_separator(self, title):
        """显示分隔线"""
        border_char = "="
        title_formatted = f" {title} "
        title_len = len(title_formatted)
        border_len = (self.width - title_len) // 2
        
        separator = self.colors['border'] + border_char * border_len + title_formatted + border_char * border_len + self.colors['reset']
        if len(title_formatted) + 2 * border_len < self.width:
            separator += self.colors['border'] + border_char + self.colors['reset']
        
        print(separator)
    
    def _format_area_content(self, content, width):
        """格式化区域内容，确保宽度一致"""
        # 移除颜色代码计算纯文本长度
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        plain_content = ansi_escape.sub('', content)
        
        if len(plain_content) > width:
            # 截断过长内容，保持颜色代码
            truncated = plain_content[:width-3] + "..."
            return truncated.ljust(width)
        else:
            # 用空格填充到指定宽度
            padding = width - len(plain_content)
            return content + " " * padding
    
    def _center_colored_text(self, colored_text, width):
        """居中彩色文本"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        plain_text = ansi_escape.sub('', colored_text)
        
        if len(plain_text) >= width:
            return colored_text
        
        padding = (width - len(plain_text)) // 2
        return " " * padding + colored_text + " " * (width - len(plain_text) - padding)
    
    def _print_three_columns(self, left, center, right, area_width):
        """打印三列布局"""
        separator = f" {self.colors['border']}|{self.colors['reset']} "
        line = left + separator + center + separator + right
        print(line)
    
    def _print_two_columns(self, left, right, left_width):
        """打印两列布局"""
        separator = f" {self.colors['border']}|{self.colors['reset']} "
        line = left + separator + right
        print(line)
    
    def add_chat_message(self, player_name, message):
        """添加聊天消息"""
        chat_entry = {
            'time': datetime.now().strftime('%H:%M'),
            'player': player_name,
            'message': message
        }
        self.chat_history.append(chat_entry)
    
    def add_action_log(self, action_description):
        """添加操作记录"""
        action_entry = {
            'time': datetime.now().strftime('%H:%M'),
            'action': action_description
        }
        self.action_log.append(action_entry)
    
    def add_system_message(self, message):
        """添加系统消息到聊天区"""
        self.add_chat_message("系统", message)

# 全局显示器实例
enhanced_display = ColoredGameDisplay()

def show_enhanced_game(game_state, current_player_id=None, chat_messages=None, recent_actions=None):
    """显示增强版多人游戏界面的主函数"""
    enhanced_display.show_game(game_state, current_player_id, chat_messages, recent_actions)

def add_chat_message(player_name, message):
    """添加聊天消息的便捷函数"""
    enhanced_display.add_chat_message(player_name, message)

def add_action_log(action_description):
    """添加操作记录的便捷函数"""
    enhanced_display.add_action_log(action_description)

def add_system_message(message):
    """添加系统消息的便捷函数"""
    enhanced_display.add_system_message(message)
