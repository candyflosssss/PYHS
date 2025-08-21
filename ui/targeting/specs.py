"""Skill target specifications (single source of truth for UI).
Can be overridden or provided dynamically from backend later.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Dict, Any
import os, json

@dataclass
class SkillTargetSpec:
    team: str                  # 'enemy' | 'ally' | 'self' | 'any'
    select: str                # 'none' | 'single' | 'multi' | 'aoe'
    min_targets: int = 0
    max_targets: Optional[int] = 1
    excludes_self: bool = False
    allow_random: bool = False
    fallback: str = 'cancel'   # 'random' | 'cancel' | 'prompt'
    predicates: List[str] = field(default_factory=list)

# Default specs; backend may provide authoritative ones.
DEFAULT_SPECS: Dict[str, SkillTargetSpec] = {
    'attack': SkillTargetSpec(team='enemy', select='single', min_targets=1, max_targets=1, predicates=['is_alive','can_be_attacked']),
    'basic_heal': SkillTargetSpec(team='ally', select='single', min_targets=1, max_targets=1, excludes_self=True, predicates=['is_alive','is_wounded']),
    'drain': SkillTargetSpec(team='enemy', select='single', min_targets=1, max_targets=1, predicates=['is_alive','can_be_attacked']),
    'taunt': SkillTargetSpec(team='self', select='none'),
    'sweep': SkillTargetSpec(team='enemy', select='aoe', predicates=['is_alive','can_be_attacked']),
    'arcane_missiles': SkillTargetSpec(team='enemy', select='single', min_targets=0, max_targets=1, allow_random=True, predicates=['is_alive','can_be_attacked']),
}

# Attempt to overlay from external catalog if present
def _load_overrides() -> Dict[str, SkillTargetSpec]:
    try:
        p = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'systems', 'skills_catalog.json'))
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        out: Dict[str, SkillTargetSpec] = {}
        for rec in (data.get('skills') or []):
            if not isinstance(rec, dict):
                continue
            sid = rec.get('id')
            spec = rec.get('spec') or {}
            if not sid or not isinstance(spec, dict):
                continue
            out[sid] = SkillTargetSpec(
                team=spec.get('team','enemy'),
                select=spec.get('select','single'),
                min_targets=int(spec.get('min_targets', 0) or 0),
                max_targets=spec.get('max_targets', 1),
                excludes_self=bool(spec.get('excludes_self', False)),
                allow_random=bool(spec.get('allow_random', False)),
                fallback=str(spec.get('fallback','cancel')),
                predicates=list(spec.get('predicates', [])),
            )
        return out
    except Exception:
        return {}

_OVR = _load_overrides()
if _OVR:
    DEFAULT_SPECS.update(_OVR)

