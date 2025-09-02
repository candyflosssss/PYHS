# 事件清单与 UI 绑定

本项目采用超轻量事件总线（`src/core/events.py`）。下表列出了与战斗与 UI 强相关的事件、典型触发点、建议载荷，以及 Tk UI 的处理要点。

## 战斗单位/棋盘

- card_added
  - 触发：`Player.play_card` 成功后
  - 载荷：`{ card, owner }`
  - UI：`BattlefieldView` 将卡添加到我方区域并渲染

- card_damaged / card_healed
  - 触发：`Card.take_damage` / `Card.heal`
  - 载荷：`{ card, amount, hp_before, hp_after }`
  - UI：播放命中/治疗动画与飘字，轻量刷新卡面

- card_will_die / card_died
  - 触发：`Card.take_damage` 内部 / `Player.check_deaths`
  - 载荷：`{ card }`
  - UI：播放死亡动画后从我方区域移除

## 敌人区

- enemy_added / enemy_removed / enemies_changed / enemies_reset / enemies_cleared
  - 触发：`ObservableList` on_add/on_remove 等（`SimplePvEGame.enemies`）
  - 载荷：`{ item/name }`（已在 `zone.py` 内组装）
  - UI：`BattlefieldView` 重新载入敌人列表并渲染

- enemy_damaged
  - 触发：`Enemy.take_damage`、部分技能直接更改 hp
  - 载荷：`{ enemy, amount, hp_before, hp_after }`
  - UI：播放命中动画与飘字并轻量刷新

- enemy_will_die / enemy_died
  - 触发：`Enemy.on_death` / `SimplePvEGame._handle_enemy_death`
  - 载荷：`{ enemy, scene_changed: bool }`
  - UI：若 `scene_changed` 为真，交由场景切换逻辑；否则播放死亡动画并移除

## 角色状态/属性

- equipment_changed
  - 触发：`EquipmentSystem.equip/unequip`
  - 载荷：`{ owner, slot, item, removed? }`
  - UI：轻量刷新卡面（攻击/AC/装备槽文本）

- stamina_changed
  - 触发：`Combatant.refill_stamina/spend_stamina`
  - 载荷：`{ owner, stamina, stamina_max, reason }`
  - UI：轻量刷新体力胶囊

- hp_changed（可选，如需从其他系统统一发出）
  - 触发：集中修改 hp 的地方
  - 载荷：`{ owner, hp, max_hp, reason }`
  - UI：轻量刷新血条

## UI 订阅点

- `BattlefieldView._mount_events` 订阅上述大部分事件，实现动态增删/刷新/动画。
- `ResourcesView` 订阅 `inventory_changed/resource_changed`，保持资源/背包区同步。
- `OperationsView` 订阅 `equipment_changed/stamina_changed` 等，更新操作可用状态。

如需新增事件，按“小写+下划线”命名，并在产生方 `publish(event, payload)`，UI 视图内增订阅并实现最小刷新逻辑即可。
