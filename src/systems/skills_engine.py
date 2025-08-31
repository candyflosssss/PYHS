"""
技能引擎（集中管理所有主动技能的实现）

- 目标：把散落在各处/类方法里的技能实现统一搬到这里，便于查阅、调整与扩展。
- 约定：每个技能函数签名均为 skill_xxx(game, src, tgt) -> tuple[bool, str]
  - game: 当前 SimplePvEGame 实例（用于日志、投骰工具、敌人列表、场景切换等）
  - src: 施放者（通常是 Combatant/随从/玩家单位）
  - tgt: 目标（可为 None，某些技能会自行选择目标或作用于群体）
  - 返回 (ok, msg)

添加新技能步骤：
1) 在此文件新增函数 skill_your_skill(game, src, tgt)。
2) 在 SKILLS 注册表中加入 'your_skill': skill_your_skill。
3) 在 settings.rules.skill_costs 中配置体力消耗（未配置则默认 1）。
4) 若需要在 UI 的技能目录中出现，请在相应 catalog/配置里添加名称与描述。

注意：本文件依赖 game 上的若干私有/辅助方法（_to_character_sheet/_enrich_to_hit/_enrich_damage/
_handle_enemy_death/_has_shield/_unequip_and_loot/_get_attr 等），这些方法依然保留在游戏类中，
技能函数通过传入的 game 参数调用它们。
"""
from __future__ import annotations

from typing import Callable, Dict, Tuple


def skill_sweep(game, src, tgt) -> Tuple[bool, str]:
    """横扫：对所有敌人各进行一次命中与伤害（伤害=自身总攻一半，向下取整）。"""
    try:
        from src.systems.dnd_rules import to_hit_roll, roll_damage
    except Exception:
        to_hit_roll = roll_damage = None
    hits = []
    atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
    dmg_each = max(0, atk_val // 2)
    for e in list(game.enemies):
        hit = True
        meta = {}
        th = None
        if to_hit_roll:
            att = game._to_character_sheet(src)
            dfn = game._to_character_sheet(e)
            th = to_hit_roll(att, dfn, use_str=True, weapon_bonus=0, is_proficient=False)
            th = game._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=e)
            hit = th['hit']
            meta['to_hit'] = th
        if hit:
            prev = e.hp
            dmg_r = None
            if roll_damage and dmg_each > 0:
                att = game._to_character_sheet(src)
                dmg_r = roll_damage(att, dice=(1, max(1, dmg_each)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False)
                dmg_r = game._enrich_damage(dmg_r, att, (1, max(1, dmg_each)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False, use_str_for_damage=True)
                amount = int(dmg_r['total'])
            else:
                amount = dmg_each
            dead = e.take_damage(amount)
            dealt = max(0, prev - e.hp)
            meta['damage'] = dmg_r
            meta['target'] = {'hp_before': prev, 'hp_after': e.hp}
            game.log({'type': 'skill', 'text': f"{src} 使用 横扫 对 {e.name} 造成 {dealt} 伤害", 'meta': meta})
            if dead:
                changed = game._handle_enemy_death(e)
                if changed:
                    src.can_attack = False
                    return True, '横扫 执行完毕'
                # 若清场则按 on_clear 跳转
                try:
                    if not game.enemies and game._check_on_clear_transition():
                        src.can_attack = False
                        return True, '横扫 执行完毕'
                except Exception:
                    pass
        else:
            game.log({'type': 'skill', 'text': f"{src} 使用 横扫 未命中 {e.name}", 'meta': meta})
    src.can_attack = False
    return True, '横扫 执行完毕'


def skill_basic_heal(game, src, tgt) -> Tuple[bool, str]:
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
    game.log({'type': 'skill', 'text': f"{src} 对 {getattr(tgt, 'name', tgt)} 恢复 {heal} 点生命", 'meta': {'heal': heal, 'target': {'hp_before': prev, 'hp_after': getattr(tgt, 'hp', prev)}}})
    return True, '治疗完成'


def skill_drain(game, src, tgt) -> Tuple[bool, str]:
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
        att = game._to_character_sheet(src)
        dfn = game._to_character_sheet(tgt)
        th = to_hit_roll(att, dfn, use_str=True, weapon_bonus=0, is_proficient=False)
        th = game._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=tgt)
        hit = th.get('hit', True)
        meta['to_hit'] = th
    if not hit:
        game.log({'type': 'skill', 'text': f"{src} 的 汲取 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
        return True, '未命中'
    atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
    prev = getattr(tgt, 'hp', 0)
    dmg_r = roll_damage(game._to_character_sheet(src), dice=(1, max(1, atk_val)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False) if roll_damage else None
    if dmg_r:
        att = game._to_character_sheet(src)
        dmg_r = game._enrich_damage(dmg_r, att, (1, max(1, atk_val)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False, use_str_for_damage=True)
    amount = int(dmg_r['total']) if dmg_r else atk_val
    dead = tgt.take_damage(amount)
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    # lifesteal equal to dealt
    try:
        src.heal(dealt)
    except Exception:
        try:
            src.hp = min(getattr(src, 'max_hp', getattr(src, 'hp', 0) + dealt), getattr(src, 'hp', 0) + dealt)
        except Exception:
            pass
    if dead and tgt in game.enemies:
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '汲取完成'
    meta['damage'] = dmg_r
    meta['lifesteal'] = dealt
    meta['target'] = {'hp_before': prev, 'hp_after': getattr(tgt, 'hp', prev)}
    game.log({'type': 'skill', 'text': f"{src} 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 汲取伤害并恢复 {dealt} 点生命", 'meta': meta})
    return True, '汲取完成'


def skill_taunt(game, src, tgt) -> Tuple[bool, str]:
    try:
        src.add_tag('taunt')
    except Exception:
        try:
            if not hasattr(src, 'tags'):
                src.tags = set()
            src.tags.add('taunt')
        except Exception:
            pass
    game.log({'type': 'skill', 'text': f"{src} 施放 嘲讽，吸引仇恨", 'meta': {'tags_added': ['taunt']}})
    return True, '嘲讽已施放'


def skill_arcane_missiles(game, src, tgt) -> Tuple[bool, str]:
    import random
    try:
        from src.systems.dnd_rules import roll_damage
    except Exception:
        roll_damage = None
    try:
        if tgt is None:
            if not game.enemies:
                return False, '无敌人'
            tgt = random.choice(game.enemies)
        total = 0
        meta_all = {'bolts': []}
        att = game._to_character_sheet(src)
        for _ in range(3):
            prev = getattr(tgt, 'hp', 0)
            if roll_damage:
                dmg_r = roll_damage(att, dice=(1, 4), damage_bonus=1, critical=False)
                dmg_r = game._enrich_damage(dmg_r, att, (1, 4), damage_bonus=1, critical=False, use_str_for_damage=True)
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
            game.log({'type': 'skill', 'text': f"{src} 的 奥术飞弹 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 点伤害", 'meta': bolt_meta})
            if dead:
                if tgt in game.enemies:
                    changed = game._handle_enemy_death(tgt)
                    if changed:
                        return True, '奥术飞弹 完成'
                break
        meta_all['total'] = total
        game.log({'type': 'skill', 'text': f"奥术飞弹 总计造成 {total} 点伤害", 'meta': meta_all})
        return True, '奥术飞弹 完成'
    except Exception:
        return False, '奥术飞弹 失败'


def skill_power_slam(game, src, tgt) -> Tuple[bool, str]:
    if tgt is None:
        return False, '未选择目标'
    try:
        from src.systems.dnd_rules import to_hit_roll, roll_damage
    except Exception:
        to_hit_roll = roll_damage = None
    str_mod = (game._get_attr(src, 'str') - 10) // 2
    atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
    meta = {}
    hit = True
    th = None
    if to_hit_roll:
        th = to_hit_roll(game._to_character_sheet(src), game._to_character_sheet(tgt), use_str=True, weapon_bonus=0, is_proficient=False)
        hit = th.get('hit', True)
        meta['to_hit'] = th
    if not hit:
        game.log({'type': 'skill', 'text': f"{src} 的 力量猛击 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
        return True, '未命中'
    dmg_r = None
    amount = max(1, atk_val + max(0, str_mod))
    if roll_damage:
        dmg_r = roll_damage(game._to_character_sheet(src), dice=(1, max(1, amount)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False)
        amount = int(dmg_r.get('total', amount))
    prev = getattr(tgt, 'hp', 0)
    dead = tgt.take_damage(amount)
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    meta['damage'] = dmg_r
    game.log({'type': 'skill', 'text': f"{src} 使用 力量猛击 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
    if dead and tgt in game.enemies:
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '力量猛击 完成'
    return True, '力量猛击 完成'


def skill_destiny(game, src, tgt) -> Tuple[bool, str]:
    """命运：对单体进行最多10次优势命中检定，若任意一次命中，则造成等同于目标当前生命的伤害（通常为处决）。"""
    if tgt is None:
        return False, '未选择目标'
    try:
        from src.systems.dnd_rules import to_hit_roll
    except Exception:
        to_hit_roll = None
    # 若没有 to_hit 模块，直接执行处决性伤害
    if to_hit_roll is None:
        prev = getattr(tgt, 'hp', 0)
        try:
            dead = tgt.take_damage(prev)
        except Exception:
            try:
                tgt.hp = 0
                dead = True
            except Exception:
                dead = False
        game.log({'type': 'skill', 'text': f"{src} 使用 命运 处决 {getattr(tgt,'name',tgt)}", 'meta': {'auto': True, 'hp_before': prev}})
        if dead and tgt in getattr(game, 'enemies', []):
            changed = game._handle_enemy_death(tgt)
            if changed:
                return True, '命运 完成'
        return True, '命运 完成'

    # 有命中规则：做10次优势检定，命中即处决
    att = game._to_character_sheet(src)
    dfn = game._to_character_sheet(tgt)
    rolls = []
    hit_any = False
    for _ in range(10):
        th = to_hit_roll(att, dfn, use_str=True, advantage=True)
        th = game._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=tgt)
        rolls.append({'roll': th.get('roll'), 'total': th.get('total'), 'needed': th.get('needed'), 'hit': th.get('hit')})
        if th.get('hit'):
            hit_any = True
            break
    if not hit_any:
        game.log({'type': 'skill', 'text': f"{src} 的 命运 未命中 {getattr(tgt,'name',tgt)}（10次优势）", 'meta': {'rolls': rolls}})
        return True, '未命中'
    # 命中：造成等同于目标当前生命的伤害
    prev = getattr(tgt, 'hp', 0)
    dead = False
    try:
        dead = tgt.take_damage(prev)
    except Exception:
        try:
            tgt.hp = 0
            dead = True
        except Exception:
            dead = False
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    game.log({'type': 'skill', 'text': f"{src} 的 命运 命中 {getattr(tgt,'name',tgt)}，造成 {dealt} 处决伤害", 'meta': {'rolls': rolls, 'execute': True}})
    if dead and tgt in getattr(game, 'enemies', []):
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '命运 完成'
    return True, '命运 完成'


def skill_touch_of_undeath(game, src, tgt) -> Tuple[bool, str]:
    """亡灵之触：召唤一个骷髅（六维皆10，体力1），装备3攻锈蚀短剑与3防破旧木盾，总攻3、防3。"""
    try:
        from src.core.cards import NormalCard
        from src.systems.equipment_system import WeaponItem, ShieldItem
    except Exception:
        return False, '召唤失败（模块缺失）'
    # 创建基础骷髅：基础攻设为0，通过武器提供3攻
    sk = NormalCard(0, 1, name='骷髅', tags=['undead'])
    try:
        sk.dnd = {'level': 1, 'attrs': {'str': 10, 'dex': 10, 'con': 10, 'int': 10, 'wis': 10, 'cha': 10}, 'bonuses': {}}
    except Exception:
        pass
    # 装备：锈蚀短剑(+3攻)与破旧木盾(+3防)
    try:
        sword = WeaponItem('锈蚀短剑', '破旧且迟钝的短剑', 30, attack=3)
        shield = ShieldItem('破旧木盾', '破旧的木盾，仍可提供些许防护', 30, defense=3)
        sk.equipment.equip(sword, game=game)
        sk.equipment.equip(shield, game=game)
    except Exception:
        pass
    # 允许普攻
    sk.can_attack = True
    # 放入我方棋盘
    try:
        board = getattr(game.player, 'board', [])
        if len(board) < 15:
            board.append(sk)
            game.log({'type': 'skill', 'text': f"{src} 的 亡灵之触 召唤了 {sk}", 'meta': {}})
            return True, '召唤完成'
        else:
            return False, '棋盘已满，无法召唤'
    except Exception:
        return False, '召唤失败'


def skill_bloodlust_priority(game, src, tgt) -> Tuple[bool, str]:
    import math
    try:
        from src.systems.dnd_rules import to_hit_roll, roll_damage
    except Exception:
        to_hit_roll = roll_damage = None
    if tgt is None and game.enemies:
        tgt = min(game.enemies, key=lambda e: getattr(e, 'hp', 0))
    if tgt is None:
        return False, '无可选目标'
    meta = {}
    hit = True
    th = None
    if to_hit_roll:
        th = to_hit_roll(game._to_character_sheet(src), game._to_character_sheet(tgt), use_str=True, weapon_bonus=0, is_proficient=False)
        hit = th.get('hit', True)
        meta['to_hit'] = th
    if not hit:
        game.log({'type': 'skill', 'text': f"{src} 的 血腥优先 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
        return True, '未命中'
    atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
    dmg_r = None
    if roll_damage:
        dmg_r = roll_damage(game._to_character_sheet(src), dice=(1, max(1, atk_val)), damage_bonus=1, critical=th.get('critical', False) if isinstance(th, dict) else False)
        amount = int(dmg_r.get('total', atk_val))
    else:
        amount = atk_val + 1
    prev = getattr(tgt, 'hp', 0)
    dead = tgt.take_damage(amount)
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    meta['damage'] = dmg_r
    game.log({'type': 'skill', 'text': f"{src} 的 血腥优先 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
    if dead and tgt in game.enemies:
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '血腥优先 完成'
        try:
            src.heal(2)
        except Exception:
            pass
        game.log({'type': 'skill', 'text': f"{src} 因击杀而恢复 2 点生命", 'meta': {}})
    return True, '血腥优先 完成'


def skill_execute_mage(game, src, tgt) -> Tuple[bool, str]:
    if tgt is None:
        return False, '未选择目标'
    try:
        from src.systems.dnd_rules import to_hit_roll, roll_damage
    except Exception:
        to_hit_roll = roll_damage = None
    is_mage = False
    try:
        tags = [str(t).lower() for t in (getattr(tgt, 'tags', []) or [])]
        if 'mage' in tags or 'wizard' in tags:
            is_mage = True
        else:
            is_mage = game._get_attr(tgt, 'int', 10) >= 12
    except Exception:
        pass
    meta = {}
    hit = True
    th = None
    if to_hit_roll:
        th = to_hit_roll(game._to_character_sheet(src), game._to_character_sheet(tgt), use_str=True, weapon_bonus=0, is_proficient=False)
        hit = th.get('hit', True)
        meta['to_hit'] = th
    if not hit:
        game.log({'type': 'skill', 'text': f"{src} 的 斩杀法师 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
        return True, '未命中'
    atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
    base = atk_val * (2 if is_mage else 1)
    bonus = 2 if is_mage else -1
    dmg_r = None
    if roll_damage:
        dmg_r = roll_damage(game._to_character_sheet(src), dice=(1, max(1, base)), damage_bonus=max(0, bonus), critical=th.get('critical', False) if isinstance(th, dict) else False)
        amount = int(dmg_r.get('total', base))
    else:
        amount = max(1, base + max(0, bonus))
    prev = getattr(tgt, 'hp', 0)
    dead = tgt.take_damage(amount)
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    meta['damage'] = dmg_r
    game.log({'type': 'skill', 'text': f"{src} 的 斩杀法师 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
    if dead and tgt in game.enemies:
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '斩杀法师 完成'
    return True, '斩杀法师 完成'


def skill_mass_intimidate(game, src, tgt) -> Tuple[bool, str]:
    try:
        from src.systems.dnd_rules import roll_d20
    except Exception:
        roll_d20 = None
    cha_mod = (game._get_attr(src, 'cha') - 10) // 2
    for e in list(game.enemies):
        wis_mod = (game._get_attr(e, 'wis') - 10) // 2
        if roll_d20:
            a, _ = roll_d20()
            d, _ = roll_d20()
            success = (a + max(0, cha_mod)) >= (10 + max(0, wis_mod))
        else:
            success = (cha_mod >= wis_mod)
        if success:
            game.log({'type': 'skill', 'text': f"{src} 的 群体恐惧 震慑了 {getattr(e,'name',e)}", 'meta': {}})
        else:
            game.log({'type': 'skill', 'text': f"{getattr(e,'name',e)} 抵抗了 群体恐惧", 'meta': {}})
    return True, '群体恐惧 完成'


def skill_precise_strike(game, src, tgt) -> Tuple[bool, str]:
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
        att = game._to_character_sheet(src)
        dfn = game._to_character_sheet(tgt)
        th = to_hit_roll(att, dfn, use_str=True, weapon_bonus=0, is_proficient=False, advantage=True)
        th = game._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=tgt)
        hit = th.get('hit', True)
        meta['to_hit'] = th
    if not hit:
        game.log({'type': 'skill', 'text': f"{src} 的 精准打击 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
        return True, '未命中'
    atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
    dmg_r = None
    if roll_damage:
        att = game._to_character_sheet(src)
        dmg_r = roll_damage(att, dice=(1, max(1, atk_val)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False)
        dmg_r = game._enrich_damage(dmg_r, att, (1, max(1, atk_val)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False, use_str_for_damage=True)
        amount = int(dmg_r.get('total', atk_val))
    else:
        amount = atk_val
    prev = getattr(tgt, 'hp', 0)
    dead = tgt.take_damage(amount)
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    meta['damage'] = dmg_r
    game.log({'type': 'skill', 'text': f"{src} 的 精准打击 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
    if dead and tgt in game.enemies:
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '精准打击 完成'
    return True, '精准打击 完成'


def skill_disarm(game, src, tgt) -> Tuple[bool, str]:
    if tgt is None:
        return False, '未选择目标'
    try:
        from src.systems.dnd_rules import to_hit_roll
    except Exception:
        to_hit_roll = None
    hit = True
    th = None
    if to_hit_roll:
        th = to_hit_roll(game._to_character_sheet(src), game._to_character_sheet(tgt), use_str=True)
        hit = th.get('hit', True)
    if not hit:
        game.log({'type': 'skill', 'text': f"{src} 的 缴械 未能成功作用于 {getattr(tgt,'name',tgt)}", 'meta': {'to_hit': th}})
        return True, '未命中'
    if game._unequip_and_loot(tgt, 'right_hand'):
        game.log({'type': 'skill', 'text': f"{src} 缴械成功：{getattr(tgt,'name',tgt)} 右手装备被卸下", 'meta': {}})
        return True, '缴械成功'
    if game._unequip_and_loot(tgt, 'left_hand'):
        game.log({'type': 'skill', 'text': f"{src} 缴械成功：{getattr(tgt,'name',tgt)} 左手装备被卸下", 'meta': {}})
        return True, '缴械成功'
    game.log({'type': 'skill', 'text': f"{src} 尝试缴械，但 {getattr(tgt,'name',tgt)} 无可卸下装备", 'meta': {}})
    return True, '无可缴械'


def skill_shield_breaker(game, src, tgt) -> Tuple[bool, str]:
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
        att = game._to_character_sheet(src)
        dfn = game._to_character_sheet(tgt)
        th = to_hit_roll(att, dfn, use_str=True)
        th = game._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=tgt)
        hit = th.get('hit', True)
        meta['to_hit'] = th
    if not hit:
        game.log({'type': 'skill', 'text': f"{src} 的 破盾 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
        return True, '未命中'
    bonus = 3 if game._has_shield(tgt) else 0
    if bonus > 0:
        if game._unequip_and_loot(tgt, 'left_hand'):
            game.log({'type': 'skill', 'text': f"{src} 击碎了 {getattr(tgt,'name',tgt)} 的盾牌!", 'meta': {}})
    atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
    dmg_r = None
    amount = max(1, atk_val // 2 + bonus)
    if roll_damage:
        att = game._to_character_sheet(src)
        dmg_r = roll_damage(att, dice=(1, max(1, amount)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False)
        dmg_r = game._enrich_damage(dmg_r, att, (1, max(1, amount)), damage_bonus=0, critical=th.get('critical', False) if isinstance(th, dict) else False, use_str_for_damage=True)
        amount = int(dmg_r.get('total', amount))
    prev = getattr(tgt, 'hp', 0)
    dead = tgt.take_damage(amount)
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    meta['damage'] = dmg_r
    game.log({'type': 'skill', 'text': f"{src} 的 破盾 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
    if dead and tgt in game.enemies:
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '破盾 完成'
    return True, '破盾 完成'


def skill_dual_wield_bane(game, src, tgt) -> Tuple[bool, str]:
    if tgt is None:
        return False, '未选择目标'
    try:
        from src.systems.dnd_rules import to_hit_roll, roll_damage
    except Exception:
        to_hit_roll = roll_damage = None
    dual = game._has_dual_wield(tgt)
    meta = {}
    hit = True
    th = None
    if to_hit_roll:
        att = game._to_character_sheet(src)
        dfn = game._to_character_sheet(tgt)
        th = to_hit_roll(att, dfn, use_str=True, advantage=dual)
        th = game._enrich_to_hit(th, att, dfn, weapon_bonus=0, is_proficient=False, use_str=True, defender_entity=tgt)
        hit = th.get('hit', True)
        meta['to_hit'] = th
    if not hit:
        game.log({'type': 'skill', 'text': f"{src} 的 双刀克星 未命中 {getattr(tgt,'name',tgt)}", 'meta': meta})
        return True, '未命中'
    atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
    bonus = 2 if dual else 0
    dmg_r = None
    if roll_damage:
        att = game._to_character_sheet(src)
        dmg_r = roll_damage(att, dice=(1, max(1, atk_val)), damage_bonus=bonus, critical=th.get('critical', False) if isinstance(th, dict) else False)
        dmg_r = game._enrich_damage(dmg_r, att, (1, max(1, atk_val)), damage_bonus=bonus, critical=th.get('critical', False) if isinstance(th, dict) else False, use_str_for_damage=True)
        amount = int(dmg_r.get('total', atk_val + bonus))
    else:
        amount = atk_val + bonus
    prev = getattr(tgt, 'hp', 0)
    dead = tgt.take_damage(amount)
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    meta['damage'] = dmg_r
    game.log({'type': 'skill', 'text': f"{src} 的 双刀克星 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': meta})
    if dead and tgt in game.enemies:
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '双刀克星 完成'
    return True, '双刀克星 完成'


def skill_mind_over_matter(game, src, tgt) -> Tuple[bool, str]:
    if tgt is None:
        return False, '未选择目标'
    int_mod = (game._get_attr(src, 'int') - 10) // 2
    amount = max(1, int_mod + 2)
    prev = getattr(tgt, 'hp', 0)
    dead = tgt.take_damage(amount)
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    game.log({'type': 'skill', 'text': f"{src} 的 强于心智 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 精神伤害", 'meta': {'psychic': True}})
    if dead and tgt in game.enemies:
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '强于心智 完成'
    return True, '强于心智 完成'


def skill_trial_of_wisdom(game, src, tgt) -> Tuple[bool, str]:
    if tgt is None:
        return False, '未选择目标'
    try:
        from src.systems.dnd_rules import roll_damage
    except Exception:
        roll_damage = None
    if game._get_attr(src, 'int') < game._get_attr(tgt, 'int'):
        game.log({'type': 'skill', 'text': f"{src} 的 智慧试炼 被 {getattr(tgt,'name',tgt)} 识破，未起效果", 'meta': {}})
        return True, '未起效果'
    int_mod = (game._get_attr(src, 'int') - 10) // 2
    dmg_r = None
    if roll_damage:
        att = game._to_character_sheet(src)
        dmgb = max(0, int_mod)
        dmg_r = roll_damage(att, dice=(1, 6), damage_bonus=dmgb, critical=False)
        dmg_r = game._enrich_damage(dmg_r, att, (1, 6), damage_bonus=dmgb, critical=False, use_str_for_damage=True)
        amount = int(dmg_r.get('total', 1 + dmgb))
    else:
        amount = 1 + max(0, int_mod)
    prev = getattr(tgt, 'hp', 0)
    dead = tgt.take_damage(amount)
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    game.log({'type': 'skill', 'text': f"{src} 的 智慧试炼 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': {'damage': dmg_r}})
    if dead and tgt in game.enemies:
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '智慧试炼 完成'
    return True, '智慧试炼 完成'


def skill_execute_wounded(game, src, tgt) -> Tuple[bool, str]:
    if tgt is None:
        return False, '未选择目标'
    try:
        mhp = int(getattr(tgt, 'max_hp', getattr(tgt, 'hp', 1)))
        hp = int(getattr(tgt, 'hp', 0))
    except Exception:
        mhp = 1; hp = 0
    threshold = max(1, (mhp * 3) // 10)
    if hp <= threshold:
        prev = hp
        try:
            tgt.take_damage(hp)
        except Exception:
            tgt.hp = 0
        game.log({'type': 'skill', 'text': f"{src} 的 重伤补刀 处决了 {getattr(tgt,'name',tgt)}", 'meta': {'execute': True, 'hp_before': prev}})
        if tgt in game.enemies:
            changed = game._handle_enemy_death(tgt)
            if changed:
                return True, '处决完成'
        return True, '处决完成'
    # 否则造成中等伤害：ATK/2 +1
    try:
        from src.systems.dnd_rules import roll_damage
    except Exception:
        roll_damage = None
    atk_val = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 1))
    base = max(1, atk_val // 2 + 1)
    dmg_r = None
    if roll_damage:
        att = game._to_character_sheet(src)
        dmg_r = roll_damage(att, dice=(1, base), damage_bonus=0, critical=False)
        dmg_r = game._enrich_damage(dmg_r, att, (1, base), damage_bonus=0, critical=False, use_str_for_damage=True)
        amount = int(dmg_r.get('total', base))
    else:
        amount = base
    prev = getattr(tgt, 'hp', 0)
    dead = tgt.take_damage(amount)
    dealt = max(0, prev - getattr(tgt, 'hp', prev))
    game.log({'type': 'skill', 'text': f"{src} 的 重伤补刀 对 {getattr(tgt,'name',tgt)} 造成 {dealt} 伤害", 'meta': {'damage': dmg_r}})
    if dead and tgt in game.enemies:
        changed = game._handle_enemy_death(tgt)
        if changed:
            return True, '重伤补刀 完成'
    return True, '重伤补刀 完成'


def skill_fair_distribution(game, src, tgt) -> Tuple[bool, str]:
    if not game.enemies:
        return False, '无敌人'
    total = int(src.get_total_attack() if hasattr(src, 'get_total_attack') else getattr(src, 'attack', 0))
    n = len(game.enemies)
    if n <= 0 or total <= 0:
        game.log({'type': 'skill', 'text': f"{src} 的 公平分配 未造成伤害", 'meta': {}})
        return True, '无伤害'
    each = max(1, total // n)
    for e in list(game.enemies):
        prev = getattr(e, 'hp', 0)
        dead = e.take_damage(each)
        dealt = max(0, prev - getattr(e, 'hp', prev))
        game.log({'type': 'skill', 'text': f"{src} 的 公平分配 对 {getattr(e,'name',e)} 造成 {dealt} 伤害", 'meta': {'each': each}})
        if dead:
            changed = game._handle_enemy_death(e)
            if changed:
                return True, '公平分配 完成'
    return True, '公平分配 完成'


# 注册表：技能名 -> 实现函数
SKILLS: Dict[str, Callable] = {
    'sweep': skill_sweep,
    'basic_heal': skill_basic_heal,
    'drain': skill_drain,
    'taunt': skill_taunt,
    'arcane_missiles': skill_arcane_missiles,
    'power_slam': skill_power_slam,
    'bloodlust_priority': skill_bloodlust_priority,
    'execute_mage': skill_execute_mage,
    'mass_intimidate': skill_mass_intimidate,
    'precise_strike': skill_precise_strike,
    'disarm': skill_disarm,
    'shield_breaker': skill_shield_breaker,
    'dual_wield_bane': skill_dual_wield_bane,
    'mind_over_matter': skill_mind_over_matter,
    'trial_of_wisdom': skill_trial_of_wisdom,
    'execute_wounded': skill_execute_wounded,
    'fair_distribution': skill_fair_distribution,
    # admin/new
    'destiny': skill_destiny,
    'touch_of_undeath': skill_touch_of_undeath,
}


def execute(game, name: str, src, tgt) -> Tuple[bool, str]:
    """执行技能：根据名字在注册表中查找并调用实现。未找到返回 False。"""
    fn = SKILLS.get(name)
    if not fn:
        return False, f'未知技能：{name}'
    return fn(game, src, tgt)
