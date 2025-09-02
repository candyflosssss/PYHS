"""
视图渲染层 - MVC模式中的View层
负责渲染游戏界面和显示信息
"""

from typing import List, Dict, Any
from src.ui import colors as C


class GameView:
    """游戏视图渲染器"""
    
    def __init__(self):
        self.history = []  # 操作历史
        self.info = []     # 信息区
    
    def add_history(self, line: str):
        """添加历史记录"""
        self.history.append(line)
        if len(self.history) > 10:
            self.history.pop(0)
    
    def set_info(self, info_lines: List[str]):
        """设置信息区内容"""
        self.info = info_lines
    
    def add_info(self, line: str):
        """添加信息区内容"""
        self.info.append(line)
        if len(self.info) > 10:
            self.info.pop(0)
    
    def render_full_view(self, model) -> str:
        """渲染完整游戏视图"""
        sep = C.dim('────────────────────────────────')
        parts: List[str] = []
        
        # 场景标题
        try:
            scene_name = getattr(model, 'current_scene_title', None) or model.current_scene
            if scene_name:
                import os
                title = scene_name if getattr(model, 'current_scene_title', None) else os.path.basename(scene_name)
                parts.append(C.heading(f"【场景】{title}"))
                parts.append(sep)
        except Exception:
            pass
        
        # 信息区置顶
        parts.append(self._render_info_section(model))
        parts.append(sep)
        
        # 队伍 -> 敌人 -> 资源 -> 背包 -> 历史
        parts.append(self._render_player_section(model))
        parts.append(sep)
        parts.append(self._render_enemy_section(model))
        parts.append(sep)
        parts.append(self._render_resources_section(model))
        parts.append(sep)
        parts.append(self._render_inventory_section(model))
        parts.append(sep)
        parts.append(self._render_history_section(model))
        
        return "\n".join(parts)
    
    def _render_info_section(self, model) -> str:
        """渲染信息区"""
        if not self.info:
            return "信息区: (无)"
        
        lines: List[str] = [C.heading("信息区:")]
        recent = self.info[-10:]
        
        for i, line in enumerate(recent):
            if i == 0:
                txt = line
                if any(k in txt for k in ("失败", "无效", "错误")):
                    lines.append(C.error(txt))
                elif any(k in txt for k in ("成功", "进入回合", "拾取", "使用", "攻击")):
                    lines.append(C.success(txt))
                else:
                    lines.append(C.warning(txt))
            else:
                # 次要细节用淡色
                lines.append(C.dim(line))
        
        return "\n".join(lines)
    
    def _render_player_section(self, model) -> str:
        """渲染玩家队伍区域"""
        board = model.player.board
        lines = [C.label(f"队伍({len(board)}):")]
        
        if board:
            pairs: List[tuple[str, str]] = []
            for i, m in enumerate(board, 1):
                # 显示体力
                try:
                    st = int(getattr(m, 'stamina', 0))
                    sm = int(getattr(m, 'stamina_max', st))
                    status = C.dim(f'·体力 {st}/{sm}')
                except Exception:
                    status = C.dim('·体力 -')
                
                # 计算数值
                try:
                    base_atk = int(getattr(m, 'base_atk', getattr(m, 'atk', 0)))
                except Exception:
                    base_atk = int(getattr(m, 'atk', 0))
                
                try:
                    eq_atk = int(m.equipment.get_total_attack() if hasattr(m, 'equipment') and m.equipment else 0)
                except Exception:
                    eq_atk = 0
                
                total_atk = base_atk + eq_atk
                
                try:
                    eq_def = int(m.equipment.get_total_defense() if hasattr(m, 'equipment') and m.equipment else 0)
                except Exception:
                    eq_def = 0
                
                cur_hp = int(getattr(m, 'hp', 0))
                max_hp = int(getattr(m, 'max_hp', cur_hp))
                
                # 名称
                try:
                    name = getattr(m, 'display_name', None) or m.__class__.__name__
                except Exception:
                    name = '随从'
                name_colored = C.friendly(str(name))
                
                # DND概览
                try:
                    dnd = getattr(m, 'dnd', None)
                    ac = dnd.get('ac') if isinstance(dnd, dict) else None
                    dnd_part = f" AC:{ac}" if ac is not None else ""
                except Exception:
                    dnd_part = ""
                
                # 装备摘要
                eq = getattr(m, 'equipment', None)
                eq_parts = []
                try:
                    if eq and getattr(eq, 'left_hand', None):
                        lh = eq.left_hand
                        if getattr(lh, 'is_two_handed', False):
                            bonus = []
                            if getattr(lh, 'attack', 0): bonus.append(f"+{lh.attack}攻")
                            if getattr(lh, 'defense', 0): bonus.append(f"+{lh.defense}防")
                            eq_parts.append(f"双手:{lh.name}({ ' '.join(bonus) })" if bonus else f"双手:{lh.name}")
                        else:
                            bonus = []
                            if getattr(lh, 'attack', 0): bonus.append(f"+{lh.attack}攻")
                            if getattr(lh, 'defense', 0): bonus.append(f"+{lh.defense}防")
                            eq_parts.append(f"左:{lh.name}({ ' '.join(bonus) })" if bonus else f"左:{lh.name}")
                    
                    if eq and getattr(eq, 'right_hand', None):
                        rh = eq.right_hand
                        bonus = []
                        if getattr(rh, 'attack', 0): bonus.append(f"+{rh.attack}攻")
                        if getattr(rh, 'defense', 0): bonus.append(f"+{rh.defense}防")
                        eq_parts.append(f"右:{rh.name}({ ' '.join(bonus) })" if bonus else f"右:{rh.name}")
                    
                    if eq and getattr(eq, 'armor', None):
                        ar = eq.armor
                        bonus = []
                        if getattr(ar, 'attack', 0): bonus.append(f"+{ar.attack}攻")
                        if getattr(ar, 'defense', 0): bonus.append(f"+{ar.defense}防")
                        eq_parts.append(f"甲:{ar.name}({ ' '.join(bonus) })" if bonus else f"甲:{ar.name}")
                except Exception:
                    pass
                
                eq_str = f" [{', '.join(eq_parts)}]" if eq_parts else ""
                
                # 组装行
                atk_str = C.stat_atk(f"{total_atk}攻 ({base_atk}+{eq_atk})")
                hp_str = C.stat_hp(f"{cur_hp}/{max_hp} HP")
                def_str = C.stat_def(f"{eq_def}防")
                stat_str = f"[{atk_str} | {hp_str} | {def_str}]{dnd_part}"
                line = f"{name_colored} {stat_str}{eq_str} {status}"
                pairs.append((f"m{i}", line))
            
            lines.extend(self._format_token_list(pairs))
        else:
            lines.append("  (空)")
        
        return "\n".join(lines)
    
    def _render_enemy_section(self, model) -> str:
        """渲染敌人区域"""
        enemies = model.enemies
        lines = [C.label(f"敌人({len(enemies)}):")]
        
        if enemies:
            pairs = []
            for i, e in enumerate(enemies, 1):
                try:
                    name = getattr(e, 'name', f'敌人#{i}')
                    atk = int(getattr(e, 'attack', 0))
                    hp = int(getattr(e, 'hp', 0))
                    mhp = int(getattr(e, 'max_hp', hp))
                except Exception:
                    name, atk, hp, mhp = (f'敌人#{i}', 0, 0, 0)
                
                atk_str = C.stat_atk(f"{atk}攻")
                hp_str = C.stat_hp(f"{hp}/{mhp} HP")
                name_colored = C.enemy(str(name))
                line = f"{name_colored} [{atk_str} | {hp_str}]"
                pairs.append((f"e{i}", line))
            
            lines.extend(self._format_token_list(pairs))
        else:
            lines.append("  (无)")
        
        return "\n".join(lines)
    
    def _render_resources_section(self, model) -> str:
        """渲染资源区域"""
        res = model.resources
        lines = [C.label(f"资源区({len(res)}):")]
        
        if res:
            pairs = [(f"r{i}", str(r)) for i, r in enumerate(res, 1)]
            lines.extend(self._format_token_list(pairs))
        else:
            lines.append("  (空)")
        
        return "\n".join(lines)
    
    def _render_inventory_section(self, model) -> str:
        """渲染背包区域"""
        inv = model.player.inventory
        lines = [C.label(f"背包({len(inv.slots)}/{inv.max_slots}):")]
        
        if inv.slots:
            pairs = [(f"i{i}", str(slot)) for i, slot in enumerate(inv.slots, 1)]
            lines.extend(self._format_token_list(pairs))
        else:
            lines.append("  (空)")
        
        # 可合成清单
        craftables = self._get_craftable_recipes(model)
        lines.append(C.label(f"可合成({len(craftables)}):"))
        
        if craftables:
            cpairs = [(f"c{i}", r['name']) for i, r in enumerate(craftables, 1)]
            lines.extend(self._format_token_list(cpairs))
            lines.append(C.dim("提示: 输入 c1/c2... 可快速合成"))
        else:
            lines.append("  (暂无可合成配方)")
        
        return "\n".join(lines)
    
    def _render_history_section(self, model) -> str:
        """渲染历史区域"""
        if not self.history:
            return "历史: (无)"
        return "历史(最新在下):\n" + "\n".join(self.history[-10:])
    
    def _format_token_list(self, pairs: List[tuple[str, str]], pad: int = 2) -> List[str]:
        """格式化令牌列表"""
        if not pairs:
            return []
        w = max(len(t) for t, _ in pairs)
        gap = ' ' * pad
        return [f"  {t.ljust(w)}{gap}{s}" for t, s in pairs]
    
    def _get_craftable_recipes(self, model) -> List[Dict[str, Any]]:
        """获取可合成的配方"""
        # 这里可以添加合成配方的逻辑
        return []
    
    def render_section(self, section_name: str, model) -> str:
        """渲染指定区域"""
        section_map = {
            'player': self._render_player_section,
            'enemy': self._render_enemy_section,
            'resources': self._render_resources_section,
            'inventory': self._render_inventory_section,
            'history': self._render_history_section,
            'info': self._render_info_section
        }
        
        render_func = section_map.get(section_name)
        if render_func:
            return render_func(model)
        else:
            return f"未知区域: {section_name}"
