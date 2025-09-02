"""
技能策略接口 - 使用策略模式解耦技能系统
每个技能都是一个独立的策略对象
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple, Optional, List


class SkillStrategy(ABC):
    """技能策略抽象基类"""
    
    def __init__(self, name: str, description: str = "", stamina_cost: int = 1):
        self.name = name
        self.description = description
        self.stamina_cost = stamina_cost
    
    @abstractmethod
    def execute(self, game, source, target=None) -> Tuple[bool, str]:
        """
        执行技能
        
        Args:
            game: 游戏实例
            source: 技能施放者
            target: 技能目标（可选）
            
        Returns:
            (是否成功, 结果消息)
        """
        pass
    
    def can_execute(self, source) -> bool:
        """检查是否可以执行技能"""
        try:
            if hasattr(source, 'has_stamina'):
                return source.has_stamina(self.stamina_cost)
            elif hasattr(source, 'stamina'):
                return source.stamina >= self.stamina_cost
            return True
        except Exception:
            return True
    
    def consume_stamina(self, source) -> bool:
        """消耗体力"""
        try:
            if hasattr(source, 'spend_stamina'):
                return source.spend_stamina(self.stamina_cost)
            elif hasattr(source, 'stamina'):
                if source.stamina >= self.stamina_cost:
                    source.stamina -= self.stamina_cost
                    return True
            return True
        except Exception:
            return True
    
    def __str__(self):
        return f"{self.name}(消耗体力:{self.stamina_cost})"
    
    def __repr__(self):
        return self.__str__()


class SweepSkill(SkillStrategy):
    """横扫技能策略"""
    
    def __init__(self):
        super().__init__("横扫", "对所有敌人各进行一次攻击", stamina_cost=2)
    
    def execute(self, game, source, target=None) -> Tuple[bool, str]:
        """执行横扫技能"""
        if not self.can_execute(source):
            return False, f"{source} 体力不足，无法使用 {self.name}"
        
        # 消耗体力
        if not self.consume_stamina(source):
            return False, f"{source} 体力不足，无法使用 {self.name}"
        
        # 获取攻击力
        try:
            atk_val = int(source.get_total_attack() if hasattr(source, 'get_total_attack') else getattr(source, 'attack', 1))
        except Exception:
            atk_val = 1
        
        dmg_each = max(0, atk_val // 2)
        hits = []
        
        # 攻击所有敌人
        for enemy in list(game.enemies):
            try:
                # 这里可以添加命中判定逻辑
                hit = True
                if hit:
                    prev_hp = enemy.hp
                    enemy.take_damage(dmg_each)
                    dealt = max(0, prev_hp - enemy.hp)
                    hits.append(f"{enemy.name}(-{dealt})")
                    
                    # 检查敌人死亡
                    if enemy.hp <= 0:
                        try:
                            if hasattr(game, '_handle_enemy_death'):
                                game._handle_enemy_death(enemy)
                        except Exception:
                            pass
            except Exception:
                hits.append(f"{enemy.name}(失败)")
        
        # 标记已攻击
        if hasattr(source, 'can_attack'):
            source.can_attack = False
        
        return True, f"{source} 使用 {self.name}，结果: {', '.join(hits)}"


class BasicHealSkill(SkillStrategy):
    """基础治疗技能策略"""
    
    def __init__(self):
        super().__init__("基础治疗", "恢复目标3点生命值", stamina_cost=1)
    
    def execute(self, game, source, target=None) -> Tuple[bool, str]:
        """执行基础治疗技能"""
        if not target:
            return False, '未选择目标'
        
        if not self.can_execute(source):
            return False, f"{source} 体力不足，无法使用 {self.name}"
        
        # 消耗体力
        if not self.consume_stamina(source):
            return False, f"{source} 体力不足，无法使用 {self.name}"
        
        # 治疗目标
        heal_amount = 3
        prev_hp = getattr(target, 'hp', 0)
        
        try:
            if hasattr(target, 'heal'):
                target.heal(heal_amount)
            else:
                target.hp = min(getattr(target, 'max_hp', prev_hp), prev_hp + heal_amount)
        except Exception:
            return False, f"治疗失败: {target}"
        
        current_hp = getattr(target, 'hp', prev_hp)
        actual_heal = current_hp - prev_hp
        
        return True, f"{source} 对 {target} 使用 {self.name}，恢复 {actual_heal} 点生命值"


class DrainSkill(SkillStrategy):
    """生命汲取技能策略"""
    
    def __init__(self):
        super().__init__("生命汲取", "对目标造成伤害并恢复等量生命值", stamina_cost=2)
    
    def execute(self, game, source, target=None) -> Tuple[bool, str]:
        """执行生命汲取技能"""
        if not target:
            return False, '未选择目标'
        
        if not self.can_execute(source):
            return False, f"{source} 体力不足，无法使用 {self.name}"
        
        # 消耗体力
        if not self.consume_stamina(source):
            return False, f"{source} 体力不足，无法使用 {self.name}"
        
        # 计算伤害
        try:
            damage = int(source.get_total_attack() if hasattr(source, 'get_total_attack') else getattr(source, 'attack', 1))
        except Exception:
            damage = 1
        
        # 对目标造成伤害
        prev_target_hp = getattr(target, 'hp', 0)
        try:
            if hasattr(target, 'take_damage'):
                target.take_damage(damage)
            else:
                target.hp = max(0, prev_target_hp - damage)
        except Exception:
            return False, f"造成伤害失败: {target}"
        
        actual_damage = prev_target_hp - getattr(target, 'hp', 0)
        
        # 恢复施法者生命值
        prev_source_hp = getattr(source, 'hp', 0)
        try:
            if hasattr(source, 'heal'):
                source.heal(actual_damage)
            else:
                source.hp = min(getattr(source, 'max_hp', prev_source_hp), prev_source_hp + actual_damage)
        except Exception:
            pass
        
        current_source_hp = getattr(source, 'hp', prev_source_hp)
        actual_heal = current_source_hp - prev_source_hp
        
        return True, f"{source} 使用 {self.name} 对 {target} 造成 {actual_damage} 伤害，恢复 {actual_heal} 点生命值"


class TauntSkill(SkillStrategy):
    """嘲讽技能策略"""
    
    def __init__(self):
        super().__init__("嘲讽", "吸引敌人攻击自己", stamina_cost=1)
    
    def execute(self, game, source, target=None) -> Tuple[bool, str]:
        """执行嘲讽技能"""
        if not self.can_execute(source):
            return False, f"{source} 体力不足，无法使用 {self.name}"
        
        # 消耗体力
        if not self.consume_stamina(source):
            return False, f"{source} 体力不足，无法使用 {self.name}"
        
        # 添加嘲讽标记
        try:
            if hasattr(source, 'add_tag'):
                source.add_tag('taunt')
            elif hasattr(source, 'tags'):
                if 'taunt' not in source.tags:
                    source.tags.append('taunt')
        except Exception:
            pass
        
        return True, f"{source} 使用 {self.name}，成功吸引敌人注意"


class ArcaneMissilesSkill(SkillStrategy):
    """奥术飞弹技能策略"""
    
    def __init__(self):
        super().__init__("奥术飞弹", "发射3发奥术飞弹，每发造成1点伤害", stamina_cost=1)
    
    def execute(self, game, source, target=None) -> Tuple[bool, str]:
        """执行奥术飞弹技能"""
        if not self.can_execute(source):
            return False, f"{source} 体力不足，无法使用 {self.name}"
        
        # 消耗体力
        if not self.consume_stamina(source):
            return False, f"{source} 体力不足，无法使用 {self.name}"
        
        # 选择目标（如果没有指定目标，随机选择敌人）
        if not target and game.enemies:
            import random
            target = random.choice(game.enemies)
        
        if not target:
            return False, '没有可攻击的目标'
        
        # 发射3发飞弹
        total_damage = 0
        for i in range(3):
            try:
                # 这里可以添加命中判定逻辑
                hit = True
                if hit:
                    prev_hp = target.hp
                    target.take_damage(1)
                    dealt = max(0, prev_hp - target.hp)
                    total_damage += dealt
                    
                    # 检查目标死亡
                    if target.hp <= 0:
                        try:
                            if hasattr(game, '_handle_enemy_death'):
                                game._handle_enemy_death(target)
                        except Exception:
                            pass
                        break
            except Exception:
                pass
        
        return True, f"{source} 使用 {self.name} 对 {target} 造成总计 {total_damage} 点伤害"


# 技能注册表
SKILL_REGISTRY = {
    'sweep': SweepSkill(),
    'basic_heal': BasicHealSkill(),
    'drain': DrainSkill(),
    'taunt': TauntSkill(),
    'arcane_missiles': ArcaneMissilesSkill(),
}

# 从原技能系统导入更多技能
try:
    from src.systems.skills_engine import (
        skill_sweep, skill_basic_heal, skill_drain, skill_taunt, skill_arcane_missiles,
        skill_power_slam, skill_bloodlust_priority, skill_execute_mage, skill_mass_intimidate,
        skill_precise_strike, skill_disarm, skill_shield_breaker, skill_dual_wield_bane,
        skill_mind_over_matter, skill_trial_of_wisdom, skill_execute_wounded, skill_fair_distribution,
        skill_destiny, skill_touch_of_undeath
    )
    
    # 创建包装器类来适配原技能系统
    class LegacySkillWrapper(SkillStrategy):
        """原技能系统的包装器"""
        
        def __init__(self, name: str, skill_func, description: str = "", stamina_cost: int = 1):
            super().__init__(name, description, stamina_cost)
            self.skill_func = skill_func
        
        def execute(self, game, source, target=None) -> Tuple[bool, str]:
            """执行原技能系统的技能"""
            if not self.can_execute(source):
                return False, f"{source} 体力不足，无法使用 {self.name}"
            
            # 消耗体力
            if not self.consume_stamina(source):
                return False, f"{source} 体力不足，无法使用 {self.name}"
            
            try:
                # 调用原技能函数
                success, msg = self.skill_func(game, source, target)
                return success, msg
            except Exception as e:
                return False, f"技能执行失败: {e}"
    
    # 注册更多技能
    SKILL_REGISTRY.update({
        'power_slam': LegacySkillWrapper("力量猛击", skill_power_slam, "基于力量的重击", 2),
        'bloodlust_priority': LegacySkillWrapper("血腥优先", skill_bloodlust_priority, "自动优先攻击残血目标", 1),
        'execute_mage': LegacySkillWrapper("斩杀法师", skill_execute_mage, "对法师型目标造成高额伤害", 3),
        'mass_intimidate': LegacySkillWrapper("群体恐吓", skill_mass_intimidate, "群体对抗检定，震慑敌人", 2),
        'precise_strike': LegacySkillWrapper("精准打击", skill_precise_strike, "优势命中的精确打击", 2),
        'disarm': LegacySkillWrapper("缴械", skill_disarm, "卸下目标武器并据为己有", 2),
        'shield_breaker': LegacySkillWrapper("破盾", skill_shield_breaker, "破坏盾牌并造成额外伤害", 2),
        'dual_wield_bane': LegacySkillWrapper("双刀克星", skill_dual_wield_bane, "针对双持目标的克星攻击", 2),
        'mind_over_matter': LegacySkillWrapper("强于心智", skill_mind_over_matter, "用心智打击对手", 1),
        'trial_of_wisdom': LegacySkillWrapper("智慧试炼", skill_trial_of_wisdom, "以智取胜的试炼", 1),
        'execute_wounded': LegacySkillWrapper("重伤补刀", skill_execute_wounded, "对重伤目标处决", 2),
        'fair_distribution': LegacySkillWrapper("公平分配", skill_fair_distribution, "按总攻平分对群体伤害", 2),
        'destiny': LegacySkillWrapper("命运", skill_destiny, "10次优势命中，命中则对目标造成等同于其当前生命的伤害", 5),
        'touch_of_undeath': LegacySkillWrapper("亡灵之触", skill_touch_of_undeath, "召唤1个1生命的骷髅随从，攻3防3", 3),
    })
    
except ImportError as e:
    print(f"导入原技能系统失败: {e}")
    # 如果导入失败，至少保留基础技能
    pass


def get_skill(skill_name: str) -> Optional[SkillStrategy]:
    """获取技能策略"""
    return SKILL_REGISTRY.get(skill_name.lower())


def register_skill(skill_name: str, skill_strategy: SkillStrategy):
    """注册新技能"""
    SKILL_REGISTRY[skill_name.lower()] = skill_strategy


def list_available_skills() -> List[str]:
    """列出所有可用技能"""
    return list(SKILL_REGISTRY.keys())
