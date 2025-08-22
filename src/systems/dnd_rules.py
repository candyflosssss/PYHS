"""Minimal D&D-like rules: attributes, to-hit and damage resolution.

Designed for integration with existing Combatant/Character models.
Provides deterministic hooks (roll_override) for testing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, List, Optional
import random


def roll_d20(advantage: bool = False, disadvantage: bool = False, roll_override: Optional[int] = None) -> Tuple[int, List[int]]:
    """Roll a d20. Returns (chosen_roll, all_rolls).
    If roll_override provided, it's used as the single roll result (bypasses advantage/disadvantage).
    """
    if roll_override is not None:
        return (int(roll_override), [int(roll_override)])
    if advantage and not disadvantage:
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        return (max(a, b), [a, b])
    if disadvantage and not advantage:
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        return (min(a, b), [a, b])
    r = random.randint(1, 20)
    return (r, [r])


@dataclass
class Attributes:
    str: int = 10
    dex: int = 10
    con: int = 10
    int: int = 10
    wis: int = 10
    cha: int = 10

    def mod(self, name: str) -> int:
        v = getattr(self, name)
        return (v - 10) // 2


@dataclass
class CharacterSheet:
    name: str
    level: int = 1
    attrs: Attributes = field(default_factory=Attributes)
    # flat AC if provided; otherwise callers may provide armor base
    ac: Optional[int] = None
    # generic bonuses (to_hit, damage, ac, etc.)
    bonuses: dict = field(default_factory=dict)

    @property
    def proficiency(self) -> int:
        # 5e style progression (1-4: +2, 5-8:+3, 9-12:+4, etc.)
        return 2 + ((max(1, self.level) - 1) // 4)

    def ability_mod(self, abbr: str) -> int:
        return self.attrs.mod(abbr) + int(self.bonuses.get(abbr, 0) or 0)

    def get_ac(self, base_ac: Optional[int] = None) -> int:
        # priority: explicit self.ac > provided base_ac > 10
        target = self.ac if self.ac is not None else (base_ac if base_ac is not None else 10)
        dex_mod = self.ability_mod('dex')
        return int(target + dex_mod + int(self.bonuses.get('ac', 0) or 0))


def to_hit_roll(attacker: CharacterSheet,
                defender: Optional[CharacterSheet] = None,
                weapon_bonus: int = 0,
                use_str: bool = True,
                is_proficient: bool = False,
                advantage: bool = False,
                disadvantage: bool = False,
                roll_override: Optional[int] = None,
                target_ac_override: Optional[int] = None) -> dict:
    """Compute a to-hit attempt.

    Returns dict: {
      'roll': int, 'rolls': List[int], 'total': int, 'needed': int, 'hit': bool, 'critical': bool
    }
    """
    roll, rolls = roll_d20(advantage=advantage, disadvantage=disadvantage, roll_override=roll_override)
    critical = (roll == 20)
    fumble = (roll == 1)
    ab_mod = attacker.ability_mod('str' if use_str else 'dex')
    prof = attacker.proficiency if is_proficient else 0
    extra = int(attacker.bonuses.get('to_hit', 0) or 0)
    total = roll + ab_mod + prof + weapon_bonus + extra
    needed = (defender.get_ac(target_ac_override) if defender is not None else (target_ac_override or 10))
    hit = critical or (not fumble and total >= needed)
    return {'roll': roll, 'rolls': rolls, 'total': total, 'needed': needed, 'hit': hit, 'critical': critical, 'fumble': fumble}


def roll_damage(attacker: CharacterSheet,
                dice: Tuple[int, int],
                damage_bonus: int = 0,
                use_str_for_damage: bool = True,
                critical: bool = False,
                roll_overrides: Optional[List[int]] = None) -> dict:
    """Roll damage as dice = (count, sides). If critical, dice are doubled per 5e.

    roll_overrides can be provided for deterministic dice (list of ints used sequentially).
    Returns {'dice_total': int, 'dice_rolls': List[int], 'total': int}
    """
    count, sides = dice
    rolls: List[int] = []
    times = 2 if critical else 1
    needed = count * times
    # use provided overrides first, then random
    for i in range(needed):
        if roll_overrides and i < len(roll_overrides):
            r = int(roll_overrides[i])
        else:
            r = random.randint(1, sides)
        rolls.append(r)
    dice_total = sum(rolls)
    str_mod = attacker.ability_mod('str') if use_str_for_damage else attacker.ability_mod('dex')
    bonus = int(attacker.bonuses.get('damage', 0) or 0) + int(damage_bonus or 0) + str_mod
    total = dice_total + bonus
    return {'dice_total': dice_total, 'dice_rolls': rolls, 'total': total, 'bonus': bonus}


__all__ = ['Attributes', 'CharacterSheet', 'to_hit_roll', 'roll_damage', 'roll_d20']
