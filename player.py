from battlefield import Battlefield
from cards import draw_card, BattlecryCard, CombinedCard

class Player:
    def __init__(self, name, is_me=True, game=None):
        self.name = name
        self.is_me = is_me
        self.hand = []
        self.hp = 30  # 每个玩家自己的生命值
        self.max_hp = 30
        self.battlefield = Battlefield()
        self.game = game  # 添加对Game的引用

    def draw_card(self):
        """抽牌逻辑"""
        from cards import draw_card
        card = draw_card()
        self.hand.append(card)
        print(f"{self.name} 抽到 {card}")
        return card

    def play_card(self, hand_idx, target_idx=None):
        """出牌逻辑"""
        try:
            if hand_idx < 0 or hand_idx >= len(self.hand):
                raise IndexError("手牌索引无效")
            card = self.hand.pop(hand_idx)
            
            # 对于战吼卡牌，如果没有提供目标，则要求玩家选择目标
            if (isinstance(card, BattlecryCard) or isinstance(card, CombinedCard)) and target_idx is None:
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
            
            # 其余逻辑保持不变
            board = self.battlefield.my_board if self.is_me else self.battlefield.op_board
            if not self.battlefield.add_card(board, card):
                self.hand.insert(hand_idx, card)  # 如果失败，放回手牌
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
            
            # 出牌后同步战场状态
            if self.game and hasattr(self.game, 'network'):
                # 发送出牌指令给对方
                cmd = f"p {hand_idx+1}"
                if target_idx is not None:
                    cmd += f" {target_idx}"
                self.game.network.send(cmd)
                
                # 同步战场状态
                self.battlefield.sync_state(self.game.network)
        except IndexError as e:
            print(f"错误: {e}")
            return
        except ValueError as e:
            print(f"输入错误: {e}")
            return

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
            max_att = 2 if isinstance(c, WindfuryCard) or isinstance(c, CombinedCard) else 1
            if c.attacks >= max_att:
                print("!"); continue

            if di == 0:
                # 攻击对方英雄
                # 这里假设有 self.enemy_player 指向对方Player对象
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
        return f"{self.name}[HP:{self.hp}/{self.max_hp}] 手牌:{hand_str}"