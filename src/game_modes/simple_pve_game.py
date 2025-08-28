"""场景版 PvE 最小引擎
- 以场景 JSON 驱动：初始化敌人、资源、己方随从。
- 回合推进仅刷新随从可攻标记；其余按场景/指令驱动。
"""

from __future__ import annotations
from typing import List
import json
import os
import sys
from src import app_config as CFG
from src.game_modes.entities import Enemy, ResourceItem
from src.game_modes.pve_content_factory import EnemyFactory, ResourceFactory
from src.core.player import Player
from src.core.cards import NormalCard
from src.ui import colors as C
from src.core.events import publish as publish_event
from src.core.zone import ObservableList


class SimplePvEGame:
    def __init__(self, player_name: str):
        # 基本状态
        self.player = Player(player_name, is_me=True, game=self)
        self.turn = 1
        self.running = True
        self.enemies: ObservableList = ObservableList(
            [],
            on_add='enemy_added', on_remove='enemy_removed', on_clear='enemies_cleared', on_reset='enemies_reset', on_change='enemies_changed',
            to_payload=lambda e: getattr(e, 'name', str(e))
        )
        self.resources: ObservableList = ObservableList(
            [],
            on_add='resource_added', on_remove='resource_removed', on_clear='resources_cleared', on_reset='resources_reset', on_change='resources_changed',
            to_payload=lambda r: getattr(r, 'name', str(r))
        )
        # 日志缓冲（控制器会读取并清空）
        self._log_buffer: list[str] = []
        # 场景管理：兼容源码与打包路径
        # 优先使用 <pkg>/scenes (源码运行常见)，其次使用 <pkg父>/scenes（GUI 打包可能放到根 scenes）
        pkg_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        # 首选集中配置提供的候选，其次保留历史备选以增强兼容性
        candidates = list(CFG.scenes_roots())
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
        # 启用被动系统（事件驱动）
        try:
            from src.systems import passives_system as PS
            PS.setup()
        except Exception:
            pass
        # skill dispatch map
        self.skill_map = {
            'sweep': self._skill_sweep,
            'basic_heal': self._skill_basic_heal,
            'drain': self._skill_drain,
            'taunt': self._skill_taunt,
            'arcane_missiles': self._skill_arcane_missiles,
            # 新增技能（英文 key，对应外置 JSON 的 id）
            'power_slam': self._skill_power_slam,
            'bloodlust_priority': self._skill_bloodlust_priority,
            'execute_mage': self._skill_execute_mage,
            'mass_intimidate': self._skill_mass_intimidate,
            'precise_strike': self._skill_precise_strike,
            'disarm': self._skill_disarm,
            'shield_breaker': self._skill_shield_breaker,
            'dual_wield_bane': self._skill_dual_wield_bane,
            'mind_over_matter': self._skill_mind_over_matter,
            'trial_of_wisdom': self._skill_trial_of_wisdom,
            'execute_wounded': self._skill_execute_wounded,
            'fair_distribution': self._skill_fair_distribution,
        }

    # 调试用：返回内部候选场景根（按优先级）
    def _debug_scene_candidates(self) -> list[str]:
        pkg_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        candidates = list(CFG.scenes_roots())
        candidates.append(os.path.join(pkg_base, 'scenes'))
        candidates.append(os.path.join(os.path.dirname(pkg_base), 'scenes'))
        return [os.path.abspath(p) for p in candidates]

    def _write_scene_debug(self, lines: list[str]):
        r"""Append diagnostic lines to %LOCALAPPDATA%\PYHS\scene_debug.txt (safe, no raise)."""
        try:
            base = CFG.user_data_dir()
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
            # 统一标准化分隔符并去掉可能的前导 scenes/ 或 yyy/scenes/
            norm = scene_name_or_path.replace('\\', '/').lstrip('/')
            for pref in ('scenes/', 'yyy/scenes/'):
                if norm.startswith(pref):
                    norm = norm[len(pref):]
                    break
            # 多根查找：_scene_base_dir 以及候选根(_debug_scene_candidates)
            roots = []
            try:
                roots = [self._scene_base_dir]
                for p in self._debug_scene_candidates():
                    ap = os.path.abspath(p)
                    if ap not in roots and os.path.isdir(ap):
                        roots.append(ap)
            except Exception:
                roots = [self._scene_base_dir]
            found = None
            for r in roots:
                cand = os.path.abspath(os.path.join(r, norm))
                if os.path.exists(cand):
                    found = cand
                    break
            if not found and self.current_scene:
                cur_dir = os.path.dirname(os.path.abspath(self.current_scene))
                alt = os.path.abspath(os.path.join(cur_dir, norm))
                if os.path.exists(alt):
                    found = alt
            scene_path = found or os.path.abspath(os.path.join(self._scene_base_dir, norm))
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

        # 清空/保留：允许场景文件通过 refresh_board_on_enter 或 preserve_board_on_enter 覆盖
        eff_keep = keep_board
        try:
            if 'refresh_board_on_enter' in data:
                # True 表示进入本场景时刷新随从区（不保留旧随从）
                eff_keep = not bool(data.get('refresh_board_on_enter'))
            elif 'preserve_board_on_enter' in data:
                # True 表示进入本场景时保留随从区
                eff_keep = bool(data.get('preserve_board_on_enter'))
        except Exception:
            pass

        # 清空/保留
        preserved_board = list(self.player.board) if eff_keep else []
        # 重置敌人与资源为本场景定义
        self.enemies.clear()
        self.resources.clear()
        # 重置我方随从与手牌（场景模式不自动发起手牌）
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
        if eff_keep and preserved_board:
            # 保留旧随从，忽略新场景 board
            self.player.board.extend(preserved_board)
        else:
            for md in data.get('board', []):
                m = self._make_minion(md)
                if m is not None:
                    self.player.board.append(m)

        # 通知资源区已重置（UI 只订阅 resource_changed）
        try:
            publish_event('resource_changed', {'action': 'reset', 'size': len(self.resources)})
        except Exception:
            pass

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
            # 发布场景切换事件
            try:
                publish_event('scene_changed', {
                    'scene_path': self.current_scene,
                    'scene_title': self.current_scene_title,
                })
            except Exception:
                pass
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
        # 回合开始：回满体力，并保留 can_attack 标记用于兼容旧 UI 文本
        for c in self.player.board:
            try:
                c.refill_stamina()
            except Exception:
                pass
            c.can_attack = True

    def _to_character_sheet(self, entity):
        """Map a Combatant-like entity to a minimal CharacterSheet for DND computations."""
        try:
            from src.systems.dnd_rules import CharacterSheet, Attributes
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
                # Do not accept AC from JSON; compute from attributes + equipment defense
                # AC = 10 + dex_mod + defense
                # dex modifier will be computed below once attrs are available
            else:
                cs = CharacterSheet(name)
            # 若未指定 AC，则用 10 + defense 作为基础（DEX 修正由 get_ac 再叠加，避免重复）
            try:
                dfn = int(entity.get_total_defense()) if hasattr(entity, 'get_total_defense') else int(getattr(entity, 'defense', 0))
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
        # 新规则：攻击消耗体力（默认1），不足则不可攻击
        try:
            from src import settings as S
            cost = int(getattr(S, 'get_skill_cost')('attack', 1))
        except Exception:
            cost = 1
        if getattr(m, 'stamina', 0) < cost:
            return False, '体力不足，无法攻击'
        e = self.enemies[enemy_idx]
        # 使用 DND 规则判定命中与伤害（保留向后兼容）
        try:
            from src.systems.dnd_rules import to_hit_roll, roll_damage
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
            th = self._enrich_to_hit(th, att_sheet, def_sheet, weapon_bonus=weapon_bonus, is_proficient=is_proficient, use_str=True, defender_entity=e)
            # 暂不单独输出 to_hit 行，改为合并到攻击摘要里；meta 仍携带
            if not th.get('hit'):
                # 汇总一条更可读的未命中信息
                roll = th.get('roll'); total = th.get('total'); need = th.get('needed')
                bonus = (total - roll) if isinstance(roll, int) and isinstance(total, int) else None
                hit_line = f"d20={roll} + 加值{bonus} = {total} vs AC {need}" if bonus is not None else f"d20={roll} vs AC {need}"
                text = f"{m} 攻击 {getattr(e,'name',e)}: 未命中；{hit_line}"
                self.log({'type': 'attack', 'text': text, 'meta': {'to_hit': th}})
                try:
                    m.spend_stamina(cost)
                except Exception:
                    pass
                m.can_attack = False
                return True, '攻击未命中'
            dmg_spec = (1, max(1, int(m.get_total_attack()))) if hasattr(m, 'get_total_attack') else (1, 1)
            if roll_damage:
                dmg_r = roll_damage(att_sheet, dice=dmg_spec, damage_bonus=0, critical=th.get('critical', False))
                dmg_r = self._enrich_damage(dmg_r, att_sheet, dmg_spec, damage_bonus=0, critical=th.get('critical', False), use_str_for_damage=True)
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
        # 附带来源信息
        src_info = {
            'name': getattr(m, 'name', str(m)),
            'attack': int(getattr(m, 'get_total_attack')() if hasattr(m, 'get_total_attack') else getattr(m, 'attack', 0)),
        }
        try:
            eq = getattr(m, 'equipment', None)
            if eq:
                src_info['equipment'] = {
                    'left_hand': getattr(getattr(eq, 'left_hand', None), 'name', None),
                    'right_hand': getattr(getattr(eq, 'right_hand', None), 'name', None),
                    'armor': getattr(getattr(eq, 'armor', None), 'name', None),
                }
        except Exception:
            pass
        tgt_info = {
            'name': getattr(e, 'name', str(e)),
            'defense': int(getattr(e, 'get_total_defense')() if hasattr(e, 'get_total_defense') else getattr(e, 'defense', 0)),
            'hp_before': prev_e,
            'hp_after': getattr(e, 'hp', 0),
        }
        self.log({'type': 'attack', 'text': text, 'meta': {'to_hit': th, 'damage': dmg_r, 'target': tgt_info, 'sources': {'attacker': src_info}}})

        # 触发事件：攻击结算（供被动系统监听）
        try:
            publish_event('attack_resolved', {
                'attacker': m,
                'defender': e,
                'damage': dealt,
                'defender_dead': bool(dead)
            })
        except Exception:
            pass

        # 反击判定：0 攻不反击、进攻方带 no_counter 不被反击
        from src.systems import skills as SK
        try:
            if SK.should_counter(m, e):
                prev_m = m.hp
                m.take_damage(getattr(e, 'attack', 0))
                back = max(0, prev_m - m.hp)
                if back > 0:
                    self.log(f"{e.name} 反击 {m}，造成 {back} 伤害（{m.hp}/{m.max_hp}）")
                    try:
                        publish_event('counter_resolved', {
                            'attacker': e,
                            'defender': m,
                            'damage': back
                        })
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            m.spend_stamina(cost)
        except Exception:
            pass
        m.can_attack = False
        if dead:
            # 统一死亡处理：触发亡语/掉落、事件与安全移除
            changed = self._handle_enemy_death(e)
            if changed:
                return True, '攻击成功'
        if m.hp <= 0:
            self.player.board.remove(m)
        # 若清场且存在 on_clear 兜底切换，则尝试执行
        if not self.enemies:
            if self._check_on_clear_transition():
                return True, '攻击成功'
        return True, '攻击成功'

    # --- 技能入口（集中到 systems.skills_engine 执行） ---
    def use_skill(self, skill_name: str, source_idx: int, target_token: str = None):
        """Public entry to invoke a named skill from a minion (1-based index).      
        skill_name: 名称，如 'sweep'、'basic_heal' 等
        source_idx: minion index (1-based)
        target_token: 'eN' or 'mN' 或 None
        """
        try:
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
            # 体力消耗：从配置读取，默认 1；若不足则直接失败
            try:
                from src import settings as S
                cost = int(getattr(S, 'get_skill_cost')(skill_name, 1))
            except Exception:
                cost = 1
            if getattr(src, 'stamina', 0) < cost:
                return False, '体力不足'
            # 统一经由 skills_engine 执行
            try:
                from src.systems import skills_engine as SE
                ok, msg = SE.execute(self, skill_name, src, tgt)
            except Exception:
                # 兼容旧版：若注册表模块不可用，尝试回退到本类映射
                func = getattr(self, 'skill_map', {}).get(skill_name)
                if not func:
                    return False, f'未知技能: {skill_name}'
                ok, msg = func(src, tgt)
            # 体力消耗实际扣除
            try:
                src.spend_stamina(cost)
            except Exception:
                pass
            # 技能结束后若清场，触发场景切换（如有定义）
            try:
                if not self.enemies:
                    self._check_on_clear_transition()
            except Exception:
                pass
            return ok, msg
        except Exception as e:
            try:
                self.log({'type': 'error', 'text': f'技能执行出错: {e}', 'meta': {}})
            except Exception:
                pass
            return False, '技能执行失败'

    # --- 小工具 ---
    def _get_attr(self, entity, name: str, default: int = 10) -> int:
        try:
            dnd = getattr(entity, 'dnd', None)
            if isinstance(dnd, dict):
                attrs = dnd.get('attrs') or dnd.get('attributes') or {}
                val = attrs.get(name) or attrs.get(name.upper())
                if val is None:
                    return int(default)
                return int(val)
        except Exception:
            pass
        return int(default)

    def _has_dual_wield(self, entity) -> bool:
        try:
            eq = getattr(entity, 'equipment', None)
            if not eq:
                return False
            if getattr(eq, 'left_hand', None) and getattr(eq, 'right_hand', None):
                # 左手若为双手武器，则不算双持
                return not getattr(eq.left_hand, 'is_two_handed', False)
        except Exception:
            return False
        return False

    def _has_shield(self, entity) -> bool:
        try:
            eq = getattr(entity, 'equipment', None)
            if not eq:
                return False
            lh = getattr(eq, 'left_hand', None)
            if lh is None:
                return False
            # 类型判断优先
            try:
                from src.systems.equipment_system import ShieldItem
                return isinstance(lh, ShieldItem)
            except Exception:
                # 退化：槽位为左手且防御>0 且 is_two_handed=False 视为盾
                return (getattr(lh, 'slot_type', '') == 'left_hand' and not getattr(lh, 'is_two_handed', False) and int(getattr(lh, 'defense', 0)) > 0)
        except Exception:
            return False

    def _unequip_and_loot(self, target, slot: str) -> bool:
        """尝试卸下目标指定槽位装备并加入玩家背包。"""
        try:
            eq = getattr(target, 'equipment', None)
            if not eq:
                return False
            it = eq.unequip(slot)
            if it is None:
                return False
            # 加入玩家背包（若存在）
            try:
                self.player.add_item(it, 1)
            except Exception:
                # 退化：加入资源区（以字符串形式展示）
                try:
                    self.resource_zone.append(it)
                    try:
                        publish_event('resource_changed', {'action': 'add', 'resource': str(it)})
                    except Exception:
                        pass
                except Exception:
                    pass
            self.log({'type': 'loot', 'text': f"{getattr(target,'name',target)} 掉落了 {getattr(it,'name',str(it))}", 'meta': {}})
            return True
        except Exception:
            return False

    # --- 细化日志辅助 ---
    def _enrich_to_hit(self, th: dict, attacker_sheet, defender_sheet, weapon_bonus: int = 0,
                        is_proficient: bool = False, use_str: bool = True, defender_entity=None) -> dict:
        try:
            ab_mod = attacker_sheet.ability_mod('str' if use_str else 'dex')
        except Exception:
            ab_mod = 0
        try:
            prof = attacker_sheet.proficiency if is_proficient else 0
        except Exception:
            prof = 0
        try:
            hit_extra = int(getattr(attacker_sheet, 'bonuses', {}).get('to_hit', 0))
        except Exception:
            hit_extra = 0
        try:
            target_ac = defender_sheet.get_ac() if defender_sheet else th.get('needed')
        except Exception:
            target_ac = th.get('needed')
        th['breakdown'] = {
            'rolls': th.get('rolls'),
            'ability_mod': ab_mod,
            'proficiency': prof,
            'weapon_bonus': weapon_bonus,
            'extra_bonus': hit_extra,
            'formula': f"d20({th.get('roll')})+{ab_mod}+{prof}+{weapon_bonus}+{hit_extra}={th.get('total')} vs AC {target_ac}",
        }
        # 目标 AC 组成
        def_dfn = 0
        if defender_entity is not None:
            try:
                def_dfn = int(getattr(defender_entity, 'get_total_defense')()) if hasattr(defender_entity, 'get_total_defense') else int(getattr(defender_entity, 'defense', 0))
            except Exception:
                def_dfn = 0
        try:
            dex_mod_def = defender_sheet.ability_mod('dex') if defender_sheet else 0
        except Exception:
            dex_mod_def = 0
        try:
            ac_extra = int(getattr(defender_sheet, 'bonuses', {}).get('ac', 0))
        except Exception:
            ac_extra = 0
        th['target_ac'] = {
            'base': 10 + def_dfn,
            'defense': def_dfn,
            'dex_mod': dex_mod_def,
            'extra_bonus': ac_extra,
            'final': target_ac,
        }
        return th

    def _enrich_damage(self, dmg_r: dict, attacker_sheet, dice_spec: tuple[int, int], damage_bonus: int = 0,
                        critical: bool = False, use_str_for_damage: bool = True) -> dict:
        if not isinstance(dmg_r, dict):
            return dmg_r
        try:
            abil = 'str' if use_str_for_damage else 'dex'
            ab_mod = attacker_sheet.ability_mod(abil)
        except Exception:
            ab_mod = 0
        try:
            extra = int(getattr(attacker_sheet, 'bonuses', {}).get('damage', 0))
        except Exception:
            extra = 0
        count, sides = dice_spec
        dmg_r['breakdown'] = {
            'dice_total': dmg_r.get('dice_total'),
            'ability_mod': ab_mod,
            'damage_bonus': int(damage_bonus or 0),
            'extra_bonus': extra,
            'critical': bool(critical),
            'formula': f"{count}d{sides}({dmg_r.get('dice_total')})+{ab_mod}+{int(damage_bonus or 0)}+{extra}={dmg_r.get('total')}"
        }
        return dmg_r

    # --- 统一敌人死亡处理 ---
    def _handle_enemy_death(self, enemy) -> bool:
        """处理敌人死亡：触发亡语/掉落，必要时移除，并记录日志。
        返回 True 表示亡语期间发生了场景切换。"""
        prev_scene = self.current_scene
        # 触发亡语等
        try:
            enemy.on_death(self)
        except Exception:
            pass
        # 若期间发生场景切换，直接返回
        if self.current_scene != prev_scene:
            try:
                publish_event('enemy_died', {'enemy': enemy, 'scene_changed': True})
            except Exception:
                pass
            return True
        # 正常从列表移除
        try:
            if enemy in self.enemies:
                self.enemies.remove(enemy)
        except Exception:
            pass
        try:
            self.log(f"{getattr(enemy,'name',enemy)} 被消灭")
        except Exception:
            pass
        # 发布事件
        try:
            publish_event('enemy_died', {'enemy': enemy, 'scene_changed': False})
        except Exception:
            pass
        return False

    def _skill_sweep(self, src, tgt):
        """横扫：对所有敌人进行一次攻击判定并造成源攻击力的一半伤害（向下取整）。"""
        try:
            from src.systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = roll_damage = None
        hits = []
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        dmg_each = max(0, atk_val // 2)
        for i, e in enumerate(list(self.enemies)):
            # simple to-hit
            hit = True
            meta = {}
            th = None  # ensure defined even if roll_damage exists but to_hit_roll is None
            if to_hit_roll:
                att = self._to_character_sheet(src)
                dfn = self._to_character_sheet(e)
                th = to_hit_roll(att, dfn, use_str=True, weapon_bonus=0, is_proficient=False)
                th = self._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=e)
                hit = th['hit']
                meta['to_hit'] = th
            if hit:
                prev = e.hp
                # 用 DND 掷骰描述伤害（1d(dmg_each)）
                dmg_r = None
                if roll_damage and dmg_each > 0:
                    att = self._to_character_sheet(src)
                    dmg_r = roll_damage(att, dice=(1, max(1, dmg_each)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False)
                    dmg_r = self._enrich_damage(dmg_r, att, (1, max(1, dmg_each)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False, use_str_for_damage=True)
                    amount = int(dmg_r['total'])
                else:
                    amount = dmg_each
                dead = e.take_damage(amount)
                dealt = max(0, prev - e.hp)
                meta['damage'] = dmg_r
                meta['target'] = {'hp_before': prev, 'hp_after': e.hp}
                self.log({'type': 'skill', 'text': f"{src} 使用 横扫 对 {e.name} 造成 {dealt} 伤害", 'meta': meta})
                if dead:
                    changed = self._handle_enemy_death(e)
                    if changed:
                        src.can_attack = False
                        return True, '横扫 执行完毕'
                    # 若清场（所有敌人被横扫击杀），立即按 on_clear 跳转
                    try:
                        if not self.enemies and self._check_on_clear_transition():
                            src.can_attack = False
                            return True, '横扫 执行完毕'
                    except Exception:
                        pass
            else:
                self.log({'type': 'skill', 'text': f"{src} 使用 横扫 未命中 {e.name}", 'meta': meta})
        # 兼容旧规则：使用技能后视为已行动一次（仅保留 UI 提示）
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
            from src.systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = roll_damage = None
        meta = {}
        hit = True
        th = None
        if to_hit_roll:
            att = self._to_character_sheet(src)
            dfn = self._to_character_sheet(tgt)
            th = to_hit_roll(att, dfn, use_str=True, weapon_bonus=0, is_proficient=False)
            th = self._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=tgt)
            hit = th.get('hit', True)
            meta['to_hit'] = th
        if not hit:
            self.log({'type': 'skill', 'text': f"{src} 的 汲取 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
            return True, '未命中'
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        prev = getattr(tgt, 'hp', 0)
        # 用 DND 掷骰造成伤害：1dATK
        dmg_r = roll_damage(self._to_character_sheet(src), dice=(1, max(1, atk_val)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False) if roll_damage else None
        if dmg_r:
            att = self._to_character_sheet(src)
            dmg_r = self._enrich_damage(dmg_r, att, (1, max(1, atk_val)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False, use_str_for_damage=True)
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
        if dead and tgt in self.enemies:
            changed = self._handle_enemy_death(tgt)
            if changed:
                return True, '汲取完成'
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
            from src.systems.dnd_rules import roll_damage
        except Exception:
            roll_damage = None
        try:
            if tgt is None:
                if not self.enemies:
                    return False, '无敌人'
                tgt = random.choice(self.enemies)
            total = 0
            meta_all = {'bolts': []}
            att = self._to_character_sheet(src)
            for _ in range(3):
                prev = getattr(tgt, 'hp', 0)
                if roll_damage:
                    dmg_r = roll_damage(att, dice=(1, 4), damage_bonus=1, critical=False)
                    dmg_r = self._enrich_damage(dmg_r, att, (1, 4), damage_bonus=1, critical=False, use_str_for_damage=True)
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
                    if tgt in self.enemies:
                        changed = self._handle_enemy_death(tgt)
                        if changed:
                            return True, '奥术飞弹 完成'
                    break
            meta_all['total'] = total
            self.log({'type': 'skill', 'text': f"奥术飞弹 总计造成 {total} 点伤害", 'meta': meta_all})
            return True, '奥术飞弹 完成'
        except Exception:
            return False, '奥术飞弹 失败'

    # --- 新技能实现 ---
    def _skill_power_slam(self, src, tgt):
        """力量猛击：基于力量的重击；命中后造成 1d(ATK+STR修正) 伤害。"""
        if tgt is None:
            return False, '未选择目标'
        try:
            from src.systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = roll_damage = None
        str_mod = (self._get_attr(src, 'str') - 10) // 2
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        meta = {}
        hit = True
        th = None
        if to_hit_roll:
            th = to_hit_roll(self._to_character_sheet(src), self._to_character_sheet(tgt), use_str=True, weapon_bonus=0, is_proficient=False)
            hit = th.get('hit', True)
            meta['to_hit'] = th
        if not hit:
            self.log({'type': 'skill', 'text': f"{src} 的 力量猛击 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
            return True, '未命中'
        dmg_r = None
        amount = max(1, atk_val + max(0, str_mod))
        if roll_damage:
            dmg_r = roll_damage(self._to_character_sheet(src), dice=(1, max(1, amount)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False)
            amount = int(dmg_r.get('total', amount))
        prev = getattr(tgt, 'hp', 0)
        dead = tgt.take_damage(amount)
        dealt = max(0, prev - getattr(tgt, 'hp', prev))
        meta['damage'] = dmg_r
        self.log({'type': 'skill', 'text': f"{src} 使用 力量猛击 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
        if dead and tgt in self.enemies:
            changed = self._handle_enemy_death(tgt)
            if changed:
                return True, '力量猛击 完成'
        return True, '力量猛击 完成'

    def _skill_bloodlust_priority(self, src, tgt):
        """血腥优先：若未选目标，则自动选择当前生命最低的敌人；命中后造成 1dATK 伤害，若击杀，治疗自身2点。"""
        import math
        try:
            from src.systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = roll_damage = None
        # 自动选择
        if tgt is None and self.enemies:
            tgt = min(self.enemies, key=lambda e: getattr(e, 'hp', 0))
        if tgt is None:
            return False, '无可选目标'
        meta = {}
        hit = True
        th = None
        if to_hit_roll:
            th = to_hit_roll(self._to_character_sheet(src), self._to_character_sheet(tgt), use_str=True, weapon_bonus=0, is_proficient=False)
            hit = th.get('hit', True)
            meta['to_hit'] = th
        if not hit:
            self.log({'type': 'skill', 'text': f"{src} 的 血腥优先 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
            return True, '未命中'
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        dmg_r = None
        if roll_damage:
            dmg_r = roll_damage(self._to_character_sheet(src), dice=(1, max(1, atk_val)), damage_bonus=1, critical=th.get('critical', False) if isinstance(th, dict) else False)
            amount = int(dmg_r.get('total', atk_val))
        else:
            amount = atk_val + 1
        prev = getattr(tgt, 'hp', 0)
        dead = tgt.take_damage(amount)
        dealt = max(0, prev - getattr(tgt, 'hp', prev))
        meta['damage'] = dmg_r
        self.log({'type': 'skill', 'text': f"{src} 的 血腥优先 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
        if dead and tgt in self.enemies:
            changed = self._handle_enemy_death(tgt)
            if changed:
                return True, '血腥优先 完成'
            # 击杀回复
            try:
                src.heal(2)
            except Exception:
                pass
            self.log({'type': 'skill', 'text': f"{src} 因击杀而恢复 2 点生命", 'meta': {}})
        return True, '血腥优先 完成'

    def _skill_execute_mage(self, src, tgt):
        """斩杀法师：对法师型目标造成高额伤害；非法师仅造成较低伤害。"""
        if tgt is None:
            return False, '未选择目标'
        try:
            from src.systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = roll_damage = None
        # 判定是否法师
        is_mage = False
        try:
            tags = [str(t).lower() for t in (getattr(tgt, 'tags', []) or [])]
            if 'mage' in tags or 'wizard' in tags:
                is_mage = True
            else:
                is_mage = self._get_attr(tgt, 'int', 10) >= 12
        except Exception:
            pass
        meta = {}
        hit = True
        th = None
        if to_hit_roll:
            th = to_hit_roll(self._to_character_sheet(src), self._to_character_sheet(tgt), use_str=True, weapon_bonus=0, is_proficient=False)
            hit = th.get('hit', True)
            meta['to_hit'] = th
        if not hit:
            self.log({'type': 'skill', 'text': f"{src} 的 斩杀法师 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
            return True, '未命中'
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        base = atk_val * (2 if is_mage else 1)
        bonus = 2 if is_mage else -1
        dmg_r = None
        if roll_damage:
            dmg_r = roll_damage(self._to_character_sheet(src), dice=(1, max(1, base)), damage_bonus=max(0, bonus), critical=th.get('critical', False) if isinstance(th, dict) else False)
            amount = int(dmg_r.get('total', base))
        else:
            amount = max(1, base + max(0, bonus))
        prev = getattr(tgt, 'hp', 0)
        dead = tgt.take_damage(amount)
        dealt = max(0, prev - getattr(tgt, 'hp', prev))
        meta['damage'] = dmg_r
        self.log({'type': 'skill', 'text': f"{src} 的 斩杀法师 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
        if dead and tgt in self.enemies:
            changed = self._handle_enemy_death(tgt)
            if changed:
                return True, '斩杀法师 完成'
        return True, '斩杀法师 完成'

    def _skill_mass_intimidate(self, src, tgt):
        """群体恐吓：对所有敌人进行一次对抗检定（CHA vs WIS），成功则记录其被震慑。"""
        try:
            from src.systems.dnd_rules import roll_d20
        except Exception:
            roll_d20 = None
        cha_mod = (self._get_attr(src, 'cha') - 10) // 2
        for e in list(self.enemies):
            wis_mod = (self._get_attr(e, 'wis') - 10) // 2
            if roll_d20:
                a, _ = roll_d20()
                d, _ = roll_d20()
                success = (a + max(0, cha_mod)) >= (10 + max(0, wis_mod))
            else:
                success = (cha_mod >= wis_mod)
            if success:
                # 仅记录效果（暂不实现数值减益）
                self.log({'type': 'skill', 'text': f"{src} 的 群体恐吓 震慑了 {getattr(e,'name',e)}", 'meta': {}})
            else:
                self.log({'type': 'skill', 'text': f"{getattr(e,'name',e)} 抵抗了 群体恐吓", 'meta': {}})
        return True, '群体恐吓 完成'

    def _skill_precise_strike(self, src, tgt):
        """精准打击：优势命中，造成 1dATK 伤害。"""
        if tgt is None:
            return False, '未选择目标'
        try:
            from src.systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = roll_damage = None
        meta = {}
        hit = True
        th = None
        if to_hit_roll:
            att = self._to_character_sheet(src)
            dfn = self._to_character_sheet(tgt)
            th = to_hit_roll(att, dfn, use_str=True, weapon_bonus=0, is_proficient=False, advantage=True)
            th = self._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=tgt)
            hit = th.get('hit', True)
            meta['to_hit'] = th
        if not hit:
            self.log({'type': 'skill', 'text': f"{src} 的 精准打击 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
            return True, '未命中'
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        dmg_r = None
        if roll_damage:
            att = self._to_character_sheet(src)
            dmg_r = roll_damage(att, dice=(1, max(1, atk_val)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False)
            dmg_r = self._enrich_damage(dmg_r, att, (1, max(1, atk_val)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False, use_str_for_damage=True)
            amount = int(dmg_r.get('total', atk_val))
        else:
            amount = atk_val
        prev = getattr(tgt, 'hp', 0)
        dead = tgt.take_damage(amount)
        dealt = max(0, prev - getattr(tgt, 'hp', prev))
        meta['damage'] = dmg_r
        self.log({'type': 'skill', 'text': f"{src} 的 精准打击 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
        if dead and tgt in self.enemies:
            changed = self._handle_enemy_death(tgt)
            if changed:
                return True, '精准打击 完成'
        return True, '精准打击 完成'

    def _skill_disarm(self, src, tgt):
        """缴械：尝试卸下目标的武器（优先右手，其次左手），将装备转入我方背包。"""
        if tgt is None:
            return False, '未选择目标'
        # 命中检定（可选）
        try:
            from src.systems.dnd_rules import to_hit_roll
        except Exception:
            to_hit_roll = None
        hit = True
        th = None
        if to_hit_roll:
            th = to_hit_roll(self._to_character_sheet(src), self._to_character_sheet(tgt), use_str=True)
            hit = th.get('hit', True)
        if not hit:
            self.log({'type': 'skill', 'text': f"{src} 的 缴械 未能成功作用于 {getattr(tgt,'name',tgt)}", 'meta': {'to_hit': th}})
            return True, '未命中'
        # 尝试卸下
        if self._unequip_and_loot(tgt, 'right_hand'):
            self.log({'type': 'skill', 'text': f"{src} 缴械成功：{getattr(tgt,'name',tgt)} 右手装备被卸下", 'meta': {}})
            return True, '缴械成功'
        if self._unequip_and_loot(tgt, 'left_hand'):
            self.log({'type': 'skill', 'text': f"{src} 缴械成功：{getattr(tgt,'name',tgt)} 左手装备被卸下", 'meta': {}})
            return True, '缴械成功'
        self.log({'type': 'skill', 'text': f"{src} 尝试缴械，但 {getattr(tgt,'name',tgt)} 无可卸下装备", 'meta': {}})
        return True, '无可缴械'

    def _skill_shield_breaker(self, src, tgt):
        """破盾：若目标持盾，移除其盾牌并造成额外伤害；否则造成轻微伤害。"""
        if tgt is None:
            return False, '未选择目标'
        try:
            from src.systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = roll_damage = None
        meta = {}
        hit = True
        th = None
        if to_hit_roll:
            att = self._to_character_sheet(src)
            dfn = self._to_character_sheet(tgt)
            th = to_hit_roll(att, dfn, use_str=True)
            th = self._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=tgt)
            hit = th.get('hit', True)
            meta['to_hit'] = th
        if not hit:
            self.log({'type': 'skill', 'text': f"{src} 的 破盾 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
            return True, '未命中'
        bonus = 3 if self._has_shield(tgt) else 0
        if bonus > 0:
            # 先卸下盾
            if self._unequip_and_loot(tgt, 'left_hand'):
                self.log({'type': 'skill', 'text': f"{src} 击碎了 {getattr(tgt,'name',tgt)} 的盾牌!", 'meta': {}})
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        dmg_r = None
        amount = max(1, atk_val // 2 + bonus)
        if roll_damage:
            att = self._to_character_sheet(src)
            dmg_r = roll_damage(att, dice=(1, max(1, amount)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False)
            dmg_r = self._enrich_damage(dmg_r, att, (1, max(1, amount)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False, use_str_for_damage=True)
            amount = int(dmg_r.get('total', amount))
        prev = getattr(tgt, 'hp', 0)
        dead = tgt.take_damage(amount)
        dealt = max(0, prev - getattr(tgt, 'hp', prev))
        meta['damage'] = dmg_r
        self.log({'type': 'skill', 'text': f"{src} 的 破盾 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
        if dead and tgt in self.enemies:
            changed = self._handle_enemy_death(tgt)
            if changed:
                return True, '破盾 完成'
        return True, '破盾 完成'

    def _skill_dual_wield_bane(self, src, tgt):
        """双刀克星：若目标为双持，则优势命中并造成额外伤害；否则普通伤害。"""
        if tgt is None:
            return False, '未选择目标'
        try:
            from src.systems.dnd_rules import to_hit_roll, roll_damage
        except Exception:
            to_hit_roll = roll_damage = None
        dual = self._has_dual_wield(tgt)
        meta = {}
        hit = True
        th = None
        if to_hit_roll:
            att = self._to_character_sheet(src)
            dfn = self._to_character_sheet(tgt)
            th = to_hit_roll(att, dfn, use_str=True, advantage=dual)
            th = self._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=tgt)
            hit = th.get('hit', True)
            meta['to_hit'] = th
        if not hit:
            self.log({'type': 'skill', 'text': f"{src} 的 双刀克星 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
            return True, '未命中'
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        bonus = 2 if dual else 0
        dmg_r = None
        if roll_damage:
            att = self._to_character_sheet(src)
            dmg_r = roll_damage(att, dice=(1, max(1, atk_val)), damage_bonus=bonus, critical=th.get('critical', False) if isinstance(th, dict) else False)
            dmg_r = self._enrich_damage(dmg_r, att, (1, max(1, atk_val)), damage_bonus=bonus, critical=th.get('critical', False) if isinstance(th, dict) else False, use_str_for_damage=True)
            amount = int(dmg_r.get('total', atk_val + bonus))
        else:
            amount = atk_val + bonus
        prev = getattr(tgt, 'hp', 0)
        dead = tgt.take_damage(amount)
        dealt = max(0, prev - getattr(tgt, 'hp', prev))
        meta['damage'] = dmg_r
        self.log({'type': 'skill', 'text': f"{src} 的 双刀克星 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
        if dead and tgt in self.enemies:
            changed = self._handle_enemy_death(tgt)
            if changed:
                return True, '双刀克星 完成'
        return True, '双刀克星 完成'

    def _skill_mind_over_matter(self, src, tgt):
        """强于心智：精神打击，不进行命中检定，造成 INT 修正+2 的伤害（至少 1）。"""
        if tgt is None:
            return False, '未选择目标'
        int_mod = (self._get_attr(src, 'int') - 10) // 2
        amount = max(1, int_mod + 2)
        prev = getattr(tgt, 'hp', 0)
        dead = tgt.take_damage(amount)
        dealt = max(0, prev - getattr(tgt, 'hp', prev))
        self.log({'type': 'skill', 'text': f"{src} 的 强于心智 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 精神伤害", 'meta': {'psychic': True}})
        if dead and tgt in self.enemies:
            changed = self._handle_enemy_death(tgt)
            if changed:
                return True, '强于心智 完成'
        return True, '强于心智 完成'

    def _skill_trial_of_wisdom(self, src, tgt):
        """智慧试炼：若施法者 INT 不低于目标，则造成 1d6+INT修正 伤害；否则无效果。"""
        if tgt is None:
            return False, '未选择目标'
        try:
            from src.systems.dnd_rules import roll_damage
        except Exception:
            roll_damage = None
        if self._get_attr(src, 'int') < self._get_attr(tgt, 'int'):
            self.log({'type': 'skill', 'text': f"{src} 的 智慧试炼 被 {getattr(tgt,'name',tgt)} 识破，未起效果", 'meta': {}})
            return True, '未起效果'
        int_mod = (self._get_attr(src, 'int') - 10) // 2
        dmg_r = None
        if roll_damage:
            att = self._to_character_sheet(src)
            dmgb = max(0, int_mod)
            dmg_r = roll_damage(att, dice=(1, 6), damage_bonus=dmgb, critical=False)
            dmg_r = self._enrich_damage(dmg_r, att, (1, 6), damage_bonus=dmgb, critical=False, use_str_for_damage=True)
            amount = int(dmg_r.get('total', 1 + dmgb))
        else:
            amount = 1 + max(0, int_mod)
        prev = getattr(tgt, 'hp', 0)
        dead = tgt.take_damage(amount)
        dealt = max(0, prev - getattr(tgt, 'hp', prev))
        self.log({'type': 'skill', 'text': f"{src} 的 智慧试炼 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': {'damage': dmg_r}})
        if dead and tgt in self.enemies:
            changed = self._handle_enemy_death(tgt)
            if changed:
                return True, '智慧试炼 完成'
        return True, '智慧试炼 完成'

    def _skill_execute_wounded(self, src, tgt):
        """重伤补刀：若目标生命≤30%最大值，直接处决；否则造成中等伤害。"""
        if tgt is None:
            return False, '未选择目标'
        try:
            mhp = int(getattr(tgt, 'max_hp', getattr(tgt, 'hp', 1)))
            hp = int(getattr(tgt, 'hp', 0))
        except Exception:
            mhp = 1; hp = 0
        threshold = max(1, (mhp * 3) // 10)
        if hp <= threshold:
            # 处决
            prev = hp
            try:
                tgt.take_damage(hp)
            except Exception:
                tgt.hp = 0
            self.log({'type': 'skill', 'text': f"{src} 的 重伤补刀 处决了 {getattr(tgt,'name',tgt)}", 'meta': {'execute': True, 'hp_before': prev}})
            if tgt in self.enemies:
                changed = self._handle_enemy_death(tgt)
                if changed:
                    return True, '处决完成'
            return True, '处决完成'
        # 否则造成中等伤害：ATK 的一半 +1
        try:
            from src.systems.dnd_rules import roll_damage
        except Exception:
            roll_damage = None
        atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
        base = max(1, atk_val // 2 + 1)
        dmg_r = None
        if roll_damage:
            att = self._to_character_sheet(src)
            dmg_r = roll_damage(att, dice=(1, base), damage_bonus=0, critical=False)
            dmg_r = self._enrich_damage(dmg_r, att, (1, base), damage_bonus=0, critical=False, use_str_for_damage=True)
            amount = int(dmg_r.get('total', base))
        else:
            amount = base
        prev = getattr(tgt, 'hp', 0)
        dead = tgt.take_damage(amount)
        dealt = max(0, prev - getattr(tgt, 'hp', prev))
        self.log({'type': 'skill', 'text': f"{src} 的 重伤补刀 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': {'damage': dmg_r}})
        if dead and tgt in self.enemies:
            changed = self._handle_enemy_death(tgt)
            if changed:
                return True, '重伤补刀 完成'
        return True, '重伤补刀 完成'

    def _skill_fair_distribution(self, src, tgt):
        """公平分配：将自身总攻击力平均分配对所有敌人造成伤害（向下取整）。"""
        if not self.enemies:
            return False, '无敌人'
        total = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 0))
        n = len(self.enemies)
        if n <= 0 or total <= 0:
            self.log({'type': 'skill', 'text': f"{src} 的 公平分配 未造成伤害", 'meta': {}})
            return True, '无伤害'
        each = max(1, total // n)
        for e in list(self.enemies):
            prev = getattr(e, 'hp', 0)
            dead = e.take_damage(each)
            dealt = max(0, prev - getattr(e, 'hp', prev))
            self.log({'type': 'skill', 'text': f"{src} 的 公平分配 对 {getattr(e,'name',e)} 造成 {dealt} 伤害", 'meta': {'each': each}})
            if dead:
                changed = self._handle_enemy_death(e)
                if changed:
                    return True, '公平分配 完成'
        return True, '公平分配 完成'

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
                                    try:
                                        publish_event('resource_changed', {'action': 'add', 'resource': str(res)})
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                e = Enemy(name or '敌人', atk, hp, death_effect)
                # 可选增强字段：tags/passive/skills/profession/race
                try:
                    if isinstance(ed.get('tags'), list):
                        e.tags = list(ed.get('tags'))
                    if isinstance(ed.get('passive') or ed.get('passives'), dict):
                        e.passive = dict(ed.get('passive') or ed.get('passives'))
                    if isinstance(ed.get('skills'), list):
                        e.skills = list(ed.get('skills'))
                    if ed.get('profession'):
                        e.profession = ed.get('profession')
                    if ed.get('race'):
                        e.race = ed.get('race')
                except Exception:
                    pass
                # 初始装备（与随从相同格式）
                equip_data = ed.get('equip') if 'equip' in ed else ed.get('equipment')
                if equip_data:
                    try:
                        self._equip_from_json(e, equip_data)
                    except Exception:
                        pass
                # DND 数据
                try:
                    dnd = None
                    if isinstance(ed.get('dnd'), dict):
                        dnd = ed.get('dnd')
                    else:
                        flat = {}
                        if 'ac' in ed: flat['ac'] = ed.get('ac')
                        if 'level' in ed: flat['level'] = ed.get('level')
                        if 'attrs' in ed and isinstance(ed.get('attrs'), dict):
                            flat['attrs'] = ed.get('attrs')
                        if 'attributes' in ed and isinstance(ed.get('attributes'), dict):
                            flat['attrs'] = ed.get('attributes')
                        if 'bonuses' in ed and isinstance(ed.get('bonuses'), dict):
                            flat['bonuses'] = ed.get('bonuses')
                        if flat:
                            dnd = flat
                    if dnd:
                        setattr(e, 'dnd', dnd)
                except Exception:
                    pass
                return e
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
                # 结构化日志：明确清场触发切换
                try:
                    self.log({'type': 'info', 'text': f"清场，切换至 {to_scene}", 'meta': {'on_clear': True, 'to': to_scene, 'preserve_board': preserve}})
                except Exception:
                    pass
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
                            # 集中配置的职业技能映射表
                            ppath = CFG.profession_skills_path()
                            # try package-local first
                            pj = CFG.profession_skills_path()
                            data = None
                            try:
                                with open(pj, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                            except Exception:
                                try:
                                    with open(CFG.profession_skills_path(), 'r', encoding='utf-8') as f:
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
            from src.systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
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
                # 支持 passives/active_skills 字段
                act_sk = it.get('active_skills') or []
                psv = it.get('passives') or {}
                if t == 'weapon':
                    w = WeaponItem(str(name), str(desc), dur, attack=atk, slot_type=str(slot), is_two_handed=two, active_skills=act_sk, passives=psv)
                    card.equipment.equip(w, game=self)
                elif t == 'armor':
                    a = ArmorItem(str(name), str(desc), dur, defense=dfn, slot_type='armor', active_skills=act_sk, passives=psv)
                    card.equipment.equip(a, game=self)
                elif t == 'shield':
                    s = ShieldItem(str(name), str(desc), dur, defense=dfn, attack=atk, active_skills=act_sk, passives=psv)
                    card.equipment.equip(s, game=self)
                else:
                    # 未知类型忽略
                    continue
            except Exception:
                # 单件失败时继续下一件
                continue

    #（无自动配装函数）
