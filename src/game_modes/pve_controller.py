"""
重构后的PvE控制器 - 内部使用MVC架构
- 保持与Tkinter UI的兼容性
- 内部使用MVC组件进行逻辑分离
- 删除CLI相关代码，专注于核心游戏逻辑
"""

from typing import Callable, List, Tuple, Optional, Any
from .mvc import GameModel, GameView, GameController
from src.ui import colors as C


class SimplePvEController:
    """
    重构后的PvE控制器
    
    内部使用MVC架构：
    - Model: 游戏状态管理
    - View: 视图渲染逻辑  
    - Controller: 命令处理逻辑
    
    对外保持原有接口，确保Tkinter UI兼容性
    """
    
    def __init__(self, player_name: str | None = None, initial_scene: str | None = None):
        # 获取玩家名称（Tkinter UI会传入，不需要input）
        name = (player_name or '').strip() or "玩家"
        
        # 初始化MVC组件
        self.model = GameModel(name)
        self.view = GameView()
        self.controller = GameController(self.model, self.view)
        
        # 指定初始场景（若提供）
        if initial_scene:
            try:
                self.model.load_scene(initial_scene, keep_board=False)
            except Exception:
                pass
        
        # 开始游戏
        self.model.start_turn()
        
        # 兼容性属性（Tkinter UI需要）
        self.game = self.model  # 保持game属性兼容性
        self.history = self.view.history  # 操作历史
        self.info = self.view.info  # 信息区
        
        # 区块渲染映射（保持原有接口）
        self.sections = {
            '0': self._section_player,
            '1': self._section_enemy,
            '2': self._section_resources,
            '3': self._section_history,
            '4': self._section_inventory,
            '5': self._section_info,
        }
        
        # 常用消息
        self.MSG_INVALID_SECTION = "无效区域编号 (0-5)"
        self.MSG_HELP_TITLE = "=== 简单 PvE 指令帮助 ==="
        self.MSG_HELP = (
            "s 5 : 查看信息摘要  |  s 3 : 查看最近战斗日志\n"
            "a <mN> e<N> : 用我方单位攻击指定敌人\n"
            "skill <name> <mN> [targets...] : 释放技能（体力消耗见 UI 提示）\n"
            "end : 结束回合  |  h : 帮助  |  q : 退出"
        )
        
        # 缓存技能名（用于通用分段上色）
        self._skill_names: set[str] = set()
        try:
            self._load_skill_names()
        except Exception:
            pass
    
    # --- 兼容性方法（保持原有接口） ---
    
    def _section_player(self) -> str:
        """玩家队伍区域 - 兼容性方法"""
        return self.view.render_section('player', self.model)
    
    def _section_enemy(self) -> str:
        """敌人区域 - 兼容性方法"""
        return self.view.render_section('enemy', self.model)
    
    def _section_resources(self) -> str:
        """资源区域 - 兼容性方法"""
        return self.view.render_section('resources', self.model)
    
    def _section_history(self) -> str:
        """历史区域 - 兼容性方法"""
        return self.view.render_section('history', self.model)
    
    def _section_inventory(self) -> str:
        """背包区域 - 兼容性方法"""
        return self.view.render_section('inventory', self.model)
    
    def _section_info(self) -> str:
        """信息区域 - 兼容性方法"""
        return self.view.render_section('info', self.model)
    
    def _process_command(self, command: str) -> Tuple[List[str], dict]:
        """
        处理命令 - Tkinter UI需要的方法
        
        Args:
            command: 命令字符串
            
        Returns:
            Tuple[List[str], dict]: (消息列表, 数据字典)
        """
        try:
            # 直接调用MVC Controller处理命令
            messages, should_exit = self.controller.process_command(command)
            
            # 如果命令执行成功，添加到历史记录
            if not should_exit and messages:
                for msg in messages:
                    self.view.add_history(msg)
            
            # 返回Tkinter UI期望的格式
            return messages, {}
            
        except Exception as e:
            error_msg = f"命令处理错误: {e}"
            self.view.add_info(error_msg)
            return [error_msg], {}
    
    # --- 核心游戏逻辑（委托给MVC组件） ---
    
    def start_turn(self):
        """开始新回合"""
        self.model.start_turn()
    
    def end_turn(self):
        """结束当前回合"""
        self.model.end_turn()
    
    def is_game_over(self) -> bool:
        """检查游戏是否结束"""
        return self.model.is_game_over()
    
    def get_state(self) -> dict:
        """获取游戏状态"""
        return self.model.get_state()
    
    def get_player_info(self) -> dict:
        """获取玩家信息"""
        return self.model.get_player_info()
    
    def get_enemies_info(self) -> list:
        """获取敌人信息"""
        return self.model.get_enemies_info()
    
    def get_resources_info(self) -> list:
        """获取资源信息"""
        return self.model.get_resources_info()
    
    # --- 命令处理（委托给Controller） ---
    
    def process_command(self, command_line: str) -> Tuple[List[str], bool]:
        """处理命令 - 委托给MVC Controller"""
        return self.controller.process_command(command_line)
    
    def execute_attack(self, attacker_idx: int, target_idx: int) -> str:
        """执行攻击 - 委托给MVC Controller"""
        try:
            # 构建攻击命令
            cmd = f"a m{attacker_idx + 1} e{target_idx + 1}"
            output_lines, _ = self.controller.process_command(cmd)
            return output_lines[0] if output_lines else "攻击失败"
        except Exception as e:
            return f"攻击执行错误: {e}"
    
    def execute_skill(self, skill_name: str, source_idx: int, target_idx: Optional[int] = None) -> str:
        """执行技能 - 委托给MVC Controller"""
        try:
            # 构建技能命令
            cmd = f"skill {skill_name} m{source_idx + 1}"
            if target_idx is not None:
                cmd += f" m{target_idx + 1}"
            
            output_lines, _ = self.controller.process_command(cmd)
            return output_lines[0] if output_lines else "技能执行失败"
        except Exception as e:
            return f"技能执行错误: {e}"
    
    def use_item(self, item_name: str, target_idx: Optional[int] = None) -> str:
        """使用物品 - 委托给MVC Controller"""
        try:
            # 构建使用物品命令
            cmd = f"use {item_name}"
            if target_idx is not None:
                cmd += f" m{target_idx + 1}"
            
            output_lines, _ = self.controller.process_command(cmd)
            return output_lines[0] if output_lines else "物品使用失败"
        except Exception as e:
            return f"物品使用错误: {e}"
    
    def take_resource(self, resource_idx: int) -> str:
        """拾取资源 - 委托给MVC Controller"""
        try:
            cmd = f"take r{resource_idx + 1}"
            output_lines, _ = self.controller.process_command(cmd)
            return output_lines[0] if output_lines else "资源拾取失败"
        except Exception as e:
            return f"资源拾取错误: {e}"
    
    def equip_item(self, item_name: str, target_idx: int) -> str:
        """装备物品 - 委托给MVC Controller"""
        try:
            cmd = f"equip {item_name} m{target_idx + 1}"
            output_lines, _ = self.controller.process_command(cmd)
            return output_lines[0] if output_lines else "装备失败"
        except Exception as e:
            return f"装备错误: {e}"
    
    def unequip_item(self, target_idx: int, slot: str) -> str:
        """卸下装备 - 委托给MVC Controller"""
        try:
            cmd = f"unequip m{target_idx + 1} {slot}"
            output_lines, _ = self.controller.process_command(cmd)
            return output_lines[0] if output_lines else "卸下装备失败"
        except Exception as e:
            return f"卸下装备错误: {e}"
    
    def craft_item(self, recipe_name: str) -> str:
        """合成物品 - 委托给MVC Controller"""
        try:
            cmd = f"craft {recipe_name}"
            output_lines, _ = self.controller.process_command(cmd)
            return output_lines[0] if output_lines else "合成失败"
        except Exception as e:
            return f"合成错误: {e}"
    
    # --- 日志和UI辅助方法 ---
    
    def add_history(self, message: str):
        """添加历史记录"""
        self.view.add_history(message)
    
    def add_info(self, message: str):
        """添加信息"""
        self.view.add_info(message)
    
    def get_full_view(self) -> str:
        """获取完整游戏视图"""
        return self.view.render_full_view(self.model)
    
    def refresh_view(self):
        """刷新视图"""
        # 视图会自动更新，这里只是占位符
        pass
    
    # --- 技能名称缓存（保持原有功能） ---
    
    def _load_skill_names(self):
        """加载技能名称缓存"""
        import json as _json, os as _os
        try:
            base = _os.path.dirname(_os.path.dirname(__file__))  # src/
            path = _os.path.join(base, 'systems', 'skills_catalog.json')
            with open(path, 'r', encoding='utf-8') as f:
                data = _json.load(f)
            names = set()
            for it in data:
                if isinstance(it, dict):
                    ncn = it.get('name_cn'); nen = it.get('name_en'); nid = it.get('id')
                    if ncn: names.add(str(ncn))
                    if nen: names.add(str(nen))
                    if nid: names.add(str(nid))
            self._skill_names = set(names)
        except Exception:
            self._skill_names = set()
    
    def _colorize_numbers(self, s: str, for_heal: bool = False) -> str:
        """数字着色 - 保持原有功能"""
        import re as _re
        # 优先给 AC 数值上防御色
        s2 = _re.sub(r"AC\s*(\d+)", lambda m: "AC " + C.stat_def(m.group(1)), s)
        # 其他数字统一高亮；治疗场景用 success 绿
        if for_heal:
            return _re.sub(r"(\d+)", lambda m: C.success(m.group(1)), s2)
        return _re.sub(r"(\d+)", lambda m: C.stat_atk(m.group(1)), s2)
    
    def _colorize_known_skills(self, s: str) -> str:
        """技能名称着色 - 保持原有功能"""
        if not self._skill_names:
            return s
        # 按长度降序替换，避免短名抢先覆盖长名
        for name in sorted(self._skill_names, key=len, reverse=True):
            if name and name in s:
                try:
                    s = s.replace(name, C.skill(name))
                except Exception:
                    pass
        return s
    
    def _expand_log_entry(self, entry) -> list[str]:
        """展开日志条目 - 保持原有功能"""
        try:
            lines: list[str] = []
            if isinstance(entry, dict):
                typ = (entry.get('type') or '').lower()
                txt = str(entry.get('text', entry))
                # 通用：着色已在 _fmt_log_line 完成；补上已知技能名和数字上色
                txt = self._colorize_known_skills(txt)
                healish = ('恢复' in txt or '治疗' in txt or typ == 'heal')
                txt = self._colorize_numbers(txt, for_heal=healish)
                lines.append("  · " + txt)
            else:
                lines.append("  · " + str(entry))
            return lines
        except Exception:
            return ["  · <日志解析错误>"]
    
    # --- 兼容性属性访问器 ---
    
    @property
    def player(self):
        """玩家对象 - 兼容性访问器"""
        return self.model.player
    
    @property
    def enemies(self):
        """敌人列表 - 兼容性访问器"""
        return self.model.enemies
    
    @property
    def resources(self):
        """资源列表 - 兼容性访问器"""
        return self.model.resources
    
    @property
    def turn(self):
        """当前回合 - 兼容性访问器"""
        return self.model.turn
    
    @property
    def running(self):
        """游戏运行状态 - 兼容性访问器"""
        return self.model.running
