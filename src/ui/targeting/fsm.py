"""Targeting state & helpers.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, Optional
from .specs import SkillTargetSpec, DEFAULT_SPECS
from .predicates import PREDICATE_MAP

@dataclass
class TargetingContext:
    src: str
    skill_name: str
    spec: SkillTargetSpec
    candidates: List[str] = field(default_factory=list)
    selected: Set[str] = field(default_factory=set)
    state: str = 'Idle'   # 'Idle' | 'Selecting' | 'Confirmable' | 'Executing'

class TargetingEngine:
    def __init__(self, app):
        self.app = app
        self.ctx: Optional[TargetingContext] = None

    def reset(self):
        self.ctx = None

    def begin(self, src_token: str, skill_name: str, spec: Optional[SkillTargetSpec] = None):
        spec = spec or DEFAULT_SPECS.get(skill_name)
        if spec is None:
            # default to enemy single
            spec = SkillTargetSpec(team='enemy', select='single', min_targets=1, max_targets=1, predicates=['is_alive'])
        self.ctx = TargetingContext(src=src_token, skill_name=skill_name, spec=spec)
        if spec.select in ('none','aoe'):
            # no target needed
            self.ctx.state = 'Executing'
            return True
        # compute candidates
        self.ctx.candidates = self._compute_candidates(self.ctx)
        self.ctx.selected.clear()
        # 若无候选且需要选择，依据 fallback 策略：默认 cancel，从而让上层清理而不卡住
        if not self.ctx.candidates:
            fb = getattr(spec, 'fallback', 'cancel')
            if fb == 'random' and (spec.min_targets or 0) > 0:
                # 允许随机（但此时 candidates 为空，仍无法随机）-> 视为 cancel
                pass
            # 置为 Executing 交由上层直接执行（将不带目标），或上层看到无候选时直接 clear
            self.ctx.state = 'Executing'
            return True
        self.ctx.state = 'Selecting'
        return False

    def _compute_candidates(self, ctx: TargetingContext) -> List[str]:
        app = self.app
        team = ctx.spec.team
        base: List[str] = []
        if team in ('enemy','any'):
            for i, e in enumerate(getattr(app.controller.game, 'enemies', []) or [], start=1):
                base.append(f'e{i}')
        if team in ('ally','self','any'):
            for i, m in enumerate(getattr(app.controller.game.player, 'board', []) or [], start=1):
                base.append(f'm{i}')
        # self exclusion
        if ctx.spec.excludes_self:
            base = [t for t in base if t != ctx.src]
        # apply predicates
        preds = [PREDICATE_MAP.get(p) for p in (ctx.spec.predicates or []) if PREDICATE_MAP.get(p)]
        def ok(tok: str) -> bool:
            try:
                return all(p(self.app, ctx.src, tok) for p in preds)
            except Exception:
                return False
        filtered = [t for t in base if ok(t)]
        # clamp to team real set
        if team == 'enemy':
            filtered = [t for t in filtered if t.startswith('e')]
        if team == 'ally':
            filtered = [t for t in filtered if t.startswith('m')]
        if team == 'self':
            filtered = [t for t in filtered if t == ctx.src]
        return filtered

    def revalidate(self):
        if not self.ctx:
            return
        self.ctx.candidates = self._compute_candidates(self.ctx)
        self.ctx.selected &= set(self.ctx.candidates)
        if not self.ctx.selected and self.ctx.spec.min_targets > 0:
            # stay selecting or fallback
            pass

    def pick(self, token: str):
        if not self.ctx or self.ctx.state not in ('Selecting','Confirmable'):
            return
        if token not in self.ctx.candidates:
            return
        if self.ctx.spec.select == 'single':
            self.ctx.selected = {token}
        elif self.ctx.spec.select == 'multi':
            if self.ctx.spec.max_targets is None or len(self.ctx.selected) < self.ctx.spec.max_targets:
                self.ctx.selected.add(token)
        self._update_state_after_pick()

    def unpick(self, token: str):
        if not self.ctx:
            return
        self.ctx.selected.discard(token)
        if len(self.ctx.selected) < max(1, self.ctx.spec.min_targets):
            self.ctx.state = 'Selecting'

    def _update_state_after_pick(self):
        if not self.ctx:
            return
        mn = self.ctx.spec.min_targets or 0
        if len(self.ctx.selected) >= mn:
            self.ctx.state = 'Confirmable'
        else:
            self.ctx.state = 'Selecting'

    def is_ready(self) -> bool:
        if not self.ctx:
            return False
        mn = self.ctx.spec.min_targets or 0
        mx = self.ctx.spec.max_targets or 9999
        return mn <= len(self.ctx.selected) <= mx

    def get_selected(self) -> List[str]:
        return list(self.ctx.selected) if self.ctx else []

    def has_candidates(self) -> bool:
        try:
            return bool(self.ctx and (self.ctx.candidates or []))
        except Exception:
            return False
