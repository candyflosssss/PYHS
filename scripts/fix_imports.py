#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量将 `from core|game_modes|systems|ui|tools ...` 与 `import core|game_modes|systems|ui|tools...`
重写为以 `src.` 为前缀的绝对导入（例如 `from src.core...`）。
- 仅处理顶层包名为上述集合的导入；不改相对导入（from . / from ..）。
- 针对逗号分隔的多模块 import 也做处理。
运行位置：项目根/或 yyy 目录均可，但推荐在 yyy 下运行。
"""
from __future__ import annotations
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # yyy 目录
SRC = BASE / "src"
PACKAGES = ("core", "game_modes", "systems", "ui", "tools")

re_from = re.compile(r"^(\s*from\s+)(%s)(\b)" % ("|".join(PACKAGES)))
# import 行较复杂，按逗号拆分后逐个加前缀
re_import = re.compile(r"^(\s*import\s+)(.+)$")


def transform_line(line: str) -> str:
    s = line
    stripped = s.lstrip()
    # 跳过相对导入
    if stripped.startswith("from .") or stripped.startswith("from .."):
        return s
    # 处理 from X import Y
    s2 = re_from.sub(r"\1src.\2\3", s)
    if s2 != s:
        return s2
    # 处理 import X[, Y, Z]
    m = re_import.match(s)
    if not m:
        return s
    head, body = m.groups()
    parts = [p.strip() for p in body.split(",")]
    new_parts = []
    for p in parts:
        if not p:
            continue
        # 保留 'as' 别名
        if " as " in p:
            mod, alias = p.split(" as ", 1)
            new_parts.append(f"{prefix_module(mod)} as {alias}")
        else:
            new_parts.append(prefix_module(p))
    return head + ", ".join(new_parts) + "\n"


def prefix_module(mod: str) -> str:
    mod = mod.strip()
    for pkg in PACKAGES:
        if mod == pkg or mod.startswith(pkg + "."):
            return "src." + mod
    return mod


def should_rewrite(path: Path) -> bool:
    # 仅处理 .py
    if path.suffix != ".py":
        return False
    # 不处理编译缓存
    return "__pycache__" not in path.parts


def rewrite_file(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    changed_lines = []
    changed = False
    for line in text.splitlines(keepends=True):
        new_line = transform_line(line)
        if new_line != line:
            changed = True
        changed_lines.append(new_line)
    if changed:
        path.write_text("".join(changed_lines), encoding="utf-8")
    return changed


def main() -> None:
    targets = []
    # yyy 根下的入口/脚本
    targets.extend(BASE.glob("*.py"))
    # src 下所有源码
    if SRC.exists():
        targets.extend(SRC.rglob("*.py"))
    total = 0
    changed = 0
    for p in targets:
        if not should_rewrite(p):
            continue
        total += 1
        if rewrite_file(p):
            changed += 1
    print(f"[fix_imports] scanned={total}, changed={changed}")


if __name__ == "__main__":
    main()
