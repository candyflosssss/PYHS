class Battlefield:
    _instance = None  # 单例实例

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Battlefield, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):  # 防止重复初始化
            self.my_board = []
            self.op_board = []
            self.initialized = True

    def add_card(self, board, card):
        """添加随从到战场"""
        if len(board) >= 5:  # 假设战场最多容纳 5 个随从
            print("战场已满，无法添加随从")
            return False
        board.append(card)
        return True

    def remove_card(self, board, card):
        """从战场移除随从"""
        if card in board:
            board.remove(card)

    def check_deaths(self, board, owner, game):
        """检查随从是否死亡"""
        for card in board[:]:  # 遍历副本以安全移除
            if card.hp <= 0:
                print(f"{card} 死亡")
                card.on_death(game, owner)
                self.remove_card(board, card)

    def sync_state(self, network):
        """同步战场状态"""
        def board_to_str(board):
            return ';'.join(c.sync_state() for c in board)
        msg = f"s {board_to_str(self.my_board)}|{board_to_str(self.op_board)}"
        network.send(msg)

    def apply_state(self, msg):
        """解析同步的战场状态"""
        parts = msg.split()
        boards = parts[1].split('|')

        def str_to_board(s):
            res = []
            if not s:
                return res
            for item in s.split(';'):
                if not item:
                    continue
                cls_name, atk, hp, max_hp, attacks, can_attack = item.split(',')
                from cards import card_types  # 避免循环导入
                cls = next((c for c in card_types if c.__name__ == cls_name), None)
                if cls:
                    card = cls(int(atk), int(max_hp))
                    card.hp = int(hp)
                    card.attacks = int(attacks)
                    card.can_attack = bool(int(can_attack))
                    res.append(card)
            return res

        self.op_board = str_to_board(boards[0])
        self.my_board = str_to_board(boards[1])