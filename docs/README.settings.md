# 界面/动画/时间 配置说明

项目支持通过用户配置文件调整 Tk 界面配色、动画开关与节奏、场景切换淡入时间等。

- 用户配置文件位置：
  - 源码运行：`yyy/config/user_config.json`
  - 打包运行：`%LOCALAPPDATA%/PYHS/user_config.json`

## 配置结构

新增配置均在 `ui` 与 `console` 命名空间下：

```jsonc
{
  "console": { "theme": "default" },
  "ui": {
    "tk": {
      "card": { "width": 180, "height": 80 },
      "border": { "default": 3, "selected_enemy": 3, "selected_member": 3 },
      "highlight": {
        "cand_enemy_border": "#FAD96B",
        "cand_enemy_bg": "#FFF7CC",
        "cand_ally_border": "#7EC6F6",
        "cand_ally_bg": "#E6F4FF",
        "sel_enemy_border": "#FF4D4F",
        "sel_enemy_bg": "#FFE6E6",
        "sel_ally_border": "#1E90FF",
        "sel_ally_bg": "#D6EBFF"
      },
      "overlay": { "target_alpha": 0.8, "fade_interval_ms": 16, "fade_step": 0.1 },
      "scene_transition": { "delay_ms": 250 },
      "tooltip": { "tick_ms": 120 },
      "stats_colors": { "atk": "#E6B800", "hp_pos": "#27ae60", "hp_zero": "#c0392b", "ac": "#2980b9" },
      "log": { "tags": { "info": "#222", "success": "#27ae60", "warning": "#E67E22", "error": "#d9534f", "state": "#666", "attack": "#c0392b", "heal": "#27ae60", "crit": "#8E44AD", "miss": "#95A5A6", "block": "#2C3E50" } }
    },
    "animations": {
      "enabled": true,
      "colors": { "damage": "#c0392b", "heal": "#27ae60" },
      "shake": { "enabled": false, "amplitude": 3, "cycles": 8, "interval_ms": 18 },
      "flash": { "repeats": 3, "interval_ms": 110 },
      "fade_out": { "steps": 16, "interval_ms": 45, "delay_before_ms": 200 },
      "float_text": { "dy": 30, "steps": 18, "interval_ms": 36, "font_size": 27 }
    }
  }
}
```

## 生效范围

- 颜色：
  - 选中/候选高亮：卡片边框与背景（app.HL）
  - 战斗日志：所有 tag 前景色（LogPane）
  - 属性文本：ATK/HP/AC 颜色可配
  - 飘字：伤害/治疗颜色可配
- 动画与时间：
  - on_hit: 闪烁、抖动参数；全局 enabled=false 则不播放
  - on_death: 淡出步数/间隔与开始前延时
  - float_text: 位移步数/间隔/字号
  - Tooltip: hover 轮询间隔 tick_ms
  - 场景切换：遮罩淡入目标透明度/步进/间隔；切换重建延时 delay_ms

修改配置后，重新启动 GUI 生效；如需运行时刷新，可在代码里调用 `src.settings.reload()` 后重新进入场景。
