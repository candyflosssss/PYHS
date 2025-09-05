from __future__ import annotations

"""
无头验证：
- 左手为双手武器时，右手按钮应禁用，文本显示占用（右手: -）。
- 左手为单手时，右手按钮可用。
- 敌方卡片全部禁用。
运行：python scripts/qt_equipment_bar_sanity.py
"""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.ui.pyqt.qt_compat import QtWidgets
from src.ui.pyqt.widgets.card import CardWidget


class Eq:
    def __init__(self, l=None, r=None, a=None):
        self.left_hand = l
        self.right_hand = r
        self.armor = a


class Item:
    def __init__(self, name: str, two: bool = False):
        self.name = name
        self.is_two_handed = two


class Model:
    def __init__(self, eq=None):
        self.name = '测试'
        self.equipment = eq
        self.hp = 5
        self.max_hp = 10
        self.stamina = 2
        self.stamina_max = 4


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ctx = type('Ctx', (), {})()
    setattr(ctx, '_slot_click', lambda *a, **k: None)

    # Case1: 双手武器在左手 -> 右手禁用
    m1 = Model(Eq(Item('大剑', True), None, None))
    w1 = CardWidget(ctx, m1, 1, is_enemy=False)
    print('case1 enabled_right=', w1.btn_right.isEnabled(), 'text_right=', w1.btn_right.text())

    # Case2: 单手左手 + 右手空 -> 右手可用
    m2 = Model(Eq(Item('短剑', False), None, None))
    w2 = CardWidget(ctx, m2, 1, is_enemy=False)
    print('case2 enabled_right=', w2.btn_right.isEnabled(), 'text_right=', w2.btn_right.text())

    # Case3: 敌人 -> 全部禁用
    m3 = Model(Eq(Item('锤子', False), Item('盾', False), None))
    w3 = CardWidget(ctx, m3, 1, is_enemy=True)
    print('case3 enabled_left=', w3.btn_left.isEnabled(), 'enabled_right=', w3.btn_right.isEnabled())


if __name__ == '__main__':
    main()
