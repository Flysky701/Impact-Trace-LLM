"""Static Python AST snapshot and control-flow extractor matching the unified graph schema."""
import ast
from collections import defaultdict
import hashlib
from pathlib import Path

from . import code_graph, git_service as git

BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler, ast.Match)


def _compact(text: str, limit: int = 150) -> str:
    return " ".join(text.split()).strip()[:limit]


def _slice_lines(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[max(0, start - 1):min(len(lines), end)])


def _py_statements(nodes: list[ast.stmt], path: str, lines: list[str], depth: int = 0) -> list[dict]:
    if depth > 6:
        return []
    items = []
    for stmt in nodes:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            continue  # Skip docstrings in execution flow.
        line = getattr(stmt, "lineno", 1)
        end = getattr(stmt, "end_lineno", line) or line
        raw = _slice_lines(lines, line, end)
        head = _compact(raw.splitlines()[0] if raw else ast.dump(stmt))
        entry = {"kind": "step", "label": head, "code": raw, "path": path, "line": line, "end": end, "children": []}
        if isinstance(stmt, ast.If):
            cond = _compact(ast.unparse(stmt.test) if hasattr(ast, "unparse") else head)
            entry.update(kind="if", label=f"if {cond}")
            entry["branches"] = [
                {"label": "是", "items": _py_statements(stmt.body, path, lines, depth + 1)},
                {"label": "否", "items": _py_statements(stmt.orelse, path, lines, depth + 1)},
            ]
        elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            entry.update(kind="loop", label=head.rstrip(":"))
            entry["children"] = _py_statements(stmt.body, path, lines, depth + 1)
        elif isinstance(stmt, ast.Try):
            entry.update(kind="try", label="try / except 异常保护", branches=[
                {"label": "正常路径", "items": _py_statements(stmt.body, path, lines, depth + 1)},
            ])
            for handler in stmt.handlers:
                h_name = ast.unparse(handler.type) if handler.type is not None else "Exception"
                entry["branches"].append({
                    "label": f"捕获 {h_name}",
                    "items": _py_statements(handler.body, path, lines, depth + 1),
                })
            if stmt.finalbody:
                entry["branches"].append({
                    "label": "finally 清理",
                    "items": _py_statements(stmt.finalbody, path, lines, depth + 1),
                })
        elif isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            entry["kind"] = "exit"
        items.append(entry)
    return items


def _call_info(node: ast.Call) -> tuple[str, str] | None:
    expr = _compact(ast.unparse(node.func), 120)
    if isinstance(node.func, ast.Name):
        return node.func.id, expr
    if isinstance(node.func, ast.Attribute):
        return node.func.attr, expr
    return None


def parse_python(path: str, source: str, module: str, test: bool = False) -> dict:
    lines = source.splitlines()
    pkg = path[:-3].replace("/", ".")
    if pkg.endswith(".__init__"):
        pkg = pkg[:-9]
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        err_line = exc.lineno or 1
        return {
            "path": path, "module": module, "origin": "python", "test": test,
            "lines": len(lines), "package": pkg, "imports": [], "symbols": [],
            "entities": [], "errors": [{"path": path, "line": err_line, "end": err_line, "kind": "SyntaxError"}],
            "grammar": "python-ast",
        }

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "name": alias.name,
                    "alias": (alias.asname or alias.name.rsplit(".", 1)[-1]),
                    "line": node.lineno,
                })
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for alias in node.names:
                target = f"{base}.{alias.name}".strip(".") if base else alias.name
                imports.append({
                    "name": target,
                    "alias": alias.asname or alias.name,
                    "line": node.lineno,
                })

    symbols, entities = [], []

    def visit_defs(stmts: list[ast.stmt], parents: tuple[str, ...] = ()):
        for stmt in stmts:
            if isinstance(stmt, ast.ClassDef):
                qual = ".".join((*parents, stmt.name))
                line = stmt.lineno
                end = stmt.end_lineno or line
                raw = _slice_lines(lines, line, end)
                identity = f"{path}::{qual}"
                fields = []
                for item in stmt.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        fields.append({
                            "name": item.target.id,
                            "type": _compact(ast.unparse(item.annotation), 60),
                            "primary": item.target.id == "id",
                            "line": item.lineno,
                        })
                if fields:
                    entities.append({
                        "id": identity, "name": stmt.name, "table": stmt.name,
                        "fields": fields, "foreignKeys": [], "path": path, "line": line, "end": end,
                    })
                symbols.append({
                    "id": identity, "name": stmt.name, "qualified": qual, "package": pkg,
                    "module": module, "kind": "class", "test": test, "path": path, "line": line, "end": end,
                    "lines": end - line + 1, "branches": 0, "calls": [],
                    "signature": f"class {stmt.name}",
                    "fingerprint": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                    "parseError": False,
                })
                visit_defs(stmt.body, (*parents, stmt.name))
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = ".".join((*parents, stmt.name))
                line = stmt.lineno
                end = stmt.end_lineno or line
                raw = _slice_lines(lines, line, end)
                args_str = ast.unparse(stmt.args)
                identity = f"{path}::{qual}({args_str})"
                calls = []
                branches = 0
                for sub in ast.walk(stmt):
                    if sub is not stmt and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        continue
                    if isinstance(sub, BRANCH_NODES):
                        branches += 1
                    if isinstance(sub, ast.Call):
                        info = _call_info(sub)
                        if info:
                            calls.append({"name": info[0], "expression": info[1], "line": getattr(sub, "lineno", line)})
                symbols.append({
                    "id": identity, "name": stmt.name, "qualified": qual, "package": pkg,
                    "module": module, "kind": "function", "test": test, "path": path, "line": line, "end": end,
                    "lines": end - line + 1, "branches": branches, "calls": calls,
                    "signature": _compact(f"def {stmt.name}({args_str})", 200),
                    "fingerprint": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                    "parseError": False,
                    "flow": _py_statements(stmt.body, path, lines),
                })

    visit_defs(tree.body)
    return {
        "path": path, "module": module, "origin": "python", "test": test,
        "lines": len(lines), "package": pkg, "imports": imports, "symbols": symbols,
        "entities": entities, "errors": [], "grammar": "python-ast",
    }


def _module_for_python_path(path: str) -> tuple[str, bool]:
    parts = [p for p in path.split("/") if p]
    name = parts[-1]
    is_test = (
        any(p in ("tests", "test", "e2e") for p in parts[:-1])
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
    )
    if len(parts) == 1:
        return "root", is_test
    if parts[0] in ("src", "app", "lib") and len(parts) >= 2:
        mod = parts[1][:-3] if parts[1].endswith(".py") else parts[1]
        return mod or parts[0], is_test
    if len(parts) == 2 and parts[1].endswith(".py"):
        stem = parts[1][:-3]
        return (parts[0] if stem == "__init__" else f"{parts[0]}.{stem}"), is_test
    return parts[0], is_test


def connect_python(snapshot_data: dict) -> None:
    symbols = [s for f in snapshot_data["files"] for s in f["symbols"]]
    files_by_pkg = {f["package"]: f for f in snapshot_data["files"] if f["package"]}
    by_name = defaultdict(list)
    by_class_method = defaultdict(list)
    for s in symbols:
        if not s["test"]:
            by_name[s["name"]].append(s)
            if "." in s["qualified"] and s["kind"] == "function":
                owner = s["qualified"].rsplit(".", 1)[0]
                by_class_method[(s["path"], owner, s["name"])].append(s)

    import_edges = []
    for f in snapshot_data["files"]:
        for imp in f["imports"]:
            candidates = [imp["name"], imp["name"].rsplit(".", 1)[0]]
            for cand in candidates:
                target_file = files_by_pkg.get(cand)
                if target_file and target_file["path"] != f["path"]:
                    import_edges.append({
                        "source": f["path"], "target": target_file["path"],
                        "line": imp["line"], "symbol": cand,
                    })
                    break

    files_map = {f["path"]: f for f in snapshot_data["files"]}
    for s in symbols:
        if s["kind"] != "function":
            continue
        owner = s["qualified"].rsplit(".", 1)[0] if "." in s["qualified"] else ""
        imported_files = {
            e["target"] for e in import_edges if e["source"] == s["path"]
        }
        for call in s["calls"]:
            if call["expression"].startswith("self.") and owner:
                same_cls = by_class_method.get((s["path"], owner, call["name"]), [])
                if same_cls:
                    call["targets"] = [t["id"] for t in same_cls]
                    call["resolution"] = "resolved"
                    continue
            choices = [t for t in by_name.get(call["name"], []) if t["kind"] == "function"]
            scoped = [
                t for t in choices
                if t["path"] == s["path"] or t["path"] in imported_files or files_map[t["path"]]["module"] == s["module"]
            ]
            picked = scoped or (choices if len(choices) == 1 else [])
            call["targets"] = [t["id"] for t in picked]
            call["resolution"] = "candidate" if call["targets"] else "unresolved"

    snapshot_data["importEdges"] = import_edges


def snapshot_python(repo: Path, revision: str) -> dict:
    working = revision == "WORKTREE"
    sha = git.resolve_revision(repo, "HEAD" if working else revision)
    entries = code_graph.tree_entries(repo, sha)
    names = set(entries)
    if working:
        names.update(git.git(repo, "ls-files", "--others", "--exclude-standard", "-z").decode("utf-8", errors="replace").split("\0"))
    py_paths = sorted(
        p for p in names
        if p.endswith(".py") and not any(part.startswith(".") or part in ("venv", "node_modules", "dist", "build") for part in p.split("/"))
    )[:2000]
    if working:
        sources = {}
        root_resolved = repo.resolve()
        for p in py_paths:
            f = repo / p
            if f.is_file() and not f.is_symlink() and f.resolve().is_relative_to(root_resolved) and f.stat().st_size <= 2 * 1024 * 1024:
                sources[p] = f.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    else:
        sources = code_graph.read_blobs(repo, entries, py_paths)

    parsed_files = []
    for p, content in sources.items():
        mod, is_test = _module_for_python_path(p)
        parsed_files.append(parse_python(p, content, mod, is_test))

    data = {
        "revision": "WORKTREE" if working else sha,
        "commit": sha,
        "files": parsed_files,
        "buildEdges": [],
        "excluded": [],
        "derivedSources": [],
        "_sources": sources,
    }
    connect_python(data)
    production = [f for f in parsed_files if not f["test"]]
    data["metrics"] = {
        "files": len(production),
        "lines": sum(f["lines"] for f in production),
        "functions": sum(s["kind"] == "function" for f in production for s in f["symbols"]),
        "classes": sum(s["kind"] == "class" for f in production for s in f["symbols"]),
        "testFiles": sum(f["test"] for f in parsed_files),
        "parseErrorFiles": sum(bool(f["errors"]) for f in parsed_files),
        "coverage": None,
        "testsExecuted": False,
    }
    return data
