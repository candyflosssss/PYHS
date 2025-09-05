# 变更记录：PyQt 卡片/体力胶囊/伙伴区与敌人区描边

日期：2025-09-05
作者：自动化代理（GitHub Copilot）

修改摘要：
- CardWidget：
  - 卡片外框样式改为从 settings 读取（bg、stroke_color、stroke_width、radius），默认 1px 描边。
  - 体力胶囊（stamina capsules）新增 1px 描边，从 settings 中 `ui.tk.stamina.stroke_*` 读取。
- BattlefieldView：
  - 伙伴区/敌人区的 GroupBox 使用配置色描边（分别取 `ALLY_BORDER`/`ENEMY_BORDER`），圆角沿用卡片半径。
- settings：
  - 新增 `ui.tk.card.stroke_color/stroke_width/radius/bg` 和 `ui.tk.stamina.stroke_color/stroke_width` 默认项。
  - 在 `apply_to_tk_app` 中注入 `_card_cfg` 与增强 `_stamina_cfg`（含 stroke 配置）。

影响范围：
- PyQt 前端显示层（不影响核心逻辑与 Tk）。

风险与回滚：
- 风险较低，均为样式层变更。
- 回滚：删除或恢复 `card.py`/`battlefield_view.py` 的样式设置；或在用户配置中将 `stroke_width` 设为 0 以禁用描边。

相关文档/测试：
- 建议在 `docs/README.settings.md` 增补字段说明；可通过 `config/user_config.json` 覆盖颜色与宽度。
