"""
简化版单人 PvE 控制器
- 负责命令行交互与视图渲染；核心战斗与数值逻辑在 SimplePvEGame 中。
- 抽取重复逻辑（区块映射、消息常量），提高可读性与扩展性。
"""

from typing import Callable, List, Tuple

from game_modes.simple_pve_game import SimplePvEGame


class SimplePvEController:
    def __init__(self):
        name = input("请输入你的名字: ").strip() or "玩家"
        self.game = SimplePvEGame(name)
        self.game.start_turn()
        self.history: list[str] = []  # 操作历史（最近 50 条）
        self.info: list[str] = []     # 信息区（最近一次关键反馈）
        # 区块渲染映射
        self.sections: dict[str, Callable[[], str]] = {
            '0': self._section_player,
            '1': self._section_enemy,
            '2': self._section_resources,
            '3': self._section_history,
            '4': self._section_inventory,
            '5': self._section_info,
        }
        # 常用消息
        self.MSG_INVALID_SECTION = "无效区域编号 (0-5)"
        self.MSG_HELP_TITLE = "=== 简单 PvE 指令帮助 ==="
        self.MSG_HELP = (
            "s <编号> : 显示区域 (0=自己 1=敌人 2=资源 3=历史 4=背包 5=信息)\n"
            "p <手牌序号> : 出牌\n"
            "a <随从序号> e<敌人序号> : 攻击该敌人\n"
            "take <资源序号> : 拾取资源到背包\n"
            "use <物品名> [mN] : 使用背包物品(可指定目标随从)\n"
            "end : 结束回合\n"
            "i|inv : 查看背包  | h : 帮助  | q : 退出"
        )
        self._print_help(initial=True)

    # --- 帮助与区域显示 ---
    def _print_help(self, initial=False):
        print()
        print(self.MSG_HELP_TITLE if initial else "=== 帮助 ===")
        print(self.MSG_HELP)
        if initial:
            print("输入指令开始。示例: s 0 显示自己状态")

    # (移除清屏) 直接打印文本
    def _print(self, text: str):
        print(text)

    def _clear(self):
        # 跨平台清屏：Windows 使用 cls，其他使用 clear；失败则发 ANSI 清屏
        try:
            import os
            os.system('cls' if os.name == 'nt' else 'clear')
        except Exception:
            print("\033c", end="")

    def _record(self, line: str):
        self.history.append(line)
        if len(self.history) > 50:
            self.history.pop(0)

    # --- 区域内容 ---
    def _section_player(self):
        s = self.game.get_state()
        lines = [f"回合:{s['turn']}"]
        lines.append("手牌:")
        if s['hand']:
            for i, c in enumerate(s['hand'], 1):
                lines.append(f"  {i}. {c}")
        else:
            lines.append("  (空)")
        lines.append("随从:")
        if s['board']:
            for c in s['board']:
                lines.append(f"  {c}")
        else:
            lines.append("  (空)")
        return "\n".join(lines)

    def _section_enemy(self):
        s = self.game.get_state()
        lines = [f"回合:{s['turn']}", "敌人:"]
        if s['enemies']:
            lines.extend(f"  {e}" for e in s['enemies'])
        else:
            lines.append("  (无)")
        return "\n".join(lines)

    def _section_resources(self):
        s = self.game.get_state()
        res = s.get('resources', [])
        lines = [f"回合:{s['turn']}", "资源区:"]
        if res:
            for i, r in enumerate(res, 1):
                lines.append(f"  {i}. {r}")
        else:
            lines.append("  (空)")
        return "\n".join(lines)

    def _section_inventory(self):
        inv = self.game.player.inventory
        lines = [f"背包 ({len(inv.slots)}/{inv.max_slots})"]
        if inv.slots:
            for i, slot in enumerate(inv.slots, 1):
                lines.append(f"  {i}. {slot}")
        else:
            lines.append("  (空)")
        return "\n".join(lines)

    def _section_history(self):
        if not self.history:
            return "历史: (无)"
        return "历史(最新在下):\n" + "\n".join(self.history[-20:])

    def _section_info(self):
        if not self.info:
            return "信息区: (无)"
        return "信息区:\n" + "\n".join(self.info[-10:])

    def _show_section(self, idx: str):
        func = self.sections.get(idx)
        if not func:
            self._print(self.MSG_INVALID_SECTION)
            return
        content = func()
        self._print(content)

    # --- 主循环 ---
    def loop(self):
        while self.game.running:
            raw = input('> ').strip()
            if not raw:
                continue
            # 每次执行指令前清屏，让该次输出在干净界面呈现
            self._clear()
            out_lines, should_exit = self._process_command(raw)
            if out_lines:
                self._print("\n".join(out_lines))
            if should_exit:
                break
        # 结束输出（场景模式无英雄HP/Boss，这里仅打印退出）
        self._print('游戏结束')

    def _process_command(self, cmd_line: str):
        """处理单条命令，返回 (输出行列表, 是否退出循环)"""
        parts = cmd_line.split()
        if not parts:
            return [], False
        c = parts[0].lower()
        args = parts[1:]
        out = []
        if c == 'q':
            out.append('退出游戏')
            return out, True
        if c == 'h':
            self._print_help()
            return [], False  # 已直接显示帮助
        if c == 's':
            if args:
                key = args[0]
                func = self.sections.get(key)
                out.append(func() if func else self.MSG_INVALID_SECTION)
            else:
                # 等价于 "s 0-s 1-s 2-s 3"
                for key in ['0','1','2','3','4','5']:
                    out.append(self.sections[key]())
            return out, False
        if c in ('i', 'inv'):
            out.append(self._section_inventory())
            return out, False
        if c == 'take':
            if not args:
                # 缺少参数时列出现有资源并给出用法
                s = self.game.get_state()
                res = s.get('resources', [])
                lines = ["缺少资源序号。用法: take <资源序号>"]
                if res:
                    lines.append('当前资源:')
                    for i, r in enumerate(res, 1):
                        lines.append(f"  {i}. {r}")
                else:
                    lines.append('资源区当前为空')
                return lines, False
            try:
                ridx = int(args[0]) - 1
                res_list = getattr(self.game, 'resources', [])
                if not (0 <= ridx < len(res_list)):
                    s = self.game.get_state()
                    res = s.get('resources', [])
                    lines = ["资源序号无效。用法: take <资源序号>"]
                    if res:
                        lines.append('当前资源:')
                        for i, r in enumerate(res, 1):
                            lines.append(f"  {i}. {r}")
                    else:
                        lines.append('资源区当前为空')
                    return lines, False
                res = res_list.pop(ridx)
                # 尝试转换为背包物品
                from systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
                from systems.inventory import ConsumableItem, MaterialItem
                item = None
                if res.item_type == 'weapon':
                    item = WeaponItem(res.name, f"从资源拾取的{res.name}", 50, attack=res.effect_value)
                elif res.item_type == 'armor':
                    item = ArmorItem(res.name, f"从资源拾取的{res.name}", 50, defense=res.effect_value)
                elif res.item_type == 'shield':
                    item = ShieldItem(res.name, f"从资源拾取的{res.name}", 50, defense=res.effect_value)
                elif res.item_type == 'potion':
                    def effect(player, target):
                        # 简单：为玩家回1*effect_value血
                        player.heal(res.effect_value)
                    item = ConsumableItem(res.name, f"恢复{res.effect_value}点生命", max_stack=5, effect=effect)
                else:
                    item = MaterialItem(res.name, f"材料，价值{res.effect_value}")
                added = self.game.player.add_item(item, 1)
                msg = f"拾取 {res} -> 背包+{added}"
                self._record(msg)
                # 信息区
                self.info = [msg]
                # 合并日志
                logs = getattr(self.game, 'pop_logs', None)
                if callable(logs):
                    for line in logs():
                        detail = f"  · {line}"
                        self._record(detail)
                        self.info.append(detail)
                out.append(msg)
            except ValueError:
                out.append('资源序号需为数字')
            return out, False
        if c == 'use':
            if not args:
                # 缺少物品名：列出背包与用法
                inv = self.game.player.inventory
                lines = ["缺少物品名。用法: use <物品名> [mN]", "当前背包:"]
                if inv.slots:
                    for i, slot in enumerate(inv.slots, 1):
                        lines.append(f"  {i}. {slot}")
                    lines.append("提示：装备(如 武器/护甲/盾牌)通常需要指定目标 mN，例如: use 木剑 m1")
                else:
                    lines.append("  (空)")
                return lines, False
            name = args[0]
            tgt = None
            if len(args) >= 2:
                tgt = self._resolve_target_token(args[1])
            # 如果可能是装备且未提供目标，给出引导或交互
            if tgt is None:
                try:
                    from systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
                except Exception:
                    WeaponItem = ArmorItem = ShieldItem = tuple()
                inv = self.game.player.inventory
                item_obj = None
                for slot in inv.slots:
                    if slot.item.name == name:
                        item_obj = slot.item
                        break
                if item_obj is not None and isinstance(item_obj, (WeaponItem, ArmorItem, ShieldItem)):
                    # 需要指定随从目标
                    self._print('该物品为装备，需要指定随从作为目标(mN)。可选:')
                    board = self.game.player.board
                    if board:
                        for i, m in enumerate(board, 1):
                            self._print(f"  m{i}. {m}")
                        token = input('选择目标(如 m1，回车取消): ').strip()
                        if not token:
                            return ['已取消使用物品'], False
                        tgt = self._resolve_target_token(token)
                        if tgt is None:
                            return ['无效的目标'], False
                    else:
                        return ['当前没有可装备目标(随从为空)'], False
            # 尝试/记录
            attempt = f"{self.game.player.name} 使用物品 {name}{(' 对 ' + self._format_target(tgt)) if tgt is not None else ''}"
            ok, msg = self.game.player.use_item(name, 1, target=tgt)
            self._record(f"{attempt} -> {msg}")
            logs = getattr(self.game, 'pop_logs', None)
            info_lines = [f"{attempt} -> {msg}"]
            if callable(logs):
                for line in logs():
                    detail = f"  · {line}"
                    self._record(detail)
                    info_lines.append(detail)
            # 汇总到信息区
            self.info = info_lines
            out.append(msg)
            return out, False
        if c == 'p':
            if not args:
                # 无参数时：显示手牌与用法提示
                s = self.game.get_state()
                out.append('缺少手牌序号。用法: p <手牌序号> [target]')
                if s.get('hand'):
                    out.append('当前手牌:')
                    for i, c in enumerate(s['hand'], 1):
                        out.append(f"  {i}. {c}")
                return out, False
            try:
                idx = int(args[0]) - 1
                # 读取卡牌对象
                card = self.game.player.hand[idx] if 0 <= idx < len(self.game.player.hand) else None
                if card is None:
                    out.append('无效的手牌序号')
                    return out, False

                # 需要目标的卡，若未提供，交互式罗列目标
                target = None
                requires_target = getattr(card, 'requires_target', False)
                if len(args) >= 2:
                    target_token = args[1]
                    target = self._resolve_target_token(target_token)
                elif requires_target:
                    # 一步式交互：列出并请求目标
                    self._print('该卡牌需要目标。可选:')
                    for line in self._list_play_targets():
                        self._print(line)
                    token = input('选择目标(如 e1 / m1，回车取消): ').strip()
                    if not token:
                        out.append('已取消出牌')
                        return out, False
                    target = self._resolve_target_token(token)
                    if target is None:
                        out.append('无效的目标')
                        return out, False

                # 构建更详细的历史记录
                # 构建更自然的语句
                card_desc = str(card)
                target_desc = self._format_target(target) if target is not None else '(无)'
                attempt = f"{self.game.player.name} 使用 {card_desc}{(' 对 ' + target_desc) if target is not None else ''}"

                ok = self.game.play_card(idx, target)
                msg = '出牌成功' if ok else '出牌失败'
                self._record(f"{attempt} -> {msg}")
                # 合并来自游戏的细节日志
                logs = getattr(self.game, 'pop_logs', None)
                info_lines = [f"{attempt} -> {msg}"]
                if callable(logs):
                    for line in logs():
                        detail = f"  · {line}"
                        self._record(detail)
                        info_lines.append(detail)
                # 把出牌反馈收纳到信息区
                self.info = info_lines
                # 出牌后视为使用一次 s 指令：直接展示所有板块
                for key in ['0','1','2','3','4','5']:
                    out.append(self.sections[key]())
            except ValueError:
                out.append('请输入手牌序号')
            return out, False
        if c == 'a':
            if len(args) < 2:
                # 引导：列出我方随从、敌人
                lines = ['缺少目标。用法: a <随从序号> e<敌人序号>', '我方随从:']
                board = self.game.player.board
                if board:
                    for i, m in enumerate(board, 1):
                        lines.append(f"  {i}. {m}")
                else:
                    lines.append('  (无)')
                enemies = getattr(self.game, 'enemies', None) or getattr(self.game, 'enemy_zone', [])
                lines.append('敌人:')
                if enemies:
                    for i, e in enumerate(enemies, 1):
                        lines.append(f"  e{i}. {e}")
                else:
                    lines.append('  (无)')
                # 无 Boss 区
                return lines, False
            try:
                m_idx = int(args[0]) - 1
                tgt = args[1]
                if tgt.startswith('e'):
                    try:
                        e_idx = int(tgt[1:]) - 1
                        attempt = f"{self.game.player.name} 的随从#{m_idx+1} 攻击 敌人 e{e_idx+1}"
                        _, msg = self.game.attack_enemy(m_idx, e_idx)
                        self._record(f"{attempt} -> {msg}")
                        logs = getattr(self.game, 'pop_logs', None)
                        info_lines = [f"{attempt} -> {msg}"]
                        if callable(logs):
                            for line in logs():
                                detail = f"  · {line}"
                                self._record(detail)
                                info_lines.append(detail)
                        self.info = info_lines
                        out.append(msg)
                    except ValueError:
                        out.extend(['敌人格式 e数字', '示例: a 1 e1'])
                elif tgt == 'boss':
                    out.append('当前模式无 Boss 区')
                else:
                    out.extend(['目标格式: e数字', '示例: a 1 e1'])
            except ValueError:
                # 同样提供引导
                guide = ['随从序号错误。你的随从:']
                board = self.game.player.board
                if board:
                    for i, m in enumerate(board, 1):
                        guide.append(f"  {i}. {m}")
                else:
                    guide.append('  (无)')
                out.extend(guide)
            return out, False
        if c == 'end':
            self.game.end_turn()
            msg = f"进入回合 {self.game.turn}"
            self._record(msg)
            logs = getattr(self.game, 'pop_logs', None)
            if callable(logs):
                for line in logs():
                    self._record(f"  · {line}")
            out.append(msg)
            return out, False
        out.append('未知指令，h 查看帮助')
        return out, False

    # --- 目标解析与列出 ---
    def _resolve_target_token(self, token: str):
        token = token.lower()
        # 敌人: e1/e2...
        if token.startswith('e'):
            try:
                idx = int(token[1:]) - 1
                enemies = getattr(self.game, 'enemies', None) or getattr(self.game, 'enemy_zone', [])
                return enemies[idx] if 0 <= idx < len(enemies) else None
            except Exception:
                return None
        # Boss
        # 场景模式无 Boss
        if token == 'boss':
            return None
        # 我方随从: m1/m2...
        if token.startswith('m'):
            try:
                idx = int(token[1:]) - 1
                board = self.game.player.board
                return board[idx] if 0 <= idx < len(board) else None
            except Exception:
                return None
        # 敌方法术目标保留位（多人时可扩展）
        return None

    def _list_play_targets(self):
        lines = []
        # 敌人
        enemies = getattr(self.game, 'enemies', None) or getattr(self.game, 'enemy_zone', [])
        if enemies:
            lines.append('敌人:')
            for i, e in enumerate(enemies, 1):
                lines.append(f"  e{i}. {e}")
    # 场景模式无 Boss
        # 我方随从
        board = self.game.player.board
        if board:
            lines.append('我方随从:')
            for i, m in enumerate(board, 1):
                lines.append(f"  m{i}. {m}")
        if not lines:
            lines.append('(当前没有可选目标)')
        return lines

    # --- 辅助格式化 ---
    def _format_target(self, target) -> str:
        if target is None:
            return '(无)'
        try:
            return str(target)
        except Exception:
            return f"{type(target).__name__}"


def start_simple_pve_game():
    controller = SimplePvEController()
    controller.loop()

# 兼容旧入口：主程序调用的多人PvE入口名
def start_pve_multiplayer_game():
    start_simple_pve_game()
