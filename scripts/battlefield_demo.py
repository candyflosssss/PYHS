from __future__ import annotations

import random
import tkinter as tk
from tkinter import ttk

import os, sys, pathlib

# ensure project root on sys.path
THIS_FILE = pathlib.Path(__file__).resolve()
ROOT = THIS_FILE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui.tkinter.views.battlefield_view import BattlefieldView


class Token:
    def __init__(self, name: str):
        self.name = name
    def __repr__(self):
        return f"<{self.name}>"


def main():
    root = tk.Tk()
    root.title("BattlefieldView Demo")
    root.geometry("900x540")

    bf_container = ttk.Frame(root)
    bf_container.pack(fill=tk.BOTH, expand=True)

    bf = BattlefieldView(root)
    bf.attach(bf_container)

    allies = [Token(f"A{i}") for i in range(1, 6)]
    enemies = [Token(f"E{i}") for i in range(1, 5)]
    bf.set_allies(allies)
    bf.set_enemies(enemies)

    # controls
    ctrl = ttk.Frame(root)
    ctrl.pack(fill=tk.X)

    def add_ally():
        bf.add(False, Token(f"A{random.randint(6, 99)}"), index=0)
    def add_enemy():
        bf.add(True, Token(f"E{random.randint(6, 99)}"), index=0)
    def del_ally():
        if bf._allies:
            bf.remove(False, bf._allies[0])
    def del_enemy():
        if bf._enemies:
            bf.remove(True, bf._enemies[0])
    def move_ally():
        if bf._allies:
            t = bf._allies[-1]
            bf.move(False, t, 0)
    def move_enemy():
        if bf._enemies:
            t = bf._enemies[-1]
            bf.move(True, t, 0)
    def shake_random():
        pool = (bf._allies + bf._enemies)
        if pool:
            t = random.choice(pool)
            bf.shake(t in bf._enemies, t)

    for text, cmd in [
        ("+ Ally", add_ally), ("- Ally", del_ally), ("Move Ally", move_ally),
        ("+ Enemy", add_enemy), ("- Enemy", del_enemy), ("Move Enemy", move_enemy),
        ("Shake Any", shake_random)
    ]:
        ttk.Button(ctrl, text=text, command=cmd).pack(side=tk.LEFT, padx=4, pady=6)

    root.mainloop()


if __name__ == "__main__":
    main()
