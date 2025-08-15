"""
PvE多人游戏核心实现（精简版）
保留核心机制，抽离通用实体，提升可读性与扩展性。
"""

import threading
from enum import Enum
from core.player import Player
from core.cards import draw_card
from game_modes.entities import Enemy, ResourceItem, Boss
import random

class GamePhase(Enum):
    """游戏阶段"""
    WAITING = "等待玩家"
    PREPARATION = "准备阶段"  
    PLAYING = "游戏进行中"
    SYSTEM_TURN = "系统回合"
    PLAYER_TURN = "玩家回合"
    GAME_OVER = "游戏结束"

class PvEMultiplayerGame:
    """PvE多人游戏管理器"""
    
    def __init__(self, server_player_id=None):
        self.server_player_id = server_player_id  # 服务器玩家（房主）
        self.players = {}  # {player_id: Player对象}
        self.player_order = []  # 回合顺序
        self.current_player_index = 0
        self.phase = GamePhase.WAITING
        self.turn_number = 0
        self.system_turn_count = 0
        
        # 游戏区域
        self.resource_zone = []  # 资源区
        self.enemy_zone = []    # 敌人区
        self.boss = Boss()      # Boss
        
        # 游戏状态锁
        self.game_state_lock = threading.Lock()
        self.running = False
        
        # 为了保持兼容性，每个玩家有自己的战场
        # 但这里的战场主要用于玩家自己的随从
    
    def add_player(self, player_id, player_name):
        """添加玩家到游戏"""
        with self.game_state_lock:
            if player_id in self.players:
                return False, "玩家已存在"
            
            if self.phase not in [GamePhase.WAITING, GamePhase.PREPARATION]:
                return False, "游戏已开始，无法加入"
            
            # 创建玩家
            player = Player(player_name, is_me=(player_id == self.server_player_id))
            player.player_id = player_id
            player.game = self
            
            # 添加到游戏
            self.players[player_id] = player
            self.player_order.append(player_id)
            
            return True, f"玩家 {player_name} 已加入游戏"
    
    def remove_player(self, player_id):
        """移除玩家"""
        with self.game_state_lock:
            if player_id in self.players:
                player = self.players[player_id]
                del self.players[player_id]
                if player_id in self.player_order:
                    self.player_order.remove(player_id)
                return True
            return False
    
    def start_preparation(self):
        """开始准备阶段（仅服务器玩家可调用）"""
        with self.game_state_lock:
            if len(self.players) < 1:
                return False, "至少需要1个玩家"
            
            self.phase = GamePhase.PREPARATION
            
            # 初始化每个玩家：发3张初始手牌
            for player in self.players.values():
                player.hand = []
                for _ in range(3):
                    player.draw_card()
                # 清空战场 - 使用简单列表代替battlefield对象
                player.board = []  # 玩家战场上的随从
            
            # 初始化游戏区域
            self._initialize_zones()
            
            return True, "进入准备阶段"
    
    def start_game(self):
        """开始游戏（仅服务器玩家可调用）"""
        with self.game_state_lock:
            if self.phase != GamePhase.PREPARATION:
                return False, "必须在准备阶段才能开始游戏"
            
            self.phase = GamePhase.PLAYING
            self.running = True
            self.turn_number = 1
            self.current_player_index = 0
            
            # 开始第一个系统回合
            self._start_system_turn()
            
            return True, "游戏开始！"
    
    def _initialize_zones(self):
        """初始化游戏区域"""
        from game_modes.pve_content_factory import ResourceFactory, EnemyFactory, BossFactory
        
        player_count = len(self.players)
        
        # 资源区最大数量 = 玩家数 + 3
        max_resources = player_count + 3
        self.resource_zone = []
        for i in range(max_resources):
            # 使用工厂创建多样化的资源
            if i < 2:  # 前两个是木剑
                resource = ResourceFactory.create_wooden_sword()
            else:
                resource = ResourceFactory.create_random_resource()
            self.resource_zone.append(resource)
        
        # 敌人区最大数量 = 玩家数
        max_enemies = player_count
        self.enemy_zone = []
        for i in range(max_enemies):
            # 使用工厂创建多样化的敌人
            enemy = EnemyFactory.create_random_enemy()
            self.enemy_zone.append(enemy)
        
        # 创建随机Boss
        import random
        boss_types = [
            BossFactory.create_dragon_boss,
            BossFactory.create_demon_boss,
            BossFactory.create_lich_boss
        ]
        self.boss = random.choice(boss_types)()
    
    def _start_system_turn(self):
        """开始系统回合"""
        self.phase = GamePhase.SYSTEM_TURN
        self.system_turn_count += 1
        
        # 敌人攻击：根据敌人区存在的敌人数，对所有人造成等量伤害
        enemy_count = len(self.enemy_zone)
        if enemy_count > 0:
            for player in self.players.values():
                player.hp -= enemy_count
                if player.hp < 0:
                    player.hp = 0
        
        # 填充资源区和敌人区
        self._refill_zones()
        
        # 重置所有玩家随从的攻击状态
        for player in self.players.values():
            for card in player.board:  # 使用简化的board列表
                card.can_attack = True
        
        # 系统回合结束，开始玩家回合
        self.phase = GamePhase.PLAYER_TURN
        self.current_player_index = 0
    
    def _refill_zones(self):
        """根据在场人数填充资源区和敌人区"""
        from game_modes.pve_content_factory import ResourceFactory, EnemyFactory
        
        player_count = len(self.players)
        
        # 填充资源区到最大容量
        max_resources = player_count + 3
        while len(self.resource_zone) < max_resources:
            resource = ResourceFactory.create_random_resource()
            self.resource_zone.append(resource)
        
        # 填充敌人区到最大容量
        max_enemies = player_count
        while len(self.enemy_zone) < max_enemies:
            enemy = EnemyFactory.create_random_enemy()
            self.enemy_zone.append(enemy)
    
    def get_current_player(self):
        """获取当前回合玩家"""
        if (self.phase == GamePhase.PLAYER_TURN and 
            0 <= self.current_player_index < len(self.player_order)):
            player_id = self.player_order[self.current_player_index]
            return self.players.get(player_id)
        return None
    
    def next_turn(self):
        """下一个回合"""
        with self.game_state_lock:
            if self.phase != GamePhase.PLAYER_TURN:
                return
            
            # 当前玩家抽一张牌
            current_player = self.get_current_player()
            if current_player:
                current_player.draw_card()
            
            self.current_player_index += 1
            
            # 如果所有玩家都完成了回合，开始新的系统回合
            if self.current_player_index >= len(self.player_order):
                self.turn_number += 1
                self._start_system_turn()
            else:
                # 重置新玩家随从的攻击状态
                next_player = self.get_current_player()
                if next_player:
                    for card in next_player.board:  # 使用简化的board列表
                        card.can_attack = True
    
    def collect_resource(self, player_id, resource_index):
        """收集资源"""
        with self.game_state_lock:
            if (resource_index < 0 or resource_index >= len(self.resource_zone) or
                player_id not in self.players):
                return None
            
            resource = self.resource_zone.pop(resource_index)
            player = self.players[player_id]
            
            # 将资源添加到玩家背包
            if hasattr(player, 'inventory'):
                # 创建一个简单的物品对象用于背包系统
                from systems.inventory import Item
                item = Item(resource.name, resource.item_type, max_stack=10)
                player.inventory.add_item(item, 1)
            
            return resource
    
    def attack_enemy(self, player_id, attacker_index, enemy_index):
        """攻击敌人"""
        with self.game_state_lock:
            if player_id not in self.players:
                return False, "玩家不存在"
            
            player = self.players[player_id]
            
            # 获取攻击者（玩家的随从）
            if attacker_index < 0 or attacker_index >= len(player.board):
                return False, "无效的攻击者"
            
            attacker = player.board[attacker_index]
            if not attacker.can_attack:
                return False, "该随从本回合已攻击过"
            
            # 获取目标敌人
            if enemy_index < 0 or enemy_index >= len(self.enemy_zone):
                return False, "无效的敌人目标"
            
            enemy = self.enemy_zone[enemy_index]
            
            # 执行战斗
            self._resolve_combat(attacker, enemy)
            
            # 检查敌人是否死亡
            if enemy.hp <= 0:
                enemy.on_death(self)
                self.enemy_zone.remove(enemy)
            
            # 检查攻击者是否死亡
            if attacker.hp <= 0:
                player.board.remove(attacker)
            
            return True, f"攻击成功"
    
    def attack_boss(self, player_id, attacker_index):
        """攻击Boss（仅当敌人区无敌人时）"""
        with self.game_state_lock:
            if len(self.enemy_zone) > 0:
                return False, "敌人区还有敌人，无法攻击Boss"
            
            if player_id not in self.players:
                return False, "玩家不存在"
            
            player = self.players[player_id]
            
            # 获取攻击者
            if attacker_index < 0 or attacker_index >= len(player.board):
                return False, "无效的攻击者"
            
            attacker = player.board[attacker_index]
            if not attacker.can_attack:
                return False, "该随从本回合已攻击过"
            
            # 攻击Boss
            boss_died = self.boss.take_damage(attacker.attack)
            attacker.can_attack = False
            
            if boss_died:
                self.phase = GamePhase.GAME_OVER
                return True, "Boss被击败！游戏胜利！"
            
            return True, f"对Boss造成{attacker.attack}点伤害"
    
    def attack_player_minion(self, attacker_player_id, attacker_index, target_player_id, target_index):
        """攻击其他玩家的随从"""
        with self.game_state_lock:
            if (attacker_player_id not in self.players or 
                target_player_id not in self.players):
                return False, "玩家不存在"
            
            attacker_player = self.players[attacker_player_id]
            target_player = self.players[target_player_id]
            
            # 获取攻击者
            if (attacker_index < 0 or 
                attacker_index >= len(attacker_player.board)):
                return False, "无效的攻击者"
            
            attacker = attacker_player.board[attacker_index]
            if not attacker.can_attack:
                return False, "该随从本回合已攻击过"
            
            # 获取目标
            if (target_index < 0 or 
                target_index >= len(target_player.board)):
                return False, "无效的目标"
            
            target = target_player.board[target_index]
            
            # 执行战斗
            self._resolve_combat(attacker, target)
            
            # 检查死亡
            if target.hp <= 0:
                target_player.board.remove(target)
            
            if attacker.hp <= 0:
                attacker_player.board.remove(attacker)
            
            return True, f"攻击成功"
    
    def get_game_state(self):
        """获取游戏状态"""
        with self.game_state_lock:
            return {
                'phase': self.phase.value,
                'turn_number': self.turn_number,
                'system_turn_count': self.system_turn_count,
                'current_player_index': self.current_player_index,
                'players': {pid: {
                    'name': p.name,
                    'hp': p.hp,
                    'max_hp': p.max_hp,
                    'hand_count': len(p.hand),
                    'board_count': len(p.board)  # 使用简化的board列表
                } for pid, p in self.players.items()},
                'player_order': self.player_order,
                'resource_zone': [str(r) for r in self.resource_zone],
                'enemy_zone': [str(e) for e in self.enemy_zone],
                'boss': str(self.boss),
                'running': self.running
            }
    
    def draw(self, owner):
        """抽牌逻辑（兼容旧卡牌系统）"""
        # 在PvE模式中，owner应该是一个玩家ID或者"me"/"op"的标识
        # 我们需要找到对应的玩家并让其抽牌
        current_player = self.get_current_player()
        if current_player:
            return current_player.draw_card()
        return None

    # --- 内部工具 ---
    def _resolve_combat(self, attacker, defender):
        """简化的战斗解析：双方互相造成一次伤害并标记攻击过"""
        defender.take_damage(attacker.attack)
        if hasattr(defender, 'attack'):
            attacker.take_damage(defender.attack)
        attacker.can_attack = False

class PvEGameManager:
    """PvE游戏管理器"""
    
    def __init__(self):
        self.games = {}  # {game_id: PvEMultiplayerGame}
        self.next_game_id = 1
    
    def create_game(self, server_player_id):
        """创建新游戏"""
        game_id = self.next_game_id
        self.next_game_id += 1
        
        game = PvEMultiplayerGame(server_player_id)
        self.games[game_id] = game
        
        return game_id, game
    
    def get_game(self, game_id):
        """获取游戏"""
        return self.games.get(game_id)
    
    def remove_game(self, game_id):
        """移除游戏"""
        if game_id in self.games:
            del self.games[game_id]
            return True
        return False
