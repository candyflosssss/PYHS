"""
简化版单人 PvE 控制器
- 负责命令行交互与视图渲染；核心战斗与数值逻辑在 SimplePvEGame 中。
- 抽取重复逻辑（区块映射、消息常量），提高可读性与扩展性。
"""

from typing import Callable, List, Tuple

from game_modes.simple_pve_game import SimplePvEGame
from ui import colors as C


class SimplePvEController:
    def __init__(self, player_name: str | None = None, initial_scene: str | None = None):
        name = (player_name or '').strip() or input("请输入你的名字: ").strip() or "玩家"
        self.game = SimplePvEGame(name)
        # 指定初始场景（若提供）
        if initial_scene:
            try:
                self.game.load_scene(initial_scene, keep_board=False)
            except Exception:
                pass
        self.game.start_turn()
        self.history = []  # 操作历史（最近 10 条）
        self.info = []     # 信息区（最近一次关键反馈）
        # 区块渲染映射
        self.sections = {
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
            "a <队伍序号|mN> e<敌人序号> : 攻击该敌人\n"
            "take|t <rN|序号> : 拾取资源到背包\n"
            "use|u <物品名> [mN] : 使用背包物品(可指定目标队伍成员)\n"
            "equip|eq <物品名|iN> mN : 为指定队员装备(支持背包序号 iN)\n"
            "unequip|uneq mN <left|right|armor> : 卸下队员装备到背包\n"
            "moveeq mN <left|right|armor> mK : 将一名队员的装备直接转移给另一名队员\n"
            "craft|c [list|<索引|名称>] : 合成（背包中会显示可合成，用 cN 快速合成）\n"
            "back|b : 返回上一级场景(若当前场景定义了返回路径)\n"
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
        if len(self.history) > 10:
            self.history.pop(0)

    # --- 区域内容 ---
    def _section_player(self):
        # 直接读取对象以便展示可攻标签
        board = self.game.player.board
        lines = [C.label(f"队伍({len(board)}):")]
        if board:
            pairs: list[tuple[str, str]] = []
            for i, m in enumerate(board, 1):
                status = C.dim('·已攻') if not getattr(m, 'can_attack', False) else C.dim('·可攻')
                # 计算数值：基础攻、装备攻、总攻、防御、生命
                try:
                    base_atk = int(getattr(m, 'base_atk', getattr(m, 'atk', 0)))
                except Exception:
                    base_atk = int(getattr(m, 'atk', 0))
                try:
                    eq_atk = int(m.equipment.get_total_attack() if hasattr(m, 'equipment') and m.equipment else 0)
                except Exception:
                    eq_atk = 0
                total_atk = base_atk + eq_atk
                try:
                    eq_def = int(m.equipment.get_total_defense() if hasattr(m, 'equipment') and m.equipment else 0)
                except Exception:
                    eq_def = 0
                cur_hp = int(getattr(m, 'hp', 0))
                max_hp = int(getattr(m, 'max_hp', cur_hp))
                # 名称（带颜色）
                try:
                    name = getattr(m, 'display_name', None) or m.__class__.__name__
                except Exception:
                    name = '随从'
                name_colored = C.friendly(str(name))
                # DND 概览（可选）
                try:
                    dnd = getattr(m, 'dnd', None)
                    ac = dnd.get('ac') if isinstance(dnd, dict) else None
                    dnd_part = f" AC:{ac}" if ac is not None else ""
                except Exception:
                    dnd_part = ""
                # 装备摘要
                eq = getattr(m, 'equipment', None)
                eq_parts = []
                try:
                    if eq and getattr(eq, 'left_hand', None):
                        lh = eq.left_hand
                        if getattr(lh, 'is_two_handed', False):
                            bonus = []
                            if getattr(lh, 'attack', 0): bonus.append(f"+{lh.attack}攻")
                            if getattr(lh, 'defense', 0): bonus.append(f"+{lh.defense}防")
                            eq_parts.append(f"双手:{lh.name}({ ' '.join(bonus) })" if bonus else f"双手:{lh.name}")
                        else:
                            bonus = []
                            if getattr(lh, 'attack', 0): bonus.append(f"+{lh.attack}攻")
                            if getattr(lh, 'defense', 0): bonus.append(f"+{lh.defense}防")
                            eq_parts.append(f"左:{lh.name}({ ' '.join(bonus) })" if bonus else f"左:{lh.name}")
                    if eq and getattr(eq, 'right_hand', None):
                        rh = eq.right_hand
                        bonus = []
                        if getattr(rh, 'attack', 0): bonus.append(f"+{rh.attack}攻")
                        if getattr(rh, 'defense', 0): bonus.append(f"+{rh.defense}防")
                        eq_parts.append(f"右:{rh.name}({ ' '.join(bonus) })" if bonus else f"右:{rh.name}")
                    if eq and getattr(eq, 'armor', None):
                        ar = eq.armor
                        bonus = []
                        if getattr(ar, 'attack', 0): bonus.append(f"+{ar.attack}攻")
                        if getattr(ar, 'defense', 0): bonus.append(f"+{ar.defense}防")
                        eq_parts.append(f"甲:{ar.name}({ ' '.join(bonus) })" if bonus else f"甲:{ar.name}")
                except Exception:
                    pass
                eq_str = f" [{', '.join(eq_parts)}]" if eq_parts else ""
                # 组装行：名称 [攻 基+装=总计 | HP 当前/最大 | 防 装] [装备摘要] 状态
                atk_str = C.stat_atk(f"{total_atk}攻 ({base_atk}+{eq_atk})")
                hp_str = C.stat_hp(f"{cur_hp}/{max_hp} HP")
                def_str = C.stat_def(f"{eq_def}防")
                stat_str = f"[{atk_str} | {hp_str} | {def_str}]{dnd_part}"
                line = f"{name_colored} {stat_str}{eq_str} {status}"
                pairs.append((f"m{i}", line))
            lines.extend(self._format_token_list(pairs))
        else:
            lines.append("  (空)")
        return "\n".join(lines)

    # --- 渲染辅助 ---
    def _format_token_list(self, pairs: list[tuple[str, str]], pad: int = 2) -> list[str]:
        """将 [(token, text)] 渲染为对齐的行：token 左对齐，名称列起始对齐。
        例如："e1  未上锁的木门(0/2)" / "m1  张伟[8/8]"
        """
        if not pairs:
            return []
        w = max(len(t) for t, _ in pairs)
        gap = ' ' * pad
        return [f"  {t.ljust(w)}{gap}{s}" for t, s in pairs]

    def _section_enemy(self):
        enemies = getattr(self.game, 'enemies', None) or getattr(self.game, 'enemy_zone', [])
        lines = [C.label(f"敌人({len(enemies)}):")]
        if enemies:
            pairs = []
            for i, e in enumerate(enemies, 1):
                try:
                    name = getattr(e, 'name', f'敌人#{i}')
                    atk = int(getattr(e, 'attack', 0))
                    hp = int(getattr(e, 'hp', 0))
                    mhp = int(getattr(e, 'max_hp', hp))
                except Exception:
                    name, atk, hp, mhp = (f'敌人#{i}', 0, 0, 0)
                atk_str = C.stat_atk(f"{atk}攻")
                hp_str = C.stat_hp(f"{hp}/{mhp} HP")
                # 仅给名字上敌人颜色，避免整行染色导致与攻/HP颜色冲突
                name_colored = C.enemy(str(name))
                line = f"{name_colored} [{atk_str} | {hp_str}]"
                pairs.append((f"e{i}", line))
            lines.extend(self._format_token_list(pairs))
        else:
            lines.append("  (无)")
        return "\n".join(lines)

    def _section_resources(self):
        s = self.game.get_state()
        res = s.get('resources', [])
        lines = [C.label(f"资源区({len(res)}):")]
        if res:
            pairs = [(f"r{i}", str(r)) for i, r in enumerate(res, 1)]
            lines.extend(self._format_token_list(pairs))
        else:
            lines.append("  (空)")
        return "\n".join(lines)

    def _section_inventory(self):
        inv = self.game.player.inventory
        lines = [C.label(f"背包({len(inv.slots)}/{inv.max_slots}):")]
        if inv.slots:
            pairs = [(f"i{i}", str(slot)) for i, slot in enumerate(inv.slots, 1)]
            lines.extend(self._format_token_list(pairs))
        else:
            lines.append("  (空)")
        # 附加可合成清单
        craftables = self._craftable_recipes()
        lines.append(C.label(f"可合成({len(craftables)}):"))
        if craftables:
            cpairs = [(f"c{i}", r['name']) for i, r in enumerate(craftables, 1)]
            lines.extend(self._format_token_list(cpairs))
            lines.append(C.dim("提示: 输入 c1/c2... 可快速合成"))
        else:
            lines.append("  (暂无可合成配方)")
        return "\n".join(lines)

    def _section_history(self):
        if not self.history:
            return "历史: (无)"
        return "历史(最新在下):\n" + "\n".join(self.history[-10:])

    def _section_info(self):
        if not self.info:
            return "信息区: (无)"
        lines: list[str] = [C.heading("信息区:")]
        recent = self.info[-10:]
        for i, line in enumerate(recent):
            if i == 0:
                txt = line
                if any(k in txt for k in ("失败", "无效", "错误")):
                    lines.append(C.error(txt))
                elif any(k in txt for k in ("成功", "进入回合", "拾取", "使用", "攻击")):
                    lines.append(C.success(txt))
                else:
                    lines.append(C.warning(txt))
            else:
                # 次要细节用淡色
                lines.append(C.dim(line))
        return "\n".join(lines)

    def _show_section(self, idx: str):
        func = self.sections.get(idx)
        if not func:
            self._print(self.MSG_INVALID_SECTION)
            return
        content = func()
        self._print(content)

    def _render_full_view(self) -> str:
        sep = C.dim('────────────────────────────────')
        parts: list[str] = []
        # 场景标题（显眼）
        try:
            scene_name = getattr(self.game, 'current_scene_title', None) or self.game.current_scene
            if scene_name:
                import os
                title = scene_name if getattr(self.game, 'current_scene_title', None) else os.path.basename(scene_name)
                parts.append(C.heading(f"【场景】{title}"))
                parts.append(sep)
        except Exception:
            pass
        # 信息区置顶
        parts.append(self._section_info())
        parts.append(sep)
        # 队伍 -> 敌人 -> 资源 -> 背包 -> 历史
        parts.append(self._section_player())
        parts.append(sep)
        parts.append(self._section_enemy())
        parts.append(sep)
        parts.append(self._section_resources())
        parts.append(sep)
        parts.append(self._section_inventory())
        parts.append(sep)
        parts.append(self._section_history())
        return "\n".join(parts)

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
                # 展示完整视图（信息区置顶）
                out.append(self._render_full_view())
            return out, False
        # craft 简化：支持 craft 与 c
        if c in ('craft', 'c'):
            return self._cmd_craft(args), False
        if c in ('back', 'b'):
            if getattr(self.game, 'can_navigate_back', None) and self.game.can_navigate_back():
                ok = self.game.navigate_back()
                if ok:
                    self.info = ["已返回上一级", f"  · 当前: {self.game.current_scene_title or self.game.current_scene}"]
                    out.append(self._render_full_view())
                    return out, False
                return ["返回失败"], False
            return ["当前场景未定义返回路径"], False
        if c in ('equip', 'eq'):
            # equip <物品名> mN
            if len(args) == 0:
                # 引导：列出可装备物品与可选队伍目标
                lines = ["用法: equip|eq <物品名|iN> mN", C.label('可装备物品(支持 iN):')]
                try:
                    from systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
                except Exception:
                    WeaponItem = ArmorItem = ShieldItem = tuple()
                inv = self.game.player.inventory
                equip_pairs = []
                for idx, slot in enumerate(inv.slots, 1):
                    it = slot.item
                    if isinstance(it, (WeaponItem, ArmorItem, ShieldItem)):
                        pretty = str(it)
                        equip_pairs.append((f"i{idx}", f"{pretty} x{slot.quantity}"))
                if equip_pairs:
                    lines.extend(self._format_token_list(equip_pairs))
                else:
                    lines.append("  (背包中暂无可装备物品)")
                lines.append(C.label('可选目标:'))
                board = self.game.player.board
                if board:
                    pairs = [(f"m{i}", str(m)) for i, m in enumerate(board, 1)]
                    lines.extend(self._format_token_list(pairs))
                else:
                    lines.append('  (队伍为空)')
                return lines, False
            if len(args) == 1:
                # 仅提供物品名，交互选择目标
                name = args[0]
                self._print(C.label('该指令需要指定队伍成员(mN)作为目标。可选目标:'))
                board = self.game.player.board
                if board:
                    pairs = [(f"m{i}", C.friendly(str(m))) for i, m in enumerate(board, 1)]
                    for line in self._format_token_list(pairs):
                        self._print(line)
                    token = input('选择队伍目标(如 m1，回车取消): ').strip()
                    if not token:
                        return ['已取消装备'], False
                    tgt = self._resolve_target_token(token)
                    if tgt is None:
                        return ['无效的队伍目标'], False
                else:
                    return ['当前没有可装备目标(队伍为空)'], False
                # 支持 iN：如果 name 是 iN，按序号取背包物品
                if name.lower().startswith('i') and name[1:].isdigit():
                    idx = int(name[1:]) - 1
                    inv = self.game.player.inventory
                    if not (0 <= idx < len(inv.slots)):
                        return ["无效的背包序号"], False
                    item = inv.slots[idx].item
                    try:
                        from systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
                    except Exception:
                        WeaponItem = ArmorItem = ShieldItem = tuple()
                    if not isinstance(item, (WeaponItem, ArmorItem, ShieldItem)):
                        return ["该物品不可装备"], False
                    ok = tgt.equipment.equip(item, game=self.game)
                    info_lines = []
                    if ok:
                        # 移除该背包槽位（装备均为不可堆叠）
                        inv.slots.pop(idx)
                        pretty = str(item)
                        info_lines.append(f"为 {self._format_target(tgt)} 装备了 {pretty}")
                    else:
                        info_lines.append("装备失败：槽位冲突或条件不满足")
                    logs = getattr(self.game, 'pop_logs', None)
                    if callable(logs):
                        for line in logs():
                            info_lines.append(f"  · {line}")
                    self.info = info_lines
                else:
                    ok, msg = self.game.player.use_item(name, 1, target=tgt)
                    info_lines = [msg]
                    logs = getattr(self.game, 'pop_logs', None)
                    if callable(logs):
                        for line in logs():
                            info_lines.append(f"  · {line}")
                    self.info = info_lines
                return [self._render_full_view()], False
            # 正常路径：item + mN
            name = args[0]
            tgt = self._resolve_target_token(args[1])
            if tgt is None:
                return ["无效的队伍目标(mN)"], False
            # 支持 iN + mN
            if name.lower().startswith('i') and name[1:].isdigit():
                idx = int(name[1:]) - 1
                inv = self.game.player.inventory
                if not (0 <= idx < len(inv.slots)):
                    return ["无效的背包序号"], False
                item = inv.slots[idx].item
                try:
                    from systems.equipment_system import WeaponItem, ArmorItem, ShieldItem
                except Exception:
                    WeaponItem = ArmorItem = ShieldItem = tuple()
                if not isinstance(item, (WeaponItem, ArmorItem, ShieldItem)):
                    return ["该物品不可装备"], False
                ok = tgt.equipment.equip(item, game=self.game)
                info_lines = []
                if ok:
                    inv.slots.pop(idx)
                    pretty = str(item)
                    info_lines.append(f"为 {self._format_target(tgt)} 装备了 {pretty}")
                else:
                    info_lines.append("装备失败：槽位冲突或条件不满足")
                logs = getattr(self.game, 'pop_logs', None)
                if callable(logs):
                    for line in logs():
                        info_lines.append(f"  · {line}")
                self.info = info_lines
            else:
                ok, msg = self.game.player.use_item(name, 1, target=tgt)
                info_lines = [msg]
                logs = getattr(self.game, 'pop_logs', None)
                if callable(logs):
                    for line in logs():
                        info_lines.append(f"  · {line}")
                self.info = info_lines
            return [self._render_full_view()], False
        if c in ('unequip', 'uneq'):
            # unequip mN <left|right|armor>
            if len(args) == 0:
                # 引导：列出队伍与可卸下槽位
                lines = ["用法: unequip|uneq mN <left|right|armor>", C.label('当前队伍装备:')]
                board = self.game.player.board
                if board:
                    for i, m in enumerate(board, 1):
                        eq = getattr(m, 'equipment', None)
                        parts = []
                        try:
                            if eq and getattr(eq, 'left_hand', None):
                                lh = eq.left_hand
                                bonus = []
                                if getattr(lh, 'attack', 0): bonus.append(f"+{lh.attack}攻")
                                if getattr(lh, 'defense', 0): bonus.append(f"+{lh.defense}防")
                                if getattr(lh, 'is_two_handed', False):
                                    parts.append(f"双手:{lh.name}({ ' '.join(bonus) })" if bonus else f"双手:{lh.name}")
                                else:
                                    parts.append(f"左:{lh.name}({ ' '.join(bonus) })" if bonus else f"左:{lh.name}")
                            if eq and getattr(eq, 'right_hand', None):
                                rh = eq.right_hand
                                bonus = []
                                if getattr(rh, 'attack', 0): bonus.append(f"+{rh.attack}攻")
                                if getattr(rh, 'defense', 0): bonus.append(f"+{rh.defense}防")
                                parts.append(f"右:{rh.name}({ ' '.join(bonus) })" if bonus else f"右:{rh.name}")
                            if eq and getattr(eq, 'armor', None):
                                ar = eq.armor
                                bonus = []
                                if getattr(ar, 'attack', 0): bonus.append(f"+{ar.attack}攻")
                                if getattr(ar, 'defense', 0): bonus.append(f"+{ar.defense}防")
                                parts.append(f"甲:{ar.name}({ ' '.join(bonus) })" if bonus else f"甲:{ar.name}")
                        except Exception:
                            pass
                        eq_str = (" [" + ", ".join(parts) + "]") if parts else ""
                        lines.append(f"  m{i}  {str(m)}{eq_str}")
                else:
                    lines.append('  (队伍为空)')
                lines.append(C.dim('提示: 只可卸下已占用的槽位(left/right/armor)'))
                return lines, False
            if len(args) == 1:
                # 提供了目标但未给槽位 -> 交互选择占用槽位
                tgt = self._resolve_target_token(args[0])
                if tgt is None:
                    return ["无效的队伍目标(mN)"], False
                eq = getattr(tgt, 'equipment', None)
                if not eq:
                    return ["该单位没有装备系统"], False
                choices = []
                if getattr(eq, 'left_hand', None): choices.append('left')
                if getattr(eq, 'right_hand', None): choices.append('right')
                if getattr(eq, 'armor', None): choices.append('armor')
                if not choices:
                    return ["该单位当前没有可卸下的装备"], False
                self._print(C.label(f"可卸下槽位: {', '.join(choices)}"))
                slot_in = input('选择槽位(left|right|armor，回车取消): ').strip().lower()
                if not slot_in:
                    return ['已取消卸下'], False
                args = [args[0], slot_in]
            # 正常路径
            tgt = self._resolve_target_token(args[0])
            if tgt is None:
                return ["无效的队伍目标(mN)"], False
            slot_key = args[1].lower()
            slot_map = {'left':'left_hand','right':'right_hand','armor':'armor'}
            slot = slot_map.get(slot_key)
            if slot is None:
                return ["槽位需为 left|right|armor"], False
            eq = getattr(tgt, 'equipment', None)
            if not eq:
                return ["该单位没有装备系统"], False
            removed = eq.unequip(slot)
            if not removed:
                return ["该槽位当前为空"], False
            added = self.game.player.add_item(removed, 1)
            pretty = str(removed)
            slot_label = {'left_hand':'left','right_hand':'right','armor':'armor'}.get(slot, slot)
            self.info = [f"已卸下({slot_label}) {pretty} -> 背包+{added}"]
            return [self._render_full_view()], False
        if c == 'moveeq':
            # moveeq mA <left|right|armor> mB
            if len(args) < 3:
                return ["用法: moveeq mA <left|right|armor> mB"], False
            src = self._resolve_target_token(args[0])
            dst = self._resolve_target_token(args[2])
            if src is None or dst is None:
                return ["无效的队伍目标(mN)"], False
            slot_key = args[1].lower()
            slot_map = {'left':'left_hand','right':'right_hand','armor':'armor'}
            slot = slot_map.get(slot_key)
            if slot is None:
                return ["槽位需为 left|right|armor"], False
            seq = getattr(src, 'equipment', None)
            deq = getattr(dst, 'equipment', None)
            if not seq or not deq:
                return ["源或目标没有装备系统"], False
            item = seq.unequip(slot)
            if not item:
                return ["源槽位为空"], False
            ok = deq.equip(item, game=self.game)
            if not ok:
                # 放回源
                seq.equip(item, game=self.game)
                return ["目标槽位冲突，移动失败"], False
            self.info = [
                f"已移动装备: {item.name} 从 {self._format_target(args[0])} 到 {self._format_target(args[2])}",
                f"  · {str(item)}"
            ]
            return [self._render_full_view()], False
        if c in ('i', 'inv'):
            out.append(self._section_inventory())
            return out, False
        if c in ('take', 't'):
            if not args:
                # 缺少参数时列出现有资源并给出用法
                s = self.game.get_state()
                res = s.get('resources', [])
                lines = ["缺少资源序号。用法: take|t <rN|序号>"]
                if res:
                    lines.append('当前资源:')
                    pairs = [(f"r{i}", str(r)) for i, r in enumerate(res, 1)]
                    lines.extend(self._format_token_list(pairs))
                else:
                    lines.append('资源区当前为空')
                return lines, False
            try:
                arg0 = args[0].lower()
                if arg0.startswith('r'):
                    ridx = int(arg0[1:]) - 1
                else:
                    ridx = int(arg0) - 1
                res_list = getattr(self.game, 'resources', [])
                if not (0 <= ridx < len(res_list)):
                    s = self.game.get_state()
                    res = s.get('resources', [])
                    lines = ["资源序号无效。用法: take|t <rN|序号>"]
                    if res:
                        lines.append('当前资源:')
                        pairs = [(f"r{i}", str(r)) for i, r in enumerate(res, 1)]
                        lines.extend(self._format_token_list(pairs))
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
                        self.info.append(detail)
                # 不单独打印成功行，避免干扰；展示完整视图
                out.append(self._render_full_view())
                return out, False
            except ValueError:
                out.append('资源序号需为数字或 rN')
            return out, False
        if c in ('use', 'u'):
            if not args:
                # 缺少物品名：列出背包与用法
                inv = self.game.player.inventory
                lines = ["缺少物品名。用法: use|u <物品名> [mN]", "当前背包:"]
                if inv.slots:
                    pairs = [(f"i{i}", str(slot)) for i, slot in enumerate(inv.slots, 1)]
                    lines.extend(self._format_token_list(pairs))
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
                    # 需要指定队伍目标
                    self._print(C.label('该物品为装备，需要指定队伍成员作为目标(mN)。可选目标:'))
                    board = self.game.player.board
                    if board:
                        pairs = [(f"m{i}", C.friendly(str(m))) for i, m in enumerate(board, 1)]
                        for line in self._format_token_list(pairs):
                            self._print(line)
                        token = input('选择队伍目标(如 m1，回车取消): ').strip()
                        if not token:
                            return ['已取消使用物品'], False
                        tgt = self._resolve_target_token(token)
                        if tgt is None:
                            return ['无效的队伍目标'], False
                    else:
                        return ['当前没有可装备目标(队伍为空)'], False
            # 尝试/记录
            attempt = f"{self.game.player.name} 使用物品 {name}{(' 对 ' + self._format_target(tgt)) if tgt is not None else ''}"
            ok, msg = self.game.player.use_item(name, 1, target=tgt)
            self._record(f"{attempt} -> {msg}")
            logs = getattr(self.game, 'pop_logs', None)
            info_lines = [f"{attempt} -> {msg}"]
            if callable(logs):
                for line in logs():
                    detail = f"  · {line}"
                    info_lines.append(detail)
            # 汇总到信息区
            self.info = info_lines
            # 不单独打印成功行；展示完整视图
            out.append(self._render_full_view())
            return out, False
        # 快捷合成：cN 例如 c1
        if c.startswith('c') and len(c) > 1 and c[1:].isdigit():
            idx = int(c[1:])
            lines = self._craft_by_index(idx)
            return lines, False
        if c == 'p':
            if not args:
                out.append('缺少手牌序号。用法: p <手牌序号> [target]')
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
                    self._print(C.label('该卡牌需要目标。可选目标:'))
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
                        info_lines.append(detail)
                # 把出牌反馈收纳到信息区
                self.info = info_lines
                # 出牌后展示完整视图
                out.append(self._render_full_view())
            except ValueError:
                out.append('请输入手牌序号')
            return out, False
        if c == 'a':
            if len(args) < 2:
                # 引导：列出我方队伍、敌人（带颜色）
                lines = [C.warning('缺少目标。用法: a <队伍序号|mN> e<敌人序号>'), C.label('我方队伍:')]
                board = self.game.player.board
                if board:
                    pairs = [(f"m{i}", str(m)) for i, m in enumerate(board, 1)]
                    lines.extend(self._format_token_list(pairs))
                else:
                    lines.append('  (无)')
                enemies = getattr(self.game, 'enemies', None) or getattr(self.game, 'enemy_zone', [])
                lines.append(C.label('敌人:'))
                if enemies:
                    pairs = [(f"e{i}", str(e)) for i, e in enumerate(enemies, 1)]
                    lines.extend(self._format_token_list(pairs))
                else:
                    lines.append('  (无)')
                # 无 Boss 区
                return lines, False
            try:
                # 支持数字或 mN 两种形式
                first = args[0].lower()
                if first.startswith('m'):
                    m_idx = int(first[1:]) - 1
                else:
                    m_idx = int(first) - 1
                tgt = args[1]
                # healer: 允许 a mA mB 作为对友方的治疗（攻击即治疗）
                if tgt.startswith('m'):
                    try:
                        m_tgt = int(tgt[1:]) - 1
                        board = self.game.player.board
                        if not (0 <= m_idx < len(board) and 0 <= m_tgt < len(board)):
                            return ['友方目标不存在'], False
                        healer = board[m_idx]
                        ally = board[m_tgt]
                        from systems import skills as SK
                        if not SK.is_healer(healer):
                            return ['该随从不是治疗者，无法对友方使用攻击治疗'], False
                        heal_amount = SK.get_heal_amount(healer, getattr(healer, 'attack', 0))
                        prev = ally.hp
                        ally.heal(heal_amount)
                        gain = ally.hp - prev
                        attempt = f"{self.game.player.name} 的队伍#{m_idx+1} 治疗 我方 m{m_tgt+1}"
                        self._record(f"{attempt} -> 恢复 {gain}")
                        self.info = [f"{attempt} -> 恢复 {gain}"]
                        # 展示完整视图
                        out.append(self._render_full_view())
                        return out, False
                    except ValueError:
                        return ['友方目标格式 mN (如 m1)'], False
                if tgt.startswith('e'):
                    try:
                        e_idx = int(tgt[1:]) - 1
                        attempt = f"{self.game.player.name} 的队伍#{m_idx+1} 攻击 敌人 e{e_idx+1}"
                        _, msg = self.game.attack_enemy(m_idx, e_idx)
                        self._record(f"{attempt} -> {msg}")
                        logs = getattr(self.game, 'pop_logs', None)
                        info_lines = [f"{attempt} -> {msg}"]
                        if callable(logs):
                            for line in logs():
                                detail = f"  · {line}"
                                info_lines.append(detail)
                        self.info = info_lines
                        # 不单独打印成功行；展示完整视图
                        out.append(self._render_full_view())
                        return out, False
                    except ValueError:
                        out.extend(['敌人格式 eN (如 e1)', '示例: a m1 e1 或 a 1 e1'])
                        return out, False
                elif tgt == 'boss':
                    out.append('当前模式无 Boss 区')
                    return out, False
                else:
                    out.extend(['目标格式: eN (如 e1)', '示例: a m1 e1 或 a 1 e1'])
                    return out, False
            except ValueError:
                # 同样提供引导
                guide = [C.error('队伍目标错误（应为数字或 mN）。'), C.label('你的队伍:')]
                board = self.game.player.board
                if board:
                    pairs = [(f"m{i}", str(m)) for i, m in enumerate(board, 1)]
                    guide.extend(self._format_token_list(pairs))
                else:
                    guide.append('  (无)')
                out.extend(guide)
                return out, False
        # 技能调用: skill <name> <source mN> [target]
        if c in ('skill', 'sk') or c in ('sweep','basic_heal','drain','taunt','arcane_missiles'):
            # 支持直接以技能名开头的快捷方式
            if c in ('skill', 'sk'):
                if not args:
                    return ['用法: skill <name> <source mN> [target]'], False
                skill_name = args[0]
                rest = args[1:]
            else:
                skill_name = c
                rest = args
            if not rest:
                return ['请指定来源随从: mN'], False
            src_tok = rest[0]
            if not src_tok.startswith('m'):
                return ['来源需为随从标记 mN'], False
            try:
                src_idx = int(src_tok[1:])
            except Exception:
                return ['来源随从格式错误 mN'], False
            tgt_tok = rest[1] if len(rest) >= 2 else None
            ok, msg = self.game.use_skill(skill_name, src_idx, tgt_tok)
            self._record(f"技能 {skill_name} -> {msg}")
            logs = getattr(self.game, 'pop_logs', None)
            info_lines = [f"技能 {skill_name} 执行: {msg}"]
            if callable(logs):
                for line in logs():
                    info_lines.append(f"  · {line}")
            self.info = info_lines
            out.append(self._render_full_view())
            return out, False
        if c == 'end':
            self.game.end_turn()
            msg = f"进入回合 {self.game.turn}"
            self._record(msg)
            logs = getattr(self.game, 'pop_logs', None)
            if callable(logs):
                for line in logs():
                    # 历史区不再记录详细日志，保持简洁
                    pass
            out.append(msg)
            return out, False
        out.append('未知指令，h 查看帮助')
        return out, False

    # --- 合成 ---
    def _recipes(self):
        # 最小可用配方表（名称 -> 消耗 -> 产出描述/效果）
        # 仅示例：生命药水(小/大)、解毒药剂
        return [
            {
                'name': '小治疗药水',
                'cost': {'药草': 1, '空瓶': 1},
                'result': ('生命药水', 1, '恢复3点生命', 'potion', 3),
            },
            {
                'name': '大治疗药水',
                'cost': {'药草': 2, '空瓶': 1},
                'result': ('生命药水', 1, '恢复6点生命', 'potion', 6),
            },
            {
                'name': '解毒药剂',
                'cost': {'药草': 1, '黏液': 1, '空瓶': 1},
                'result': ('解毒药剂', 1, '解除中毒', 'potion', 0),
            },
        ]

    def _cmd_craft(self, args: list[str]):
        inv = self.game.player.inventory
        # 无参数：优先显示当前可合成清单，并提供 cN 提示
        if not args:
            crafts = self._craftable_recipes()
            lines = [C.heading('当前可合成:')]
            for i, r in enumerate(crafts, 1):
                cost = ', '.join([f"{k}x{v}" for k, v in r['cost'].items()])
                lines.append(f"c{i}  {r['name']}  =  {cost}")
            if not crafts:
                lines.append('  (暂无)')
            lines.append('提示: 输入 c1/c2... 直接合成；查看所有: craft list')
            return lines
        # list: 显示全部配方
        if args[0] in ('list', 'ls'):
            lines = [C.heading('所有配方:')]
            for r in self._recipes():
                cost = ', '.join([f"{k}x{v}" for k, v in r['cost'].items()])
                lines.append(f"- {r['name']} = {cost}")
            lines.append('用法: craft <名称> 或 craft <索引>')
            return lines
        # 数字：作为当前可合成索引
        if args[0].isdigit():
            return self._craft_by_index(int(args[0]))
        # 名称：按名合成
        name = args[0]
        recipe = next((r for r in self._recipes() if r['name'] == name), None)
        if not recipe:
            return [f"未知配方: {name}", '输入 craft list 查看所有配方']
        # 校验材料
        for mat, n in recipe['cost'].items():
            if not inv.has_item(mat, n):
                return [f"材料不足: 需要 {mat} x{n}"]
        return self._apply_recipe(recipe)

    def _apply_recipe(self, recipe: dict) -> list[str]:
        inv = self.game.player.inventory
        # 消耗材料
        for mat, n in recipe['cost'].items():
            inv.remove_item(mat, n, game=getattr(self.game, 'log', None) and self.game)
        # 产出
        from systems.inventory import ConsumableItem
        res_name, qty, desc, typ, val = recipe['result']
        if typ == 'potion':
            def eff(player, target):
                # 简单：若有目标则治疗目标，否则治疗玩家英雄（简化）
                if target is not None and hasattr(target, 'heal'):
                    target.heal(max(1, val))
                elif hasattr(player, 'heal'):
                    player.heal(max(1, val))
            item = ConsumableItem(res_name, desc, max_stack=5, effect=eff)
            inv.add_item(item, qty, game=self.game)
            # 信息区与历史，并展示全视图
            msg = f"合成成功: {res_name} x{qty}"
            self.info = [msg]
            self._record(msg)
            return [self._render_full_view()]
        return ["配方产出类型未实现"]

    def _craftable_recipes(self) -> list[dict]:
        inv = self.game.player.inventory
        crafts = []
        for r in self._recipes():
            ok = True
            for mat, n in r['cost'].items():
                if not inv.has_item(mat, n):
                    ok = False
                    break
            if ok:
                crafts.append(r)
        return crafts

    def _craft_by_index(self, idx: int) -> list[str]:
        if idx <= 0:
            return ['索引应为正整数']
        crafts = self._craftable_recipes()
        if not crafts:
            return ['暂无可合成配方']
        if idx > len(crafts):
            return [f'索引超出范围(1-{len(crafts)})']
        return self._apply_recipe(crafts[idx - 1])

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
        # 敌人（带颜色）
        enemies = getattr(self.game, 'enemies', None) or getattr(self.game, 'enemy_zone', [])
        if enemies:
            lines.append(C.label('敌人:'))
            epairs = [(f"e{i}", str(e)) for i, e in enumerate(enemies, 1)]
            lines.extend(self._format_token_list(epairs))
    # 场景模式无 Boss
        # 我方队伍
        board = self.game.player.board
        if board:
            lines.append(C.label('我方队伍:'))
            mpairs = [(f"m{i}", str(m)) for i, m in enumerate(board, 1)]
            lines.extend(self._format_token_list(mpairs))
        if not lines:
            lines.append(C.dim('(当前没有可选目标)'))
        return lines

    # --- 辅助格式化 ---
    def _format_target(self, target) -> str:
        if target is None:
            return '(无)'
        try:
            return str(target)
        except Exception:
            return f"{type(target).__name__}"


def start_simple_pve_game(name: str | None = None, scene: str | None = None):
    controller = SimplePvEController(player_name=name, initial_scene=scene)
    controller.loop()

# 兼容旧入口：主程序调用的多人PvE入口名
def start_pve_multiplayer_game(name: str | None = None, scene: str | None = None):
    start_simple_pve_game(name=name, scene=scene)
