"""Inspect a Git snapshot without importing or running its source code.

This selection probe counts AST entities and same-class self.method() syntax.
It is not a complete Python call resolver or the platform's analysis engine.
"""

import argparse
import ast
import json
import sqlite3
import subprocess
from collections import deque
from pathlib import Path


def git(repo, *args):
    output = subprocess.check_output(
        ["git", "-C", str(repo), *args], encoding="utf-8"
    )
    return output if args[0] == "show" else output.strip()


class Calls(ast.NodeVisitor):
    def __init__(self, module):
        self.module = module
        self.classes = []
        self.functions = []
        self.edges = []

    def visit_ClassDef(self, node):
        methods = {
            n.name for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.classes.append((node.name, methods))
        self.generic_visit(node)
        self.classes.pop()

    def visit_FunctionDef(self, node):
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        target = node.func
        if (self.classes and self.functions and isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name) and target.value.id == "self"
                and target.attr in self.classes[-1][1]):
            prefix = self.module + "." + ".".join(c[0] for c in self.classes)
            self.edges.append({
                "caller": prefix + "." + ".".join(self.functions),
                "callee": prefix + "." + target.attr,
                "line": node.lineno,
            })
        self.generic_visit(node)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--changed", default="tinydb.table.Table._read_table")
    args = parser.parse_args()
    sha = git(args.repo, "rev-parse", "--verify", args.revision + "^{commit}")
    paths = git(args.repo, "ls-tree", "-r", "--name-only", sha).splitlines()
    result = {"sha": sha, "reachable_commits": int(git(args.repo, "rev-list", "--count", sha)),
              "files": [], "errors": [], "same_class_call_candidates": []}
    for path in paths:
        if not path.endswith(".py") or not path.startswith(("tinydb/", "tests/")):
            continue
        source = git(args.repo, "show", sha + ":" + path)
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            result["errors"].append({"path": path, "error": str(exc)})
            continue
        result["files"].append({
            "path": path, "lines": len(source.splitlines()),
            "classes": sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree)),
            "functions": sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                             for n in ast.walk(tree)),
        })
        if path.startswith("tinydb/"):
            visitor = Calls(path[:-3].replace("/", "."))
            visitor.visit(tree)
            for edge in visitor.edges:
                edge["path"] = path
            result["same_class_call_candidates"].extend(visitor.edges)

    # Probe the proposed edge table and reverse lookup with real AST candidates.
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE edge(snapshot TEXT, caller TEXT, callee TEXT, line INTEGER)")
    db.execute("CREATE INDEX reverse_edge ON edge(snapshot, callee)")
    db.executemany("INSERT INTO edge VALUES (?, ?, ?, ?)", [
        (sha, e["caller"], e["callee"], e["line"])
        for e in result["same_class_call_candidates"]
    ])
    queue = deque([(args.changed, [args.changed])])
    seen = {args.changed}
    impact = []
    while queue:
        callee, chain = queue.popleft()
        for (caller,) in db.execute(
            "SELECT DISTINCT caller FROM edge WHERE snapshot=? AND callee=? ORDER BY caller",
            (sha, callee),
        ):
            if caller in seen:
                continue
            seen.add(caller)
            next_chain = chain + [caller]
            impact.append(next_chain)
            queue.append((caller, next_chain))
    result["probe_changed_entity"] = args.changed
    result["reverse_paths"] = impact
    result["other_snapshot_edges"] = db.execute(
        "SELECT count(*) FROM edge WHERE snapshot=?", ("not-this-snapshot",)
    ).fetchone()[0]
    db.close()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
