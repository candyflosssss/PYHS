import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.game_modes.simple_pve_game import SimplePvEGame

g=SimplePvEGame('tester')
ok=g.load_scene('adventure_pack/world_map.json', keep_board=False)
print('load ok', ok)
for i,m in enumerate(g.player.board,1):
    print(i, getattr(m,'name',None), 'skills=', getattr(m,'skills',None), 'dnd=', getattr(m,'dnd',None))
