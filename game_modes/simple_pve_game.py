"""
最小可用的单人 PvE 游戏实现（场景版）：
- 通过 JSON 场景文件初始化敌人区、资源区、己方随从区
- 不再在回合切换时自动抽牌、生成敌人/资源，也不包含 Boss 与友方英雄生命
- 易于扩展（可加入技能、掉落、区域事件等）
"""

from __future__ import annotations
from typing import List
import json
import os
from game_modes.entities import Enemy, ResourceItem
from game_modes.pve_content_factory import EnemyFactory, ResourceFactory
from core.player import Player
from core.cards import NormalCard


class SimplePvEGame:
    def __init__(self, player_name: str):
        # 基本状态
        self.player = Player(player_name, is_me=True, game=self)
        self.turn = 1
        self.running = True
        self.enemies: List[Enemy] = []
        self.resources: List[ResourceItem] = []
        # 日志缓冲（控制器会读取并清空）
        self._log_buffer: list[str] = []
        # 场景管理
        self._scene_base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scenes'))
        self.current_scene: str | None = None
        # 兼容旧接口
        self.resource_zone = self.resources
        self.players = {self.player.name: self.player}
        # 初始化默认场景
        self._init_board()


    # --- 初始化与状态 ---
    def _init_board(self):
        """从场景文件加载：默认读取 scenes/default_scene.json。
        格式示例：
        {
          "board": [ {"atk":2, "hp":3}, {"atk":1, "hp":4} ],
          "enemies": [ {"name":"哥布林"}, {"name":"骷髅"} ],
          "resources": [ {"name":"木剑"}, {"name":"生命药水"} ]
        }
        - board：若提供 atk/hp，则生成普通随从；也可后续扩展 type 指定卡类型
        - enemies：若提供已知名称，则使用工厂创建（含掉落）；否则可提供 {name,hp,attack}
        - resources：若提供已知名称，则使用工厂创建；否则可提供 {name,type(weapon/armor/shield/potion/material),value}
        """
        # 默认加载 default_scene.json
        self.load_scene('default_scene.json', keep_board=False)

    def load_scene(self, scene_name_or_path: str, keep_board: bool = False):
        """加载指定场景。
        - scene_name_or_path: 文件名或绝对路径
        - keep_board: 为 True 时保留当前随从区，并忽略新场景的 board
        """
        if not scene_name_or_path:
            return False
        scene_path = scene_name_or_path
        if not os.path.isabs(scene_path):
            scene_path = os.path.join(self._scene_base_dir, scene_name_or_path)
        scene_path = os.path.abspath(scene_path)
        data = {}
        try:
            with open(scene_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.log(f"读取场景失败: {e}")
            return False

        # 记录当前场景
        self.current_scene = scene_path

        # 清空/保留
        preserved_board = list(self.player.board) if keep_board else []
        self.enemies = []
        self.resources = []
        self.player.board.clear()
        self.player.hand.clear()  # 场景模式不自动发起手牌

        # 敌人
        for ed in data.get('enemies', []):
            e = self._make_enemy(ed)
            if e is not None:
                self.enemies.append(e)

        # 资源
        for rd in data.get('resources', []):
            r = self._make_resource(rd)
            if r is not None:
                self.resources.append(r)

        # 我方随从
        if keep_board and preserved_board:
            # 保留旧随从，忽略新场景 board
            self.player.board.extend(preserved_board)
        else:
            for md in data.get('board', []):
                m = self._make_minion(md)
                if m is not None:
                    self.player.board.append(m)

        self.log(f"进入场景: {os.path.basename(scene_path)}")
        return True

    def transition_to_scene(self, scene_name_or_path: str, preserve_board: bool = False):
        """场景切换：按需保留随从区"""
        ok = self.load_scene(scene_name_or_path, keep_board=preserve_board)
        if ok:
            # 切换场景后，回合不变，仅刷新随从可攻击标记
            self.start_turn()
        return ok

    def get_state(self):
        return {
            'turn': self.turn,
            'hand': [str(c) for c in self.player.hand],
            'board': [str(c) for c in self.player.board],
            'enemies': [str(e) for e in self.enemies],
            'resources': [str(r) for r in self.resources],
        }

    # --- 回合流 ---
    def start_turn(self):
        # 重置随从攻击标记
        for c in self.player.board:
            c.can_attack = True

    def end_turn(self):
        # 场景模式：无自动伤害/刷新，仅推进回合并恢复随从攻击
        self.turn += 1
        self.start_turn()

    # --- 行动 ---
    def play_card(self, idx: int, target=None):
        return self.player.play_card(idx, target)

    def attack_enemy(self, minion_idx: int, enemy_idx: int):
        if not (0 <= minion_idx < len(self.player.board)):
            return False, '随从序号无效'
        if not (0 <= enemy_idx < len(self.enemies)):
            return False, '敌人序号无效'
        m = self.player.board[minion_idx]
        if not m.can_attack:
            return False, '该随从本回合已攻击过'
        e = self.enemies[enemy_idx]
        # 互相伤害并记录具体数值
        prev_e = e.hp
        dead = e.take_damage(m.attack)
        dealt = max(0, prev_e - e.hp)
        self.log(f"{m} 攻击 {e.name}，造成 {dealt} 伤害（{e.hp}/{e.max_hp}）")
        if hasattr(e, 'attack'):
            prev_m = m.hp
            m.take_damage(e.attack)
            back = max(0, prev_m - m.hp)
            self.log(f"{e.name} 反击 {m}，造成 {back} 伤害（{m.hp}/{m.max_hp}）")
        m.can_attack = False
        if dead:
            # 亡语可能依赖多人接口，这里容错
            try:
                e.on_death(self)
            except Exception:
                pass
            self.enemies.pop(enemy_idx)
            self.log(f"{e.name} 被消灭")
        if m.hp <= 0:
            self.player.board.remove(m)
        return True, '攻击成功'

    # Boss 攻击逻辑已移除（场景模式无 Boss）

    # 兼容旧卡组接口（Battlecry等会调用）
    def draw(self, owner=None):
        return self.player.draw_card()

    # --- 日志 ---
    def log(self, text: str):
        # 控制器会在每次操作后读取并清空该缓冲
        self._log_buffer.append(str(text))

    def pop_logs(self) -> list[str]:
        logs = self._log_buffer[:]
        self._log_buffer.clear()
        return logs

    # --- 构造辅助 ---
    def _make_enemy(self, ed):
        # ed 可以是字符串名称或包含 name/hp/attack 的对象
        try:
            if isinstance(ed, str):
                name = ed
            else:
                name = ed.get('name')
            # 先尝试使用工厂（带亡语掉落）
            if name in ('哥布林', '地精'):
                return EnemyFactory.create_goblin()
            if name in ('兽人', '半兽人'):
                return EnemyFactory.create_orc()
            if name in ('骷髅',):
                return EnemyFactory.create_skeleton()
            # 否则使用通用 Enemy
            if isinstance(ed, dict):
                hp = int(ed.get('hp', 2))
                atk = int(ed.get('attack', ed.get('atk', 1)))
                drops = ed.get('drops')
                death_effect = None
                # on_death 行为：支持 {action:'transition', to:'scene2.json', preserve_board:true}
                od = ed.get('on_death') if isinstance(ed, dict) else None
                if isinstance(od, dict) and od.get('action') == 'transition':
                    to_scene = od.get('to')
                    preserve = bool(od.get('preserve_board', False))
                    def death_effect(game):
                        try:
                            game.transition_to_scene(to_scene, preserve_board=preserve)
                        except Exception:
                            pass
                if isinstance(drops, list):
                    def death_effect(game):
                        # 将定义的掉落加入资源区
                        for rd in drops:
                            # 名称映射（优先工厂）
                            res = None
                            if isinstance(rd, str):
                                mapping = {
                                    '木剑': ResourceFactory.create_wooden_sword,
                                    '铁剑': ResourceFactory.create_iron_sword,
                                    '生命药水': ResourceFactory.create_health_potion,
                                    '法力药水': ResourceFactory.create_mana_potion,
                                    '皮甲': ResourceFactory.create_leather_armor,
                                }
                                if rd in mapping:
                                    try:
                                        res = mapping[rd]()
                                    except Exception:
                                        res = None
                            elif isinstance(rd, dict):
                                try:
                                    rname = rd.get('name', '资源')
                                    rtype = rd.get('type', 'material')
                                    rval = int(rd.get('value', 1))
                                    res = ResourceItem(rname, rtype, rval)
                                except Exception:
                                    res = None
                            if res is not None:
                                try:
                                    game.resource_zone.append(res)
                                except Exception:
                                    pass
                return Enemy(name or '敌人', atk, hp, death_effect)
            return None
        except Exception:
            return None

    def _make_resource(self, rd):
        # rd 可以是字符串名称或包含 name/type/value 的对象
        try:
            if isinstance(rd, str):
                name = rd
            else:
                name = rd.get('name')
            # 工厂映射
            mapping = {
                '木剑': ResourceFactory.create_wooden_sword,
                '铁剑': ResourceFactory.create_iron_sword,
                '生命药水': ResourceFactory.create_health_potion,
                '法力药水': ResourceFactory.create_mana_potion,
                '皮甲': ResourceFactory.create_leather_armor,
            }
            if name in mapping:
                return mapping[name]()
            # 否则通用 ResourceItem
            if isinstance(rd, dict):
                item_type = rd.get('type', 'material')
                value = int(rd.get('value', 1))
                return ResourceItem(name or '资源', item_type, value)
            return None
        except Exception:
            return None

    def _make_minion(self, md):
        # md 期望 {atk,hp}，生成普通随从；可扩展 type -> 不同卡
        try:
            if isinstance(md, dict):
                atk = int(md.get('atk', 1))
                hp = int(md.get('hp', 1))
                return NormalCard(atk, hp)
            if isinstance(md, (list, tuple)) and len(md) >= 2:
                return NormalCard(int(md[0]), int(md[1]))
            return None
        except Exception:
            return None
