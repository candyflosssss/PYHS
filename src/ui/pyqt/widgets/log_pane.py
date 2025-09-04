from __future__ import annotations

from ..qt_compat import QtWidgets
import json
import re


class LogPane:
    def __init__(self):
        self.panel = QtWidgets.QGroupBox("战斗日志")
        v = QtWidgets.QVBoxLayout(self.panel)
        v.setContentsMargins(0, 0, 0, 0)
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        # Optional external color palette injected by MainWindow/App
        self._palette_override = None
        self.text.setStyleSheet("QTextEdit { font-family: Consolas, 'Courier New', monospace; font-size: 11px; }")
        v.addWidget(self.text)

    def _color_for_type(self, typ: str) -> str:
        # try to fetch from a globally applied palette on app context if present
        try:
            from ..app import GameQtApp  # avoid circular at import time
            # Probe any existing top-level app to grab its palette
            for w in QtWidgets.QApplication.instance().topLevelWidgets():
                # GameQtApp stores _log_tag_colors on app_ctx, but here we only have widgets
                # So fall back to defaults if not found.
                pass
        except Exception:
            pass
        # prefer injected palette if available
        if self._palette_override:
            val = self._palette_override.get(typ)
            if isinstance(val, str):
                return val
        # default palette
        colors = {
            'info': '#222222', 'success': '#27ae60', 'warning': '#E67E22', 'error': '#d9534f',
            'skill': '#E67E22', 'attack': '#c0392b', 'damage': '#c0392b', 'heal': '#27ae60',
            'crit': '#8E44AD', 'miss': '#95A5A6', 'block': '#2C3E50',
        }
        return colors.get(typ.lower(), '#222222')

    def _infer_type(self, s: str) -> str:
        ss = s.strip().lower()
        if ss.startswith('技能 ') or ss.startswith('skill '):
            return 'skill'
        if '暴击' in s or 'crit' in ss:
            return 'crit'
        if '未命中' in s or 'miss' in ss:
            return 'miss'
        if ('造成' in s and '伤害' in s) or '攻击' in s or 'attack' in ss:
            return 'attack'
        if '治疗' in s or '+hp' in ss or 'heal' in ss:
            return 'heal'
        return 'info'

    def _render_ansi_html(self, s: str) -> str:
        # Convert ANSI SGR to span styles (subset)
        ansi_re = re.compile(r"\x1b\[([0-9;]*)m")
        parts = []
        idx = 0
        styles = []
        def style_str():
            css = []
            for t in styles:
                if t == 'bold':
                    css.append('font-weight:bold')
                elif t == 'dim':
                    css.append('opacity:0.85')
                elif t.startswith('fg:'):
                    css.append(f"color:{t[3:]}")
            return ';'.join(css)
        def color_code(c: int) -> str | None:
            mapping = {
                31: '#d9534f', 32: '#27ae60', 33: '#E6B800', 34: '#2980b9', 35: '#8e44ad', 36: '#17a2b8',
                93: '#f1c40f', 95: '#9b59b6', 96: '#1abc9c', 97: '#f2f2f2',
            }
            return mapping.get(c)
        for m in ansi_re.finditer(s):
            if m.start() > idx:
                seg = s[idx:m.start()]
                if seg:
                    st = style_str()
                    if st:
                        parts.append(f"<span style=\"{st}\">{QtWidgets.QTextDocument().toHtmlEscaped(seg)}" if hasattr(QtWidgets.QTextDocument, 'toHtmlEscaped') else f"<span style=\"{st}\">{seg}")
                        parts.append("</span>")
                    else:
                        parts.append(seg)
            codes = m.group(1)
            if not codes:
                styles = []
            else:
                for tok in codes.split(';'):
                    if not tok:
                        continue
                    try:
                        c = int(tok)
                    except Exception:
                        continue
                    if c == 0:
                        styles = []
                    elif c == 1:
                        if 'bold' not in styles:
                            styles.append('bold')
                    elif c == 2:
                        if 'dim' not in styles:
                            styles.append('dim')
                    else:
                        col = color_code(c)
                        if col:
                            styles = [t for t in styles if not t.startswith('fg:')]
                            styles.append(f'fg:{col}')
            idx = m.end()
        if idx < len(s):
            seg = s[idx:]
            st = style_str()
            if st:
                parts.append(f"<span style=\"{st}\">{seg}</span>")
            else:
                parts.append(seg)
        return ''.join(parts)

    def append(self, entry):
        if isinstance(entry, dict):
            typ = (entry.get('type', 'info') or 'info').lower()
            txt = entry.get('text', '')
        else:
            typ = 'info'
            txt = str(entry)
        raw = str(txt)
        has_ansi = bool(re.search(r"\x1b\[[0-9;]*m", raw))
        if not isinstance(entry, dict):
            typ = self._infer_type(raw)
        color = self._color_for_type(typ)
        if has_ansi:
            html = self._render_ansi_html(raw)
            line = f"<div>{html}</div>"
        else:
            esc = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            line = f"<div style=\"color:{color}\">{esc}</div>"
        self.text.moveCursor(self.text.textCursor().End)
        self.text.insertHtml(line)
        self.text.moveCursor(self.text.textCursor().End)

    def set_palette(self, palette: dict):
        """Inject external color palette mapping types to hex strings.
        Example keys: info, warn, error, debug, event. Values like '#RRGGBB'.
        """
        self._palette_override = palette or None
    def clear(self):
        self.text.clear()


