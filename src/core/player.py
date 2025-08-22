from .cards import draw_card, BattlecryCard, CombinedCard, WindfuryCard
from src.systems.inventory import Inventory

class Player:
    def __init__(self, name, is_me=True, game=None, inventory_size=20):
        self.name = name
        self.is_me = is_me
        self.hand = []
        self.hp = 30  # 每个玩家自己的生命值
        self.max_hp = 30
        self.board = []  # PvE模式的简化战场列表
        self.game = game  # 添加对Game的引用
        self.inventory = Inventory(inventory_size)  # 添加背包系统

    def draw_card(self):
        """抽牌逻辑"""
        from .cards import draw_card
        card = draw_card()
        self.hand.append(card)
        return card

    def play_card(self, card_idx, target=None):
        """出牌逻辑（支持目标选择与统一 on_play 回调）"""
        if card_idx < 0 or card_idx >= len(self.hand):
            return False

        card = self.hand[card_idx]

        # 简化的出牌逻辑，直接添加到战场
        if len(self.board) < 7:  # 最多7张牌
            self.board.append(card)
            self.hand.pop(card_idx)

            # 统一触发 on_play
            try:
                card.on_play(getattr(self, 'game', None), self, target)
            except Exception:
                # 兜底：老逻辑仍可通过 battlecry 触发
                if isinstance(card, BattlecryCard) or isinstance(card, CombinedCard):
                    card.battlecry(self, target)

            return True
        return False

    def attack(self, attacker_idx, target):
        """攻击逻辑 - PvE简化版本"""
        if attacker_idx < 0 or attacker_idx >= len(self.board):
            return False
        
        attacker = self.board[attacker_idx]
        
        # 对目标造成伤害
        if hasattr(target, 'hp'):
            target.hp -= attacker.attack
            
            # 如果目标反击
            if hasattr(target, 'attack') and hasattr(attacker, 'hp'):
                attacker.hp -= target.attack
        
        # 检查死亡
        self.check_deaths()
        return True

    def check_deaths(self):
        """检查并移除死亡的卡牌"""
        self.board = [card for card in self.board if card.hp > 0]

    def take_damage(self, damage):
        """受到伤害"""
        self.hp -= damage
        if self.hp < 0:
            self.hp = 0

    def heal(self, amount):
        """治疗"""
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    def use_item(self, item_name, amount=1, target=None):
        """使用物品（可指定目标，如 m1 随从）"""
        return self.inventory.use_item(item_name, amount, self, target)

    def add_item(self, item, amount=1):
        """添加物品到背包"""
        return self.inventory.add_item(item, amount, game=getattr(self, 'game', None))

    def get_total_attack(self):
        """获取总攻击力（包括装备加成）"""
        base_attack = sum(card.attack for card in self.board)
        equipment_bonus = 0
        
        # 如果有装备系统
        if hasattr(self, 'equipment_system'):
            equipment_bonus = self.equipment_system.get_total_attack()
        
        return base_attack + equipment_bonus

    def get_total_defense(self):
        """获取总防御力（包括装备加成）"""
        base_defense = 0  # 玩家基础防御为0
        equipment_bonus = 0
        
        # 如果有装备系统
        if hasattr(self, 'equipment_system'):
            equipment_bonus = self.equipment_system.get_total_defense()
        
        return base_defense + equipment_bonus

    def show_hand(self):
        """显示手牌"""
        if not self.hand:
            print("手牌为空")
            return
        
        print(f"{self.name} 的手牌:")
        for i, card in enumerate(self.hand):
            print(f"{i+1}. {card}")

    def show_board(self):
        """显示战场"""
        if not self.board:
            print(f"{self.name} 的战场为空")
            return
        
        print(f"{self.name} 的战场:")
        for i, card in enumerate(self.board):
            print(f"{i+1}. {card}")

    def show_status(self):
        """显示玩家状态"""
        print(f"\n=== {self.name} 状态 ===")
        print(f"生命值: {self.hp}/{self.max_hp}")
        print(f"手牌数量: {len(self.hand)}")
        print(f"战场随从: {len(self.board)}")
        
        if hasattr(self, 'equipment_system'):
            print(f"装备: {self.equipment_system}")

    def __str__(self):
        return f"{self.name}(HP:{self.hp}/{self.max_hp}, 手牌:{len(self.hand)}, 战场:{len(self.board)})"
