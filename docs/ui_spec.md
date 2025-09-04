### COMOS UI 规格说明（基于现有 Tk 界面）

本规格梳理现有 Tk UI 的功能结构、布局、尺寸与配色，并给出等价的 PyQt 设计基线，作为后续重构与迭代的一致性依据。

## 1. 顶层结构与窗口
- **窗口最小尺寸**: 980x700
- **模式**: `menu` / `game`
- **字体参考**: Segoe UI（Win，可回退），标题 14-16，正文 10-12
- **主题与运行期设置**: 通过 `src/settings.py` 的 `apply_to_tk_app`/`tk_cfg` 注入（PyQt 版本将提供等价接口）

## 2. 主菜单（Menu）
- 顶部信息行：显示当前玩家与最近场景（`玩家: <name> 场景: <pack>/<scene>`）
- 操作项：
  - **开始游戏**：进入最近保存的主地图
  - **选择存档**：弹窗列出 `%LOCALAPPDATA%/PYHS/save_*.json`
  - **修改玩家名称**：弹窗输入
  - **选择地图组**：左侧地图组、右侧主地图，双列选择
  - **重新载入场景列表**：刷新包缓存
  - **退出**

## 3. 游戏界面（Game）
整体分区：
1) 顶栏：场景标题 + 返回主菜单按钮
2) 战场区（Arena）：伙伴区（左）/ 敌人区（右），居顶，三列流式网格（≤5行）
3) 中部主体：左侧资源按钮区，右侧背包 List；下方是“返回上一级/结束回合”操作行
4) 底部日志区：战斗日志文本面板

### 3.1 顶栏
- 标签：`场景: <title or filename>`（粗体 10-12pt）
- 按钮：`主菜单`

### 3.2 战场区（Battlefield）
- **布局**：左右两面板，中间竖直分割线；每侧是三列锚点网格（COLS=3），最多 5 行
- **卡片尺寸**：
  - App 基线：`CARD_W=180`, `CARD_H=80`
  - Battlefield View 默认（无 app 时）：`CARD_W=88`, `CARD_H=96`（由 app 覆盖为 180x80）
- **卡片容器（wrapper）样式**：
  - 默认描边：`#cccccc`，`highlightthickness=3`
  - 背景：`#f7f7f7`
- **高亮风格（app.HL）**：
  - 候选敌人：描边 `#FAD96B`，底色 `#FFF7CC`
  - 候选友方：描边 `#7EC6F6`，底色 `#E6F4FF`
  - 选中敌人：描边 `#FF4D4F`，底色 `#FFE6E6`
  - 选中友方：描边 `#1E90FF`，底色 `#D6EBFF`
- **面板外观**：
  - 伙伴侧面板外框色：`#7EC6F6`
  - 敌人侧面板外框色：`#FAD96B`
- **交互**：
  - 点击我方卡 -> 选中成员（mN）；点击敌人卡 -> 选中敌人（eN）
  - 选中成员后可打开操作弹窗/操作栏；装备槽点击触发装备对话
- **动画**：
  - 轻微平移动画（160ms, 12步）在重排时触发
  - 击中/治疗抖动与飘字（伤害 `#c0392b`，治疗 `#27ae60`）

### 3.3 资源与背包
- 左侧 `资源 (点击拾取)`：
  - 垂直按钮列表（等宽），空时显示占位 `(空)`（灰 `#888`）
  - 按钮文本为资源名（去 ANSI/去前缀）
  - 按钮宽度建议：18-20（PyQt 使用内容自适配 + 最小宽度）
- 右侧 `背包 / 可合成 (iN / 名称 / cN)`：
  - 列表（带滚动），显示 `_section_inventory()` 的条目行

### 3.4 操作行（中部下方）
- 按钮：
  - `返回上一级` -> 发送 `back`
  - `结束回合 (end)` -> 发送 `end`
- 按钮风格：紧凑（Tiny），8-10pt 字号，水平分布

### 3.5 操作栏/弹窗（Operations）
- 底部操作栏已弱化，改为卡片附近的悬浮弹窗（Click/ Hover 模式）
- 弹窗内容：
  - 标题：成员名称
  - `攻击`（根据体力禁用，有 tooltip：体力消耗+描述）
  - 技能按钮组（含装备授予主动技，禁用逻辑同上；tooltip 含消耗与描述）
  - 若处于目标选择会话：列出候选目标按钮、`确定/取消`
- 弹窗定位：锚点卡片右上方（偏移默认 `[+4, 0]`）

### 3.6 日志（LogPane）
- 统一聚合：控制器 `history[-1]` 概要 + `info` 细节（结构化 dict 可着色）
- UI 内显示精简文本；完整结构化日志写入持久文件 `log/game.log`
- 文本面板支持 hover tooltip（可选）

### 3.7 场景切换与抑制窗口
- 进入场景切换时启用 UI 抑制合并窗口，部分刷新延后
- 顶层覆盖层（淡入至 0.8 透明度）提示“正在切换场景…”
- 切换完成后移除覆盖层并重建子 UI

## 4. 颜色与主题（语义）
- 语义色（控制台/文本）：see `src/ui/colors.py`（保留 API：heading/label/friendly/enemy/resource/skill/success/warning/error/stat_*）
- UI 高亮色：见 3.2 高亮风格

## 5. 组件尺寸与间距（建议值）
- 卡片：`180x80`
- 卡片网格内边距：行间 `2-4px`，列间 `2-4px`
- 资源区按钮：垂直 2-4px 间距；最小宽度 ~120px
- 顶/底/中部容器左右内边距：`6-8px`

## 6. 事件与命令
- 命令入口（与控制器兼容）：
  - 攻击：`a mN eK`
  - 技能：`skill <id> mN [targets...]`
  - 拾取：`t rN`
  - 装备/卸下：`eq iN mK` / `uneq mK <slot>`
  - 回合/返回：`end` / `back`
- 事件总线：`inventory_changed` / `resource_changed` / `equipment_changed` / `stamina_changed` / 友方/敌方增删/受伤/死亡 等

## 7. PyQt 重构设计基线
- 包结构：`src/ui/pyqt/`
  - `app.py`：`GameQtApp`，封装控制器、命令路由、全局高亮与会话状态
  - `main_window.py`：`MainWindow`（`QMainWindow`），搭建上述分区与菜单
  - `views/`：
    - `battlefield_view.py`：两侧三列网格、卡片 wrapper 与导出映射、点击选择、基本高亮
    - `resources_view.py`：资源/背包刷新逻辑
    - `operations_view.py`：底部操作行 + 预留弹窗 API
  - `widgets/log_pane.py`：文本日志面板，支持字典与字符串
  - `dialogs/equipment_dialog.py`：装备选择对话框（最小实现）
- 运行入口：`qt_main.py`
- 与控制器耦合：沿用现有 `SimplePvEController`，通过 `_send()` 兼容命令；事件总线后续接入（第一版以直接刷新为主）

## 8. 交互与高亮规范（PyQt 实现）
- 选中/候选高亮通过 wrapper 的 `setStyleSheet` 应用边框色与浅底色
- 伙伴/敌人 1-based 索引与 token 规则保持不变（`mN`/`eN`）
- 选择控制：
  - 点击卡片：更新 `selected_member_index` 或 `selected_enemy_index`
  - 触发技能后：根据 `TargetingEngine` 候选刷新高亮；`确定/取消` 与 Tk 行为一致

—— 本文档将作为 PyQt UI 框架的实现蓝本；详细控件命名见实现代码。


