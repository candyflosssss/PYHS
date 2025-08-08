"""
增强的游戏界面显示系统
支持五区域布局：主游戏区域 + 聊天区 + 操作记录区
"""

import os
import time
from datetime import datetime

class GameDisplay:
    """增强的游戏界面显示器"""
    
    def __init__(self):
        self.width = 140  # 增加界面宽度以容纳更多区域
        self.chat_history = []  # 聊天记录
        self.action_log = []    # 操作记录
        self.max_chat_lines = 8  # 最大聊天显示行数
        self.max_action_lines = 8  # 最大操作记录显示行数
    
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def show_game(self, game_state, current_player_id=None, chat_messages=None, recent_actions=None):
        """显示完整游戏界面（五区域布局）"""
        self.clear_screen()
        
        # 更新聊天和操作记录
        if chat_messages:
            self.chat_history.extend(chat_messages)
            # 保持聊天记录在合理长度
            if len(self.chat_history) > 50:
                self.chat_history = self.chat_history[-50:]
        
        if recent_actions:
            self.action_log.extend(recent_actions)
            # 保持操作记录在合理长度  
            if len(self.action_log) > 50:
                self.action_log = self.action_log[-50:]
        
        # 顶部标题
        self._show_header(game_state)
        
        # 主体区域（上半部分：三大游戏区域）
        self._show_main_areas(game_state)
        
        # 分隔线
        print("=" * self.width)
        
        # 下半部分：聊天区 + 操作记录区
        self._show_communication_areas()
        
        # 当前玩家信息
        if current_player_id:
            self._show_current_player_info(game_state, current_player_id)
        
        # 底部操作提示
        self._show_command_help()
    
    def _show_header(self, game_state):
        """显示顶部标题区域"""
        print("=" * self.width)
        title = "COMOS 多人卡牌对战"
        print(title.center(self.width))
        
        phase_info = f"阶段: {game_state['phase']} | 回合: {game_state['turn']}"
        current_info = f"当前玩家: {game_state['current_player'] or '无'}"
        time_info = f"时间: {datetime.now().strftime('%H:%M:%S')}"
        info_line = f"{phase_info} | {current_info} | {time_info}"
        print(info_line.center(self.width))
        print("=" * self.width)
    
    def _show_main_areas(self, game_state):
        """显示三大主要游戏区域"""
        # 计算每个区域的宽度
        area_width = (self.width - 8) // 3  # 减去分隔符空间
        
        print()
        # 区域标题行
        self._print_three_columns(
            "🏟️ 玩家竞技场".center(area_width),
            "👹 NPC敌人区".center(area_width), 
            "💎 公共资源区".center(area_width),
            area_width
        )
        
        print("-" * self.width)
        
        # 区域内容（多行显示）
        self._show_game_area_contents(game_state, area_width)
    
    def _show_game_area_contents(self, game_state, area_width):
        """显示游戏区域内容"""
        # 准备各区域的内容行
        player_lines = self._prepare_player_area_lines(game_state['players'], area_width)
        npc_lines = self._prepare_npc_area_lines(game_state['npc_zone'], area_width)
        resource_lines = self._prepare_resource_area_lines(game_state['resource_zone'], area_width)
        
        # 确保所有区域行数相同
        max_lines = max(len(player_lines), len(npc_lines), len(resource_lines), 6)
        player_lines.extend([''] * (max_lines - len(player_lines)))
        npc_lines.extend([''] * (max_lines - len(npc_lines)))
        resource_lines.extend([''] * (max_lines - len(resource_lines)))
        
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
        self._print_two_columns(
            "💬 聊天区".center(chat_width),
            "📜 操作记录".center(action_width),
            chat_width
        )
        
        print("-" * self.width)
        
        # 准备聊天和操作记录内容
        chat_lines = self._prepare_chat_lines(chat_width)
        action_lines = self._prepare_action_lines(action_width)
        
        # 确保两个区域行数相同
        max_lines = max(len(chat_lines), len(action_lines), self.max_chat_lines)
        chat_lines.extend([''] * (max_lines - len(chat_lines)))
        action_lines.extend([''] * (max_lines - len(action_lines)))
        
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
        
        # 显示最近的聊天消息
        recent_chats = self.chat_history[-self.max_chat_lines:]
        
        if not recent_chats:
            lines.append("暂无聊天消息")
            return lines
        
        for chat in recent_chats:
            # 格式化聊天消息：[时间] 玩家名: 消息
            time_str = chat.get('time', '00:00')
            player_name = chat.get('player', '系统')[:8]  # 限制名字长度
            message = chat.get('message', '')
            
            # 处理长消息换行
            if len(message) > width - 15:  # 为时间和玩家名留空间
                message = message[:width-18] + "..."
            
            chat_line = f"[{time_str}] {player_name}: {message}"
            lines.append(chat_line)
        
        return lines
    
    def _prepare_action_lines(self, width):
        """准备操作记录内容行"""
        lines = []
        
        # 显示最近的操作记录
        recent_actions = self.action_log[-self.max_action_lines:]
        
        if not recent_actions:
            lines.append("暂无操作记录")
            return lines
        
        for action in recent_actions:
            # 格式化操作记录：[时间] 动作描述
            time_str = action.get('time', '00:00')
            action_text = action.get('action', '')
            
            # 处理长操作记录
            if len(action_text) > width - 10:  # 为时间留空间
                action_text = action_text[:width-13] + "..."
            
            action_line = f"[{time_str}] {action_text}"
            lines.append(action_line)
        
        return lines
    
    def _prepare_player_area_lines(self, players, width):
        """准备玩家区域内容行"""
        lines = []
        
        if not players:
            lines.append("等待玩家加入...")
            return lines
        
        for pid, player in players.items():
            # 玩家基础信息
            hp_info = f"HP:{player['hp']}/{player['max_hp']}"
            hand_info = f"手牌:{player['hand_count']}"
            board_info = f"随从:{player['board_count']}"
            bag_info = f"背包:{player['inventory_count']}"
            
            name = player['name'][:8]  # 限制名字长度
            player_line = f"{name} {hp_info}"
            lines.append(player_line)
            lines.append(f"  {hand_info} {board_info}")
            lines.append(f"  {bag_info}")
            lines.append("")  # 空行分隔
        
        return lines
    
    def _prepare_npc_area_lines(self, npc_zone, width):
        """准备NPC区域内容行"""
        lines = []
        
        npcs = npc_zone.get('npcs', [])
        difficulty = npc_zone.get('difficulty', 1)
        boss_present = npc_zone.get('boss_present', False)
        
        lines.append(f"难度等级: {difficulty}")
        
        if boss_present:
            lines.append("*** BOSS已出现! ***")
        
        lines.append("")
        
        for npc in npcs:
            npc_name = npc['name'][:12]
            npc_line = f"{npc_name}"
            lines.append(npc_line)
            lines.append(f"  攻:{npc['atk']} 血:{npc['hp']}")
            lines.append("")
        
        if not npcs:
            lines.append("暂无敌人")
        
        return lines
    
    def _prepare_resource_area_lines(self, resource_zone, width):
        """准备资源区域内容行"""
        lines = []
        
        resources = resource_zone.get('available_resources', [])
        next_refresh = resource_zone.get('next_refresh', 0)
        
        lines.append(f"刷新倒计时: {next_refresh}")
        lines.append("")
        
        for i, resource in enumerate(resources, 1):
            resource_name = resource['name'][:10]
            resource_line = f"{i}. {resource_name}"
            lines.append(resource_line)
            lines.append(f"   ({resource['type'][:8]})")
            lines.append("")
        
        if not resources:
            lines.append("暂无可用资源")
        
        return lines
    
    def _show_current_player_info(self, game_state, current_player_id):
        """显示当前玩家详细信息"""
        if current_player_id not in game_state['players']:
            return
        
        player = game_state['players'][current_player_id]
        
        print()
        print("-" * self.width)
        info = f"当前玩家: {player['name']} | "
        info += f"生命值: {player['hp']}/{player['max_hp']} | "
        info += f"手牌: {player['hand_count']} | "
        info += f"背包: {player['inventory_count']}"
        
        print(info.center(self.width))
        print("-" * self.width)
    
    def _show_command_help(self):
        """显示操作提示"""
        print()
        print("=" * self.width)
        
        commands = [
            "游戏命令: play <编号> | attack <目标> | bag | challenge <玩家> | resource <编号> | end",
            "聊天命令: say <消息> | whisper <玩家> <消息>",
            "其他命令: help | status | quit"
        ]
        
        for cmd in commands:
            print(cmd.center(self.width))
        
        print("=" * self.width)
    
    def _format_area_content(self, content, width):
        """格式化区域内容"""
        if len(content) > width:
            content = content[:width-3] + "..."
        return content.ljust(width)
    
    def _print_three_columns(self, left, center, right, area_width):
        """打印三列布局"""
        separator = " | "
        line = left + separator + center + separator + right
        print(line)
    
    def _print_two_columns(self, left, right, left_width):
        """打印两列布局"""
        separator = " | "
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

# 显示器实例
display = GameDisplay()

def show_multiplayer_game(game_state, current_player_id=None, chat_messages=None, recent_actions=None):
    """显示多人游戏界面的主函数"""
    display.show_game(game_state, current_player_id, chat_messages, recent_actions)

def add_chat_message(player_name, message):
    """添加聊天消息的便捷函数"""
    display.add_chat_message(player_name, message)

def add_action_log(action_description):
    """添加操作记录的便捷函数"""
    display.add_action_log(action_description)

def add_system_message(message):
    """添加系统消息的便捷函数"""
    display.add_system_message(message)
