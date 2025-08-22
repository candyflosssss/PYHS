import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.game_modes.simple_pve_game import SimplePvEGame

def dump(g):
    print('scene_base_dir:', g._scene_base_dir)
    print('candidates:')
    for p in g._debug_scene_candidates():
        print('  ', p, 'exists=', os.path.isdir(p))
    # check existence of some paths
    candidates = [
        os.path.join(g._scene_base_dir, 'default_scene.json'),
        os.path.join(g._scene_base_dir, 'adventure_pack', 'world_map.json'),
    ]
    for p in candidates:
        print('exists?', p, os.path.exists(p))
    print('current_scene (before):', g.current_scene)
    print('title (before):', g.current_scene_title)
    # try transition
    ok = g.load_scene('adventure_pack/world_map.json')
    print('load ok:', ok)
    print('current_scene:', g.current_scene)
    print('current_title:', g.current_scene_title)
    print('enemies:', [getattr(e,'name',str(e)) for e in g.enemies])
    print('resources:', [str(r) for r in g.resources])

if __name__ == '__main__':
    g = SimplePvEGame('tester')
    dump(g)
