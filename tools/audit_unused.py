import ast, os, sys, json
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()

IGNORE_DIRS = {"__pycache__", "build", ".venv", "venv", ".git"}
SUSPICIOUS_TOKENS = (
    "legacy", "deprecated", "_old", "old_", "_v0", "v0_", "unused", "tmp", "demo"
)


def py_files(root: Path):
    for p in root.rglob("*.py"):
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        yield p


def module_name(p: Path) -> str:
    rel = p.relative_to(ROOT)
    parts = list(rel.parts)
    parts[-1] = parts[-1].replace(".py", "")
    return ".".join(parts)


class Indexer(ast.NodeVisitor):
    def __init__(self, mod: str):
        self.mod = mod
        self.defs: List[Dict] = []
        self.names: Set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # 忽略双下划线魔术方法
        if not (node.name.startswith("__") and node.name.endswith("__")):
            self.defs.append({"name": node.name, "kind": "function", "line": node.lineno})
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if not (node.name.startswith("__") and node.name.endswith("__")):
            self.defs.append({"name": node.name, "kind": "function", "line": node.lineno})
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.defs.append({"name": node.name, "kind": "class", "line": node.lineno})
        for b in node.body:
            if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # 忽略类中的双下划线魔术方法
                if not (b.name.startswith("__") and b.name.endswith("__")):
                    self.defs.append({"name": f"{node.name}.{b.name}", "kind": "method", "line": b.lineno})
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        self.names.add(node.id)

    def visit_Attribute(self, node: ast.Attribute):
        # 记录属性名（可能对应方法名或常量名）
        try:
            if isinstance(node.attr, str):
                self.names.add(node.attr)
        except Exception:
            pass
        self.generic_visit(node)


def build_index() -> Tuple[Dict, Dict]:
    index: Dict[str, Dict] = {}
    uses: Dict[str, Dict] = {}
    for f in py_files(ROOT):
        mod = module_name(f)
        try:
            text = f.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(f))
        except Exception:
            continue
        ix = Indexer(mod)
        ix.visit(tree)
        index[mod] = {"file": str(f), "defs": ix.defs}
        uses[mod] = {"file": str(f), "names": sorted(ix.names)}
    return index, uses


def find_unreferenced(index: Dict, uses: Dict) -> List[Dict]:
    # 聚合所有定义的顶层名字（类名/函数名；方法按 ClassName.MethodName 保留，但匹配时用顶层 ClassName/方法名）
    defined: Dict[str, List[Tuple[str, Dict]]] = {}
    for mod, data in index.items():
        for d in data["defs"]:
            base = d["name"].split(".")[0]
            defined.setdefault(base, []).append((mod, d))

    used_names: Set[str] = set()
    for _, data in uses.items():
        used_names.update(data["names"])

    candidates: List[Dict] = []
    for basename, defs in defined.items():
        if basename not in used_names:
            for mod, d in defs:
                reason = "未被引用（名称级粗匹配）"
                name_lower = d["name"].lower()
                if any(tok in name_lower for tok in SUSPICIOUS_TOKENS):
                    reason += "; 命名提示"
                candidates.append({
                    "module": mod,
                    "file": index[mod]["file"],
                    "name": d["name"],
                    "kind": d["kind"],
                    "line": d["line"],
                    "reason": reason,
                })
    return candidates


def suspicious_modules(index: Dict) -> List[Dict]:
    out: List[Dict] = []
    for mod, data in index.items():
        base = Path(data["file"]).name.lower()
        mod_l = mod.lower()
        if any(tok in base or tok in mod_l for tok in SUSPICIOUS_TOKENS):
            out.append({"module": mod, "file": data["file"], "reason": "文件/模块命名提示"})
    return out


def main():
    index, uses = build_index()
    unused = find_unreferenced(index, uses)
    sus_mods = suspicious_modules(index)
    result = {
        "summary": {
            "modules": len(index),
            "defs": sum(len(v["defs"]) for v in index.values()),
            "unused_defs": len(unused),
            "suspicious_modules": len(sus_mods),
        },
        "unused_candidates": unused,
        "suspicious_modules": sus_mods,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
