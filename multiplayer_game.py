"""
多人游戏核心架构
支持多个玩家同时游戏，包含三大区域：
1. 玩家对战区域
2. 共同NPC敌人区域  
3. 公共资源区域
"""

import threading
import time
from enum import Enum

class GamePhase(Enum):
    """游戏阶段"""
    WAITING = "等待玩家"
    PREPARATION = "准备阶段"
    BATTLE = "战斗阶段"
    NPC_PHASE = "NPC回合"
    RESOURCE_PHASE = "资源阶段"
    GAME_OVER = "游戏结束"

class AreaType(Enum):
    """区域类型"""
    PLAYER_ARENA = "玩家竞技场"
    NPC_ZONE = "NPC敌人区"
    RESOURCE_ZONE = "公共资源区"

class MultiPlayerGame:
    """多人游戏管理器"""
    
    def __init__(self, max_players=4):
        self.max_players = max_players
        self.players = {}  # {player_id: Player对象}
        self.player_order = []  # 回合顺序
        self.current_player_index = 0
        self.phase = GamePhase.WAITING
        self.turn_number = 1
        
        # 三大区域
        self.player_arena = PlayerArena()
        self.npc_zone = NPCZone()
        self.resource_zone = ResourceZone()
        
        self.game_state_lock = threading.Lock()
        self.running = False
    
    def add_player(self, player_id, player_name):
        """添加玩家"""
        if len(self.players) >= self.max_players:
            return False, "游戏已满"
        
        if player_id in self.players:
            return False, "玩家已存在"
        
        from player import Player
        new_player = Player(player_name)
        new_player.player_id = player_id
        new_player.game = self
        
        self.players[player_id] = new_player
        self.player_order.append(player_id)
        
        print(f"玩家 {player_name} ({player_id}) 加入游戏")
        
        # 检查是否可以开始游戏
        if len(self.players) >= 2:  # 至少2个玩家才能开始
            self.phase = GamePhase.PREPARATION
        
        return True, "加入成功"
    
    def remove_player(self, player_id):
        """移除玩家"""
        if player_id in self.players:
            player_name = self.players[player_id].name
            del self.players[player_id]
            if player_id in self.player_order:
                self.player_order.remove(player_id)
            print(f"玩家 {player_name} 离开游戏")
            
            # 如果玩家太少，暂停游戏
            if len(self.players) < 2:
                self.phase = GamePhase.WAITING
    
    def get_current_player(self):
        """获取当前回合玩家"""
        if not self.player_order:
            return None
        return self.players[self.player_order[self.current_player_index]]
    
    def next_turn(self):
        """切换到下一个玩家回合"""
        self.current_player_index = (self.current_player_index + 1) % len(self.player_order)
        
        # 如果回到第一个玩家，增加回合数
        if self.current_player_index == 0:
            self.turn_number += 1
            # 执行NPC阶段
            self.npc_phase()
            # 执行资源阶段
            self.resource_phase()
    
    def npc_phase(self):
        """NPC敌人阶段"""
        print("\n=== NPC敌人回合 ===")
        self.npc_zone.execute_turn(self.players)
    
    def resource_phase(self):
        """公共资源阶段"""
        print("\n=== 资源更新阶段 ===")
        self.resource_zone.update_resources()
    
    def start_game(self):
        """开始游戏"""
        if len(self.players) < 2:
            return False, "至少需要2个玩家"
        
        self.running = True
        self.phase = GamePhase.BATTLE
        
        # 初始化各区域
        self.npc_zone.initialize()
        self.resource_zone.initialize()
        
        # 为每个玩家抽取初始手牌
        for player in self.players.values():
            for _ in range(3):
                player.draw_card()
        
        print("游戏开始！")
        return True, "游戏已开始"
    
    def get_game_state(self):
        """获取游戏状态用于显示"""
        return {
            'phase': self.phase.value,
            'turn': self.turn_number,
            'current_player': self.get_current_player().name if self.get_current_player() else None,
            'players': {pid: self._get_player_state(player) for pid, player in self.players.items()},
            'npc_zone': self.npc_zone.get_state(),
            'resource_zone': self.resource_zone.get_state()
        }
    
    def _get_player_state(self, player):
        """获取玩家状态"""
        return {
            'name': player.name,
            'hp': player.hp,
            'max_hp': player.max_hp,
            'hand_count': len(player.hand),
            'board_count': len(getattr(player, 'board', [])),
            'inventory_count': len(player.get_inventory_summary())
        }

class PlayerArena:
    """玩家竞技场区域"""
    
    def __init__(self):
        self.battles = {}  # {(player1_id, player2_id): battle_state}
        self.challenge_requests = {}  # 挑战请求
    
    def challenge_player(self, challenger_id, target_id):
        """发起挑战"""
        key = f"{challenger_id}_vs_{target_id}"
        self.challenge_requests[key] = {
            'challenger': challenger_id,
            'target': target_id,
            'timestamp': time.time()
        }
        return True
    
    def accept_challenge(self, challenger_id, target_id):
        """接受挑战"""
        key = f"{challenger_id}_vs_{target_id}"
        if key in self.challenge_requests:
            # 创建战斗实例
            battle_key = tuple(sorted([challenger_id, target_id]))
            self.battles[battle_key] = PlayerBattle(challenger_id, target_id)
            del self.challenge_requests[key]
            return True
        return False

class PlayerBattle:
    """玩家之间的战斗"""
    
    def __init__(self, player1_id, player2_id):
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.battlefield = None
        self.current_attacker = player1_id
        self.battle_turn = 1
    
    def execute_battle(self, game):
        """执行战斗回合"""
        # 这里实现玩家间战斗逻辑
        pass

class NPCZone:
    """NPC敌人区域"""
    
    def __init__(self):
        self.npcs = []
        self.difficulty_level = 1
        self.boss_present = False
    
    def initialize(self):
        """初始化NPC区域"""
        self.spawn_initial_npcs()
    
    def spawn_initial_npcs(self):
        """生成初始NPC"""
        from cards import Card
        
        # 生成一些基础NPC敌人
        npc1 = Card(2, 3)
        npc1.name = "哥布林战士"
        npc1.is_npc = True
        
        npc2 = Card(1, 4)
        npc2.name = "石头守卫"
        npc2.is_npc = True
        
        self.npcs = [npc1, npc2]
    
    def execute_turn(self, players):
        """执行NPC回合"""
        for npc in self.npcs:
            if hasattr(npc, 'npc_ai'):
                npc.npc_ai(players)
            else:
                # 默认AI：攻击生命值最低的玩家
                self.default_npc_ai(npc, players)
    
    def default_npc_ai(self, npc, players):
        """默认NPC AI"""
        if not players:
            return
        
        # 找到生命值最低的玩家
        target_player = min(players.values(), key=lambda p: p.hp)
        damage = npc.atk
        target_player.hp -= damage
        print(f"{npc.name} 对 {target_player.name} 造成 {damage} 点伤害")
    
    def get_state(self):
        """获取NPC区域状态"""
        return {
            'npcs': [{'name': npc.name, 'atk': npc.atk, 'hp': npc.hp} for npc in self.npcs],
            'difficulty': self.difficulty_level,
            'boss_present': self.boss_present
        }

class ResourceZone:
    """公共资源区域"""
    
    def __init__(self):
        self.available_resources = []
        self.resource_pool = []
        self.update_timer = 0
    
    def initialize(self):
        """初始化资源区域"""
        self.refresh_resources()
    
    def refresh_resources(self):
        """刷新可用资源"""
        from inventory import create_sample_items
        
        # 生成一些随机资源
        items = create_sample_items()
        self.available_resources = items[:3]  # 提供3个资源
        print("公共资源区域已刷新")
    
    def update_resources(self):
        """更新资源（每回合调用）"""
        self.update_timer += 1
        
        # 每3回合刷新一次资源
        if self.update_timer >= 3:
            self.refresh_resources()
            self.update_timer = 0
    
    def claim_resource(self, player_id, resource_index):
        """玩家领取资源"""
        if 0 <= resource_index < len(self.available_resources):
            resource = self.available_resources.pop(resource_index)
            return resource
        return None
    
    def get_state(self):
        """获取资源区域状态"""
        return {
            'available_resources': [{'name': r.name, 'type': type(r).__name__} for r in self.available_resources],
            'next_refresh': 3 - self.update_timer
        }

# 游戏实例管理器
class GameManager:
    """游戏管理器单例"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.games = {}  # {game_id: MultiPlayerGame}
            cls._instance.next_game_id = 1
        return cls._instance
    
    def create_game(self, max_players=4):
        """创建新游戏"""
        game_id = self.next_game_id
        self.next_game_id += 1
        
        game = MultiPlayerGame(max_players)
        self.games[game_id] = game
        
        return game_id, game
    
    def get_game(self, game_id):
        """获取游戏实例"""
        return self.games.get(game_id)
    
    def remove_game(self, game_id):
        """移除游戏"""
        if game_id in self.games:
            del self.games[game_id]

# 全局游戏管理器
game_manager = GameManager()
