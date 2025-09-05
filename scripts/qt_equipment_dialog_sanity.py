from __future__ import annotations

"""
快速验证 PyQt 装备选择对话框：
- 构造最小 app_ctx/controller/game/player/inventory/m1 结构
- 打开三次对话框（左手/盔甲/右手），观察过滤与悬浮提示
运行：python scripts/qt_equipment_dialog_sanity.py
"""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui.pyqt.qt_compat import QtWidgets
from src.ui.pyqt.dialogs.equipment_dialog import EquipmentDialog
from src.systems.inventory import Inventory
from src.systems.equipment_system import EquipmentSystem, WeaponItem, ArmorItem, ShieldItem


class Member:
    def __init__(self):
        self.name = '测试随从'
        self.equipment = EquipmentSystem()
        self.hp = 10
        self.max_hp = 10

class Player:
    def __init__(self):
        self.inventory = Inventory(max_slots=16)
        # 添加一些装备
        self.inventory.slots.append(type('S', (), {'item': WeaponItem('短剑', '单手', 80, attack=3, defense=0, slot_type='right_hand', is_two_handed=False), 'quantity': 1, 'remove': lambda self, n: None, 'is_empty': lambda self: False})())
        self.inventory.slots.append(type('S', (), {'item': ShieldItem('木盾', '左手', 60, defense=2), 'quantity': 1, 'remove': lambda self, n: None, 'is_empty': lambda self: False})())
        self.inventory.slots.append(type('S', (), {'item': ArmorItem('皮甲', '护甲', 60, defense=2), 'quantity': 1, 'remove': lambda self, n: None, 'is_empty': lambda self: False})())
        self.inventory.slots.append(type('S', (), {'item': WeaponItem('大剑', '双手', 100, attack=6, defense=0, slot_type='left_hand', is_two_handed=True), 'quantity': 1, 'remove': lambda self, n: None, 'is_empty': lambda self: False})())

class Game:
    def __init__(self):
        self.player = Player()
        self.log = print

class Controller:
    def __init__(self):
        self.game = Game()

class Ctx:
    def __init__(self):
        self.controller = Controller()


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ctx = Ctx()
    m = Member()
    # 假设成员在 board[0]
    ctx.controller.game.player.board = [m]

    for slot in ('left', 'armor', 'right'):
        dlg = EquipmentDialog(ctx, None, 1, slot)
        res = dlg.get_result()
        print(f'slot={slot} chosen={res}')

if __name__ == '__main__':
    main()
