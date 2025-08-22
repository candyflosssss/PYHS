from src.ui.tkinter import run_tk
from src import app_config as CFG
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

        # 使用集中配置提供的候选路径，逐个尝试
        for _p in CFG.startup_local_candidates():
            try:
                with open(_p, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines) + '\n')
                break
            except Exception:
                continue
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
    # 默认从主菜单启动；仅当命令行显式传入场景路径/ID 时才直接进入游戏
    cli_scene = sys.argv[1] if len(sys.argv) > 1 else None
    # 说明：不再自动探测 default_scene.json，以避免误入关卡而看不到主菜单
    run_tk(player_name="玩家", initial_scene=cli_scene)
