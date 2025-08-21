import sys
import json
import os


def _get_base_dir() -> str:
    """获取资源基路径。
    - 普通运行：返回当前文件所在目录
    - PyInstaller 打包：返回临时解包目录(sys._MEIPASS) 或可执行文件同级目录
    """
    try:
        if getattr(sys, 'frozen', False):  # type: ignore[attr-defined]
            # 优先使用 _MEIPASS（onefile 解包目录），否则退回到可执行文件所在目录
            base = getattr(sys, '_MEIPASS', None)  # type: ignore[attr-defined]
            return base or os.path.dirname(sys.executable)
    except Exception:
        pass
    return os.path.dirname(__file__)


def _get_config_path() -> str:
    """获取配置写入路径。
    - 普通运行：项目目录 user_config.json
    - 打包运行：用户目录 %LOCALAPPDATA%\\PYHS\\user_config.json（保证可写）
    """
    try:
        if getattr(sys, 'frozen', False):  # type: ignore[attr-defined]
            base = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PYHS")
            os.makedirs(base, exist_ok=True)
            return os.path.join(base, 'user_config.json')
    except Exception:
        pass
    return os.path.join(_get_base_dir(), 'user_config.json')


CONFIG_PATH = _get_config_path()


def load_config():
    cfg = {"name": "玩家", "last_pack": "", "last_scene": "default_scene.json"}
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
    except Exception:
        pass
    return cfg


def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def list_scenes():
    """列出基础包(根目录)下的场景文件（聚合多个可能的根：scenes 与 yyy/scenes）。"""
    roots = _get_scene_roots()
    seen = set()
    for root in roots:
        try:
            for name in os.listdir(root):
                if name.lower().endswith('.json'):
                    seen.add(name)
        except Exception:
            continue
    return sorted(seen)


def _detect_scene_is_main(scene_file: str) -> bool:
    """检测场景是否为主地图。
    优先以场景 JSON 中的 main/is_main/type=main 为准；否则用文件名包含 default/main 作为兜底。
    """
    # 在所有已知根里定位该文件并读取元数据
    roots = _get_scene_roots()
    for base in roots:
        path = os.path.join(base, scene_file)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if bool(data.get('main')) or bool(data.get('is_main')):
                        return True
                    if str(data.get('type', '')).lower() == 'main':
                        return True
        except Exception:
            continue
    low = scene_file.lower()
    if 'default' in low or 'main' in low:
        return True
    return False


def list_scenes_partition():
    """把基础包中的场景分为主地图与子地图。"""
    mains: list[str] = []
    subs: list[str] = []
    for s in list_scenes():
        (mains if _detect_scene_is_main(s) else subs).append(s)
    return mains, subs

def _get_scene_roots() -> list[str]:
    """返回可能存在的场景根目录列表，按优先顺序：
    1) <base>/scenes
    2) <base>/yyy/scenes (GUI 打包时使用)
    过滤不存在的路径。
    """
    base = _get_base_dir()
    candidates = [
        os.path.join(base, 'scenes'),
        os.path.join(base, 'yyy', 'scenes'),
    ]
    roots: list[str] = []
    for p in candidates:
        if os.path.isdir(p) and p not in roots:
            roots.append(p)
    return roots


def discover_packs():
    """发现地图组：返回 {pack_id: {name, dir, mains, subs}}。
    pack_id 为子目录名；基础包用空字符串 '' 表示。
    同时兼容 scenes 与 yyy/scenes 两种根路径。
    """
    roots = _get_scene_roots()
    packs: dict[str, dict] = {}
    # 基础包（根目录聚合）
    mains, subs = list_scenes_partition()
    # 选一个存在的根目录作为基础包的 dir 展示用（优先第一个）
    base_dir = roots[0] if roots else os.path.join(_get_base_dir(), 'scenes')
    packs[''] = {
        'name': '基础',
        'dir': base_dir,
        'mains': mains,
        'subs': subs,
    }
    # 子目录包：聚合所有根下的包名，并合并场景
    pack_names = set()
    for r in roots:
        try:
            for entry in os.listdir(r):
                p = os.path.join(r, entry)
                if os.path.isdir(p):
                    pack_names.add(entry)
        except Exception:
            continue
    for entry in sorted(pack_names):
        # 聚合该包在所有根下的内容
        scenes_set = set()
        pack_meta = {}
        pack_dirs = [os.path.join(r, entry) for r in roots if os.path.isdir(os.path.join(r, entry))]
        # 读取第一个可用的 pack.json 作为名称信息
        for pd in pack_dirs:
            meta_path = os.path.join(pd, 'pack.json')
            try:
                if os.path.exists(meta_path):
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        pack_meta = json.load(f) or {}
                        break
            except Exception:
                continue
        # 收集场景文件名（去重）
        for pd in pack_dirs:
            try:
                for name in os.listdir(pd):
                    if name.lower().endswith('.json') and name != 'pack.json':
                        scenes_set.add(name)
            except Exception:
                continue
        scenes = sorted(scenes_set)
        mains2: list[str] = []
        subs2: list[str] = []
        # 主地图：pack.json 指定 mains 优先；否则按场景规则判定
        mains_cfg = pack_meta.get('mains') if isinstance(pack_meta, dict) else None
        if isinstance(mains_cfg, list) and mains_cfg:
            for s in scenes:
                if s in mains_cfg:
                    mains2.append(s)
                else:
                    subs2.append(s)
        else:
            for s in scenes:
                # 传入 "entry/s" 以便 _detect 在多根下定位
                if _detect_scene_is_main(os.path.join(entry, s)) or _detect_scene_is_main(s):
                    mains2.append(s)
                else:
                    subs2.append(s)
        packs[entry] = {
            'name': pack_meta.get('name', entry) if isinstance(pack_meta, dict) else entry,
            'dir': pack_dirs[0] if pack_dirs else os.path.join(base_dir, entry),
            'mains': mains2,
            'subs': subs2,
        }
    return packs

def _pick_default_main(mains: list[str]) -> str:
    if not mains:
        return ''
    # 明确优先顺序
    if 'default_scene.json' in mains:
        return 'default_scene.json'
    # 其次名字包含 default/main 的
    for key in ('default', 'main'):
        for s in mains:
            if key in s.lower():
                return s
    # 否则取首个
    return mains[0]


def _clear_screen():
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
    except Exception:
        print("\033c", end="")


def main():
    cfg = load_config()
    while True:
        _clear_screen()
        print("=== COMOS PvE 合作卡牌游戏 ===")
        print("请选择:")
        pack_id = cfg.get('last_pack', '')
        current_scene = cfg.get('last_scene', 'default_scene.json')
        scene_label = (pack_id + '/' if pack_id else '') + current_scene
        print(f"1. 🎮 开始游戏 (玩家: {cfg.get('name','玩家')}, 场景: {scene_label})")
        print("2. ✏️ 修改玩家名称")
        print("3. 🗺️ 选择地图组")
        print("4. 🔄 重新载入场景列表")
        print("5. 🚪 退出")
        choice = input("请输入选择 (1/2/3/4/5): ").strip()

        if choice == '1':
            print("启动PvE合作游戏模式...")
            # 兜底：若当前 last_scene 不在所选包的主地图内，则挑一个默认主地图
            packs = discover_packs()
            pack = packs.get(pack_id) or packs.get('')
            mains = (pack or {}).get('mains', [])
            if cfg.get('last_scene') not in mains and mains:
                cfg['last_scene'] = _pick_default_main(mains)
                save_config(cfg)
            start_scene_path = (pack_id + '/' if pack_id else '') + cfg.get('last_scene', 'default_scene.json')
            from game_modes.pve_controller import start_simple_pve_game as pve_start
            pve_start(name=cfg.get('name'), scene=start_scene_path)
            break

        elif choice == '2':
            new_name = input("请输入新名称: ").strip()
            if new_name:
                cfg['name'] = new_name
                save_config(cfg)

        elif choice == '3':
            packs = discover_packs()
            if not packs:
                print("未发现任何地图组")
                input("按回车返回菜单...")
                continue
            # 列出地图组
            pack_ids = list(packs.keys())
            print("可选地图组:")
            for i, pid in enumerate(pack_ids, 1):
                pname = packs[pid]['name']
                print(f"  {i}. {pname} ({'基础' if pid=='' else pid})")
            sel_p = input("输入序号选择地图组: ").strip()
            try:
                pidx = int(sel_p) - 1
                if not (0 <= pidx < len(pack_ids)):
                    print("无效选择")
                    input("按回车返回菜单...")
                    continue
                pid = pack_ids[pidx]
                pack = packs[pid]
                mains = pack.get('mains', [])
                if not mains:
                    print("该地图组没有主地图")
                    input("按回车返回菜单...")
                    continue
                # 自动选择主地图
                chosen = _pick_default_main(mains)
                cfg['last_pack'] = pid
                cfg['last_scene'] = chosen
                save_config(cfg)
                print(f"已选择地图组: {pack.get('name', pid)}，主地图: {chosen}")
                input("按回车返回菜单...")
            except ValueError:
                print("请输入数字序号")
                input("按回车返回菜单...")

        elif choice == '4':
            _ = list_scenes()
            print("场景列表已刷新")
            input("按回车返回菜单...")

        elif choice == '5':
            print("再见!")
            break

        else:
            print("无效选择，请输入 1/2/3/4/5")
            input("按回车返回菜单...")


# 旧的多人别名入口已移除，仅保留单人 PvE 入口


if __name__ == "__main__":
    main()
