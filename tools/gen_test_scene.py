"""
生成综合测试场景：
- 8 个队员：随机职业/六维/装备/标签，随机分配当前 skills_catalog.json 中的技能（每人2-3个）。
- 4-6 个敌人：混合双持/持盾/法师/高血等配置。
输出到 scenes/test/generated_test_scene.json。
"""
from __future__ import annotations
import os, json, random

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SCENE_DIR = os.path.join(BASE, 'scenes', 'test')
CATALOG = os.path.join(BASE, 'systems', 'skills_catalog.json')

def load_catalog_ids():
    try:
        with open(CATALOG, 'r', encoding='utf-8') as f:
            data = json.load(f)
        ids = [rec['id'] for rec in data.get('skills', []) if isinstance(rec, dict) and rec.get('id')]
        return ids
    except Exception:
        return ['sweep','basic_heal','drain','taunt','arcane_missiles']

def rnd_attrs():
    # 3-4 级强度的六维
    return {
        'str': random.choice([10,12,14,16]),
        'dex': random.choice([10,12,14,16]),
        'con': random.choice([12,14,16]),
        'int': random.choice([8,10,12,14,16]),
        'wis': random.choice([8,10,12,14,16]),
        'cha': random.choice([8,10,12,14,16]),
    }

def rnd_member(i: int, skill_ids: list[str]):
    names = ['战士','牧师','法师','游侠','坦克','格斗家','学者','盗贼']
    name = names[i % len(names)] + chr(ord('A') + i)
    atk = random.randint(3, 7)
    hp = random.randint(14, 24)
    prof = random.choice(['warrior','priest','mage','tank',''])
    tags = [prof] if prof else []
    # 2-3 个随机技能
    sk = random.sample(skill_ids, k=min(3, max(2, len(skill_ids)//8))) if len(skill_ids)>=3 else skill_ids
    d = {
        'name': name,
        'atk': atk,
        'hp': hp,
        'profession': prof or None,
        'tags': tags,
        'skills': sk,
        'dnd': {'level': 3, 'attrs': rnd_attrs()},
    }
    # 随机装备：双手/盾+剑/双持/轻甲
    roll = random.random()
    eq = {'items': []}
    if roll < 0.25:
        eq['items'].append({'type':'weapon','name':'巨剑','attack':5,'slot':'left_hand','two_handed':True})
    elif roll < 0.5:
        eq['items'].append({'type':'weapon','name':'钢剑','attack':4,'slot':'right_hand'})
        eq['items'].append({'type':'shield','name':'圆盾','defense':2})
    elif roll < 0.75:
        eq['items'].append({'type':'weapon','name':'短剑','attack':2,'slot':'left_hand'})
        eq['items'].append({'type':'weapon','name':'短剑','attack':2,'slot':'right_hand'})
    else:
        eq['items'].append({'type':'armor','name':'皮甲','defense':2})
    d['equip'] = eq
    return d

def rnd_enemy(i: int):
    kinds = [
        {'name':'盗贼(双持)','cfg':'dual'},
        {'name':'盾卫','cfg':'shield'},
        {'name':'术士','cfg':'mage'},
        {'name':'狂战士','cfg':'barb'},
        {'name':'步兵','cfg':'plain'},
    ]
    k = kinds[i % len(kinds)]
    hp = random.randint(18, 28)
    atk = random.randint(4, 7)
    base = {
        'name': k['name'], 'hp': hp, 'attack': atk, 'tags': [],
        'dnd': {'level': 3, 'attrs': rnd_attrs()},
    }
    if k['cfg'] == 'dual':
        base['tags'].append('rogue')
        base['equip'] = {'items':[{'type':'weapon','name':'匕首','attack':2,'slot':'left_hand'},{'type':'weapon','name':'匕首','attack':2,'slot':'right_hand'}]}
    elif k['cfg'] == 'shield':
        base['tags'].append('guard')
        base['equip'] = {'items':[{'type':'shield','name':'塔盾','defense':4},{'type':'weapon','name':'短剑','attack':2,'slot':'right_hand'}]}
    elif k['cfg'] == 'mage':
        base['tags'].append('mage')
        # 强化智力
        base['dnd']['attrs']['int'] = max(14, base['dnd']['attrs']['int'])
    elif k['cfg'] == 'barb':
        base['tags'].append('warrior')
        base['equip'] = {'items':[{'type':'weapon','name':'巨斧','attack':6,'slot':'left_hand','two_handed':True}]}
    return base

def main():
    os.makedirs(SCENE_DIR, exist_ok=True)
    sids = load_catalog_ids()
    board = [rnd_member(i, sids) for i in range(8)]
    enemies = [rnd_enemy(i) for i in range(random.randint(4,6))]
    res = [
        {'name':'生命药水','type':'potion','value':3},
        {'name':'皮甲','type':'armor','value':2},
        {'name':'铁剑','type':'weapon','value':3}
    ]
    data = {'title':'Generated 综合测试场景','board':board,'enemies':enemies,'resources':res}
    out_path = os.path.join(SCENE_DIR, 'generated_test_scene.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print('写入:', out_path)

if __name__ == '__main__':
    main()
