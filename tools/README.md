# tools 模块

- `gen_scene_graph.py`：扫描 `scenes/` 目录，生成场景拓扑图 `scene_graph.html`。
  - 根据 `on_death`/`on_clear`/`parent` 推断边；按包分组并计算层级布局。
  - 产出可交互的 HTML（平移/缩放、图例、节点信息）。

使用方法：在 `yyy/` 根目录执行 `python tools/gen_scene_graph.py`。
