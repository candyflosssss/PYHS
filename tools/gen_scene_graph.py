import os
import json
from collections import defaultdict, deque

SCENES_ROOT = os.path.join(os.path.dirname(__file__), '..', 'scenes')
OUT_HTML = os.path.join(SCENES_ROOT, 'scene_graph.html')

# Simple inlined D3-like force layout is heavy; use lightweight SVG with groups
# We'll arrange nodes by pack columns and simple vertical spacing.

COLORS = {
    'main': '#4FC3F7',
    'boss': '#EF5350',
    'puzzle': '#FFCA28',
    'side': '#A5D6A7',
    'hub': '#9575CD',
    'normal': '#B0BEC5',
}

def classify_scene(name, data):
    title = (data.get('title') or data.get('name') or name).lower()
    t = str(data.get('type','')).lower()
    if 'boss' in title or 'boss' in t:
        return 'boss'
    if 'puzzle' in title or '谜' in title:
        return 'puzzle'
    if 'world' in title or t == 'main' or data.get('main') or data.get('is_main'):
        return 'main'
    # hubs: have many outgoing nodes
    enemies = data.get('enemies', [])
    outs = 0
    for e in enemies:
        if isinstance(e, dict) and isinstance(e.get('on_death'), dict) and e['on_death'].get('action') == 'transition':
            outs += 1
    if outs >= 3:
        return 'hub'
    # side: has parent and few enemies
    if data.get('parent'):
        return 'side'
    return 'normal'


def load_scenes():
    packs = defaultdict(list)  # pack_id -> list of (rel_path, data)
    for root, dirs, files in os.walk(SCENES_ROOT):
        for fn in files:
            if not fn.endswith('.json'):
                continue
            if fn == 'pack.json':
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, SCENES_ROOT).replace('\\', '/')
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # pack id
                d = os.path.dirname(rel)
                pack = d if d != '' else 'base'
                packs[pack].append((rel, data))
            except Exception:
                # skip malformed
                continue
    return packs


def build_graph(packs):
    nodes = {}  # id -> node
    edges = []  # (src, dst, kind)
    for pack, items in packs.items():
        for rel, data in items:
            sid = rel
            title = data.get('title') or data.get('name') or os.path.basename(rel)
            kind = classify_scene(rel, data)
            parent = data.get('parent') or data.get('back_to')
            nodes[sid] = {
                'id': sid,
                'title': title,
                'pack': pack,
                'kind': kind,
            }
            # parent edge (back)
            if parent:
                # resolve relative parent within same dir
                if '/' not in parent and '/' in rel:
                    parent_id = rel.rsplit('/', 1)[0] + '/' + parent
                else:
                    parent_id = parent
                edges.append((sid, parent_id, 'back'))
            # transitions
            for e in data.get('enemies', []):
                if isinstance(e, dict):
                    od = e.get('on_death')
                    if isinstance(od, dict) and od.get('action') == 'transition':
                        to = od.get('to')
                        if to:
                            if '/' not in to and '/' in rel:
                                to_id = rel.rsplit('/', 1)[0] + '/' + to
                            else:
                                to_id = to
                            edges.append((sid, to_id, 'go'))
            # on_clear
            oc = data.get('on_clear')
            if isinstance(oc, dict) and oc.get('action') == 'transition' and oc.get('to'):
                to = oc['to']
                if '/' not in to and '/' in rel:
                    to_id = rel.rsplit('/', 1)[0] + '/' + to
                else:
                    to_id = to
                edges.append((sid, to_id, 'clear'))
    return nodes, edges


def _compute_levels_per_pack(nodes, edges):
    """Return dict: pack -> {node_id -> level}, using go/clear edges for forward depth.
    Fallback to back edges if needed.
    """
    # Build adjacency and indegree per pack for go/clear edges
    fwd_adj = defaultdict(lambda: defaultdict(list))  # pack -> src -> [dst]
    fwd_indeg = defaultdict(lambda: defaultdict(int))  # pack -> node -> indeg
    back_adj = defaultdict(lambda: defaultdict(list))  # pack -> src -> [parent]

    for src, dst, kind in edges:
        if src not in nodes or dst not in nodes:
            continue
        psrc = nodes[src]['pack']
        pdst = nodes[dst]['pack']
        if kind in ('go', 'clear') and psrc == pdst:
            fwd_adj[psrc][src].append(dst)
            fwd_indeg[psrc][dst] += 1
            # ensure keys exist
            _ = fwd_indeg[psrc][src]
        if kind == 'back' and psrc == pdst:
            back_adj[psrc][src].append(dst)

    levels = {}
    # Process per pack
    packs = sorted({n['pack'] for n in nodes.values()})
    for pk in packs:
        # collect node ids in this pack
        ids = [nid for nid, n in nodes.items() if n['pack'] == pk]
        if not ids:
            continue
        kind_map = {nid: nodes[nid]['kind'] for nid in ids}
        indeg = fwd_indeg[pk]
        # roots preference: main/hub with indeg 0; else any indeg 0; else arbitrary a main/hub; else any
        roots = [nid for nid in ids if indeg.get(nid, 0) == 0 and kind_map[nid] in ('main', 'hub')]
        if not roots:
            roots = [nid for nid in ids if indeg.get(nid, 0) == 0]
        if not roots:
            roots = [nid for nid in ids if kind_map[nid] in ('main', 'hub')]
        if not roots:
            roots = [ids[0]]

        lv = {nid: None for nid in ids}
        q = deque()
        for r in roots:
            lv[r] = 0
            q.append(r)
        # BFS on go/clear
        while q:
            u = q.popleft()
            for v in fwd_adj[pk].get(u, []):
                nl = (lv[u] or 0) + 1
                if lv.get(v) is None or nl < lv[v]:
                    lv[v] = nl
                    q.append(v)
        # Fill remaining by back (child right of parent)
        changed = True
        while changed:
            changed = False
            for u in ids:
                if lv[u] is None:
                    # try any parent via back edge
                    parents = back_adj[pk].get(u, [])
                    if parents:
                        pl = min((lv.get(p) for p in parents if lv.get(p) is not None), default=None)
                        if pl is not None:
                            lv[u] = pl + 1
                            changed = True
        # Any still None -> put to level 1
        for u in ids:
            if lv[u] is None:
                lv[u] = 1
        levels[pk] = lv
    return levels


def layout(nodes, edges):
    # Group by pack with layered left-to-right layout within each pack
    pack_levels = _compute_levels_per_pack(nodes, edges)
    packs = sorted(pack_levels.keys())

    # Layout constants
    node_w = 280
    node_h = 84
    x_gap = 120
    y_gap = 20
    col_gap = node_w + x_gap
    pack_gap = 160  # gap between packs (extra on top of columns)
    margin_x = 80
    margin_y = 120

    positions = {}
    pack_bounds = {}  # pk -> (x0,y0,x1,y1)

    cur_x = margin_x
    for pk in packs:
        lv_map = pack_levels[pk]
        # invert: level -> list of nodes
        levels_sorted = sorted(set(lv_map.values()))
        lvl_nodes = {lv: [nid for nid, l in lv_map.items() if l == lv] for lv in levels_sorted}
        # sort nodes in each level by kind for stability
        for lv in lvl_nodes:
            lvl_nodes[lv].sort(key=lambda nid: {'main':0,'hub':1,'puzzle':2,'side':3,'normal':4,'boss':5}.get(nodes[nid]['kind'],9))

        # compute y per level
        # tallest column determines height
        col_heights = {lv: len(lvl_nodes[lv]) for lv in levels_sorted}
        max_rows = max(col_heights.values()) if col_heights else 1
        pack_height = max_rows * (node_h + y_gap) - y_gap
        base_y = margin_y

        # x for each level
        level_x = {lv: cur_x + (i * col_gap) for i, lv in enumerate(levels_sorted)}

        # place nodes
        for lv in levels_sorted:
            nodes_in_level = lvl_nodes[lv]
            # center this column vertically within pack_height
            used_h = len(nodes_in_level) * (node_h + y_gap) - y_gap if nodes_in_level else 0
            start_y = base_y + max(0, (pack_height - used_h) // 2)
            for idx, nid in enumerate(nodes_in_level):
                x = level_x[lv]
                y = start_y + idx * (node_h + y_gap)
                positions[nid] = (x, y)

        # bounds for this pack
        min_x = cur_x
        max_x = cur_x + (max(1, len(levels_sorted)) - 1) * col_gap + node_w
        min_y = base_y
        max_y = base_y + pack_height
        pack_bounds[pk] = (min_x, min_y, max_x, max_y)

        # advance x for next pack
        cur_x = max_x + pack_gap

    return positions, pack_bounds


def render_html(nodes, edges, pos, pack_bounds):
    # size
    if pos:
        max_x = max(x for x, _ in pos.values()) + 600
        max_y = max(y for _, y in pos.values()) + 400
    else:
        max_x, max_y = 1200, 800

    # legend
    legend_items = ''.join(
        '<div style="display:flex;align-items:center;margin-right:16px">'
        f'<span style="display:inline-block;width:14px;height:14px;background:{COLORS[k]};margin-right:6px;border-radius:3px"></span>'
        f'{k}</div>' for k in ['main', 'hub', 'puzzle', 'side', 'boss', 'normal']
    )

    # pack headers/backgrounds
    pack_divs = []
    for pk, (x0, y0, x1, y1) in pack_bounds.items():
        name = pk.split('/')[-1]
        width = x1 - x0
        height = y1 - y0
        pack_divs.append(
            f'<div class="pack" style="left:{x0 - 30}px; top:{y0 - 60}px; width:{width + 60}px; height:{height + 100}px">'
            f'<div class="pack-title">{name}</div>'
            '</div>'
        )

    # nodes HTML
    node_divs = []
    for nid, n in nodes.items():
        if nid not in pos:
            continue
        x, y = pos[nid]
        color = COLORS.get(n['kind'], COLORS['normal'])
        node_divs.append(
            f'<div class="node" id="n_{nid}" style="left:{x}px;top:{y}px">'
            f'<div class="bar" style="background:{color}"></div>'
            f'<div class="title">{n["title"]}</div>'
            f'<div class="meta">{n["pack"]} · {n["kind"]}</div>'
            f'<div class="id">{nid}</div>'
            '</div>'
        )
    nodes_html = '\n'.join(node_divs)

    # edges SVG as curved paths with single defs
    marker_defs = (
        '<defs>'
        '<marker id="m_go" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L0,6 L9,3 z" fill="#64B5F6"/></marker>'
        '<marker id="m_clear" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L0,6 L9,3 z" fill="#81C784"/></marker>'
        '<marker id="m_back" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L0,6 L9,3 z" fill="#B0BEC5"/></marker>'
        '</defs>'
    )

    def path_curve(x1, y1, x2, y2):
        # control point: midway with horizontal offset
        mx = (x1 + x2) / 2
        dx = max(60, abs(x2 - x1) * 0.2)
        cx = mx + (dx if x2 >= x1 else -dx)
        cy = (y1 + y2) / 2
        return f'M {x1} {y1} Q {cx} {cy} {x2} {y2}'

    svg_edges = []
    for src, dst, kind in edges:
        if src not in pos or dst not in pos:
            continue
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        # attach from right center of src to left center of dst
        x1 += 280  # node width
        y1 += 42   # half height
        x2 += 0
        y2 += 42
        color_map = {"go": "#64B5F6", "clear": "#81C784", "back": "#B0BEC5"}
        stroke = color_map.get(kind, "#90A4AE")
        marker = {"go": "url(#m_go)", "clear": "url(#m_clear)", "back": "url(#m_back)"}.get(kind, "url(#m_go)")
        dash = ' stroke-dasharray="6,6"' if kind == 'back' else ''
        svg_edges.append(
            f'<path d="{path_curve(x1, y1, x2, y2)}" fill="none" stroke="{stroke}" stroke-width="2" marker-end="{marker}"{dash} />'
        )

    svg_html = f'<svg width="{max_x}" height="{max_y}" class="edges">{marker_defs}' + '\n'.join(svg_edges) + '</svg>'

    # HTML with pan/zoom
    html = (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        '<head>\n'
        '  <meta charset="UTF-8" />\n'
        '  <title>场景图</title>\n'
        '  <style>\n'
        '    :root { --bg:#f7f9fb; --ink:#263238; }\n'
        '    html, body { height: 100%; margin: 0; }\n'
        '    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, PingFang SC, Microsoft YaHei, sans-serif; background: var(--bg); color: var(--ink); }\n'
        '    h2 { margin: 16px 16px 0; }\n'
        '    .legend { display: flex; gap: 16px; align-items: center; margin: 8px 16px; flex-wrap: wrap; }\n'
        '    .hint { color: #607D8B; font-size: 12px; margin: 0 16px 8px; }\n'
        '    #viewport { position: absolute; inset: 120px 0 0 0; overflow: hidden; background: linear-gradient(90deg, rgba(0,0,0,0.03) 1px, transparent 1px) 0 0/40px 40px, linear-gradient(rgba(0,0,0,0.03) 1px, transparent 1px) 0 0/40px 40px; }\n'
        '    #canvas { position: absolute; left: 0; top: 0; transform-origin: 0 0; }\n'
        '    .edges { position: absolute; left: 0; top: 0; z-index: 0; }\n'
        '    .node { position: absolute; width: 280px; height: 84px; border: 1px solid #CFD8DC; border-radius: 10px; padding: 8px 10px 10px; background: #fff; box-shadow: 0 2px 6px rgba(0,0,0,0.06); z-index: 2; }\n'
        '    .node .bar { position: absolute; left: 0; top: 0; height: 6px; width: 100%; border-top-left-radius: 10px; border-top-right-radius: 10px; }\n'
        '    .node .title { font-weight: 700; margin: 8px 0 4px; font-size: 14px;}\n'
        '    .node .meta { color: #607D8B; font-size: 12px; margin-bottom: 2px; }\n'
        '    .node .id { color: #B0BEC5; font-size: 11px; word-break: break-all; }\n'
        '    .node:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.12); }\n'
        '    .pack { position: absolute; border: 1px dashed #CFD8DC; border-radius: 12px; background: rgba(236,239,241,0.35); z-index: 1; }\n'
        '    .pack-title { position: sticky; top: 0; background: #ECEFF1; color: #455A64; font-weight: 700; padding: 6px 10px; border-top-left-radius: 12px; border-top-right-radius: 12px; border-bottom: 1px solid #CFD8DC; }\n'
        '    .legend .item { display:flex;align-items:center;margin-right:16px }\n'
        '  </style>\n'
        '</head>\n'
        '<body>\n'
        '  <h2>场景拓扑图</h2>\n'
        f'  <div class="legend">{legend_items}</div>\n'
        '  <div class="hint">交互：滚轮缩放，按住鼠标左键拖拽平移。箭头：蓝=机关跳转(go)，绿=清场跳转(clear)，灰虚线=返回(back)。按包分组，包内按层级自左向右排列。</div>\n'
        '  <div id="viewport">\n'
        f'    <div id="canvas" style="width:{max_x}px;height:{max_y}px">\n'
        f'      {svg_html}\n'
        f'      {"".join(pack_divs)}\n'
        f'      {nodes_html}\n'
        '    </div>\n'
        '  </div>\n'
        '  <script>\n'
        '  (function(){\n'
        '    const viewport = document.getElementById("viewport");\n'
        '    const canvas = document.getElementById("canvas");\n'
        '    let scale = 0.8, ox = 20, oy = 20;\n'
        '    function apply(){ canvas.style.transform = `translate(${ox}px, ${oy}px) scale(${scale})`; }\n'
        '    apply();\n'
        '    let dragging = false, sx=0, sy=0, sox=0, soy=0;\n'
        '    viewport.addEventListener("mousedown", (e)=>{ dragging = true; sx = e.clientX; sy = e.clientY; sox = ox; soy = oy; });\n'
        '    window.addEventListener("mouseup", ()=> dragging=false);\n'
        '    window.addEventListener("mousemove", (e)=>{ if(!dragging) return; ox = sox + (e.clientX - sx); oy = soy + (e.clientY - sy); apply(); });\n'
        '    viewport.addEventListener("wheel", (e)=>{ e.preventDefault(); const prev = scale; scale *= (e.deltaY < 0 ? 1.1 : 0.9); scale = Math.max(0.2, Math.min(2.5, scale));\n'
        '      const rect = viewport.getBoundingClientRect(); const cx = e.clientX - rect.left; const cy = e.clientY - rect.top;\n'
        '      ox = cx - (cx - ox) * (scale/prev); oy = cy - (cy - oy) * (scale/prev); apply(); }, {passive:false});\n'
        '  })();\n'
        '  </script>\n'
        '</body>\n'
        '</html>'
    )
    return html


def main():
    packs = load_scenes()
    nodes, edges = build_graph(packs)
    pos, pack_bounds = layout(nodes, edges)
    html = render_html(nodes, edges, pos, pack_bounds)
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Wrote: {OUT_HTML}")

if __name__ == '__main__':
    main()
