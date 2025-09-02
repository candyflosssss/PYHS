"""
命令处理控制器 - MVC模式中的Controller层
负责处理玩家输入的命令和游戏逻辑
"""

from typing import List, Tuple, Any, Optional
from .model import GameModel
from .view import GameView
from src.systems.skill_strategy import get_skill, list_available_skills


class GameController:
    """游戏命令控制器"""
    
    def __init__(self, model: GameModel, view: GameView):
        self.model = model
        self.view = view
        
        # 命令映射
        self.commands = {
            'q': self._cmd_quit,
            'h': self._cmd_help,
            's': self._cmd_show,
            'end': self._cmd_end_turn,
            'a': self._cmd_attack,
            'p': self._cmd_play_card,
            'use': self._cmd_use_item,
            'take': self._cmd_take_resource,
            'equip': self._cmd_equip,
            'unequip': self._cmd_unequip,
            'craft': self._cmd_craft,
            'c': self._cmd_craft,
            'back': self._cmd_back,
            'b': self._cmd_back,
            'i': self._cmd_inventory,
            'inv': self._cmd_inventory,
        }
        
        # 帮助信息
        self.help_text = (
            "=== 简单 PvE 指令帮助 ===\n"
            "s 5 : 查看信息摘要  |  s 3 : 查看最近战斗日志\n"
            "a <mN> e<N> : 用我方单位攻击指定敌人\n"
            "skill <name> <mN> [targets...] : 释放技能（体力消耗见 UI 提示）\n"
            "end : 结束回合  |  h : 帮助  |  q : 退出"
        )
    
    def process_command(self, command_line: str) -> Tuple[List[str], bool]:
        """
        处理命令
        
        Args:
            command_line: 命令字符串
            
        Returns:
            (输出行列表, 是否退出游戏)
        """
        parts = command_line.strip().split()
        if not parts:
            return [], False
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        # 检查是否是已知命令
        if cmd in self.commands:
            try:
                return self.commands[cmd](args)
            except Exception as e:
                return [f"命令执行错误: {e}"], False
        
        # 检查是否是快捷合成命令
        if cmd.startswith('c') and len(cmd) > 1 and cmd[1:].isdigit():
            return self._cmd_craft_by_index(int(cmd[1:]))
        
        # 检查是否是技能命令
        if cmd in ['skill', 'sk', 'sweep', 'basic_heal', 'drain', 'taunt', 'arcane_missiles']:
            return self._cmd_skill(cmd, args)
        
        return ['未知指令，h 查看帮助'], False
    
    def _cmd_quit(self, args: List[str]) -> Tuple[List[str], bool]:
        """退出游戏命令"""
        return ['退出游戏'], True
    
    def _cmd_help(self, args: List[str]) -> Tuple[List[str], bool]:
        """帮助命令"""
        print(self.help_text)
        return [], False
    
    def _cmd_show(self, args: List[str]) -> Tuple[List[str], bool]:
        """显示命令"""
        if not args:
            # 显示完整视图
            return [self.view.render_full_view(self.model)], False
        
        # 显示指定区域
        section = args[0]
        content = self.view.render_section(section, self.model)
        return [content], False
    
    def _cmd_end_turn(self, args: List[str]) -> Tuple[List[str], bool]:
        """结束回合命令"""
        self.model.start_turn()
        msg = f"进入回合 {self.model.turn}"
        self.view.add_history(msg)
        return [msg], False
    
    def _cmd_attack(self, args: List[str]) -> Tuple[List[str], bool]:
        """攻击命令"""
        if len(args) < 2:
            return ['用法: a <队伍序号|mN> e<敌人序号>'], False
        
        try:
            # 解析队伍序号
            first = args[0].lower()
            if first.startswith('m'):
                m_idx = int(first[1:]) - 1
            else:
                m_idx = int(first) - 1
            
            # 解析敌人序号
            tgt = args[1]
            if not tgt.startswith('e'):
                return ['目标格式: eN (如 e1)'], False
            
            e_idx = int(tgt[1:]) - 1
            
            # 执行攻击
            if 0 <= m_idx < len(self.model.player.board) and 0 <= e_idx < len(self.model.enemies):
                attacker = self.model.player.board[m_idx]
                target = self.model.enemies[e_idx]
                
                # 这里可以添加具体的攻击逻辑
                attack_msg = f"{attacker} 攻击 {target}"
                self.view.add_history(attack_msg)
                
                return [attack_msg], False
            else:
                return ['无效的队伍或敌人序号'], False
                
        except ValueError:
            return ['序号格式错误'], False
    
    def _cmd_play_card(self, args: List[str]) -> Tuple[List[str], bool]:
        """出牌命令"""
        if not args:
            return ['用法: p <手牌序号> [target]'], False
        
        try:
            idx = int(args[0]) - 1
            if 0 <= idx < len(self.model.player.hand):
                card = self.model.player.hand[idx]
                success = self.model.player.play_card(idx)
                
                if success:
                    msg = f"出牌成功: {card}"
                    self.view.add_history(msg)
                    return [msg], False
                else:
                    return ['出牌失败'], False
            else:
                return ['无效的手牌序号'], False
        except ValueError:
            return ['手牌序号必须是数字'], False
    
    def _cmd_use_item(self, args: List[str]) -> Tuple[List[str], bool]:
        """使用物品命令"""
        if not args:
            return ['用法: use <物品名> [mN]'], False
        
        item_name = args[0]
        target = None
        
        if len(args) >= 2:
            target = self._resolve_target_token(args[1])
        
        success, msg = self.model.player.use_item(item_name, 1, target)
        self.view.add_history(f"使用物品 {item_name}: {msg}")
        
        return [msg], False
    
    def _cmd_take_resource(self, args: List[str]) -> Tuple[List[str], bool]:
        """拾取资源命令"""
        if not args:
            return ['用法: take <资源序号|rN>'], False
        
        try:
            arg = args[0].lower()
            if arg.startswith('r'):
                idx = int(arg[1:]) - 1
            else:
                idx = int(arg) - 1
            
            if 0 <= idx < len(self.model.resources):
                resource = self.model.resources.pop(idx)
                msg = f"拾取资源: {resource}"
                self.view.add_history(msg)
                return [msg], False
            else:
                return ['无效的资源序号'], False
        except ValueError:
            return ['资源序号格式错误'], False
    
    def _cmd_equip(self, args: List[str]) -> Tuple[List[str], bool]:
        """装备命令"""
        if len(args) < 2:
            return ['用法: equip <物品名|iN> mN'], False
        
        item_name = args[0]
        target = self._resolve_target_token(args[1])
        
        if not target:
            return ['无效的目标'], False
        
        try:
            # 查找物品
            item = None
            
            # 检查是否是背包索引 (iN)
            if item_name.startswith('i') and item_name[1:].isdigit():
                idx = int(item_name[1:]) - 1
                if 0 <= idx < len(self.model.player.inventory.slots):
                    slot = self.model.player.inventory.slots[idx]
                    item = slot.item
                else:
                    return ['无效的物品索引'], False
            else:
                # 按名称查找物品
                for slot in self.model.player.inventory.slots:
                    if hasattr(slot.item, 'name') and slot.item.name == item_name:
                        item = slot.item
                        break
            
            if not item:
                return [f'未找到物品: {item_name}'], False
            
            # 检查目标是否有装备系统
            if not hasattr(target, 'equipment') or not target.equipment:
                return [f'{target} 无法装备物品'], False
            
            # 尝试装备物品
            try:
                success = target.equipment.equip(item, game=self.model)
                if success:
                    # 从背包移除物品
                    # 找到对应的slot并移除
                    for i, slot in enumerate(self.model.player.inventory.slots):
                        if slot.item == item:
                            self.model.player.inventory.slots.pop(i)
                            break
                    msg = f"成功装备 {item} 到 {target}"
                    self.view.add_history(msg)
                    return [msg], False
                else:
                    return [f"装备失败: {item} 无法装备到 {target}"], False
            except Exception as e:
                return [f"装备过程出错: {e}"], False
                
        except Exception as e:
            return [f"装备命令执行失败: {e}"], False
    
    def _cmd_unequip(self, args: List[str]) -> Tuple[List[str], bool]:
        """卸下装备命令"""
        if len(args) < 2:
            return ['用法: unequip mN <left|right|armor>'], False
        
        target = self._resolve_target_token(args[0])
        slot = args[1]
        
        if not target:
            return ['无效的目标'], False
        
        try:
            # 检查目标是否有装备系统
            if not hasattr(target, 'equipment') or not target.equipment:
                return [f'{target} 没有装备系统'], False
            
            # 映射UI槽位名称到装备系统槽位名称
            slot_mapping = {
                'left': 'left_hand',
                'right': 'right_hand',
                'armor': 'armor'
            }
            equipment_slot = slot_mapping.get(slot, slot)
            
            # 检查槽位是否有效
            valid_slots = ['left_hand', 'right_hand', 'armor']
            if equipment_slot not in valid_slots:
                return [f'无效的装备槽位: {slot}。有效槽位: left, right, armor'], False
            
            # 尝试卸下装备
            try:
                removed_item = target.equipment.unequip(equipment_slot)
                if removed_item:
                    # 将卸下的装备添加到背包
                    self.model.player.inventory.add_item(removed_item)
                    msg = f"成功卸下 {removed_item} 从 {target} 的 {slot} 槽位"
                    self.view.add_history(msg)
                    return [msg], False
                else:
                    return [f'{slot} 槽位没有装备'], False
            except Exception as e:
                return [f"卸下装备过程出错: {e}"], False
                
        except Exception as e:
            return [f"卸下装备命令执行失败: {e}"], False
    
    def _cmd_craft(self, args: List[str]) -> Tuple[List[str], bool]:
        """合成命令"""
        if not args:
            return ['用法: craft <配方名|序号>'], False
        
        if args[0].isdigit():
            return self._cmd_craft_by_index(int(args[0]))
        else:
            recipe_name = args[0]
            # 这里可以添加合成逻辑
            msg = f"合成 {recipe_name}"
            self.view.add_history(msg)
            return [msg], False
    
    def _cmd_craft_by_index(self, idx: int) -> Tuple[List[str], bool]:
        """按索引合成"""
        if idx <= 0:
            return ['索引应为正整数'], False
        
        # 这里可以添加按索引合成的逻辑
        msg = f"合成配方 #{idx}"
        self.view.add_history(msg)
        return [msg], False
    
    def _cmd_back(self, args: List[str]) -> Tuple[List[str], bool]:
        """返回命令"""
        # 这里可以添加返回逻辑
        msg = "返回上一级"
        self.view.add_history(msg)
        return [msg], False
    
    def _cmd_inventory(self, args: List[str]) -> Tuple[List[str], bool]:
        """背包命令"""
        content = self.view.render_section('inventory', self.model)
        return [content], False
    
    def _cmd_skill(self, skill_name: str, args: List[str]) -> Tuple[List[str], bool]:
        """技能命令"""
        if not args:
            return ['用法: skill <name> <source mN> [target]'], False
        
        source_tok = args[0]
        if not source_tok.startswith('m'):
            return ['来源需为随从标记 mN'], False
        
        try:
            src_idx = int(source_tok[1:]) - 1
            if 0 <= src_idx < len(self.model.player.board):
                source = self.model.player.board[src_idx]
                
                # 获取技能策略
                skill = get_skill(skill_name)
                if not skill:
                    return [f'未知技能: {skill_name}'], False
                
                # 解析目标（如果有）
                target = None
                if len(args) >= 2:
                    target = self._resolve_target_token(args[1])
                
                # 执行技能
                success, msg = skill.execute(self.model, source, target)
                
                if success:
                    self.view.add_history(f"{source} 使用技能 {skill_name}: {msg}")
                    # 标记已攻击
                    if hasattr(source, 'can_attack'):
                        source.can_attack = False
                else:
                    self.view.add_info(f"技能失败: {msg}")
                
                return [msg], False
            else:
                return ['无效的来源序号'], False
        except ValueError:
            return ['来源序号格式错误'], False
    
    def _resolve_target_token(self, token: str) -> Any:
        """解析目标令牌"""
        token = token.lower()
        
        # 敌人: e1/e2...
        if token.startswith('e'):
            try:
                idx = int(token[1:]) - 1
                if 0 <= idx < len(self.model.enemies):
                    return self.model.enemies[idx]
            except ValueError:
                pass
        
        # 我方随从: m1/m2...
        if token.startswith('m'):
            try:
                idx = int(token[1:]) - 1
                if 0 <= idx < len(self.model.player.board):
                    return self.model.player.board[idx]
            except ValueError:
                pass
        
        return None
