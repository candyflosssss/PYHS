from __future__ import annotations

import json
import re
import tkinter as tk
from tkinter import ttk

class LogPane:
    """Encapsulates the Text widget and structured log rendering with semantic tags.
    Keeps tooltip/meta storage internal, exposing append(log) and clear().
    """

    def __init__(self, parent: tk.Widget, tag_colors: dict | None = None):
        frame = ttk.LabelFrame(parent, text="战斗日志")
        frame.grid(row=0, column=0, sticky='nsew', padx=(0, 0), pady=(3, 3))
        self.frame = frame
        self.text = tk.Text(frame, height=10, wrap='word')
        try:
            # 统一基础字体
            self.text.configure(font=("Segoe UI", 12))
        except Exception:
            pass
        sb = ttk.Scrollbar(frame, orient='vertical', command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._meta = {}
        # tags
        try:
            pal = tag_colors or {}
            self.text.tag_configure('info', foreground=pal.get('info', '#222'))
            self.text.tag_configure('success', foreground=pal.get('success', '#27ae60'))
            self.text.tag_configure('warning', foreground=pal.get('warning', '#E67E22'))
            self.text.tag_configure('error', foreground=pal.get('error', '#d9534f'), underline=True)
            # 用于普通状态行（不用于细节行上色，避免覆盖片段色）
            self.text.tag_configure('state', foreground=pal.get('state', "#666"))
            self.text.tag_configure('detail', font=("Segoe UI", 12, 'italic'))
            self.text.tag_configure('skill', foreground=pal.get('skill', '#E67E22'), font=("Segoe UI", 12, 'bold'))
            self.text.tag_configure('attack', foreground=pal.get('attack', '#c0392b'), font=("Segoe UI", 12, 'bold'))
            self.text.tag_configure('heal', foreground=pal.get('heal', '#27ae60'), font=("Segoe UI", 12, 'bold'))
            self.text.tag_configure('crit', foreground=pal.get('crit', '#8E44AD'), font=("Segoe UI", 12, 'bold'))
            self.text.tag_configure('miss', foreground=pal.get('miss', '#95A5A6'), font=("Segoe UI", 12, 'italic'))
            self.text.tag_configure('block', foreground=pal.get('block', '#2C3E50'), font=("Segoe UI", 12))
            # ANSI 基础色映射（供控制台样式转义到 Tk）
            self.text.tag_configure('ansi_bold', font=("Segoe UI", 12, 'bold'))
            # 不用前景色覆盖，以斜体表示次要
            self.text.tag_configure('ansi_dim', font=("Segoe UI", 12, 'italic'))
            self.text.tag_configure('fg_red', foreground='#d9534f')
            self.text.tag_configure('fg_green', foreground='#27ae60')
            self.text.tag_configure('fg_yellow', foreground='#E6B800')
            self.text.tag_configure('fg_blue', foreground='#2980b9')
            self.text.tag_configure('fg_magenta', foreground='#8e44ad')
            self.text.tag_configure('fg_cyan', foreground='#17a2b8')
            self.text.tag_configure('fg_bright_white', foreground='#f2f2f2')
            self.text.tag_configure('fg_bright_cyan', foreground='#1abc9c')
            self.text.tag_configure('fg_bright_yellow', foreground='#f1c40f')
            self.text.tag_configure('fg_bright_magenta', foreground='#9b59b6')
        except Exception:
            pass

    def widget(self) -> tk.Text:
        return self.text

    def append(self, entry):
        try:
            if isinstance(entry, dict):
                typ = (entry.get('type', 'info') or 'info').lower()
                txt = entry.get('text', '')
                meta = entry.get('meta', {}) or {}
            else:
                typ = 'info'
                txt = str(entry)
                meta = {}
            raw_txt = str(txt)
            # 检测是否包含 ANSI 片段
            has_ansi = bool(re.search(r"\x1b\[[0-9;]*m", raw_txt))
            # 文本启发式类型推断（非细节行），以沿用主题色
            def _infer_type_from_text(s: str) -> str:
                ss = s.strip()
                if ss.startswith('技能 ') or ss.lower().startswith('skill '):
                    return 'skill'
                if '暴击' in ss or 'crit' in ss.lower():
                    return 'crit'
                if '未命中' in ss or 'miss' in ss.lower():
                    return 'miss'
                if ('造成' in ss and '伤害' in ss) or '攻击' in ss or 'attack' in ss.lower():
                    return 'attack'
                if '治疗' in ss or '+HP' in ss or 'heal' in ss.lower():
                    return 'heal'
                return 'info'
            # 插入文本（支持 ANSI 着色）
            base_tag = None
            try:
                eff = typ
                if not isinstance(entry, dict):
                    eff = _infer_type_from_text(raw_txt)
                base_tag = eff
            except Exception:
                base_tag = 'info'

            start = self.text.index(tk.END)
            if has_ansi:
                # 对包含 ANSI 的文本，不施加整行颜色，避免覆盖片段色
                extra = []
                # 细节行用斜体强调，不覆盖颜色
                if str(raw_txt).lstrip().startswith('·') or str(raw_txt).startswith('  ·'):
                    extra.append('detail')
                self._insert_with_ansi(raw_txt.rstrip("\n"), extra_tags=extra)
                self.text.insert(tk.END, "\n")
            else:
                # 无 ANSI 时，整行使用类型颜色；细节行用 detail 样式
                tags = [base_tag] if base_tag else []
                is_detail = False
                if str(raw_txt).lstrip().startswith('·') or str(raw_txt).startswith('  ·'):
                    tags.append('detail')
                    is_detail = True
                # 保留前导空格与中点，避免缩进丢失；仅去除行尾换行
                text_to_insert = raw_txt.rstrip("\n")
                self.text.insert(tk.END, text_to_insert + "\n", tuple(tags))
            end = self.text.index(tk.END)
            try:
                palette = {
                    'info': 'info','success':'success','warning':'warning','error':'error','state':'state',
                    'skill':'skill',
                    'attack':'attack','damage':'attack','heal':'heal','crit':'crit','miss':'miss','block':'block'
                }
                # 无 ANSI 的情况下才补整行颜色；细节行不涂前景色
                if not has_ansi:
                    if not (str(raw_txt).lstrip().startswith('·') or str(raw_txt).startswith('  ·')):
                        self.text.tag_add(palette.get(base_tag or 'info', 'info'), start, end)
            except Exception:
                pass
            try:
                self.text.tag_config(start, underline=False)
                self._meta[start] = meta
            except Exception:
                pass
            self.text.see(tk.END)
        except Exception:
            try:
                self.text.insert(tk.END, str(entry) + "\n")
                self.text.see(tk.END)
            except Exception:
                pass

    def _insert_with_ansi(self, s: str, extra_tags: list[str] | None = None):
        """解析一行包含 ANSI 转义的字符串，将片段按当前样式插入，并应用 Tk tags。
        支持的代码：0(重置) 1(加粗) 2(淡色) 31-36 基色，93/95/96/97 亮色。
        """
        try:
            pos = 0
            tags: set[str] = set(extra_tags or [])
            for m in re.finditer(r"\x1b\[([0-9;]*)m", s):
                if m.start() > pos:
                    seg = s[pos:m.start()]
                    if seg:
                        self.text.insert(tk.END, seg, tuple(tags))
                codes = m.group(1)
                # 解析样式码
                if not codes:
                    tags.clear()
                else:
                    for code in codes.split(';'):
                        if not code:
                            continue
                        try:
                            c = int(code)
                        except Exception:
                            continue
                        if c == 0:
                            # reset to only extra tags
                            tags = set(extra_tags or [])
                        elif c == 1:
                            tags.add('ansi_bold')
                        elif c == 2:
                            tags.add('ansi_dim')
                        elif c == 31:
                            tags.discard('fg_green'); tags.discard('fg_yellow'); tags.discard('fg_blue'); tags.discard('fg_magenta'); tags.discard('fg_cyan')
                            tags.discard('fg_bright_white'); tags.discard('fg_bright_cyan'); tags.discard('fg_bright_yellow'); tags.discard('fg_bright_magenta')
                            tags.add('fg_red')
                        elif c == 32:
                            tags = {t for t in tags if not t.startswith('fg_')}
                            tags.add('fg_green')
                        elif c == 33:
                            tags = {t for t in tags if not t.startswith('fg_')}
                            tags.add('fg_yellow')
                        elif c == 34:
                            tags = {t for t in tags if not t.startswith('fg_')}
                            tags.add('fg_blue')
                        elif c == 35:
                            tags = {t for t in tags if not t.startswith('fg_')}
                            tags.add('fg_magenta')
                        elif c == 36:
                            tags = {t for t in tags if not t.startswith('fg_')}
                            tags.add('fg_cyan')
                        elif c == 93:
                            tags = {t for t in tags if not t.startswith('fg_')}
                            tags.add('fg_bright_yellow')
                        elif c == 95:
                            tags = {t for t in tags if not t.startswith('fg_')}
                            tags.add('fg_bright_magenta')
                        elif c == 96:
                            tags = {t for t in tags if not t.startswith('fg_')}
                            tags.add('fg_bright_cyan')
                        elif c == 97:
                            tags = {t for t in tags if not t.startswith('fg_')}
                            tags.add('fg_bright_white')
                pos = m.end()
            if pos < len(s):
                self.text.insert(tk.END, s[pos:], tuple(tags))
        except Exception:
            # 失败则退回为纯文本
            try:
                self.text.insert(tk.END, re.sub(r"\x1b\[[0-9;]*m", "", s))
            except Exception:
                self.text.insert(tk.END, s)

    def clear(self):
        try:
            self.text.delete('1.0', tk.END)
            self._meta.clear()
        except Exception:
            pass

    def bind_hover_tooltip(self):
        def on_motion(event):
            try:
                idx = self.text.index(f"@{event.x},{event.y}")
                line_no = idx.split('.')[0]
                key = f"{line_no}.0"
                meta = self._meta.get(key)
                # reuse a simple tooltip window managed here
                if getattr(self, '_tip_key', None) == key and getattr(self, '_tip_win', None):
                    return
                if getattr(self, '_tip_win', None):
                    try:
                        self._tip_win.destroy()
                    except Exception:
                        pass
                    self._tip_win = None
                    self._tip_key = None
                if not meta:
                    return
                text = json.dumps(meta, ensure_ascii=False, indent=1)
                x = self.text.winfo_rootx() + event.x + 12
                y = self.text.winfo_rooty() + event.y + 12
                tw = tk.Toplevel(self.text)
                tw.wm_overrideredirect(True)
                tw.wm_geometry(f"+{x}+{y}")
                ttk.Label(tw, text=text, relief='solid', borderwidth=1, padding=6, background='#ffffe0').pack()
                self._tip_win = tw
                self._tip_key = key
            except Exception:
                pass
        try:
            self.text.bind('<Motion>', on_motion)
        except Exception:
            pass
