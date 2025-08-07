from battlefield import Battlefield
from cards import draw_card, BattlecryCard, CombinedCard, WindfuryCard
from inventory import Inventory

class Player:
    def __init__(self, name, is_me=True, game=None, inventory_size=20):
        self.name = name
        self.is_me = is_me
        self.hand = []
        self.hp = 30  # 每个玩家自己的生命值
        self.max_hp = 30
        self.battlefield = Battlefield()
        self.game = game  # 添加对Game的引用
        self.inventory = Inventory(inventory_size)  # 添加背包系统

    def draw_card(self):
        """抽牌逻辑"""
        from cards import draw_card
        card = draw_card()
        self.hand.append(card)
        print(f"{self.name} 抽到 {card}")
        return card

    def play_card(self, hand_idx, target_idx=None):
        """出牌逻辑（交互式，仅用于本地玩家）"""
        try:
            if hand_idx < 0 or hand_idx >= len(self.hand):
                raise IndexError("手牌索引无效")
            card = self.hand.pop(hand_idx)
            
            # 对于战吼卡牌，如果没有提供目标且是本地玩家，则要求玩家选择目标
            if (isinstance(card, BattlecryCard) or isinstance(card, CombinedCard)) and target_idx is None and self.is_me:
                print("需要选择战吼目标:")
                print("0 - 敌方英雄")
                
                # 显示敌方随从作为可选目标
                op_board = self.battlefield.op_board
                for i, minion in enumerate(op_board, 1):
                    print(f"{i} - {minion}")
                    
                # 获取玩家输入
                target_input = input("选择目标> ")
                try:
                    target_idx = int(target_input)
                except ValueError:
                    print("无效的目标，取消出牌")
                    self.hand.insert(hand_idx, card)
                    return
            
            # 实际出牌逻辑
            self._do_play_card(card, target_idx, hand_idx)
            
        except IndexError as e:
            print(f"错误: {e}")
            return
        except ValueError as e:
            print(f"输入错误: {e}")
            return

    def play_card_network(self, hand_idx, target_idx=None):
        """网络出牌逻辑（无交互，用于对方玩家）"""
        try:
            if hand_idx < 0 or hand_idx >= len(self.hand):
                print(f"对方出牌索引无效: {hand_idx}")
                return
            card = self.hand.pop(hand_idx)
            self._do_play_card(card, target_idx, hand_idx)
        except Exception as e:
            print(f"对方出牌错误: {e}")
            return

    def _do_play_card(self, card, target_idx=None, original_hand_idx=None):
        """实际出牌执行逻辑"""
        # 其余逻辑保持不变
        board = self.battlefield.my_board if self.is_me else self.battlefield.op_board
        if not self.battlefield.add_card(board, card):
            print("战场已满，无法出牌")
            return
        
        card.can_attack = False
        card.attacks = 0
        print(f"{self.name} 出场: {card}")

        # 处理目标
        target = None
        if isinstance(card, (BattlecryCard, CombinedCard)) and target_idx is not None:
            if target_idx == 0:
                target = 'enemy_hero'
                print(f"目标: 敌方英雄")
            elif 1 <= target_idx <= len(self.battlefield.op_board):
                target = self.battlefield.op_board[target_idx - 1]
                print(f"目标: {target}")
            else:
                print("无效的目标索引")
                
        # 所有卡牌都应调用on_play
        card.on_play(self.game, 'me' if self.is_me else 'op', target)

        # 检查死亡随从
        self.battlefield.check_deaths(self.battlefield.my_board, 'me', self.game)
        self.battlefield.check_deaths(self.battlefield.op_board, 'op', self.game)
        
        # 出牌后同步战场状态（仅本地玩家发送）
        if self.is_me and self.game and hasattr(self.game, 'network'):
            # 发送出牌指令给对方（使用原始索引）
            if original_hand_idx is not None:
                cmd = f"p {original_hand_idx + 1}"
                if target_idx is not None:
                    cmd += f" {target_idx}"
                print(f"DEBUG: 发送出牌命令: '{cmd}'")
                self.game.network.send(cmd)
            
            # 同步战场状态
            print("DEBUG: 发送同步命令")
            self.battlefield.sync_state(self.game.network)

    def attack(self, seq):
        """攻击逻辑"""
        for s in seq.split('/'):
            try:
                ai, di = map(int, s.split(','))
            except:
                print("!"); continue
            ai -= 1
            if ai < 0 or ai >= len(self.battlefield.my_board):
                print("!"); continue
            c = self.battlefield.my_board[ai]
            if not c.can_attack:
                print("!"); continue
            max_att = 2 if getattr(c, 'windfury', False) else 1
            if c.attacks >= max_att:
                print("!"); continue

            if di == 0:
                # 攻击对方英雄
                if hasattr(self, 'game') and self.game:
                    # 使用游戏的伤害方法，会自动同步血量
                    attacker_owner = 'me' if self.is_me else 'op'
                    self.game.damage_enemy_hero(attacker_owner, c.atk)
                    print(f"M{ai+1}H{c.atk}")
                    c.attacks += 1
                    if c.attacks == max_att:
                        c.can_attack = False
                    # 游戏结束检查已经在damage_enemy_hero中处理
                    if (self.is_me and self.game.player_op.hp <= 0) or (not self.is_me and self.game.player_me.hp <= 0):
                        return True
                else:
                    # 兼容旧代码
                    if hasattr(self, 'enemy_player'):
                        self.enemy_player.hp -= c.atk
                        print(f"M{ai+1}H{c.atk}")
                        c.attacks += 1
                        if c.attacks == max_att:
                            c.can_attack = False
                        if self.enemy_player.hp <= 0:
                            print(f"{self.name} 赢了！")
                            return True
                    else:
                        print("未设置敌方玩家对象")
            else:
                di -= 1
                if di < 0 or di >= len(self.battlefield.op_board):
                    print("!"); continue
                tgt = self.battlefield.op_board[di]
                tgt.hp -= c.atk
                c.hp -= tgt.atk
                print(f"M{ai+1}M{di+1}")
                c.attacks += 1
                if c.attacks == max_att:
                    c.can_attack = False
                self.battlefield.check_deaths(self.battlefield.my_board, 'me', None)
                self.battlefield.check_deaths(self.battlefield.op_board, 'op', None)
        return False

    def __str__(self):
        hand_str = ", ".join(str(card) for card in self.hand)
        inventory_count = len(self.inventory.slots)
        return f"{self.name}[HP:{self.hp}/{self.max_hp}] 手牌:{hand_str} 背包:({inventory_count}/{self.inventory.max_slots})"
    
    # 背包相关方法
    def add_to_inventory(self, item, quantity=1):
        """向背包添加物品"""
        return self.inventory.add_item(item, quantity)
    
    def remove_from_inventory(self, item_name, quantity=1):
        """从背包移除物品"""
        return self.inventory.remove_item(item_name, quantity)
    
    def use_item(self, item_name, quantity=1):
        """使用背包中的物品"""
        if not self.inventory.has_item(item_name, quantity):
            print(f"背包中没有足够的{item_name}")
            return False
        
        # 查找物品并使用
        for slot in self.inventory.slots:
            if slot.item.name == item_name:
                # 如果是消耗品，执行效果
                if hasattr(slot.item, 'effect') and slot.item.effect:
                    try:
                        slot.item.effect(self)  # 对玩家施加效果
                        self.inventory.remove_item(item_name, quantity)
                        print(f"{self.name} 使用了 {item_name}")
                        return True
                    except Exception as e:
                        print(f"使用物品时出错: {e}")
                        return False
                else:
                    print(f"{item_name} 无法使用")
                    return False
        return False
    
    def show_inventory(self):
        """显示背包内容"""
        print(f"\n=== {self.name} 的背包 ===")
        self.inventory.display()
    
    def get_inventory_summary(self):
        """获取背包摘要"""
        return self.inventory.get_all_items()