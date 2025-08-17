"""
统一的 ANSI 颜色与配色策略（节制使用）：
- 通过 NO_COLOR 环境变量禁用颜色。
- 仅对关键元素上色：标题、友方、敌方、资源/物品、状态摘要。
- 其余细节（如信息区的后续行、历史）使用淡色。
"""
from __future__ import annotations
import os
import re

ENABLE_COLOR = os.getenv('NO_COLOR') is None

# ANSI 基础
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_MAGENTA = "\033[35m"
FG_CYAN = "\033[36m"
FG_BRIGHT_WHITE = "\033[97m"
FG_BRIGHT_CYAN = "\033[96m"
FG_BRIGHT_YELLOW = "\033[93m"
FG_BRIGHT_MAGENTA = "\033[95m"


def _wrap(code: str, s: str) -> str:
    if not ENABLE_COLOR:
        return s
    return f"{code}{s}{RESET}"

"""主题化颜色支持
- 通过 COLOR_THEME 环境变量切换主题：default | mono | high-contrast
- 依然尊重 NO_COLOR 禁用颜色
"""

THEMES = {
    'default': {
        'heading': BOLD + FG_BRIGHT_CYAN,
        'label': DIM,
        'friendly': FG_GREEN,
        'enemy': FG_YELLOW,
        'resource': FG_MAGENTA,
        'success': FG_GREEN,
        'warning': FG_YELLOW,
        'error': FG_RED,
        'dim': DIM,
        'bold': BOLD,
    },
    'mono': {
        'heading': BOLD,     # 仅加粗
        'label': DIM,
        'friendly': '',
        'enemy': '',
        'resource': '',
        'success': '',
        'warning': '',
        'error': '',
        'dim': DIM,
        'bold': BOLD,
    },
    'high-contrast': {
        'heading': BOLD + FG_BRIGHT_CYAN,
        'label': DIM,
        'friendly': FG_GREEN,
        'enemy': FG_BRIGHT_YELLOW,
        'resource': FG_BRIGHT_MAGENTA,
        'success': FG_GREEN,
        'warning': FG_BRIGHT_YELLOW,
        'error': FG_RED,
        'dim': DIM,
        'bold': BOLD,
    },
}

_theme_name = os.getenv('COLOR_THEME', 'default')
_styles = THEMES.get(_theme_name, THEMES['default'])

def set_theme(theme: str | dict) -> None:
    """切换主题：传入主题名或自定义映射。"""
    global _styles
    if isinstance(theme, str):
        _styles = THEMES.get(theme, THEMES['default'])
    elif isinstance(theme, dict):
        _styles = { **THEMES['default'], **theme }

def _style(name: str, s: str) -> str:
    code = _styles.get(name, '')
    if not code:
        return s  # 单色或未定义时返回原文
    return _wrap(code, s)

# 语义化颜色（保留原 API）

def heading(s: str) -> str:
    return _style('heading', s)

def label(s: str) -> str:
    return _style('label', s)

def friendly(s: str) -> str:
    return _style('friendly', s)

def enemy(s: str) -> str:
    return _style('enemy', s)

def resource(s: str) -> str:
    return _style('resource', s)

def success(s: str) -> str:
    return _style('success', s)

def warning(s: str) -> str:
    return _style('warning', s)

def error(s: str) -> str:
    return _style('error', s)

def dim(s: str) -> str:
    return _style('dim', s)

def bold(s: str) -> str:
    return _style('bold', s)

# 去除 ANSI 颜色代码（用于日志等纯文本场景）
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def strip(s: str) -> str:
    if not isinstance(s, str):
        return s
    return _ANSI_RE.sub('', s)
