from ui.textual_app import run_textual

if __name__ == "__main__":
    # 可按需设定初始场景，例如: initial_scene="adventure_pack/world_map.json"
    run_textual(player_name="玩家", initial_scene=None)
