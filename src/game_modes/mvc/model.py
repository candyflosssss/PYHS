"""
游戏状态管理模型 - MVC模式中的Model层
负责管理所有游戏数据和状态
"""

from typing import Dict, Any, List, Optional
from src.core.player import Player
from src.core.zone import ObservableList
from src.core.save_state import SaveManager


class GameModel:
    """游戏状态管理模型"""
    
    def __init__(self, player_name: str):
        # 玩家数据
        self.player = Player(player_name, is_me=True, game=self)
        
        # 游戏状态
        self.turn = 1
        self.running = True
        self.current_scene = None
        self.current_scene_title = None
        self._scene_meta = None
        
        # 游戏对象
        self.enemies: ObservableList = ObservableList(
            [],
            on_add='enemy_added', on_remove='enemy_removed', on_clear='enemies_cleared', 
            on_reset='enemies_reset', on_change='enemies_changed',
            to_payload=lambda e: getattr(e, 'name', str(e))
        )
        self.resources: ObservableList = ObservableList(
            [],
            on_add='resource_added', on_remove='resource_removed', on_clear='resources_cleared', 
            on_reset='resources_reset', on_change='resources_changed',
            to_payload=lambda r: getattr(r, 'name', str(r))
        )
        
        # 兼容旧接口
        self.resource_zone = self.resources
        self.players = {self.player.name: self.player}
        
        # 存档/世界进度
        try:
            self.profile = SaveManager.load(self.player.name)
        except Exception:
            self.profile = None
        
        # 初始化队伍
        self._init_board()
        
        # 启用被动系统
        try:
            from src.systems import passives_system as PS
            PS.setup()
        except Exception:
            pass
        
        # 保存初始状态快照
        try:
            if self.profile:
                self.profile.snapshot_inventory(self.player.inventory)
                self.profile.snapshot_party(self.player.board)
                self.profile.save()
        except Exception:
            pass
        
        # 订阅事件
        self._setup_event_subscriptions()
    
    def _init_board(self):
        """初始化玩家队伍"""
        # 这里可以添加默认随从或从存档加载
        pass
    
    def _setup_event_subscriptions(self):
        """设置事件订阅"""
        try:
            from src.core.events import subscribe as subscribe_event
            # 订阅随从死亡事件
            self._subs = []
            self._subs.append(('card_died', subscribe_event('card_died', self._on_card_died)))
            
            # 订阅状态变化事件
            self._subs.append(('inventory_changed', subscribe_event('inventory_changed', self._on_inventory_changed)))
            self._subs.append(('party_changed', subscribe_event('party_changed', self._on_party_changed)))
            
        except Exception:
            self._subs = []
    
    def _on_card_died(self, event_name: str, payload: Dict[str, Any]):
        """处理随从死亡事件"""
        try:
            card = payload.get('card')
            if card and hasattr(card, 'on_death'):
                card.on_death(self, self.player)
        except Exception:
            pass
    
    def _on_inventory_changed(self, event_name: str, payload: Dict[str, Any]):
        """处理背包变化事件"""
        try:
            if self.profile:
                self.profile.snapshot_inventory(self.player.inventory)
                self.profile.save()
        except Exception:
            pass
    
    def _on_party_changed(self, event_name: str, payload: Dict[str, Any]):
        """处理队伍变化事件"""
        try:
            if self.profile:
                self.profile.snapshot_party(self.player.board)
                self.profile.save()
        except Exception:
            pass
    
    # --- 游戏状态查询方法 ---
    def get_state(self) -> Dict[str, Any]:
        """获取游戏状态摘要"""
        return {
            'turn': self.turn,
            'player': {
                'name': self.player.name,
                'hp': self.player.hp,
                'max_hp': self.player.max_hp,
                'board_size': len(self.player.board),
                'hand_size': len(self.player.hand),
                'inventory_size': len(self.player.inventory.slots)
            },
            'enemies': [str(e) for e in self.enemies],
            'resources': [str(r) for r in self.resources],
            'current_scene': self.current_scene,
            'current_scene_title': self.current_scene_title
        }
    
    def get_player_info(self) -> Dict[str, Any]:
        """获取玩家详细信息"""
        return {
            'name': self.player.name,
            'hp': self.player.hp,
            'max_hp': self.player.max_hp,
            'board': [str(card) for card in self.player.board],
            'hand': [str(card) for card in self.player.hand],
            'inventory': [str(slot) for slot in self.player.inventory.slots]
        }
    
    def get_enemies_info(self) -> List[Dict[str, Any]]:
        """获取敌人信息"""
        enemies_info = []
        for enemy in self.enemies:
            try:
                enemies_info.append({
                    'name': getattr(enemy, 'name', str(enemy)),
                    'hp': getattr(enemy, 'hp', 0),
                    'max_hp': getattr(enemy, 'max_hp', 0),
                    'attack': getattr(enemy, 'attack', 0)
                })
            except Exception:
                enemies_info.append({'name': str(enemy), 'hp': 0, 'max_hp': 0, 'attack': 0})
        return enemies_info
    
    def get_resources_info(self) -> List[Dict[str, Any]]:
        """获取资源信息"""
        resources_info = []
        for resource in self.resources:
            try:
                resources_info.append({
                    'name': getattr(resource, 'name', str(resource)),
                    'type': getattr(resource, 'item_type', 'unknown'),
                    'effect_value': getattr(resource, 'effect_value', 0)
                })
            except Exception:
                resources_info.append({'name': str(resource), 'type': 'unknown', 'effect_value': 0})
        return resources_info
    
    # --- 游戏状态修改方法 ---
    def start_turn(self):
        """开始新回合"""
        self.turn += 1
        # 刷新随从状态
        for card in self.player.board:
            try:
                if hasattr(card, 'refill_stamina'):
                    card.refill_stamina()
                card.can_attack = True
            except Exception:
                pass
    
    def end_turn(self):
        """结束当前回合"""
        # 这里可以添加回合结束的逻辑
        pass
    
    def load_scene(self, scene_name: str, keep_board: bool = True):
        """加载场景"""
        if not scene_name:
            return False
            
        import os
        import json
        
        scene_path = scene_name
        if not os.path.isabs(scene_path):
            # 统一标准化分隔符
            norm = scene_name.replace('\\', '/').lstrip('/')
            for pref in ('scenes/', 'yyy/scenes/'):
                if norm.startswith(pref):
                    norm = norm[len(pref):]
                    break
            
            # 查找场景文件
            scene_base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scenes')
            scene_path = os.path.abspath(os.path.join(scene_base_dir, norm))
        
        data = {}
        try:
            with open(scene_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"读取场景失败: {e}")
            return False

        # 记录当前场景
        self.current_scene = scene_path
        
        # 记录友好场景标题
        try:
            base = os.path.splitext(os.path.basename(scene_path))[0]
            human = base.replace('_', ' ')
            title = data.get('title') or data.get('name') or human
            self.current_scene_title = str(title)
        except Exception:
            self.current_scene_title = None

        # 保存场景元数据
        try:
            self._scene_meta = {
                'on_clear': data.get('on_clear'),
                'parent': data.get('parent') or data.get('back_to'),
                'type': data.get('type')
            }
        except Exception:
            self._scene_meta = None

        # 清空/保留随从区
        eff_keep = keep_board
        try:
            if 'refresh_board_on_enter' in data:
                eff_keep = not bool(data.get('refresh_board_on_enter'))
            elif 'preserve_board_on_enter' in data:
                eff_keep = bool(data.get('preserve_board_on_enter'))
        except Exception:
            pass

        # 清空/保留
        if not eff_keep:
            self.player.board.clear()
            self.player.hand.clear()
        
        # 重置敌人与资源
        self.enemies.clear()
        self.resources.clear()
        
        # 加载初始随从（如果场景文件中有board数据且不保留旧随从）
        if not eff_keep:
            board_data = data.get('board', [])
            for card_data in board_data:
                try:
                    if isinstance(card_data, dict):
                        name = card_data.get('name', '随从')
                        atk = card_data.get('atk', 1)
                        hp = card_data.get('hp', 1)
                        profession = card_data.get('profession', 'warrior')
                        
                        # 创建随从对象
                        from src.core.cards import NormalCard
                        card = NormalCard(atk, hp, name=name)
                        self.player.board.append(card)
                        
                        # 处理随从装备
                        # 支持两种格式：equip.items 和 equipment 数组
                        items_data = []
                        if 'equip' in card_data:
                            equip_data = card_data['equip']
                            if isinstance(equip_data, dict) and 'items' in equip_data:
                                items_data = equip_data['items']
                        elif 'equipment' in card_data:
                            # 直接使用 equipment 数组
                            items_data = card_data['equipment']
                        
                        if items_data:
                                for item_data in items_data:
                                    try:
                                        if isinstance(item_data, dict):
                                            name = item_data.get('name', '装备')
                                            item_type = item_data.get('type', 'weapon')
                                            
                                            if item_type == 'weapon':
                                                from src.systems.equipment_system import WeaponItem
                                                attack = item_data.get('attack', 1)
                                                slot_type = item_data.get('slot', 'right_hand')
                                                is_two_handed = item_data.get('two_handed', False)
                                                item = WeaponItem(name=name, attack=attack, slot_type=slot_type, is_two_handed=is_two_handed)
                                            elif item_type == 'shield':
                                                from src.systems.equipment_system import ShieldItem
                                                defense = item_data.get('defense', 1)
                                                item = ShieldItem(name=name, defense=defense)
                                            elif item_type == 'armor':
                                                from src.systems.equipment_system import ArmorItem
                                                defense = item_data.get('defense', 1)
                                                item = ArmorItem(name=name, defense=defense)
                                            else:
                                                continue
                                            
                                            # 装备到随从
                                            if hasattr(card, 'equipment') and card.equipment:
                                                # 直接装备，让装备系统处理槽位
                                                card.equipment.equip(item, game=self)
                                            
                                    except Exception as e:
                                        print(f"装备物品失败: {e}")
                                        pass
                        
                except Exception as e:
                    print(f"创建随从失败: {e}")
                    pass
        
        # 加载场景内容
        try:
            # 加载敌人
            enemies_data = data.get('enemies', [])
            for enemy_data in enemies_data:
                try:
                    if isinstance(enemy_data, dict):
                        name = enemy_data.get('name', '敌人')
                        attack = enemy_data.get('attack', enemy_data.get('atk', 0))
                        hp = enemy_data.get('hp', 1)
                        
                        # 创建敌人对象
                        from src.game_modes.entities import Enemy
                        enemy = Enemy(name=name, attack=attack, hp=hp)
                        
                        # 处理敌人掉落
                        drops = enemy_data.get('drops')
                        if drops:
                            enemy.drops = drops
                        
                        # 处理敌人亡语
                        on_death = enemy_data.get('on_death')
                        if on_death:
                            # 存储原始数据，不绑定方法
                            enemy.on_death_data = on_death
                        
                        # 处理敌人装备
                        equip_data = enemy_data.get('equip') if 'equip' in enemy_data else enemy_data.get('equipment')
                        if equip_data:
                            self._equip_enemy_from_json(enemy, equip_data)
                        
                        # 处理DND属性
                        dnd_data = enemy_data.get('dnd')
                        if dnd_data:
                            enemy.dnd = dnd_data
                        
                        # 处理其他属性
                        if 'tags' in enemy_data:
                            enemy.tags = enemy_data['tags']
                        if 'passive' in enemy_data:
                            enemy.passive = enemy_data['passive']
                        if 'passives' in enemy_data:
                            enemy.passives = enemy_data['passives']
                        if 'skills' in enemy_data:
                            enemy.skills = enemy_data['skills']
                        if 'profession' in enemy_data:
                            enemy.profession = enemy_data['profession']
                        if 'race' in enemy_data:
                            enemy.race = enemy_data['race']
                        
                        self.enemies.append(enemy)
                        
                except Exception as e:
                    print(f"创建敌人失败: {e}")
                    pass
            
            # 加载资源到背包
            resources_data = data.get('resources', [])
            for resource_data in resources_data:
                try:
                    if isinstance(resource_data, dict):
                        name = resource_data.get('name', '资源')
                        item_type = resource_data.get('type', 'material')
                        effect_value = resource_data.get('value', 1)
                        
                        # 根据类型创建不同的物品
                        if item_type == 'weapon':
                            from src.systems.equipment_system import WeaponItem
                            # 从资源数据中获取更多装备属性
                            slot_type = resource_data.get('slot', 'right_hand')
                            is_two_handed = resource_data.get('two_handed', False)
                            item = WeaponItem(name=name, attack=effect_value, slot_type=slot_type, is_two_handed=is_two_handed)
                        elif item_type == 'armor':
                            from src.systems.equipment_system import ArmorItem
                            item = ArmorItem(name=name, defense=effect_value)
                        elif item_type == 'shield':
                            from src.systems.equipment_system import ShieldItem
                            item = ShieldItem(name=name, defense=effect_value)
                        elif item_type == 'potion':
                            from src.systems.inventory import ConsumableItem
                            item = ConsumableItem(name=name, description=f"恢复{effect_value}点生命值")
                        else:
                            from src.systems.inventory import MaterialItem
                            item = MaterialItem(name=name, description=f"材料物品，价值{effect_value}")
                        
                        # 添加到背包
                        self.player.inventory.add_item(item)
                        
                except Exception as e:
                    print(f"创建资源失败: {e}")
                    pass
            
            # 加载专门的背包装备（如果有的话）
            inventory_equipment = data.get('inventory_equipment', [])
            for equip_data in inventory_equipment:
                try:
                    if isinstance(equip_data, dict):
                        name = equip_data.get('name', '装备')
                        item_type = equip_data.get('type', 'weapon')
                        
                        if item_type == 'weapon':
                            from src.systems.equipment_system import WeaponItem
                            attack = equip_data.get('attack', 1)
                            slot_type = equip_data.get('slot', 'right_hand')
                            is_two_handed = equip_data.get('two_handed', False)
                            item = WeaponItem(name=name, attack=attack, slot_type=slot_type, is_two_handed=is_two_handed)
                        elif item_type == 'shield':
                            from src.systems.equipment_system import ShieldItem
                            defense = equip_data.get('defense', 1)
                            item = ShieldItem(name=name, defense=defense)
                        elif item_type == 'armor':
                            from src.systems.equipment_system import ArmorItem
                            defense = equip_data.get('defense', 1)
                            item = ArmorItem(name=name, defense=defense)
                        else:
                            continue
                        
                        # 添加到背包
                        self.player.inventory.add_item(item)
                        
                except Exception as e:
                    print(f"创建背包装备失败: {e}")
                    pass
            
            # 加载inventory字段（兼容旧格式）
            inventory_data = data.get('inventory', {})
            if isinstance(inventory_data, dict) and 'items' in inventory_data:
                items_list = inventory_data['items']
                for item_data in items_list:
                    try:
                        if isinstance(item_data, dict):
                            name = item_data.get('name', '装备')
                            item_type = item_data.get('type', 'weapon')
                            
                            if item_type == 'weapon':
                                from src.systems.equipment_system import WeaponItem
                                attack = item_data.get('attack', 1)
                                slot_type = item_data.get('slot', 'right_hand')
                                is_two_handed = item_data.get('two_handed', False)
                                item = WeaponItem(name=name, attack=attack, slot_type=slot_type, is_two_handed=is_two_handed)
                            elif item_type == 'shield':
                                from src.systems.equipment_system import ShieldItem
                                defense = item_data.get('defense', 1)
                                item = ShieldItem(name=name, defense=defense)
                            elif item_type == 'armor':
                                from src.systems.equipment_system import ArmorItem
                                defense = item_data.get('defense', 1)
                                item = ArmorItem(name=name, defense=defense)
                            else:
                                continue
                            
                            # 添加到背包
                            self.player.inventory.add_item(item)
                            
                    except Exception as e:
                        print(f"创建inventory装备失败: {e}")
                        pass
                    
        except Exception as e:
            print(f"加载场景内容失败: {e}")
        
        return True
    
    def _equip_enemy_from_json(self, enemy, equip_data):
        """为敌人装备物品"""
        try:
            # 支持两种格式：equip.items 和 equipment 数组
            items_data = []
            if isinstance(equip_data, dict) and 'items' in equip_data:
                items_data = equip_data['items']
            elif isinstance(equip_data, list):
                items_data = equip_data
            
            for item_data in items_data:
                try:
                    if isinstance(item_data, dict):
                        name = item_data.get('name', '装备')
                        item_type = item_data.get('type', 'weapon')
                        
                        if item_type == 'weapon':
                            from src.systems.equipment_system import WeaponItem
                            attack = item_data.get('attack', 1)
                            slot_type = item_data.get('slot', 'right_hand')
                            is_two_handed = item_data.get('two_handed', False)
                            item = WeaponItem(name=name, attack=attack, slot_type=slot_type, is_two_handed=is_two_handed)
                        elif item_type == 'shield':
                            from src.systems.equipment_system import ShieldItem
                            defense = item_data.get('defense', 1)
                            item = ShieldItem(name=name, defense=defense)
                        elif item_type == 'armor':
                            from src.systems.equipment_system import ArmorItem
                            defense = item_data.get('defense', 1)
                            item = ArmorItem(name=name, defense=defense)
                        else:
                            continue
                        
                        # 装备到敌人
                        if hasattr(enemy, 'equipment') and enemy.equipment:
                            enemy.equipment.equip(item, game=self)
                        
                except Exception as e:
                    print(f"敌人装备物品失败: {e}")
                    pass
        except Exception as e:
            print(f"处理敌人装备失败: {e}")
            pass
    
    def _process_enemy_drops(self, enemy):
        """处理敌人死亡掉落"""
        try:
            if hasattr(enemy, 'drops') and enemy.drops:
                drops = enemy.drops
                for drop_data in drops:
                    try:
                        if isinstance(drop_data, str):
                            # 简单字符串掉落
                            from src.systems.inventory import MaterialItem
                            item = MaterialItem(name=drop_data, description=f"从{enemy.name}掉落")
                            self.player.inventory.add_item(item)
                        elif isinstance(drop_data, dict):
                            # 详细掉落配置
                            name = drop_data.get('name', '掉落物')
                            item_type = drop_data.get('type', 'material')
                            
                            if item_type == 'weapon':
                                from src.systems.equipment_system import WeaponItem
                                attack = drop_data.get('attack', drop_data.get('value', 1))
                                slot_type = drop_data.get('slot', 'right_hand')
                                is_two_handed = drop_data.get('two_handed', False)
                                item = WeaponItem(name=name, attack=attack, slot_type=slot_type, is_two_handed=is_two_handed)
                            elif item_type == 'armor':
                                from src.systems.equipment_system import ArmorItem
                                defense = drop_data.get('defense', drop_data.get('value', 1))
                                item = ArmorItem(name=name, defense=defense)
                            elif item_type == 'shield':
                                from src.systems.equipment_system import ShieldItem
                                defense = drop_data.get('defense', drop_data.get('value', 1))
                                item = ShieldItem(name=name, defense=defense)
                            elif item_type == 'potion':
                                from src.systems.inventory import ConsumableItem
                                effect_value = drop_data.get('value', 1)
                                item = ConsumableItem(name=name, description=f"恢复{effect_value}点生命值")
                            else:
                                from src.systems.inventory import MaterialItem
                                effect_value = drop_data.get('value', 1)
                                item = MaterialItem(name=name, description=f"材料物品，价值{effect_value}")
                            
                            self.player.inventory.add_item(item)
                            
                    except Exception as e:
                        print(f"处理掉落物品失败: {e}")
                        pass
        except Exception as e:
            print(f"处理敌人掉落失败: {e}")
            pass
    
    def is_game_over(self) -> bool:
        """检查游戏是否结束"""
        return not self.running or self.player.hp <= 0
    
    def save_game(self):
        """保存游戏"""
        try:
            if self.profile:
                self.profile.snapshot_inventory(self.player.inventory)
                self.profile.snapshot_party(self.player.board)
                self.profile.save()
                return True
        except Exception:
            pass
        return False
    
    def check_scene_transition(self) -> str:
        """检查是否应该切换场景（当所有敌人都被清除时）"""
        try:
            if len(self.enemies) == 0 and self._scene_meta:
                on_clear = self._scene_meta.get('on_clear')
                if isinstance(on_clear, dict) and on_clear.get('action') == 'transition':
                    to_scene = on_clear.get('to')
                    if to_scene:
                        return to_scene
        except Exception:
            pass
        return None
