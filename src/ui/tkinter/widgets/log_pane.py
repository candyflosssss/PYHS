from __future__ import annotations

import json
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
            self.text.tag_configure('state', foreground=pal.get('state', "#666"))
            self.text.tag_configure('attack', foreground=pal.get('attack', '#c0392b'), font=("Segoe UI", 8, 'bold'))
            self.text.tag_configure('heal', foreground=pal.get('heal', '#27ae60'), font=("Segoe UI", 8, 'bold'))
            self.text.tag_configure('crit', foreground=pal.get('crit', '#8E44AD'), font=("Segoe UI", 8, 'bold'))
            self.text.tag_configure('miss', foreground=pal.get('miss', '#95A5A6'), font=("Segoe UI", 8, 'italic'))
            self.text.tag_configure('block', foreground=pal.get('block', '#2C3E50'), font=("Segoe UI", 8))
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
            start = self.text.index(tk.END)
            self.text.insert(tk.END, str(txt).strip() + "\n")
            end = self.text.index(tk.END)
            try:
                palette = {
                    'info': 'info','success':'success','warning':'warning','error':'error','state':'state',
                    'attack':'attack','damage':'attack','heal':'heal','crit':'crit','miss':'miss','block':'block'
                }
                self.text.tag_add(palette.get(typ, 'info'), start, end)
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
