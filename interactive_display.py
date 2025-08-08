"""
支持鼠标滚轮滚动的增强游戏界面
使用rich库实现交互式聊天记录浏览
"""

import os
import time
from datetime import datetime
from collections import deque
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich import box
import threading
import queue

class InteractiveGameDisplay:
    """支持鼠标滚轮的交互式游戏界面"""
    
    def __init__(self):
        self.console = Console()
        self.chat_history = deque(maxlen=200)  # 增加聊天记录容量
        self.action_log = deque(maxlen=200)    # 增加操作记录容量
        
        # 滚动控制
        self.chat_scroll_position = 0    # 聊天区滚动位置
        self.action_scroll_position = 0  # 操作记录区滚动位置
        self.chat_display_lines = 10     # 聊天区显示行数
        self.action_display_lines = 10   # 操作记录区显示行数
        
        # 界面更新控制
        self.update_queue = queue.Queue()
        self.is_running = False
        
        # 样式配置
        self.styles = {
            'player': 'bold green',
            'npc': 'bold red',
            'resource': 'bold magenta',
            'chat': 'white',
            'action': 'cyan',
            'system': 'yellow',
            'private': 'bright_cyan',
            'border': 'dim white',
            'warning': 'bold red',
            'success': 'bold green',
            'info': 'blue',
            'title': 'bold yellow'
        }
    
    def show_game_interactive(self, game_state, current_player_id=None):
        """显示支持鼠标滚轮的交互式游戏界面"""
        
        # 创建布局
        layout = Layout()
        
        # 分割主要区域
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=2),
            Layout(name="communication", ratio=1),
            Layout(name="player_info", size=3),
            Layout(name="commands", size=4)
        )
        
        # 分割主游戏区域
        layout["main"].split_row(
            Layout(name="players"),
            Layout(name="npcs"), 
            Layout(name="resources")
        )
        
        # 分割聊天和操作记录区域
        layout["communication"].split_row(
            Layout(name="chat"),
            Layout(name="actions")
        )
        
        # 更新各个区域内容
        self._update_layout_content(layout, game_state, current_player_id)
        
        return layout
    
    def _update_layout_content(self, layout, game_state, current_player_id):
        """更新布局内容"""
        
        # 标题区域
        title_text = Text("COMOS 多人卡牌对战", style=self.styles['title'])
        info_text = Text(f"阶段: {game_state['phase']} | 回合: {game_state['turn']} | 当前玩家: {game_state['current_player'] or '无'} | 时间: {datetime.now().strftime('%H:%M:%S')}", style=self.styles['info'])
        
        # 组合标题内容
        header_content = Text()
        header_content.append_text(title_text)
        header_content.append("\n")
        header_content.append_text(info_text)
        
        header_panel = Panel(
            Align.center(header_content),
            box=box.DOUBLE,
            style=self.styles['border']
        )
        layout["header"].update(header_panel)
        
        # 玩家竞技场
        players_content = self._create_players_panel(game_state['players'])
        layout["players"].update(players_content)
        
        # NPC敌人区
        npcs_content = self._create_npcs_panel(game_state['npc_zone'])
        layout["npcs"].update(npcs_content)
        
        # 公共资源区
        resources_content = self._create_resources_panel(game_state['resource_zone'])
        layout["resources"].update(resources_content)
        
        # 聊天区（支持滚动）
        chat_content = self._create_scrollable_chat_panel()
        layout["chat"].update(chat_content)
        
        # 操作记录区（支持滚动）
        actions_content = self._create_scrollable_actions_panel()
        layout["actions"].update(actions_content)
        
        # 当前玩家信息
        if current_player_id and current_player_id in game_state['players']:
            player_info = self._create_player_info_panel(game_state['players'][current_player_id])
            layout["player_info"].update(player_info)
        
        # 命令帮助
        commands_content = self._create_commands_panel()
        layout["commands"].update(commands_content)
    
    def _create_players_panel(self, players):
        """创建玩家区域面板"""
        table = Table(title="🏟️ 玩家竞技场", box=box.ROUNDED, style=self.styles['player'])
        table.add_column("玩家", style=self.styles['player'])
        table.add_column("生命值", style=self.styles['success'])
        table.add_column("手牌/随从", style=self.styles['info'])
        table.add_column("背包", style=self.styles['info'])
        
        if not players:
            table.add_row("等待玩家加入...", "", "", "")
        else:
            for pid, player in players.items():
                name = player['name'][:10]
                hp_percent = player['hp'] / player['max_hp']
                hp_style = self.styles['success'] if hp_percent > 0.7 else (self.styles['info'] if hp_percent > 0.3 else self.styles['warning'])
                hp_text = Text(f"{player['hp']}/{player['max_hp']}", style=hp_style)
                
                table.add_row(
                    name,
                    str(hp_text),
                    f"{player['hand_count']}/{player['board_count']}",
                    str(player['inventory_count'])
                )
        
        return Panel(table, style=self.styles['player'])
    
    def _create_npcs_panel(self, npc_zone):
        """创建NPC区域面板"""
        table = Table(title="👹 NPC敌人区", box=box.ROUNDED, style=self.styles['npc'])
        table.add_column("敌人", style=self.styles['npc'])
        table.add_column("攻击/血量", style=self.styles['warning'])
        
        # 添加难度信息
        difficulty_text = Text(f"难度等级: {npc_zone.get('difficulty', 1)}", style=self.styles['warning'])
        
        if npc_zone.get('boss_present', False):
            boss_text = Text("*** BOSS已出现! ***", style=self.styles['warning'])
            table.add_row(str(boss_text), "")
        
        npcs = npc_zone.get('npcs', [])
        if not npcs:
            table.add_row("暂无敌人", "")
        else:
            for npc in npcs:
                name = npc['name'][:12]
                stats = f"{npc['atk']}/{npc['hp']}"
                table.add_row(name, stats)
        
        return Panel(table, style=self.styles['npc'])
    
    def _create_resources_panel(self, resource_zone):
        """创建资源区域面板"""
        table = Table(title="💎 公共资源区", box=box.ROUNDED, style=self.styles['resource'])
        table.add_column("编号", style=self.styles['info'])
        table.add_column("资源", style=self.styles['resource'])
        table.add_column("类型", style=self.styles['border'])
        
        refresh_time = resource_zone.get('next_refresh', 0)
        refresh_text = Text(f"刷新倒计时: {refresh_time} 回合", style=self.styles['info'])
        
        resources = resource_zone.get('available_resources', [])
        if not resources:
            table.add_row("", "暂无可用资源", "")
        else:
            for i, resource in enumerate(resources, 1):
                name = resource['name'][:12]
                resource_type = resource['type'][:8]
                table.add_row(str(i), name, resource_type)
        
        return Panel(table, style=self.styles['resource'])
    
    def _create_scrollable_chat_panel(self):
        """创建可滚动的聊天面板"""
        if not self.chat_history:
            content = Text("暂无聊天消息\n\n使用鼠标滚轮浏览历史记录", style=self.styles['border'])
            return Panel(content, title="💬 聊天区", style=self.styles['chat'])
        
        # 计算显示范围
        total_messages = len(self.chat_history)
        start_idx = max(0, total_messages - self.chat_display_lines - self.chat_scroll_position)
        end_idx = total_messages - self.chat_scroll_position
        
        # 显示消息
        content = Text()
        visible_messages = list(self.chat_history)[start_idx:end_idx]
        
        for chat in visible_messages:
            time_str = chat.get('time', '00:00')
            player_name = chat.get('player', '系统')
            message = chat.get('message', '')
            
            # 选择颜色
            if player_name == '系统':
                style = self.styles['system']
            elif '[私聊' in message:
                style = self.styles['private']
            else:
                style = self.styles['chat']
            
            # 限制名字长度
            if len(player_name) > 8:
                player_name = player_name[:8] + "."
            
            # 限制消息长度
            if len(message) > 50:
                message = message[:47] + "..."
            
            line = f"[{time_str}] {player_name}: {message}\n"
            content.append(line, style=style)
        
        # 添加滚动指示器
        if self.chat_scroll_position > 0:
            scroll_info = f"\n↑ 向上滚动 ({self.chat_scroll_position} 条历史记录)"
            content.append(scroll_info, style=self.styles['border'])
        
        if end_idx < total_messages:
            scroll_info = f"\n↓ 向下滚动查看更多"
            content.append(scroll_info, style=self.styles['border'])
        
        title = f"💬 聊天区 ({total_messages} 条消息)"
        return Panel(content, title=title, style=self.styles['chat'])
    
    def _create_scrollable_actions_panel(self):
        """创建可滚动的操作记录面板"""
        if not self.action_log:
            content = Text("暂无操作记录\n\n使用鼠标滚轮浏览历史记录", style=self.styles['border'])
            return Panel(content, title="📜 操作记录", style=self.styles['action'])
        
        # 计算显示范围
        total_actions = len(self.action_log)
        start_idx = max(0, total_actions - self.action_display_lines - self.action_scroll_position)
        end_idx = total_actions - self.action_scroll_position
        
        # 显示操作记录
        content = Text()
        visible_actions = list(self.action_log)[start_idx:end_idx]
        
        for action in visible_actions:
            time_str = action.get('time', '00:00')
            action_text = action.get('action', '')
            
            # 限制操作记录长度
            if len(action_text) > 55:
                action_text = action_text[:52] + "..."
            
            line = f"[{time_str}] {action_text}\n"
            content.append(line, style=self.styles['action'])
        
        # 添加滚动指示器
        if self.action_scroll_position > 0:
            scroll_info = f"\n↑ 向上滚动 ({self.action_scroll_position} 条历史记录)"
            content.append(scroll_info, style=self.styles['border'])
        
        if end_idx < total_actions:
            scroll_info = f"\n↓ 向下滚动查看更多"
            content.append(scroll_info, style=self.styles['border'])
        
        title = f"📜 操作记录 ({total_actions} 条记录)"
        return Panel(content, title=title, style=self.styles['action'])
    
    def _create_player_info_panel(self, player):
        """创建当前玩家信息面板"""
        info_text = f"当前玩家: {player['name']} | 生命值: {player['hp']}/{player['max_hp']} | 手牌: {player['hand_count']} | 背包: {player['inventory_count']}"
        content = Text(info_text, style=self.styles['info'])
        return Panel(Align.center(content), style=self.styles['border'])
    
    def _create_commands_panel(self):
        """创建命令帮助面板"""
        commands = [
            Text("游戏命令: ", style=self.styles['info']) + Text("play <编号> | attack <目标> | bag | challenge <玩家> | resource <编号> | end"),
            Text("聊天命令: ", style=self.styles['chat']) + Text("say <消息> | whisper <玩家> <消息>"),
            Text("滚动命令: ", style=self.styles['border']) + Text("up/down <区域> <行数> - 滚动聊天(chat)或操作记录(action)"),
            Text("其他命令: ", style=self.styles['border']) + Text("help | status | quit")
        ]
        
        content = Text()
        for cmd in commands:
            content.append(str(cmd) + "\n")
        
        return Panel(content, title="操作帮助", style=self.styles['border'])
    
    def scroll_chat(self, direction, lines=1):
        """滚动聊天记录"""
        if direction == "up":
            self.chat_scroll_position = min(
                self.chat_scroll_position + lines,
                max(0, len(self.chat_history) - self.chat_display_lines)
            )
        elif direction == "down":
            self.chat_scroll_position = max(0, self.chat_scroll_position - lines)
    
    def scroll_actions(self, direction, lines=1):
        """滚动操作记录"""
        if direction == "up":
            self.action_scroll_position = min(
                self.action_scroll_position + lines,
                max(0, len(self.action_log) - self.action_display_lines)
            )
        elif direction == "down":
            self.action_scroll_position = max(0, self.action_scroll_position - lines)
    
    def add_chat_message(self, player_name, message):
        """添加聊天消息"""
        chat_entry = {
            'time': datetime.now().strftime('%H:%M'),
            'player': player_name,
            'message': message
        }
        self.chat_history.append(chat_entry)
        # 自动滚动到最新消息（除非用户正在浏览历史记录）
        if self.chat_scroll_position == 0:
            pass  # 已经在最新位置
    
    def add_action_log(self, action_description):
        """添加操作记录"""
        action_entry = {
            'time': datetime.now().strftime('%H:%M'),
            'action': action_description
        }
        self.action_log.append(action_entry)
        # 自动滚动到最新记录（除非用户正在浏览历史记录）
        if self.action_scroll_position == 0:
            pass  # 已经在最新位置
    
    def add_system_message(self, message):
        """添加系统消息到聊天区"""
        self.add_chat_message("系统", message)
    
    def reset_scroll_positions(self):
        """重置滚动位置到最新消息"""
        self.chat_scroll_position = 0
        self.action_scroll_position = 0

# 全局交互式显示器实例
interactive_display = InteractiveGameDisplay()

def show_interactive_game(game_state, current_player_id=None):
    """显示支持鼠标滚轮的交互式游戏界面"""
    return interactive_display.show_game_interactive(game_state, current_player_id)

def scroll_chat_up(lines=1):
    """向上滚动聊天记录"""
    interactive_display.scroll_chat("up", lines)

def scroll_chat_down(lines=1):
    """向下滚动聊天记录"""
    interactive_display.scroll_chat("down", lines)

def scroll_actions_up(lines=1):
    """向上滚动操作记录"""
    interactive_display.scroll_actions("up", lines)

def scroll_actions_down(lines=1):
    """向下滚动操作记录"""
    interactive_display.scroll_actions("down", lines)

def add_chat_message(player_name, message):
    """添加聊天消息的便捷函数"""
    interactive_display.add_chat_message(player_name, message)

def add_action_log(action_description):
    """添加操作记录的便捷函数"""
    interactive_display.add_action_log(action_description)

def add_system_message(message):
    """添加系统消息的便捷函数"""
    interactive_display.add_system_message(message)

def reset_scroll():
    """重置滚动位置的便捷函数"""
    interactive_display.reset_scroll_positions()
