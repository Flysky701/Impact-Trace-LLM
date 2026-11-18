"""Offline, evidence-preserving Kotlin graph extraction. Never executes project code.

Tree-sitter is a syntax parser, not a Kotlin type checker: call targets are explicitly
labelled candidates. A profile describes source sets that cannot be inferred safely
without evaluating Gradle. Source locations always refer to the original repository.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from fnmatch import fnmatch
import hashlib
import json
from pathlib import Path
import re
import subprocess

from . import git_service as git

try:
    from tree_sitter import Language, Parser
    from tree_sitter_language_pack import get_language
    import tree_sitter_kotlin

    GRAMMAR = get_language("kotlin")
    ALTERNATE_GRAMMAR = Language(tree_sitter_kotlin.language())
except ImportError:  # pragma: no cover - exercised only when optional Kotlin deps are absent
    Parser = GRAMMAR = ALTERNATE_GRAMMAR = None
DECLARATIONS = {"class_declaration", "object_declaration", "function_declaration"}
COMMENTS = {"line_comment", "block_comment", "multiline_comment"}
BRANCHES = {"if_expression", "when_entry", "while_statement", "for_statement", "do_while_statement", "catch_block"}


def descendants(node, stop=()):
    for child in node.named_children:
        yield child
        if child.type not in stop:
            yield from descendants(child, stop)


def text(node):
    return node.text.decode("utf-8", errors="replace") if node else ""


def child(node, kind):
    return next((c for c in node.named_children if c.type == kind), None)


def compact(value):
    return re.sub(r"\s+", " ", value).strip()


def name_of(node):
    return text(child(node, "simple_identifier") or child(node, "type_identifier") or child(node, "identifier"))


def location(node, path):
    return {"path": path, "line": node.start_point.row + 1, "end": node.end_point.row + 1}


def statements(node, path):
    """Structured syntax activity, preserving alternatives/loops/callback boundaries."""
    if node.type in {"function_body", "block", "lambda_literal", "statements", "control_structure_body"}:
        items = []
        for c in node.named_children:
            if c.type not in COMMENTS | {"lambda_parameters"}:
                items.extend(statements(c, path))
        return items
    raw = text(node)
    result = {"kind": "step", "label": compact(raw)[:150], "code": raw,
              **location(node, path), "children": []}
    children = [c for c in node.named_children if c.type not in COMMENTS]
    if node.type == "if_expression" and children:
        result.update(kind="if", label=compact(text(children[0])))
        result["branches"] = [{"label": "是", "items": statements(children[1], path)}] if len(children) > 1 else []
        result["branches"].append({"label": "否", "items": statements(children[2], path) if len(children) > 2 else []})
    elif node.type in {"while_statement", "for_statement", "do_while_statement"}:
        result.update(kind="loop", label=compact(raw.split("{", 1)[0])[:150])
        body = child(node, "block") or child(node, "control_structure_body")
        if body:
            result["children"] = statements(body, path)
        elif len(children) > 1:
            result["children"] = statements(children[-1], path)
    elif node.type == "when_expression":
        result.update(kind="choice", label="when · 条件选择", branches=[])
        for c in children:
            if c.type == "when_entry":
                body = c.named_children[-1]
                result["branches"].append({"label": compact(text(c).split("->")[0]), "items": statements(body, path)})
    elif node.type == "try_expression":
        result.update(kind="try", label="try / catch / finally", branches=[])
        for c in children:
            body = c if c.type in {"block", "statements"} else child(c, "block") or child(c, "statements")
            if body:
                result["branches"].append({"label": "正常路径" if c.type in {"block", "statements"} else c.type.replace("_block", ""), "items": statements(body, path)})
    elif node.type in {"return_expression", "throw_expression", "jump_expression"}:
        result["kind"] = "exit"
    else:
        # Deferred lambdas are never flattened into an alleged runtime sequence.
        lambdas = [c for c in descendants(node, {"lambda_literal", "function_declaration", "object_literal"}) if c.type == "lambda_literal"]
        if lambdas:
            result["kind"] = "scope"
            result["label"] = compact(raw.split("{", 1)[0])[:150] + " {…}"
            result["children"] = statements(lambdas[0], path)
            result["boundary"] = "lambda / 回调体；执行时机由调用方决定"
            if len(lambdas) > 1:
                result["boundary"] += f"；另有 {len(lambdas) - 1} 个 lambda，见源码"
    return [result]


def parse_kotlin(path, source, module, origin, test=False, flows=()):
    if GRAMMAR is None:  # pragma: no cover
        raise git.RepositoryError("分析 Kotlin 仓库需先安装 backend/requirements-analysis.txt。")
    raw = source.encode("utf-8")
    root = Parser(GRAMMAR).parse(raw).root_node
    grammar = "language-pack-0.13.0"
    if root.has_error:
        alternate = Parser(ALTERNATE_GRAMMAR).parse(raw).root_node
        def recovery_size(node):
            if node.type == "ERROR" or node.is_missing:
                return max(1, node.end_byte - node.start_byte)
            return sum(recovery_size(c) for c in node.named_children)
        if recovery_size(alternate) < recovery_size(root):
            root, grammar = alternate, "tree-sitter-kotlin-1.1.0"
    package = text(child(root, "package_header")).removeprefix("package ").strip()
    imports = []
    for n in descendants(root, DECLARATIONS):
        if n.type in {"import", "import_header"}:
            value = text(n).removeprefix("import ").strip()
            imports.append({"name": value.split(" as ")[0], "alias": value.split(" as ")[-1].rsplit(".", 1)[-1], "line": n.start_point.row + 1})
    symbols, entities, errors = [], [], []
    identities = Counter()

    def visit(n, parents=()):
        next_parents = parents
        if n.type == "property_declaration":
            variable = child(n, "variable_declaration")
            if variable and name_of(variable):
                next_parents = (*parents, name_of(variable))
        if n.type in DECLARATIONS:
            name = name_of(n)
            if name:
                receiver = compact(text(child(n, "receiver_type")))
                if not receiver and n.type == "function_declaration":
                    prefix = text(n).split("fun ", 1)[-1].split(name + "(", 1)[0]
                    if prefix.endswith("."):
                        receiver = compact(prefix[:-1])
                qualname = ".".join((*parents, *((receiver,) if receiver else ()), name))
                parameters = compact(text(child(n, "function_value_parameters")))
                identity = f"{path}::{qualname}{parameters}"
                identities[identity] += 1
                if identities[identity] > 1:
                    identity += f"#occurrence-{identities[identity]}"
                owned = list(descendants(n, DECLARATIONS))
                calls = []
                for c in owned:
                    if c.type == "call_expression" and c.named_children:
                        callee = c.named_children[0]
                        if callee.type == "call_expression":
                            continue  # A trailing lambda wraps the same call.
                        callee_text = compact(text(callee))
                        match = re.search(r"(`[^`]+`|[A-Za-z_][\w]*)$", callee_text)
                        if match:
                            calls.append({"name": match[1].strip("`"), "expression": callee_text[:140], "line": c.start_point.row + 1})
                kind = "function" if n.type == "function_declaration" else "class"
                item = {"id": identity, "name": name, "qualified": qualname, "package": package,
                        "module": module, "kind": kind, "test": test, **location(n, path),
                        "lines": n.end_point.row - n.start_point.row + 1,
                        "branches": sum(c.type in BRANCHES for c in owned), "calls": calls if kind == "function" else [],
                        "signature": compact(text(n).split("{", 1)[0])[:220],
                        "fingerprint": hashlib.sha256(text(n).encode()).hexdigest(),
                        "parseError": n.has_error}
                body = child(n, "function_body")
                if body and (name in flows or qualname in flows):
                    item["flow"] = statements(body, path)
                symbols.append(item)
                if kind == "class" and "@Entity" in text(child(n, "modifiers")):
                    entities.append(parse_entity(n, path, identity))
                next_parents = (*parents, name)
        if n.type == "ERROR" or n.is_missing:
            errors.append({**location(n, path), "kind": n.type})
        for c in n.named_children:
            visit(c, next_parents)

    visit(root)
    return {"path": path, "module": module, "origin": origin, "test": test,
            "lines": len(source.splitlines()), "package": package, "imports": imports,
            "symbols": symbols, "entities": entities, "errors": errors, "grammar": grammar}


def parse_entity(node, path, identity):
    annotation = text(child(node, "modifiers"))
    table = re.search(r'tableName\s*=\s*"([^"\n]+)"', annotation)
    fields = []
    for p in descendants(node, {"class_body"}):
        if p.type != "class_parameter":
            continue
        value = text(p)
        prop = re.search(r"\b(?:val|var)\s+(\w+)\s*:\s*([^=\n]+)", value)
        column = re.search(r'@ColumnInfo\s*\(\s*name\s*=\s*"([^"\n]+)"', value)
        if prop:
            fields.append({"name": column[1] if column else prop[1], "type": prop[2].strip(),
                           "primary": "@PrimaryKey" in value, "line": p.start_point.row + 1})
    foreign = []
    for match in re.finditer(r"ForeignKey\s*\((.*?)\)", annotation, re.S):
        body = match[1]
        target = re.search(r"entity\s*=\s*(\w+)::class", body)
        def columns(key):
            values = re.search(key + r"\s*=\s*\[([^]]+)\]", body)
            return re.findall(r'"([^"\n]+)"', values[1]) if values else []
        delete = re.search(r"onDelete\s*=\s*ForeignKey\.(\w+)", body)
        if target:
            foreign.append({"target": target[1], "parentColumns": columns("parentColumns"),
                            "childColumns": columns("childColumns"), "onDelete": delete[1] if delete else "NO_ACTION"})
    primary = re.search(r"primaryKeys\s*=\s*\[([^]]+)\]", annotation)
    if primary:
        keys = re.findall(r'"([^"\n]+)"', primary[1])
        for f in fields:
            f["primary"] |= f["name"] in keys
    return {"id": identity, "name": name_of(node), "table": table[1] if table else name_of(node),
            "fields": fields, "foreignKeys": foreign, **location(node, path)}


def tree_entries(path, sha):
    entries = {}
    for row in git.git(path, "ls-tree", "-r", "-l", "-z", sha).split(b"\0"):
        if not row:
            continue
        meta, name = row.split(b"\t", 1)
        mode, kind, oid, size = meta.decode().split()
        if kind == "blob" and mode in {"100644", "100755"}:
            entries[name.decode("utf-8")] = (oid, int(size))
    return entries


def read_blobs(path, entries, names):
    selected = [(name, entries[name]) for name in sorted(names) if name in entries]
    if any(size > 2 * 1024 * 1024 for _, (_, size) in selected):
        raise git.RepositoryError("分析输入中有超过 2 MiB 的源码，请缩小分析范围。")
    if not selected:
        return {}
    process = subprocess.run(["git", "--no-pager", "-C", str(path), "cat-file", "--batch"],
                             input="".join(oid + "\n" for _, (oid, _) in selected).encode(),
                             capture_output=True, timeout=60, check=True)
    raw, offset, result = process.stdout, 0, {}
    for name, (_, _) in selected:
        end = raw.index(b"\n", offset)
        _, kind, length = raw[offset:end].split()
        if kind != b"blob":
            raise git.RepositoryError("源码对象类型不匹配。")
        size = int(length)
        result[name] = raw[end + 1:end + 1 + size].decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        offset = end + size + 2
    return result


def snapshot(repo, revision, profile):
    working = revision == "WORKTREE"
    sha = git.resolve_revision(repo, "HEAD" if working else revision)
    entries = tree_entries(repo, sha)
    names = set(entries)
    if working:
        names.update(git.git(repo, "ls-files", "--others", "--exclude-standard", "-z").decode().split("\0"))
    roots = profile["sourceRoots"]
    configs = {r[key] for r in roots for key in ("excludesFile", "derivedFile") if key in r}
    configs.update(profile.get("buildFiles", []))
    wanted = configs | {p for p in names if p.endswith(".kt") and any(p.startswith(r["path"].rstrip("/") + "/") for r in roots)}
    if len(wanted) > 5000:
        raise git.RepositoryError("Demo 单次最多分析 5,000 个源码文件，请缩小 profile 范围。")
    if working:
        sources = {}
        for p in sorted(wanted):
            file = repo / p
            if not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(repo.resolve()):
                continue
            if file.stat().st_size > 2 * 1024 * 1024:
                raise git.RepositoryError(f"源码超过 2 MiB：{p}")
            sources[p] = file.read_text(encoding="utf-8-sig", errors="replace")
    else:
        sources = read_blobs(repo, entries, wanted)
    files, excluded, derivations = [], [], []
    for root in roots:
        prefix = root["path"].rstrip("/") + "/"
        exclusions = [line.split("#", 1)[0].strip() for line in sources.get(root.get("excludesFile"), "").splitlines()]
        for p, value in sources.items():
            if not p.startswith(prefix) or not p.endswith(".kt"):
                continue
            if any(e and fnmatch(p[len(prefix):], e) for e in exclusions):
                excluded.append(p)
                continue
            # The graph cites original upstream source, never pretend generated edits are original.
            files.append(parse_kotlin(p, value, root["module"], root.get("origin", "desktop"), root.get("test", False), profile.get("flows", [])))
        if root.get("derivedFile"):
            for line in sources.get(root["derivedFile"], "").splitlines():
                if line.strip() and not line.startswith("#"):
                    derivations.append(prefix + line.split("|", 1)[0])
    builds = []
    for p in profile.get("buildFiles", []):
        module = p.split("/")[-2]
        for match in re.finditer(r'\b(implementation|api|compileOnly)\s*\(\s*project\s*\(\s*"(:[\w:-]+)"', sources.get(p, "")):
            builds.append({"source": module, "target": match[2].lstrip(":"), "kind": match[1],
                           "path": p, "line": sources[p][:match.start()].count("\n") + 1})
    return {"revision": revision if working else sha, "commit": sha, "files": files, "buildEdges": builds,
            "excluded": excluded, "derivedSources": sorted(set(derivations)), "_sources": sources}


def line_changes(before, after):
    old, new = [], []
    for tag, i, j, a, b in SequenceMatcher(None, before.splitlines(), after.splitlines(), autojunk=False).get_opcodes():
        if tag != "equal":
            if j > i:
                old.append([i + 1, j])
            if b > a:
                new.append([a + 1, b])
    return old, new


def connect(snapshot_data):
    symbols = [s for f in snapshot_data["files"] for s in f["symbols"]]
    by_name, by_fqn = defaultdict(list), defaultdict(list)
    files = {f["path"]: f for f in snapshot_data["files"]}
    for s in symbols:
        if not s["test"]:
            by_name[s["name"]].append(s)
            by_fqn[s["package"] + "." + s["qualified"]].append(s)
    import_edges = []
    for f in files.values():
        for imp in f["imports"]:
            for target in by_fqn.get(imp["name"], []):
                if target["path"] != f["path"]:
                    import_edges.append({"source": f["path"], "target": target["path"], "line": imp["line"], "symbol": target["id"]})
    for s in symbols:
        imported = {i["alias"]: i["name"] for i in files[s["path"]]["imports"]}
        stars = {i["name"][:-2] for i in files[s["path"]]["imports"] if i["name"].endswith(".*")}
        for call in s["calls"]:
            choices = by_name.get(call["name"], [])
            call["targets"] = [t["id"] for t in choices if t["kind"] == "function" and
                               (t["path"] == s["path"] or t["package"] == s["package"] or t["package"] in stars or
                                imported.get(call["name"]) == t["package"] + "." + t["qualified"])]
            # For chained receivers, a unique repository name is useful navigation, not proof.
            if not call["targets"] and "." in call["expression"] and len(choices) == 1:
                call["targets"] = [choices[0]["id"]]
            call["resolution"] = "candidate" if call["targets"] else "unresolved"
    snapshot_data["importEdges"] = import_edges


def analyze(repo, profile, base="HEAD", head="WORKTREE"):
    repo = Path(repo).resolve()
    before = snapshot(repo, base, profile)
    after = snapshot(repo, head, profile)
    old_sources, new_sources = before.pop("_sources"), after.pop("_sources")
    changes = []
    paths = sorted(set(old_sources) | set(new_sources))
    for p in paths:
        old, new = old_sources.get(p, ""), new_sources.get(p, "")
        if old.splitlines() == new.splitlines():
            continue
        a, b = line_changes(old, new)
        changes.append({"path": p, "status": "added" if p not in old_sources else "deleted" if p not in new_sources else "modified", "before": a, "after": b,
                        "additions": sum(j - i + 1 for i, j in b), "deletions": sum(j - i + 1 for i, j in a)})
    changed = {c["path"]: c for c in changes}
    old_symbols = {s["id"]: s for f in before["files"] for s in f["symbols"]}
    new_symbols = {s["id"]: s for f in after["files"] for s in f["symbols"]}
    for current, counterpart, side, sources in ((before, new_symbols, "before", old_sources), (after, old_symbols, "after", new_sources)):
        for f in current["files"]:
            f["status"] = changed.get(f["path"], {}).get("status", "unchanged")
            for s in f["symbols"]:
                other = counterpart.get(s["id"])
                s["status"] = ("deleted" if side == "before" else "added") if other is None else "modified" if other["fingerprint"] != s["fingerprint"] else "unchanged"
            # Any changed function gets a real, parsed activity tree, even outside the profile.
            requested = {s["qualified"] for s in f["symbols"] if s["kind"] == "function" and s["status"] != "unchanged"}
            if requested:
                parsed = parse_kotlin(f["path"], sources[f["path"]], f["module"], f["origin"], f["test"], requested)
                flows = {s["id"]: s.get("flow") for s in parsed["symbols"]}
                for s in f["symbols"]:
                    if flows.get(s["id"]) is not None:
                        s["flow"] = flows[s["id"]]
        connect(current)
        production = [f for f in current["files"] if not f["test"]]
        current["metrics"] = {"files": len(production), "lines": sum(f["lines"] for f in production),
                              "functions": sum(s["kind"] == "function" for f in production for s in f["symbols"]),
                              "classes": sum(s["kind"] == "class" for f in production for s in f["symbols"]),
                              "testFiles": sum(f["test"] for f in current["files"]),
                              "parseErrorFiles": sum(bool(f["errors"]) for f in current["files"]),
                              "coverage": None, "testsExecuted": False}
    return {"schemaVersion": 1, "name": profile.get("name", repo.name), "repository": str(repo),
            "generatedAt": datetime.now(timezone.utc).isoformat(), "parser": "Tree-sitter · Kotlin 双语法恢复",
            "before": before, "after": after, "changes": changes, "profile": profile,
            "limitations": ["静态语法分析，不执行项目、不连接游戏、不调用模型。", "函数调用目标是候选定位，尚未进行 Kotlin 类型解析或动态分派分析。",
                            "逐文件选择语法恢复范围更小的 Kotlin grammar；仍有缺口的文件保留错误位置，统计不是编译器语义结果。",
                            "活动图保留条件、循环和 lambda 边界；未展开的异常与协程调度见源码。", "复用来源按 profile 和排除清单读取；机械派生文件展示原始源码，未执行 Gradle。",
                            "测试文件数量不是覆盖率；未运行目标项目测试。", "WORKTREE 为采集时读取的工作区快照，包含未提交及范围内未忽略的新文件。"],
            "sources": {"before": {p: v for p, v in old_sources.items() if p.endswith(".kt")},
                        "after": {p: v for p, v in new_sources.items() if p.endswith(".kt")}}}
