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
        # skill dispatch map
        self.skill_map = {
            'sweep': self._skill_sweep,
            'basic_heal': self._skill_basic_heal,
            'drain': self._skill_drain,
            'taunt': self._skill_taunt,
            'arcane_missiles': self._skill_arcane_missiles,
        }

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

    def _to_character_sheet(self, entity):
        """Map a Combatant-like entity to a minimal CharacterSheet for DND computations."""
        try:
            from systems.dnd_rules import CharacterSheet, Attributes
        except Exception:
            return None
        try:
            name = getattr(entity, 'display_name', None) or getattr(entity, 'name', None) or str(entity)
            # 基于 entity.dnd 构造角色卡
            dnd = getattr(entity, 'dnd', None)
            if isinstance(dnd, dict):
                attrs = dnd.get('attrs') or dnd.get('attributes') or {}
                A = Attributes(
                    str=int(attrs.get('str', attrs.get('STR', 10) or 10)),
                    dex=int(attrs.get('dex', attrs.get('DEX', 10) or 10)),
                    con=int(attrs.get('con', attrs.get('CON', 10) or 10)),
                    int=int(attrs.get('int', attrs.get('INT', 10) or 10)),
                    wis=int(attrs.get('wis', attrs.get('WIS', 10) or 10)),
                    cha=int(attrs.get('cha', attrs.get('CHA', 10) or 10)),
                )
                cs = CharacterSheet(name, level=int(dnd.get('level', 1) or 1))
                cs.attrs = A
                cs.bonuses = dict(dnd.get('bonuses', {}))
                if dnd.get('ac') is not None:
                    cs.ac = int(dnd.get('ac'))
            else:
                cs = CharacterSheet(name)
            # 若未指定 AC，则用 10 + defense 做基础
            try:
                dfn = int(entity.get_total_defense()) if hasattr(entity, 'get_total_defense') else int(getattr(entity, 'defense', 0))
                if cs.ac is None:
                    cs.ac = 10 + dfn
            except Exception:
                pass
            return cs
        except Exception:
            return None

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
        if not getattr(m, 'can_attack', True):
            return False, '该随从本回合已攻击过'
        e = self.enemies[enemy_idx]
        # 使用 DND 规则判定命中与伤害（保留向后兼容）
        try:
            from systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = None
            roll_damage = None

        weapon_bonus = 0
        is_proficient = False
        th = None
        dmg_r = None

        if to_hit_roll:
            att_sheet = self._to_character_sheet(m)
            def_sheet = self._to_character_sheet(e)
            th = to_hit_roll(attacker=att_sheet, defender=def_sheet,
                             weapon_bonus=weapon_bonus, use_str=True, is_proficient=is_proficient)
            # 暂不单独输出 to_hit 行，改为合并到攻击摘要里；meta 仍携带
            if not th.get('hit'):
                # 汇总一条更可读的未命中信息
                roll = th.get('roll'); total = th.get('total'); need = th.get('needed')
                bonus = (total - roll) if isinstance(roll, int) and isinstance(total, int) else None
                hit_line = f"d20={roll} + 加值{bonus} = {total} vs AC {need}" if bonus is not None else f"d20={roll} vs AC {need}"
                text = f"{m} 攻击 {getattr(e,'name',e)}: 未命中；{hit_line}"
                self.log({'type': 'attack', 'text': text, 'meta': {'to_hit': th}})
                m.can_attack = False
                return True, '攻击未命中'
            dmg_spec = (1, max(1, int(m.get_total_attack()))) if hasattr(m, 'get_total_attack') else (1, 1)
            if roll_damage:
                dmg_r = roll_damage(att_sheet, dice=dmg_spec, damage_bonus=0, critical=th.get('critical', False))
                dealt = int(dmg_r.get('total', 0))
            else:
                dealt = int(m.get_total_attack() if hasattr(m, 'get_total_attack') else getattr(m, 'attack', 0))
        else:
            # 兼容旧流程：直接以攻击力造成伤害
            dealt = int(m.get_total_attack() if hasattr(m, 'get_total_attack') else getattr(m, 'attack', 0))

        prev_e = getattr(e, 'hp', 0)
        dead = e.take_damage(dealt)
        dealt = max(0, prev_e - getattr(e, 'hp', 0))
        # 组合为一条更可读的攻击信息
        if th:
            roll = th.get('roll'); total = th.get('total'); need = th.get('needed'); crit = th.get('critical')
            bonus = (total - roll) if isinstance(roll, int) and isinstance(total, int) else None
            hit_line = f"d20={roll} + 加值{bonus} = {total} vs AC {need}" if bonus is not None else f"d20={roll} vs AC {need}"
            if dmg_r:
                dice_rolls = dmg_r.get('dice_rolls'); dice_total = dmg_r.get('dice_total'); bonus_dmg = dmg_r.get('bonus')
                dmg_line = f"伤害 {dice_total}+{bonus_dmg}={dealt}" if isinstance(dice_total, int) and isinstance(bonus_dmg, int) else f"伤害 {dealt}"
            else:
                dmg_line = f"伤害 {dealt}"
            hp_line = f"HP {prev_e} → {getattr(e,'hp',0)}"
            crit_note = "（致命一击）" if crit else ""
            text = f"{m} 攻击 {getattr(e,'name',e)}: 命中{crit_note}；{hit_line}；{dmg_line}；{hp_line}"
        else:
            text = f"{m} 攻击 {getattr(e,'name',e)}，造成 {dealt} 伤害（{getattr(e,'hp',0)}/{getattr(e,'max_hp',0)}）"
        self.log({'type': 'attack', 'text': text, 'meta': {'to_hit': th, 'damage': dmg_r, 'target': {'hp_before': prev_e, 'hp_after': getattr(e,'hp',0)}}})

        # 反击判定：0 攻不反击、进攻方带 no_counter 不被反击
        from systems import skills as SK
        try:
            if SK.should_counter(m, e):
                prev_m = m.hp
                m.take_damage(getattr(e, 'attack', 0))
                back = max(0, prev_m - m.hp)
                if back > 0:
                    self.log(f"{e.name} 反击 {m}，造成 {back} 伤害（{m.hp}/{m.max_hp}）")
        except Exception:
            # 容错：若判定失败，不阻塞流程
            pass
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

    # --- 技能实现（基础版，使用 dnd_rules 做判定与掷骰） ---
    def use_skill(self, skill_name: str, source_idx: int, target_token: str = None):
        """Public entry to invoke a named skill from a minion (1-based index).
        skill_name: 名称，如 'sweep'、'basic_heal' 等
        source_idx: minion index (1-based)
        target_token: 'eN' or 'mN' 或 None
        """
        try:
            func = self.skill_map.get(skill_name)
            if not func:
                return False, f'未知技能: {skill_name}'
            # resolve source
            if not (1 <= source_idx <= len(self.player.board)):
                return False, '随从索引无效'
            src = self.player.board[source_idx - 1]
            # resolve target
            tgt = None
            if target_token:
                if target_token.startswith('e') and target_token[1:].isdigit():
                    ei = int(target_token[1:]) - 1
                    if 0 <= ei < len(self.enemies):
                        tgt = self.enemies[ei]
                if target_token.startswith('m') and target_token[1:].isdigit():
                    mi = int(target_token[1:]) - 1
                    if 0 <= mi < len(self.player.board):
                        tgt = self.player.board[mi]
            return func(src, tgt)
        except Exception as e:
            try:
                self.log({'type': 'error', 'text': f'技能执行出错: {e}', 'meta': {}})
            except Exception:
                pass
            return False, '技能执行失败'

    def _skill_sweep(self, src, tgt):
        """横扫：对所有敌人进行一次攻击判定并造成源攻击力的一半伤害（向下取整）。"""
        try:
            from systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = roll_damage = None
        hits = []
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        dmg_each = max(0, atk_val // 2)
        for i, e in enumerate(list(self.enemies)):
            # simple to-hit
            hit = True
            meta = {}
            if to_hit_roll:
                th = to_hit_roll(self._to_character_sheet(src), self._to_character_sheet(e), use_str=True, weapon_bonus=0, is_proficient=False)
                hit = th['hit']
                meta['to_hit'] = th
            if hit:
                prev = e.hp
                # 用 DND 掷骰描述伤害（1d(dmg_each)）
                dmg_r = None
                if roll_damage and dmg_each > 0:
                    dmg_r = roll_damage(self._to_character_sheet(src), dice=(1, max(1, dmg_each)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False)
                    amount = int(dmg_r['total'])
                else:
                    amount = dmg_each
                dead = e.take_damage(amount)
                dealt = max(0, prev - e.hp)
                meta['damage'] = dmg_r
                meta['target'] = {'hp_before': prev, 'hp_after': e.hp}
                self.log({'type': 'skill', 'text': f"{src} 使用 横扫 对 {e.name} 造成 {dealt} 伤害", 'meta': meta})
                if dead:
                    try:
                        e.on_death(self)
                    except Exception:
                        pass
            else:
                self.log({'type': 'skill', 'text': f"{src} 使用 横扫 未命中 {e.name}", 'meta': meta})
        src.can_attack = False
        return True, '横扫 执行完毕'

    def _skill_basic_heal(self, src, tgt):
        """基础治疗：对目标恢复固定生命（例如 3 点）。"""
        if tgt is None:
            return False, '未选择目标'
        heal = 3
        prev = getattr(tgt, 'hp', 0)
        try:
            tgt.heal(heal)
        except Exception:
            try:
                tgt.hp = min(getattr(tgt, 'max_hp', prev), prev + heal)
            except Exception:
                pass
        self.log({'type': 'skill', 'text': f"{src} 对 {getattr(tgt, 'name', tgt)} 恢复 {heal} 点生命", 'meta': {'heal': heal, 'target': {'hp_before': prev, 'hp_after': getattr(tgt, 'hp', prev)}}})
        return True, '治疗完成'

    def _skill_drain(self, src, tgt):
        """汲取：对单体命中造成伤害并将伤害值转化为自身生命恢复。"""
        if tgt is None:
            return False, '未选择目标'
        try:
            from systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = roll_damage = None
        meta = {}
        hit = True
        if to_hit_roll:
            th = to_hit_roll(self._to_character_sheet(src), self._to_character_sheet(tgt), use_str=True, weapon_bonus=0, is_proficient=False)
            hit = th['hit']
            meta['to_hit'] = th
        if not hit:
            self.log({'type': 'skill', 'text': f"{src} 的 汲取 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
            return True, '未命中'
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        prev = getattr(tgt, 'hp', 0)
        # 用 DND 掷骰造成伤害：1dATK
        dmg_r = roll_damage(self._to_character_sheet(src), dice=(1, max(1, atk_val)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False) if roll_damage else None
        amount = int(dmg_r['total']) if dmg_r else atk_val
        dead = tgt.take_damage(amount)
        dealt = max(0, prev - getattr(tgt, 'hp', prev))
        # 恢复自身
        try:
            src.heal(dealt)
        except Exception:
            try:
                src.hp = min(getattr(src, 'max_hp', getattr(src, 'hp', 0) + dealt), getattr(src, 'hp', 0) + dealt)
            except Exception:
                pass
        meta['damage'] = dmg_r
        meta['lifesteal'] = dealt
        meta['target'] = {'hp_before': prev, 'hp_after': getattr(tgt, 'hp', prev)}
        self.log({'type': 'skill', 'text': f"{src} 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 汲取伤害并恢复 {dealt} 点生命", 'meta': meta})
        return True, '汲取完成'

    def _skill_taunt(self, src, tgt):
        """嘲讽：为自己添加 taunt 标记（仇恨），使敌人偏向攻击该目标（场景模式暂不实现复杂 AI）。"""
        try:
            src.add_tag('taunt')
        except Exception:
            try:
                if not hasattr(src, 'tags'):
                    src.tags = set()
                src.tags.add('taunt')
            except Exception:
                pass
        self.log({'type': 'skill', 'text': f"{src} 施放 嘲讽，吸引仇恨", 'meta': {'tags_added': ['taunt']}})
        return True, '嘲讽已施放'

    def _skill_arcane_missiles(self, src, tgt):
        """奥术飞弹：对单体或随机敌人造成 1d4+1 的魔法伤害，分多次命中。
        为简化，向目标投掷 3 次 1d4+1，每次独立判定与伤害。
        """
        import random
        try:
            from systems.dnd_rules import roll_damage
        except Exception:
            roll_damage = None
        try:
            if tgt is None:
                if not self.enemies:
                    return False, '无敌人'
                tgt = random.choice(self.enemies)
            total = 0
            meta_all = {'bolts': []}
            for _ in range(3):
                prev = getattr(tgt, 'hp', 0)
                if roll_damage:
                    dmg_r = roll_damage(self._to_character_sheet(src), dice=(1, 4), damage_bonus=1, critical=False)
                    amount = int(dmg_r['total'])
                else:
                    r = random.randint(1, 4) + 1
                    dmg_r = {'total': r, 'dice_rolls': [], 'dice_total': 0, 'bonus': 0}
                    amount = r
                dead = tgt.take_damage(amount)
                dealt = max(0, prev - getattr(tgt, 'hp', prev))
                total += dealt
                bolt_meta = {'damage': dmg_r, 'target': {'hp_before': prev, 'hp_after': getattr(tgt, 'hp', prev)}}
                meta_all['bolts'].append(bolt_meta)
                self.log({'type': 'skill', 'text': f"{src} 的 奥术飞弹 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 点伤害", 'meta': bolt_meta})
                if dead:
                    try:
                        tgt.on_death(self)
                    except Exception:
                        pass
                    break
            meta_all['total'] = total
            self.log({'type': 'skill', 'text': f"奥术飞弹 总计造成 {total} 点伤害", 'meta': meta_all})
            return True, '奥术飞弹 完成'
        except Exception:
            return False, '奥术飞弹 失败'

    # Boss 攻击逻辑已移除（场景模式无 Boss）

    # 兼容旧卡组接口（Battlecry等会调用）
    def draw(self, owner=None):
        return self.player.draw_card()

    # --- 日志 ---
    def log(self, entry):
        """Append a structured log entry.

        Accepts either a string (back-compat) or a dict with optional fields:
        { 'type': 'info'|'to_hit'|'damage'|'heal'|'skill', 'text': str, 'meta': {...} }
        """
        try:
            if isinstance(entry, str):
                clean = C.strip(entry)
                self._log_buffer.append({'type': 'info', 'text': clean, 'meta': {}})
            elif isinstance(entry, dict):
                # ensure text and type exist
                t = entry.get('text') if isinstance(entry.get('text'), str) else str(entry)
                typ = entry.get('type') or 'info'
                meta = entry.get('meta') or {}
                self._log_buffer.append({'type': typ, 'text': C.strip(t), 'meta': meta})
            else:
                # fallback to str
                self._log_buffer.append({'type': 'info', 'text': C.strip(str(entry)), 'meta': {}})
        except Exception:
            try:
                self._log_buffer.append({'type': 'info', 'text': C.strip(str(entry)), 'meta': {}})
            except Exception:
                # last resort: append raw
                self._log_buffer.append({'type': 'info', 'text': str(entry), 'meta': {}})

    def pop_logs(self) -> list:
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
                # assign default skills based on profession if available
                try:
                    prof = None
                    if isinstance(md, dict):
                        prof = md.get('profession') or md.get('class') or md.get('job')
                    if prof:
                        try:
                            ppath = os.path.join(os.path.dirname(__file__), '..', 'systems', 'profession_skills.json')
                            # try package-local first
                            pj = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'systems', 'profession_skills.json'))
                            data = None
                            try:
                                with open(pj, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                            except Exception:
                                try:
                                    with open(os.path.join(os.path.dirname(__file__), '..', 'systems', 'profession_skills.json'), 'r', encoding='utf-8') as f:
                                        data = json.load(f)
                                except Exception:
                                    data = None
                            if isinstance(data, dict):
                                sks = data.get(str(prof).lower())
                                if sks and isinstance(sks, list):
                                    try:
                                        m.skills = list(sks)
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                except Exception:
                    pass
                # 初始装备（来自场景）：支持 equip / equipment 两种字段
                equip_data = md.get('equip') if 'equip' in md else md.get('equipment')
                if equip_data:
                    try:
                        self._equip_from_json(m, equip_data)
                    except Exception:
                        pass
                # 解析 DND 数据（不依赖是否有装备）
                try:
                    dnd = None
                    if isinstance(md, dict):
                        if isinstance(md.get('dnd'), dict):
                            dnd = md.get('dnd')
                        else:
                            # 支持扁平键
                            flat = {}
                            if 'ac' in md:
                                flat['ac'] = md.get('ac')
                            if 'level' in md:
                                flat['level'] = md.get('level')
                            if 'attrs' in md and isinstance(md.get('attrs'), dict):
                                flat['attrs'] = md.get('attrs')
                            if 'attributes' in md and isinstance(md.get('attributes'), dict):
                                flat['attrs'] = md.get('attributes')
                            if 'bonuses' in md and isinstance(md.get('bonuses'), dict):
                                flat['bonuses'] = md.get('bonuses')
                            if flat:
                                dnd = flat
                    if dnd:
                        setattr(m, 'dnd', dnd)
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
