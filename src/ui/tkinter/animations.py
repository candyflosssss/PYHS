"""Lightweight Tk animations for feedback (damage/heal/death).
No external deps. Use after() scheduling and small visual tweaks to avoid reflow.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = (h or '').strip()
    if not h.startswith('#'):
        return (204, 204, 204)
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join([c*2 for c in h])
    try:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (204, 204, 204)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _interp_color(a_hex: str, b_hex: str, t: float) -> str:
    ar, ag, ab = _hex_to_rgb(a_hex)
    br, bg, bb = _hex_to_rgb(b_hex)
    return _rgb_to_hex(_lerp(ar, br, t), _lerp(ag, bg, t))


def _get_padx(w: tk.Widget) -> int:
    try:
        info = w.grid_info()
        px = info.get('padx', 0)
        if isinstance(px, tuple):
            return int(px[0])
        return int(px)
    except Exception:
        return 0


def _set_padx(w: tk.Widget, v: int):
    try:
        w.grid_configure(padx=int(v))
    except Exception:
        pass


def _cancel_anim(w: tk.Widget):
    aid = getattr(w, '_anim_after_ids', None)
    if aid:
        try:
            top = w.winfo_toplevel()
            for i in aid:
                try:
                    top.after_cancel(i)
                except Exception:
                    pass
        except Exception:
            pass
    try:
        w._anim_after_ids = []
    except Exception:
        pass


def _schedule(w: tk.Widget, delay: int, cb: Callable[[], None]):
    try:
        i = w.after(delay, cb)
        if not hasattr(w, '_anim_after_ids'):
            w._anim_after_ids = []
        w._anim_after_ids.append(i)
    except Exception:
        pass


def flash_border(wrap: tk.Frame, color: str, base: Optional[str] = None, repeats: int = 2, interval: int = 90):
    """Flash the wrap's highlight border color briefly."""
    _cancel_anim(wrap)
    try:
        base = base or wrap.cget('highlightbackground') or '#cccccc'
    except Exception:
        base = '#cccccc'
    state = {'i': 0}

    def step():
        i = state['i']
        try:
            wrap.configure(highlightbackground=(color if i % 2 == 0 else base))
        except Exception:
            pass
        state['i'] += 1
        if state['i'] < repeats * 2:
            _schedule(wrap, interval, step)
        else:
            try:
                wrap.configure(highlightbackground=base)
            except Exception:
                pass

    step()


def shake(wrap: tk.Frame, amplitude: int = 3, cycles: int = 6, interval: int = 16):
    """Small horizontal shake by tweaking padx. Keep subtle to avoid layout jump."""
    _cancel_anim(wrap)
    base_px = _get_padx(wrap)
    seq = []
    for i in range(cycles):
        d = amplitude if i % 2 == 0 else -amplitude
        seq.append(base_px + d)
    seq.append(base_px)
    state = {'k': 0}

    def step():
        k = state['k']
        if k >= len(seq):
            return
        _set_padx(wrap, seq[k])
        state['k'] += 1
        _schedule(wrap, interval, step)

    step()


def fade_out_and_remove(wrap: tk.Frame, *, to_color: str = '#ffffff', steps: int = 10, interval: int = 40, on_done: Optional[Callable[[], None]] = None):
    """Fade the wrap bg towards to_color, then destroy and call on_done."""
    _cancel_anim(wrap)
    try:
        start = wrap.cget('background') or '#ffffff'
    except Exception:
        start = '#ffffff'
    idx = {'i': 0}

    def step():
        i = idx['i']
        t = i / float(steps)
        try:
            wrap.configure(background=_interp_color(start, to_color, t))
        except Exception:
            pass
        idx['i'] += 1
        if idx['i'] <= steps:
            _schedule(wrap, interval, step)
        else:
            try:
                wrap.destroy()
            except Exception:
                pass
            if callable(on_done):
                try:
                    on_done()
                except Exception:
                    pass

    step()


def on_hit(app, wrap: tk.Frame, kind: str = 'damage'):
    """Composite animation for hit feedback: flash + subtle shake.
    kind: 'damage' | 'heal'
    """
    try:
        if kind == 'heal':
            color = '#27ae60'  # green
        else:
            color = app.HL.get('sel_enemy_border', '#FF4D4F') if getattr(wrap, '_is_enemy', False) else '#c0392b'
    except Exception:
        color = '#c0392b'
    try:
        # 稍微增强可见度：多一次闪烁，shake 稍快
        flash_border(wrap, color, repeats=3, interval=80)
        shake(wrap, amplitude=3, cycles=8, interval=12)
    except Exception:
        pass


def on_death(app, wrap: tk.Frame, *, on_removed: Optional[Callable[[], None]] = None):
    """Death feedback: brief red flash then fade out and remove."""
    try:
        flash_border(wrap, app.HL.get('sel_enemy_border', '#FF4D4F'), repeats=2, interval=80)
    except Exception:
        pass
    try:
        fade_out_and_remove(wrap, to_color=getattr(app, '_wrap_bg_default', '#ffffff'), steps=8, interval=30, on_done=on_removed)
    except Exception:
        # fallback: remove immediately
        try:
            wrap.destroy()
        except Exception:
            pass
        if callable(on_removed):
            try:
                on_removed()
            except Exception:
                pass


def float_text(app, wrap: tk.Frame, text: str, *, color: str = '#c0392b', dy: int = 20, steps: int = 12, interval: int = 28):
    """在卡片上方显示一段浮动文本（如 -10/+5），向上飘散后消失。
    使用 place 叠加到 wrap 顶层，不影响布局。
    """
    try:
        # 取背景色用于融合
        try:
            bg = wrap.cget('background') or getattr(app, '_wrap_bg_default', '#ffffff')
        except Exception:
            bg = getattr(app, '_wrap_bg_default', '#ffffff')
        lbl = tk.Label(wrap, text=str(text), fg=color, bg=bg, font=("Segoe UI", 9, "bold"))
        # 居中置顶
        y0 = 2
        lbl.place(in_=wrap, relx=0.5, y=y0, anchor='n')
        try:
            lbl.lift()
        except Exception:
            pass
        state = {'i': 0}

        def step():
            i = state['i']
            t = i / float(max(1, steps))
            # 向上移动，逐渐淡色（通过近似：插值到背景色）
            try:
                ny = int(y0 - dy * t)
                lbl.place_configure(y=ny)
            except Exception:
                pass
            try:
                # 近似淡出：通过颜色插值接近背景（fg 无 alpha，只能近似）
                from_color = color
                to_color = bg
                lbl.configure(fg=_interp_color(from_color, to_color, t))
            except Exception:
                pass
            state['i'] += 1
            if state['i'] <= steps:
                _schedule(wrap, interval, step)
            else:
                try:
                    lbl.destroy()
                except Exception:
                    pass

        step()
    except Exception:
        pass
