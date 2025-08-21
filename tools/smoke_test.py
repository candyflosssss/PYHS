# Smoke test: load scenes and execute a few skills to catch runtime errors fast.
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from game_modes.simple_pve_game import SimplePvEGame


def run_scene(scene_path: str):
    g = SimplePvEGame('smoke')
    ok = g.load_scene(scene_path, keep_board=False)
    print(f"load {scene_path}: {ok}")
    if not ok:
        return
    # Try some actions if possible
    try:
        # Ensure there is at least one member and one enemy
        if g.player.board and g.enemies:
            # Attack first enemy with first member
            out = g.attack_enemy(1, 1)
            print('attack result:', out)
        # Try known skills if available on first member
        if g.player.board:
            m = g.player.board[0]
            skills = getattr(m, 'skills', []) or []
            # Normalize skill ids
            ids = []
            for s in skills:
                if isinstance(s, str):
                    ids.append(s)
                elif isinstance(s, dict):
                    ids.append(s.get('id') or s.get('name'))
            # Pick a couple to try
            for sid in ids[:3]:
                if not sid:
                    continue
                if sid in ('sweep','taunt','fair_distribution'):
                    r = g.use_skill(sid, 1)
                else:
                    # target first enemy if exists, else self
                    tgt = 'e1' if g.enemies else 'm1'
                    r = g.use_skill(sid, 1, tgt)
                print('skill', sid, '->', r)
    except Exception as e:
        print('smoke action error:', e)


def main():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    scenes = [
        os.path.join(base, 'scenes', 'default_scene.json'),
        os.path.join(base, 'scenes', 'test', 'test_skills_showcase.json'),
        os.path.join(base, 'scenes', 'test', 'generated_test_scene.json'),
        os.path.join(base, 'scenes', 'adventure_pack', 'world_map.json'),
    ]
    for p in scenes:
        if os.path.exists(p):
            run_scene(p)
        else:
            print('skip missing', p)


if __name__ == '__main__':
    main()
