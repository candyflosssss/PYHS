"""场景版 PvE 最小引擎
- 以场景 JSON 驱动：初始化敌人、资源、己方随从。
- 回合推进仅刷新随从可攻标记；其余按场景/指令驱动。
"""

from __future__ import annotations
from typing import List
import json
import os
import sys
from game_modes.entities import Enemy, ResourceItem
from game_modes.pve_content_factory import EnemyFactory, ResourceFactory
from core.player import Player
from core.cards import NormalCard
from ui import colors as C


class SimplePvEGame:
    def __init__(self, player_name: str):
        # 基本状态
        self.player = Player(player_name, is_me=True, game=self)
        self.turn = 1
        self.running = True
        self.enemies: list = []
        self.resources: list = []
        # 日志缓冲（控制器会读取并清空）
        self._log_buffer: list[str] = []
        # 场景管理：兼容源码与打包路径
        # 优先使用 <pkg>/scenes (源码运行常见)，其次使用 <pkg父>/scenes（GUI 打包可能放到根 scenes）
        pkg_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        # 考虑多种运行时布局：优先尝试 PyInstaller onefile 解包目录 (sys._MEIPASS)、
        # 然后是源码常见目录 <pkg>/scenes 与 父目录的 scenes
        candidates = []
        try:
            if getattr(sys, 'frozen', False):
                meipass = getattr(sys, '_MEIPASS', None)
                if meipass:
                    candidates.append(os.path.join(meipass, 'scenes'))
                    candidates.append(os.path.join(meipass, 'yyy', 'scenes'))
        except Exception:
            pass
        # 源码布局备选
        candidates.append(os.path.join(pkg_base, 'scenes'))
        candidates.append(os.path.join(os.path.dirname(pkg_base), 'scenes'))
        # 选第一个存在的，否则退回到第一个候选作为默认
        scene_base = None
        for p in candidates:
            try:
                if os.path.isdir(p):
                    scene_base = p
                    break
            except Exception:
                continue
        if not scene_base:
            scene_base = candidates[0]
        self._scene_base_dir = os.path.abspath(scene_base)
        # 初始化其它实例字段
        self.current_scene = None
        self.current_scene_title = None
        self._scene_meta = None  # 保存本场景的一些行为配置（如 on_clear）
        # 兼容旧接口
        self.resource_zone = self.resources
        self.players = {self.player.name: self.player}
        # 初始化默认场景
        self._init_board()

    # 调试用：返回内部候选场景根（按优先级）
    def _debug_scene_candidates(self) -> list[str]:
        pkg_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        candidates = []
        try:
            if getattr(sys, 'frozen', False):
                meipass = getattr(sys, '_MEIPASS', None)
                if meipass:
                    candidates.append(os.path.join(meipass, 'scenes'))
                    candidates.append(os.path.join(meipass, 'yyy', 'scenes'))
        except Exception:
            pass
        candidates.append(os.path.join(pkg_base, 'scenes'))
        candidates.append(os.path.join(os.path.dirname(pkg_base), 'scenes'))
        return [os.path.abspath(p) for p in candidates]

    def _write_scene_debug(self, lines: list[str]):
        """Append diagnostic lines to %LOCALAPPDATA%\PYHS\scene_debug.txt (safe, no raise)."""
        try:
            base = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'PYHS')
            os.makedirs(base, exist_ok=True)
            path = os.path.join(base, 'scene_debug.txt')
            from datetime import datetime
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"--- {datetime.now().isoformat()} ---\n")
                for l in lines:
                    f.write(str(l) + "\n")
                f.write("\n")
        except Exception:
            # swallow errors - debugging should not break game
            pass


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
            # 首先尝试基于 scenes 根目录
            candidate = os.path.join(self._scene_base_dir, scene_name_or_path)
            candidate = os.path.abspath(candidate)
            # 若不存在且当前场景已知，则基于当前场景所在目录回退解析（支持地图组内相对切换）
            if not os.path.exists(candidate) and self.current_scene:
                cur_dir = os.path.dirname(os.path.abspath(self.current_scene))
                alt = os.path.abspath(os.path.join(cur_dir, scene_name_or_path))
                scene_path = alt if os.path.exists(alt) else candidate
            else:
                scene_path = candidate
        else:
            scene_path = os.path.abspath(scene_path)
        data = {}
        try:
            with open(scene_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            msg = f"读取场景失败: {e}"
            self.log(msg)
            try:
                tries = [os.path.abspath(scene_path)]
                tries.extend(self._debug_scene_candidates())
            except Exception:
                tries = [scene_path]
            dbg = [msg, f"scene_base: {getattr(self, '_scene_base_dir', '?')}", "attempts:"] + tries
            try:
                self._write_scene_debug(dbg)
            except Exception:
                pass
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

        # 保存场景元数据（兜底跳转等）
        try:
            self._scene_meta = {
                'on_clear': data.get('on_clear'),
                'parent': data.get('parent') or data.get('back_to')
            }
        except Exception:
            self._scene_meta = None

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

    # 注意：不进行任何自动配装，完全以场景/玩家操作为准

        # 使用更友好的标题进行日志
        shown = self.current_scene_title or os.path.basename(scene_path)
        self.log(f"进入场景: {shown}")
        return True

    # --- 导航：返回上一级 ---
    def can_navigate_back(self) -> bool:
        try:
            return bool(self._scene_meta and self._scene_meta.get('parent'))
        except Exception:
            return False

    def navigate_back(self) -> bool:
        """尝试根据场景的 parent/back_to 字段返回上一级。"""
        try:
            meta = self._scene_meta or {}
            parent = meta.get('parent')
            if not parent:
                return False
            # 返回上一层通常需要保留当前随从
            return bool(self.transition_to_scene(parent, preserve_board=True))
        except Exception:
            return False

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
        # 若敌人已清空且场景定义 on_clear，则尝试切换，避免卡住
        if not self.enemies:
            self._check_on_clear_transition()

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
        from systems import skills as SK
        # 牧师：对己方目标时视为治疗（控制器命令仍是 a mN eN；此处聚焦对敌）
        # 这里的 a 指令默认敌方目标；若未来引入 a mN mK 则在控制器分支实现。

        # 对敌伤害
        prev_e = e.hp
        dead = e.take_damage(m.attack)
        dealt = max(0, prev_e - e.hp)
        self.log(f"{m} 攻击 {e.name}，造成 {dealt} 伤害（{e.hp}/{e.max_hp}）")

        # 反击判定：0 攻不反击、进攻方带 no_counter 不被反击
        if SK.should_counter(m, e):
            prev_m = m.hp
            m.take_damage(getattr(e, 'attack', 0))
            back = max(0, prev_m - m.hp)
            if back > 0:
                self.log(f"{e.name} 反击 {m}，造成 {back} 伤害（{m.hp}/{m.max_hp}）")
        m.can_attack = False
        if dead:
            # 若死亡效果触发场景切换，需避免继续操作已被重置的敌人列表
            prev_scene = self.current_scene
            # 亡语可能依赖多人接口，这里容错
            try:
                e.on_death(self)
            except Exception:
                pass
            # 若场景已发生变化（例如触发切换），直接返回
            if self.current_scene != prev_scene:
                return True, '攻击成功'
            # 否则按常规流程移除该敌人
            try:
                self.enemies.pop(enemy_idx)
            except Exception:
                # 防御性：索引可能已失效
                pass
            self.log(f"{e.name} 被消灭")
        if m.hp <= 0:
            self.player.board.remove(m)
        # 若清场且存在 on_clear 兜底切换，则尝试执行
        if not self.enemies:
            if self._check_on_clear_transition():
                return True, '攻击成功'
        return True, '攻击成功'

    # Boss 攻击逻辑已移除（场景模式无 Boss）

    # 兼容旧卡组接口（Battlecry等会调用）
    def draw(self, owner=None):
        return self.player.draw_card()

    # --- 日志 ---
    def log(self, text: str):
        # 控制器会在每次操作后读取并清空该缓冲
        # 确保日志无 ANSI 颜色码
        try:
            clean = C.strip(str(text))
        except Exception:
            clean = str(text)
        self._log_buffer.append(clean)

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

    # --- 兜底：清场触发 ---
    def _check_on_clear_transition(self) -> bool:
        """若场景元数据包含 on_clear 且敌人已清空，则执行跳转。
        返回是否发生了切换。
        """
        try:
            meta = self._scene_meta or {}
            oc = meta.get('on_clear') if isinstance(meta, dict) else None
            if isinstance(oc, dict) and oc.get('action') == 'transition':
                to_scene = oc.get('to')
                preserve = bool(oc.get('preserve_board', True))
                return bool(self.transition_to_scene(to_scene, preserve_board=preserve))
        except Exception:
            pass
        return False

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
                name = md.get('name')
                tags = md.get('tags')
                passive = md.get('passive') or md.get('passives')
                skills = md.get('skills')
                # 兼容 UGC 字段：透传到卡牌
                m = NormalCard(atk, hp, name=str(name) if name else None, tags=tags, passive=passive, skills=skills)
                # 初始装备（来自场景）：支持 equip / equipment 两种字段
                equip_data = md.get('equip') if 'equip' in md else md.get('equipment')
                if equip_data:
                    try:
                        self._equip_from_json(m, equip_data)
                    except Exception:
                        pass
                return m
            if isinstance(md, (list, tuple)) and len(md) >= 2:
                return NormalCard(int(md[0]), int(md[1]))
            return None
        except Exception:
            return None

    # --- 场景初始装备解析 ---
    def _equip_from_json(self, card, equip_data):
        """将场景 JSON 中定义的装备，装备到指定 card。
        支持格式：
        - 列表：[{type:'weapon|armor|shield', name:'...', attack:6, defense:4, slot:'left_hand|right_hand|armor', two_handed:true}]
        - 对象：{ items:[...同上...] }
        - 兼容简写：若直接是对象且包含 type/name，则按单件装备处理
        """
        try:
            from systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
        except Exception:
            return

        def to_list(data):
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                if 'items' in data and isinstance(data['items'], list):
                    return data['items']
                # 单件
                if any(k in data for k in ('type', 'name')):
                    return [data]
            return []

        items = to_list(equip_data)
        for it in items:
            if not isinstance(it, dict):
                continue
            t = str(it.get('type', '') or '').lower()
            name = it.get('name') or ('装备' if t else None)
            desc = it.get('desc') or it.get('description') or '场景初始装备'
            dur = int(it.get('durability', 100))
            atk = int(it.get('attack', it.get('atk', it.get('value', 0))))
            dfn = int(it.get('defense', it.get('def', it.get('value', 0))))
            slot = it.get('slot') or ('armor' if t == 'armor' else ('left_hand' if it.get('two_handed') else 'right_hand'))
            two = bool(it.get('two_handed', it.get('twoHanded', False)))
            try:
                if t == 'weapon':
                    w = WeaponItem(str(name), str(desc), dur, attack=atk, slot_type=str(slot), is_two_handed=two)
                    card.equipment.equip(w, game=self)
                elif t == 'armor':
                    a = ArmorItem(str(name), str(desc), dur, defense=dfn, slot_type='armor')
                    card.equipment.equip(a, game=self)
                elif t == 'shield':
                    s = ShieldItem(str(name), str(desc), dur, defense=dfn, attack=atk)
                    card.equipment.equip(s, game=self)
                else:
                    # 未知类型忽略
                    continue
            except Exception:
                # 单件失败时继续下一件
                continue

    #（无自动配装函数）
