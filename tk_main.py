from ui.tkinter import run_tk
import sys
import os


def _write_startup_marker():
    try:
        lines = []
        lines.append(f"pid: {os.getpid()}")
        lines.append(f"cwd: {os.getcwd()}")
        lines.append(f"executable: {getattr(sys, 'executable', '')}")
        lines.append(f"argv: {sys.argv}")
        try:
            lines.append(f"frozen: {getattr(sys, 'frozen', False)}")
        except Exception:
            lines.append("frozen: <err>")
        try:
            lines.append(f"_MEIPASS: {getattr(sys, '_MEIPASS', None)}")
        except Exception:
            lines.append("_MEIPASS: <err>")

        # 尝试写入多个位置以提高命中概率：%LOCALAPPDATA%、%TEMP%、当前工作目录
        try:
            base = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'PYHS')
            os.makedirs(base, exist_ok=True)
            p = os.path.join(base, 'startup.txt')
            with open(p, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception:
            pass
        try:
            tmp = os.getenv('TEMP') or os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Temp')
            p2 = os.path.join(tmp, 'pyhs_startup.txt')
            with open(p2, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception:
            pass
        try:
            p3 = os.path.join(os.getcwd(), 'startup_local.txt')
            with open(p3, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception:
            pass
        # 弹窗提示（确保用户能看到 EXE 已启动）
        try:
            import ctypes
            msg = 'COMOS-GUI 已启动(诊断写入尝试)。如仍无日志，请回报。'
            ctypes.windll.user32.MessageBoxW(0, msg, 'COMOS 启动', 0)
        except Exception:
            pass
    except Exception:
        pass


if __name__ == "__main__":
    # 在入口尽早记录启动信息，便于单击 EXE 时诊断路径/打包上下文
    _write_startup_marker()
    # 尝试在运行时确定一个明确的初始场景路径，优先兼容 PyInstaller onefile (_MEIPASS)
    initial = None
    try:
        # 当被打包时，场景可能在 sys._MEIPASS 下的 scenes 目录
        if getattr(sys, 'frozen', False):
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                candidate = os.path.join(meipass, 'scenes', 'default_scene.json')
                if os.path.exists(candidate):
                    initial = candidate
        # 开发环境下使用 yyy/scenes 下的默认场景
        if initial is None:
            candidate = os.path.join(os.path.dirname(__file__), 'scenes', 'default_scene.json')
            if os.path.exists(candidate):
                initial = candidate
    except Exception:
        initial = None

    # 支持通过命令行传入初始场景（覆盖），否则使用已检测到的路径或回退到默认场景名
    cli_scene = sys.argv[1] if len(sys.argv) > 1 else None
    initial_scene = cli_scene or initial or 'default_scene.json'
    # 可按需设定初始场景，例如: initial_scene="adventure_pack/world_map.json"
    run_tk(player_name="玩家", initial_scene=initial_scene)
