"""
最小可用的单人 PvE 游戏实现：
- 使用 entities 与工厂，避免重复定义
- 提供基本出牌、回合、攻击敌人/Boss 与状态查询
- 易于扩展（可加入技能、掉落、区域事件等）
"""

from __future__ import annotations
from typing import List
from game_modes.entities import Enemy, Boss, ResourceItem
from game_modes.pve_content_factory import EnemyFactory, ResourceFactory, BossFactory
from core.player import Player


class SimplePvEGame:
    def __init__(self, player_name: str):
        self.player = Player(player_name, is_me=True, game=self)
        self.turn = 1
        self.running = True
        self.enemies: List[Enemy] = []
        self.resources: List[ResourceItem] = []
        self.boss: Boss = BossFactory.create_dragon_boss()
        self._init_board()

    # --- 初始化与状态 ---
    def _init_board(self):
        # 初始敌人 1-2 个
        self.enemies = [EnemyFactory.create_random_enemy() for _ in range(1)]
        # 初始资源 2-3 个
        self.resources = [
            ResourceFactory.create_wooden_sword(),
            ResourceFactory.create_random_resource(),
        ]
        # 起手 3 张
        self.player.hand.clear()
        for _ in range(3):
            self.player.draw_card()

    def get_state(self):
        return {
            'turn': self.turn,
            'player_hp': self.player.hp,
            'hand': [str(c) for c in self.player.hand],
            'board': [str(c) for c in self.player.board],
            'enemies': [str(e) for e in self.enemies],
            'boss': str(self.boss),
            'resources': [str(r) for r in self.resources],
        }

    # --- 回合流 ---
    def start_turn(self):
        # 重置随从攻击标记
        for c in self.player.board:
            c.can_attack = True

    def end_turn(self):
        # 敌人群体攻击：每个敌人造成 1 点伤害
        if self.enemies:
            dmg = len(self.enemies)
            self.player.take_damage(dmg)
        # 刷新资源与敌人（保持简单的上限）
        while len(self.resources) < 3:
            self.resources.append(ResourceFactory.create_random_resource())
        while len(self.enemies) < 1:
            self.enemies.append(EnemyFactory.create_random_enemy())
        self.turn += 1
        self.start_turn()

    # --- 行动 ---
    def play_card(self, idx: int):
        return self.player.play_card(idx)

    def attack_enemy(self, minion_idx: int, enemy_idx: int):
        if not (0 <= minion_idx < len(self.player.board)):
            return False, '随从序号无效'
        if not (0 <= enemy_idx < len(self.enemies)):
            return False, '敌人序号无效'
        m = self.player.board[minion_idx]
        if not m.can_attack:
            return False, '该随从本回合已攻击过'
        e = self.enemies[enemy_idx]
        # 互相伤害
        dead = e.take_damage(m.attack)
        if hasattr(e, 'attack'):
            m.take_damage(e.attack)
        m.can_attack = False
        if dead:
            e.on_death(self)
            self.enemies.pop(enemy_idx)
        if m.hp <= 0:
            self.player.board.remove(m)
        return True, '攻击成功'

    def attack_boss(self, minion_idx: int):
        if self.enemies:
            return False, '还有敌人存活，不能打Boss'
        if not (0 <= minion_idx < len(self.player.board)):
            return False, '随从序号无效'
        m = self.player.board[minion_idx]
        if not m.can_attack:
            return False, '该随从本回合已攻击过'
        died = self.boss.take_damage(m.attack)
        m.can_attack = False
        if died:
            self.running = False
            return True, 'Boss被击败！胜利！'
        return True, f'对Boss造成{m.attack}点伤害'

    # 兼容旧卡组接口（Battlecry等会调用）
    def draw(self, owner=None):
        return self.player.draw_card()
