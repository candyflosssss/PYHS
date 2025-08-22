# -*- coding: utf-8 -*-
"""应用集中配置与路径管理。
- 统一 APP 名称、用户数据目录、配置文件、日志目录等。
- 统一场景、静态 JSON（技能目录）等资源路径。
- 提供跨平台 fallback：
  - Windows: %LOCALAPPDATA%/APP_NAME
  - Linux/macOS: ~/.config/APP_NAME
"""
from __future__ import annotations
import os
import sys
from typing import List

# 应用名（可用环境变量覆盖）
APP_NAME = os.getenv('PYHS_APP_NAME', 'PYHS')
APP_DOT_DIR = os.getenv('PYHS_DOT_DIR', '.pyhs')  # 家目录下的点目录


def is_frozen() -> bool:
    try:
        return bool(getattr(sys, 'frozen', False))
    except Exception:
        return False


def base_dir() -> str:
    """源码/打包共同的基路径：
    - 打包: _MEIPASS 或 EXE 同级
    - 源码: 当前文件(y y y/src)的上一级目录 (yyy)
    """
    if is_frozen():
        try:
            return getattr(sys, '_MEIPASS', None) or os.path.dirname(sys.executable)  # type: ignore[attr-defined]
        except Exception:
            return os.getcwd()
    # yyy/src/app_config.py -> yyy
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def src_dir() -> str:
    return os.path.abspath(os.path.join(base_dir(), 'src'))


def user_data_dir() -> str:
    """用户可写数据目录（跨平台）。"""
    if os.name == 'nt':
        root = os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    else:
        root = os.path.join(os.path.expanduser('~'), '.config')
    p = os.path.join(root, APP_NAME)
    os.makedirs(p, exist_ok=True)
    return p


def user_config_path() -> str:
    return os.path.join(user_data_dir(), 'user_config.json')


def log_dir() -> str:
    p = os.path.join(os.path.expanduser('~'), APP_DOT_DIR)
    os.makedirs(p, exist_ok=True)
    return p


def startup_local_candidates() -> List[str]:
    """一些启动/诊断文本写入候选位置（按顺序尝试）。"""
    cands: List[str] = []
    # 首选用户数据目录
    cands.append(os.path.join(user_data_dir(), 'startup_local.txt'))
    # 其次临时目录
    try:
        tmp = os.getenv('TEMP') or os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Temp')
        cands.append(os.path.join(tmp, 'pyhs_startup.txt'))
    except Exception:
        pass
    # 最后当前工作目录
    cands.append(os.path.join(os.getcwd(), 'startup_local.txt'))
    return cands


def scenes_roots() -> List[str]:
    """按优先顺序返回场景根目录候选。"""
    roots: List[str] = []
    # 打包时的资源
    if is_frozen():
        try:
            mp = getattr(sys, '_MEIPASS', None)
            if mp:
                for p in (os.path.join(mp, 'scenes'), os.path.join(mp, 'yyy', 'scenes')):
                    if os.path.isdir(p) and p not in roots:
                        roots.append(p)
        except Exception:
            pass
    # 源码布局
    for p in (
        os.path.join(src_dir(), 'scenes'),     # yyy/src/scenes
        os.path.join(base_dir(), 'scenes'),    # yyy/scenes（兼容旧）
    ):
        if os.path.isdir(p) and p not in roots:
            roots.append(p)
    return roots


def skills_catalog_path() -> str:
    return os.path.abspath(os.path.join(src_dir(), 'systems', 'skills_catalog.json'))


def profession_skills_path() -> str:
    return os.path.abspath(os.path.join(src_dir(), 'systems', 'profession_skills.json'))
