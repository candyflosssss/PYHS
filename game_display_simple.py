"""
简化的游戏界面显示系统
支持多人游戏的三区域布局（无颜色依赖）
"""

import os

class GameDisplay:
    """游戏界面显示器"""
    
    def __init__(self):
        self.width = 100  # 界面宽度
    
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def show_game(self, game_state, current_player_id=None):
        """显示完整游戏界面"""
        self.clear_screen()
        
        # 顶部标题
        self._show_header(game_state)
        
        # 主要内容区域（三分布局）
        self._show_main_areas(game_state)
        
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
        info_line = f"{phase_info} | {current_info}"
        print(info_line.center(self.width))
        print("=" * self.width)
    
    def _show_main_areas(self, game_state):
        """显示三大主要区域"""
        # 计算每个区域的宽度
        area_width = (self.width - 6) // 3  # 减去分隔符空间
        
        print()
        # 区域标题行
        self._print_three_columns(
            "🏟️ 玩家竞技场".center(area_width),
            "👹 NPC敌人区".center(area_width), 
            "💎 公共资源区".center(area_width)
        )
        
        print("-" * self.width)
        
        # 区域内容（多行显示）
        self._show_area_contents(game_state, area_width)
    
    def _show_area_contents(self, game_state, area_width):
        """显示各区域内容"""
        # 准备各区域的内容行
        player_lines = self._prepare_player_area_lines(game_state['players'], area_width)
        npc_lines = self._prepare_npc_area_lines(game_state['npc_zone'], area_width)
        resource_lines = self._prepare_resource_area_lines(game_state['resource_zone'], area_width)
        
        # 确保所有区域行数相同
        max_lines = max(len(player_lines), len(npc_lines), len(resource_lines), 5)
        player_lines.extend([''] * (max_lines - len(player_lines)))
        npc_lines.extend([''] * (max_lines - len(npc_lines)))
        resource_lines.extend([''] * (max_lines - len(resource_lines)))
        
        # 逐行显示
        for i in range(max_lines):
            self._print_three_columns(
                self._format_area_content(player_lines[i], area_width),
                self._format_area_content(npc_lines[i], area_width),
                self._format_area_content(resource_lines[i], area_width)
            )
    
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
            npc_name = npc['name'][:15]
            npc_line = f"{npc_name}"
            lines.append(npc_line)
            lines.append(f"  攻击:{npc['atk']} 血量:{npc['hp']}")
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
            resource_name = resource['name'][:12]
            resource_line = f"{i}. {resource_name}"
            lines.append(resource_line)
            lines.append(f"   ({resource['type']})")
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
            "可用命令:",
            "play <卡牌编号> - 出牌 | attack <目标> - 攻击 | bag - 背包",
            "challenge <玩家名> - 挑战玩家 | resource <编号> - 领取资源 | end - 结束回合"
        ]
        
        for cmd in commands:
            print(cmd.center(self.width))
        
        print("=" * self.width)
    
    def _format_area_content(self, content, width):
        """格式化区域内容"""
        if len(content) > width:
            content = content[:width-3] + "..."
        return content.ljust(width)
    
    def _print_three_columns(self, left, center, right):
        """打印三列布局"""
        separator = " | "
        line = left + separator + center + separator + right
        print(line)

# 显示器实例
display = GameDisplay()

def show_multiplayer_game(game_state, current_player_id=None):
    """显示多人游戏界面的主函数"""
    display.show_game(game_state, current_player_id)
