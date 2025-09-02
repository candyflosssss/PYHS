"""
装备访问混入类 - 提供统一的装备访问接口
避免重复的属性检查代码
"""

from typing import Optional, Union, Any
from .equipment_system import EquipmentSystem


class EquipmentMixin:
    """装备访问混入类，提供统一的装备访问接口"""
    
    def __init__(self):
        """初始化装备系统"""
        self.equipment = EquipmentSystem()
        try:
            # 让装备系统能在事件中回溯归属对象
            setattr(self.equipment, 'owner', self)
        except Exception:
            pass
    
    def get_equipment_attack(self) -> int:
        """获取装备提供的攻击力加成"""
        try:
            if hasattr(self, 'equipment') and self.equipment:
                return int(self.equipment.get_total_attack())
        except Exception:
            pass
        return 0
    
    def get_equipment_defense(self) -> int:
        """获取装备提供的防御力加成"""
        try:
            if hasattr(self, 'equipment') and self.equipment:
                return int(self.equipment.get_total_defense())
        except Exception:
            pass
        return 0
    
    def get_equipment_bonus(self, bonus_type: str) -> int:
        """获取装备提供的指定类型加成"""
        try:
            if hasattr(self, 'equipment') and self.equipment:
                if bonus_type == 'attack':
                    return int(self.equipment.get_total_attack())
                elif bonus_type == 'defense':
                    return int(self.equipment.get_total_defense())
        except Exception:
            pass
        return 0
    
    def has_equipment(self, slot: str = None) -> bool:
        """检查是否有装备"""
        try:
            if not hasattr(self, 'equipment') or not self.equipment:
                return False
            if slot is None:
                # 检查是否有任何装备
                return (bool(self.equipment.left_hand) or 
                       bool(self.equipment.right_hand) or 
                       bool(self.equipment.armor))
            else:
                # 检查指定槽位
                slot_map = {
                    'left': 'left_hand',
                    'right': 'right_hand', 
                    'armor': 'armor'
                }
                slot_key = slot_map.get(slot, slot)
                return bool(getattr(self.equipment, slot_key, None))
        except Exception:
            return False
    
    def get_equipment_info(self) -> dict:
        """获取装备信息摘要"""
        info = {
            'left_hand': None,
            'right_hand': None,
            'armor': None,
            'total_attack': 0,
            'total_defense': 0
        }
        
        try:
            if hasattr(self, 'equipment') and self.equipment:
                # 左手装备
                if self.equipment.left_hand:
                    lh = self.equipment.left_hand
                    info['left_hand'] = {
                        'name': lh.name,
                        'attack': getattr(lh, 'attack', 0),
                        'defense': getattr(lh, 'defense', 0),
                        'is_two_handed': getattr(lh, 'is_two_handed', False)
                    }
                
                # 右手装备
                if self.equipment.right_hand:
                    rh = self.equipment.right_hand
                    info['right_hand'] = {
                        'name': rh.name,
                        'attack': getattr(rh, 'attack', 0),
                        'defense': getattr(rh, 'defense', 0)
                    }
                
                # 护甲
                if self.equipment.armor:
                    ar = self.equipment.armor
                    info['armor'] = {
                        'name': ar.name,
                        'attack': getattr(ar, 'attack', 0),
                        'defense': getattr(ar, 'defense', 0)
                    }
                
                # 总计
                info['total_attack'] = self.get_equipment_attack()
                info['total_defense'] = self.get_equipment_defense()
                
        except Exception:
            pass
        
        return info
    
    def format_equipment_string(self) -> str:
        """格式化装备信息为字符串"""
        info = self.get_equipment_info()
        parts = []
        
        # 双手武器
        if info['left_hand'] and info['left_hand']['is_two_handed']:
            lh = info['left_hand']
            bonus = []
            if lh['attack']: bonus.append(f"+{lh['attack']}攻")
            if lh['defense']: bonus.append(f"+{lh['defense']}防")
            bonus_str = f"({', '.join(bonus)})" if bonus else ""
            parts.append(f"双手:{lh['name']}{bonus_str}")
        
        # 左手装备（非双手）
        elif info['left_hand'] and not info['left_hand']['is_two_handed']:
            lh = info['left_hand']
            bonus = []
            if lh['attack']: bonus.append(f"+{lh['attack']}攻")
            if lh['defense']: bonus.append(f"+{lh['defense']}防")
            bonus_str = f"({', '.join(bonus)})" if bonus else ""
            parts.append(f"左:{lh['name']}{bonus_str}")
        
        # 右手装备
        if info['right_hand']:
            rh = info['right_hand']
            bonus = []
            if rh['attack']: bonus.append(f"+{rh['attack']}攻")
            if rh['defense']: bonus.append(f"+{rh['defense']}防")
            bonus_str = f"({', '.join(bonus)})" if bonus else ""
            parts.append(f"右:{rh['name']}{bonus_str}")
        
        # 护甲
        if info['armor']:
            ar = info['armor']
            bonus = []
            if ar['attack']: bonus.append(f"+{ar['attack']}攻")
            if ar['defense']: bonus.append(f"+{ar['defense']}防")
            bonus_str = f"({', '.join(bonus)})" if bonus else ""
            parts.append(f"甲:{ar['name']}{bonus_str}")
        
        return f"[{', '.join(parts)}]" if parts else ""
    
    def safe_equipment_access(self, method_name: str, *args, **kwargs) -> Any:
        """安全访问装备方法，避免属性检查错误"""
        try:
            if hasattr(self, 'equipment') and self.equipment:
                method = getattr(self.equipment, method_name, None)
                if callable(method):
                    return method(*args, **kwargs)
        except Exception:
            pass
        return None
