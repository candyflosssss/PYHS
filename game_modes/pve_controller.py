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
        # 区块渲染映射
        self.sections: dict[str, Callable[[], str]] = {
            '0': self._section_player,
            '1': self._section_enemy,
            '2': self._section_resources,
            '3': self._section_history,
            '4': self._section_inventory,
        }
        # 常用消息
        self.MSG_INVALID_SECTION = "无效区域编号 (0-4)"
        self.MSG_HELP_TITLE = "=== 简单 PvE 指令帮助 ==="
        self.MSG_HELP = (
            "s <编号> : 显示区域 (0=自己 1=敌人+Boss 2=资源 3=历史 4=背包)\n"
            "p <手牌序号> : 出牌\n"
            "a <随从序号> e<敌人序号> : 攻击该敌人\n"
            "a <随从序号> boss : 攻击Boss(需无敌人)\n"
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

    def _record(self, line: str):
        self.history.append(line)
        if len(self.history) > 50:
            self.history.pop(0)

    # --- 区域内容 ---
    def _section_player(self):
        s = self.game.get_state()
        lines = [f"回合:{s['turn']}", f"玩家 HP {s['player_hp']}"]
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
        lines = [f"回合:{s['turn']}", f"Boss: {s['boss']}" , "敌人:"]
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
            out_lines, should_exit = self._process_command(raw)
            if out_lines:
                self._print("\n".join(out_lines))
            if should_exit:
                break
        # 结束输出
        if self.game.player.hp <= 0:
            self._print('你被击败了...')
        elif self.game.boss.hp <= 0:
            self._print('Boss 被击败! 胜利!')
        else:
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
                for key in ['0','1','2','3','4']:
                    out.append(self.sections[key]())
            return out, False
        if c in ('i', 'inv'):
            out.append(self._section_inventory())
            return out, False
        if c == 'p':
            if not args:
                out.append('缺少手牌序号')
                return out, False
            try:
                idx = int(args[0]) - 1
                ok = self.game.play_card(idx)
                msg = '出牌成功' if ok else '出牌失败'
                self._record(msg)
                out.append(msg)
            except ValueError:
                out.append('请输入手牌序号')
            return out, False
        if c == 'a':
            if len(args) < 2:
                out.append('用法: a <随从序号> e<敌人序号>|boss')
                return out, False
            try:
                m_idx = int(args[0]) - 1
                tgt = args[1]
                if tgt.startswith('e'):
                    try:
                        e_idx = int(tgt[1:]) - 1
                        _, msg = self.game.attack_enemy(m_idx, e_idx)
                        self._record(msg)
                        out.append(msg)
                    except ValueError:
                        out.append('敌人格式 e数字')
                elif tgt == 'boss':
                    _, msg = self.game.attack_boss(m_idx)
                    self._record(msg)
                    out.append(msg)
                else:
                    out.append('目标格式: e数字 或 boss')
            except ValueError:
                out.append('随从序号错误')
            return out, False
        if c == 'end':
            self.game.end_turn()
            msg = f"进入回合 {self.game.turn}"
            self._record(msg)
            out.append(msg)
            return out, False
        out.append('未知指令，h 查看帮助')
        return out, False


def start_simple_pve_game():
    controller = SimplePvEController()
    controller.loop()

# 兼容旧入口：主程序调用的多人PvE入口名
def start_pve_multiplayer_game():
    start_simple_pve_game()
