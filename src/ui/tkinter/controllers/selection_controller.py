from __future__ import annotations

from typing import Optional

class SelectionController:
    """Manages selection/highlight state for allies and enemies, and re-applies
    highlights based on current targeting mode and selections.
    """
    def __init__(self, app):
        self.app = app

    def clear_all(self):
        self.app.selected_enemy_index = None
        self.app.selected_member_index = None
        self.app.selected_skill = None
        self.app.selected_skill_name = None
        self.app.skill_target_index = None
        self.app.skill_target_token = None
        try:
            if getattr(self.app, 'target_engine', None):
                self.app.target_engine.reset()
        except Exception:
            pass
        try:
            self.app._reset_highlights()
        except Exception:
            pass
    # 视图自刷新：由事件驱动或调用方决定，无需调度 app 刷新。

    def reapply_highlights(self):
        """Reapply current selection and targeting highlights after a refresh."""
        try:
            if self.app.selected_enemy_index and self.app.selected_enemy_index in self.app.enemy_card_wraps:
                self.app.enemy_card_wraps[self.app.selected_enemy_index].configure(
                    highlightbackground=self.app.HL['sel_enemy_border'],
                    background=self.app.HL['sel_enemy_bg'],
                    highlightthickness=self.app._border_selected_enemy,
                )
            if self.app.selected_member_index and self.app.selected_member_index in self.app.card_wraps:
                self.app.card_wraps[self.app.selected_member_index].configure(
                    highlightbackground=self.app.HL['sel_ally_border'],
                    background=self.app.HL['sel_ally_bg'],
                    highlightthickness=self.app._border_selected_member,
                )
            # mode base highlighting
            if getattr(self.app, 'selected_skill', None) == 'attack':
                for idx, wrap in (self.app.enemy_card_wraps or {}).items():
                    wrap.configure(highlightbackground=self.app.HL['cand_enemy_border'], background=self.app.HL['cand_enemy_bg'])
            if getattr(self.app, 'selected_skill', None) == 'heal':
                for idx, wrap in (self.app.card_wraps or {}).items():
                    wrap.configure(highlightbackground=self.app.HL['cand_ally_border'], background=self.app.HL['cand_ally_bg'])
            # specific target highlight
            tok = getattr(self.app, 'skill_target_token', None)
            if tok:
                try:
                    if tok.startswith('e'):
                        i = int(tok[1:])
                        if i in (self.app.enemy_card_wraps or {}):
                            self.app.enemy_card_wraps[i].configure(
                                highlightbackground=self.app.HL['sel_enemy_border'],
                                background=self.app.HL['sel_enemy_bg'],
                                highlightthickness=self.app._border_selected_enemy,
                            )
                    elif tok.startswith('m'):
                        i = int(tok[1:])
                        if i in (self.app.card_wraps or {}):
                            self.app.card_wraps[i].configure(
                                highlightbackground=self.app.HL['sel_ally_border'],
                                background=self.app.HL['sel_ally_bg'],
                                highlightthickness=self.app._border_selected_member,
                            )
                except Exception:
                    pass
        except Exception:
            pass

    # --- target picking / clicks ---
    def toggle_token(self, token: str):
        """Toggle a candidate token during targeting (pick/unpick), then update highlights and ops."""
        try:
            te = getattr(self.app, 'target_engine', None)
            if not te or not getattr(te, 'ctx', None):
                return
            ctx = te.ctx
            if token in (ctx.selected or set()):
                te.unpick(token)
            else:
                te.pick(token)
            # update highlights and operations
            try:
                self.app._update_target_highlights()
            except Exception:
                pass
            # 底部操作区已移除：此处不再渲染操作栏或弹窗
        except Exception:
            pass

    # --- centralized skill flow ---
    def begin_skill(self, m_index: int, name: str | None):
        """Unified entry to start a skill including targeting session setup."""
        try:
            self.app.selected_member_index = m_index
            self.app.selected_skill_name = name
            src = f"m{m_index}"
            te = getattr(self.app, 'target_engine', None)
            if not te:
                return
            need_exec = te.begin(src, name or '')
            if need_exec:
                # self/aoe or fallback(no candidates): try execute directly
                try:
                    out = self.app._send(f"skill {name} {src}")
                    # app may have _after_cmd to handle rendering/log
                    if hasattr(self.app, '_after_cmd'):
                        try:
                            resp = out[0] if isinstance(out, (list, tuple)) and len(out) > 0 else out
                        except Exception:
                            resp = out
                        self.app._after_cmd(resp)
                finally:
                    self.clear_all()
                    try:
                        if hasattr(self.app, '_render_operations'):
                            self.app._render_operations()
                    except Exception:
                        pass
                return
            # Enter targeting mode: update highlights & ops
            try:
                if hasattr(self.app, '_update_target_highlights'):
                    self.app._update_target_highlights()
            except Exception:
                pass
                # 底部操作区已移除：不再渲染
        except Exception:
            pass

    def confirm_skill(self):
        """Confirm current selection and execute skill."""
        if hasattr(self.app, '_confirm_skill'):
            return self.app._confirm_skill()
        # Mini fallback
        try:
            m_index = getattr(self.app, 'selected_member_index', None)
            if not m_index:
                return
            name = getattr(self.app, 'selected_skill_name', None)
            src = f"m{m_index}"
            selected = []
            try:
                te = getattr(self.app, 'target_engine', None)
                if te and te.is_ready():
                    selected = te.get_selected()
            except Exception:
                selected = []
            if not selected and getattr(self.app, 'skill_target_token', None):
                selected = [self.app.skill_target_token]
            if name in (None, 'attack') and selected:
                out = self.app._send(f"a {src} {selected[0]}")
            elif name == 'basic_heal' and selected:
                out = self.app._send(" ".join(["skill", "basic_heal", src, selected[0]]))
            else:
                if selected:
                    out = self.app._send(" ".join(["skill", name or "", src] + selected).strip())
                else:
                    out = self.app._send(f"skill {name} {src}")
        finally:
            try:
                self.clear_all()
            finally:
                # 底部操作区已移除：不再渲染
                pass

    def cancel_skill(self):
        """Cancel current targeting/skill session and restore UI."""
        try:
            self.clear_all()
        finally:
            # 底部操作区已移除：不再渲染
            pass

    def on_enemy_click(self, idx: int):
        """Handle enemy card click: if in targeting mode, toggle; else set selected enemy."""
        try:
            te = getattr(self.app, 'target_engine', None)
            if te and getattr(te, 'ctx', None):
                self.toggle_token(f"e{idx}")
                return
        except Exception:
            pass
        # normal selection
        try:
            prev = getattr(self.app, 'selected_enemy_index', None)
            if prev and prev in (self.app.enemy_card_wraps or {}):
                try:
                    self.app.enemy_card_wraps[prev].configure(
                        highlightbackground="#cccccc",
                        highlightthickness=self.app._border_default,
                        background=self.app._wrap_bg_default,
                    )
                except Exception:
                    pass
            self.app.selected_enemy_index = idx
            w = (self.app.enemy_card_wraps or {}).get(idx)
            if w:
                try:
                    w.configure(
                        highlightbackground=self.app.HL['sel_enemy_border'],
                        background=self.app.HL['sel_enemy_bg'],
                        highlightthickness=self.app._border_selected_enemy,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def on_ally_click(self, idx: int):
        """Handle ally card click: if in targeting mode, toggle; else set selected member and refresh ops."""
        try:
            te = getattr(self.app, 'target_engine', None)
            if te and getattr(te, 'ctx', None):
                self.toggle_token(f"m{idx}")
                return
        except Exception:
            pass
        try:
            prev = getattr(self.app, 'selected_member_index', None)
            if prev and prev in (self.app.card_wraps or {}):
                try:
                    self.app.card_wraps[prev].configure(
                        highlightbackground="#cccccc",
                        highlightthickness=self.app._border_default,
                        background=self.app._wrap_bg_default,
                    )
                except Exception:
                    pass
            self.app.selected_member_index = idx
            w = (self.app.card_wraps or {}).get(idx)
            if w:
                try:
                    w.configure(
                        highlightbackground=self.app.HL['sel_ally_border'],
                        background=self.app.HL['sel_ally_bg'],
                        highlightthickness=self.app._border_selected_member,
                    )
                except Exception:
                    pass
            try:
                ops = (getattr(self.app, 'views', {}) or {}).get('ops')
                if ops and w and hasattr(ops, 'show_popup'):
                    ops.show_popup(idx, w)
            except Exception:
                pass
        except Exception:
            pass
