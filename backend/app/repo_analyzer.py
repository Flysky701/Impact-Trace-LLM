"""Repository comprehension, plain-language flow synthesis, diff comparison, and Q&A context engine."""
from collections import Counter, deque, defaultdict
import difflib
import json
from pathlib import Path
import re

from . import code_graph, git_service as git, llm_service, python_graph
from .config import ROOT

ROLE_CATALOG = {
    "app": ("桌面界面与总控中枢", "接收用户操作、切换账号，统筹启停自动任务与各功能模块协作"),
    "desktop": ("桌面端交互与控制", "承载桌面窗口状态、用户配置输入与运行总调度"),
    "shared": ("核心业务与本地数据账本", "集中管理业务判断规则、任务会话逻辑与本机结构化数据库"),
    "device": ("设备手脚：抓图与触控", "负责连接安卓设备/模拟器，实时采集屏幕画面并下发点击滑动指令"),
    "ocr": ("视觉眼睛：画面文字识别", "利用本地识别模型看懂当前屏幕文字与界面元素"),
    "platform": ("系统底座与本机保险箱", "管理底层外部进程、本机凭据加密存储与运行环境隔离"),
    "table": ("数据表读写与缓存核心", "负责单张数据表的增删改查、文档编号管理与查询结果缓存"),
    "database": ("数据库总入口", "管理多张数据表实例并将高层读写请求转交给对应表处理"),
    "storages": ("底层存储引擎", "负责把内存中的数据真正写入磁盘 JSON 文件或内存容器"),
    "queries": ("查询条件匹配器", "定义筛选条件并逐条判断数据记录是否符合要求"),
    "middlewares": ("读写拦截缓冲层", "在真正落盘前做缓存合并或自定义拦截处理"),
    "operations": ("字段修改动作集", "提供递增、追加、删除字段等批量修改数据的操作步骤"),
    "root": ("主入口与核心流程", "串联仓库的核心功能入口、对外接口与基础执行流程"),
}

EDGE_ACTIONS = {
    "device": ("下发抓图与触控指令", "总控确定操作时机后，让设备层抓取当前画面或执行点击"),
    "ocr": ("送入画面并读取识别结果", "将采集到的界面图像交给识别模块判读文字与位置"),
    "shared": ("调用核心业务规则与读写账本", "交由核心业务层判断页面状态，并读写本地账号与运行记录"),
    "platform": ("调用系统进程与加密存储", "借助系统底座管理底层进程生命周期与敏感凭据保护"),
    "storages": ("存取底层持久化数据", "把整理好的数据记录交给存储层读出或写入磁盘"),
    "table": ("委派数据表执行增删改查", "将具体的数据查询与更新交由表核心模块完成"),
    "queries": ("传入筛选条件进行匹配", "组合并执行记录匹配逻辑，筛出目标数据"),
}

WORD_MAP = [
    ("prepare", "准备"), ("shared", "共享"), ("account", "账号"), ("bind", "绑定"),
    ("projection", "本地档案投影"), ("clear", "清理"), ("start", "启动"), ("stop", "停止"),
    ("shutdown", "关闭并释放资源"), ("labyrinth", "迷宫"), ("auto_run", "自动运行"),
    ("autorun", "自动运行"), ("automation", "自动化"), ("recognition", "画面识别"), ("session", "会话"),
    ("handle", "处理"), ("post_entry", "进入后"), ("page", "界面"), ("frame", "画面帧"),
    ("process", "推进处理"), ("classify", "判读界面类型"), ("node", "节点"),
    ("position", "坐标位置"), ("map", "映射定位"), ("team", "队伍"), ("score", "评分筛选"),
    ("evaluate", "评估"), ("overlay", "状态浮层"), ("check", "检查"), ("status", "运行状态"),
    ("feature", "功能特性"), ("profile", "配置档案"), ("route", "路径规划"),
    ("reroll", "重刷"), ("checkpoint", "存档点"), ("character", "角色阵容"),
    ("relic", "藏品增益"), ("migration", "版本迁移"), ("run", "运行状态"),
    ("dispatch", "分发执行指令"), ("insert", "写入记录"), ("upsert", "更新或插入记录"),
    ("update", "更新记录"), ("remove", "移除记录"), ("delete", "删除记录"),
    ("search", "检索数据"), ("read", "读取数据"), ("write", "写回数据"),
    ("cache", "查询缓存"), ("login", "登录认证"), ("project", "项目"),
]


def _split_words(identifier: str) -> str:
    base = identifier.split(".")[-1]
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", base).lower()
    hits = []
    for eng, zh in WORD_MAP:
        if eng in spaced and zh not in hits:
            hits.append(zh)
    return "".join(hits[:3]) if hits else "核心步骤"


def _plain_role(mod_id: str, profile: dict, files: list[dict]) -> tuple[str, str]:
    key = mod_id.split(".")[-1].lower()
    if key in ROLE_CATALOG:
        return ROLE_CATALOG[key]
    hint = (profile.get("moduleLabels") or {}).get(mod_id, "")
    if hint:
        return (f"{hint.split('·')[0].strip()}模块", f"负责 {hint} 相关的业务处理与协作")
    sample_words = Counter()
    for f in files[:20]:
        for s in f.get("symbols", [])[:10]:
            zh = _split_words(s["name"])
            if zh != "核心步骤":
                sample_words[zh] += 1
    focus = "、".join(w for w, _ in sample_words.most_common(3)) or "核心逻辑处理"
    clean_name = mod_id.replace(".", " / ").replace("_", " ")
    return (f"「{clean_name}」功能区", f"负责仓库中与 {focus} 相关的处理流程（共 {len(files)} 个源码文件）")


def _plain_step_from_node(node: dict, idx: int) -> tuple[str, str, str]:
    raw_code = node.get("code") or node.get("label") or ""
    code_lower = raw_code.lower()
    kind = node.get("kind", "step")
    topic = _split_words(node.get("label", ""))
    if topic == "核心步骤":
        topic = _split_words(raw_code[:240])

    if kind == "if" or kind == "choice":
        if any(k in code_lower for k in ("null", "empty", "missing", "none", "not ", "!")):
            what = "检查前置数据与输入条件是否有效"
            why = "在缺少必要信息或目标不存在时提前跳过或兜底，防止后续步骤出错"
        else:
            what = f"根据当前状态分支决定「{topic}」走向"
            why = "不同场景对应不同的处理动作，先分流再执行具体操作"
    elif kind == "loop":
        what = f"循环逐项处理「{topic}」直到满足结束条件"
        why = "持续轮询状态或批量处理集合中的每一项任务"
    elif kind == "try":
        what = f"在异常保护下执行「{topic}」并准备失败兜底"
        why = "防止外部环境波动或局部报错直接中断整条主流程"
    elif kind == "scope":
        what = f"在受控协程或事务范围内执行「{topic}」"
        why = "保证异步等待或成组操作在明确边界内完成"
    elif kind == "exit":
        if "throw" in code_lower or "raise" in code_lower:
            what = "发现不满足继续执行的条件，立即中止并上报异常"
            why = "阻止错误状态继续往下传递污染数据"
        else:
            what = "整理本阶段准备好的结果并返回给上游"
            why = "结束当前流程环节，把状态交回调用方继续推进"
    elif any(k in code_lower for k in ("credential", "session", "token", "password")):
        what = "更新本机登录凭据与会话状态"
        why = "确保后续操作使用的是最新选定账号的认证信息"
    elif any(k in code_lower for k in ("insert", "Dao", "dao", "database", "storage.write", "_update_table", "commit")):
        what = "将最新业务变更写入本地存储账本"
        why = "把内存里计算好的改动持久化保存，避免刷新或重启丢失"
    elif any(k in code_lower for k in ("setting", "config", "strategy", "timeout")):
        what = "同步运行参数与策略配置并等待就绪"
        why = "让下层执行模块拿到一致的开关、超时与运行规则"
    elif any(k in code_lower for k in ("cache", "clear")):
        what = "清理或刷新缓存记录"
        why = "防止后续读取到修改前的过期旧数据"
    else:
        what = f"执行第 {idx} 步：{topic}" if topic != "核心步骤" else f"读取并准备第 {idx} 阶段所需状态数据"
        why = "承接上一步输入，为后续业务判断或落库准备好中间数据"

    how = f"对应源码第 {node['line']}–{node['end']} 行的逻辑块（类型：{kind}），需要核对具体实现时可点击下方锚点直达代码。"
    return what, why, how


def _summarize_symbol_steps(symbol: dict, max_steps: int = 5) -> list[dict]:
    flow = symbol.get("flow") or []
    while len(flow) == 1 and flow[0].get("children"):
        flow = flow[0]["children"]
    if not flow:
        return [{
            "stepNo": 1,
            "what": f"完成「{_split_words(symbol['name'])}」的核心处理",
            "why": "封装该环节的直接业务逻辑并向调用方返回结果",
            "howPlain": f"位于 {symbol['path']} 第 {symbol['line']}–{symbol['end']} 行，共 {symbol['lines']} 行代码。",
            "moduleId": symbol["module"],
            "anchors": [{"path": symbol["path"], "line": symbol["line"], "end": symbol["end"], "label": symbol["qualified"]}],
        }]
    # Compress large statement lists into up to max_steps readable chunks.
    if len(flow) <= max_steps:
        chunks = [[n] for n in flow]
    else:
        size = max(1, (len(flow) + max_steps - 1) // max_steps)
        chunks = [flow[i:i + size] for i in range(0, len(flow), size)][:max_steps]

    steps = []
    for idx, group in enumerate(chunks, 1):
        primary = next((n for n in group if n.get("kind") in ("if", "loop", "try", "scope", "choice")), group[0])
        what, why, _ = _plain_step_from_node(primary, idx)
        start_line = group[0]["line"]
        end_line = group[-1]["end"]
        how = (
            f"在 {symbol['path'].rsplit('/', 1)[-1]} 的第 {start_line}–{end_line} 行分 {len(group)} 小步完成，"
            f"包含条件判断或状态读写；点击下方源码锚点可逐行查看。"
        )
        steps.append({
            "stepNo": idx,
            "what": what,
            "why": why,
            "howPlain": how,
            "moduleId": symbol["module"],
            "anchors": [{"path": symbol["path"], "line": start_line, "end": end_line, "label": f"第 {start_line}–{end_line} 行实现"}],
        })
    return steps


def detect_repo_profile(repo: Path, revision: str = "HEAD") -> tuple[str, dict]:
    sha = git.resolve_revision(repo, "HEAD" if revision == "WORKTREE" else revision)
    entries = code_graph.tree_entries(repo, sha)
    names = set(entries)
    if revision == "WORKTREE":
        names.update(git.git(repo, "ls-files", "--others", "--exclude-standard", "-z").decode("utf-8", errors="replace").split("\0"))

    profiles_dir = ROOT / "analysis" / "profiles"
    if profiles_dir.is_dir():
        for pf_file in sorted(profiles_dir.glob("*.json")):
            try:
                pf = json.loads(pf_file.read_text(encoding="utf-8-sig"))
                prod_roots = [r["path"].rstrip("/") + "/" for r in pf.get("sourceRoots", []) if not r.get("test")]
                if prod_roots and all(any(n.startswith(prefix) for n in names) for prefix in prod_roots[:2]):
                    return "kotlin", pf
            except (OSError, ValueError, KeyError):
                continue

    kt_files = [n for n in names if n.endswith(".kt")]
    py_files = [n for n in names if n.endswith(".py")]
    if kt_files and len(kt_files) >= len(py_files):
        roots_map = {}
        build_files = sorted(n for n in names if n.endswith("build.gradle.kts"))
        for p in kt_files:
            if "/src/main/kotlin/" in p:
                prefix = p.split("/src/main/kotlin/", 1)[0] + "/src/main/kotlin"
                mod = prefix.split("/src/main/kotlin")[0].rsplit("/", 1)[-1]
                roots_map[(prefix, mod, False)] = True
            elif "/src/test/kotlin/" in p:
                prefix = p.split("/src/test/kotlin/", 1)[0] + "/src/test/kotlin"
                mod = prefix.split("/src/test/kotlin")[0].rsplit("/", 1)[-1]
                roots_map[(prefix, mod, True)] = True
            else:
                top = p.split("/", 1)[0] if "/" in p else ""
                roots_map[(top or ".", top or "app", "test" in p.lower())] = True
        source_roots = [
            {"path": path, "module": mod, "test": is_test}
            for (path, mod, is_test) in sorted(roots_map)
            if path != "."
        ]
        if not source_roots:
            # Flat Kotlin repository fallback: synthesize a single root prefix if inside src/
            first_dir = kt_files[0].split("/", 1)[0] if "/" in kt_files[0] else ""
            source_roots = [{"path": first_dir, "module": first_dir or "app", "test": False}] if first_dir else []
        return "kotlin", {"name": repo.name, "description": "自动识别的 Kotlin 代码仓库", "sourceRoots": source_roots, "buildFiles": build_files}

    return "python", {"name": repo.name, "description": "自动识别的 Python 代码仓库"}


def load_snapshot(repo: Path, revision: str = "HEAD") -> tuple[str, dict, dict]:
    lang, profile = detect_repo_profile(repo, revision)
    if lang == "kotlin" and profile.get("sourceRoots"):
        snap = code_graph.snapshot(repo, revision, profile)
        sources = snap.get("_sources", {})
        # Enrich top orchestrator functions with parsed statement flows so storylines work out-of-the-box!
        prod_funcs = [
            s for f in snap["files"] if not f["test"]
            for s in f["symbols"] if s["kind"] == "function" and not s.get("flow")
        ]
        top_funcs = sorted(prod_funcs, key=lambda s: (len(s["calls"]) * 2 + min(s["branches"], 30)), reverse=True)[:8]
        by_file = defaultdict(set)
        for s in top_funcs:
            by_file[s["path"]].add(s["qualified"])
        for f in snap["files"]:
            if f["path"] in by_file and f["path"] in sources:
                reparsed = code_graph.parse_kotlin(f["path"], sources[f["path"]], f["module"], f["origin"], f["test"], by_file[f["path"]])
                flow_map = {s["id"]: s.get("flow") for s in reparsed["symbols"] if s.get("flow")}
                for s in f["symbols"]:
                    if s["id"] in flow_map:
                        s["flow"] = flow_map[s["id"]]
        code_graph.connect(snap)
        production = [f for f in snap["files"] if not f["test"]]
        snap["metrics"] = {
            "files": len(production),
            "lines": sum(f["lines"] for f in production),
            "functions": sum(s["kind"] == "function" for f in production for s in f["symbols"]),
            "classes": sum(s["kind"] == "class" for f in production for s in f["symbols"]),
            "testFiles": sum(f["test"] for f in snap["files"]),
            "parseErrorFiles": sum(bool(f["errors"]) for f in snap["files"]),
            "coverage": None,
            "testsExecuted": False,
        }
        return "kotlin", profile, snap

    snap = python_graph.snapshot_python(repo, revision)
    return "python", profile, snap


def _plain_table_name(raw: str) -> str:
    zh = _split_words(raw)
    if zh != "核心步骤":
        return f"{zh}表"
    return f"「{raw}」数据记录"


def build_plain_overview(repo_name: str, language: str, profile: dict, snap: dict) -> tuple[dict, set[str], dict]:
    prod_files = [f for f in snap["files"] if not f["test"]]
    valid_paths = {f["path"] for f in snap["files"]}
    by_mod = defaultdict(list)
    for f in prod_files:
        by_mod[f["module"]].append(f)

    roles = []
    for mod_id, m_files in sorted(by_mod.items(), key=lambda kv: -sum(x["lines"] for x in kv[1]))[:8]:
        title, subtitle = _plain_role(mod_id, profile, m_files)
        top_files = sorted(m_files, key=lambda x: -x["lines"])[:3]
        anchors = [{"path": tf["path"], "line": 1, "end": min(tf["lines"], 40), "label": tf["path"].rsplit("/", 1)[-1]} for tf in top_files]
        func_cnt = sum(s["kind"] == "function" for tf in m_files for s in tf["symbols"])
        plain_how = (
            f"该角色由 {len(m_files)} 个源码文件（约 {sum(x['lines'] for x in m_files):,} 行、{func_cnt} 个处理过程）协同实现；"
            f"主要入口集中在 {', '.join(tf['path'].rsplit('/', 1)[-1] for tf in top_files[:2])}。"
        )
        roles.append({
            "id": mod_id,
            "title": title,
            "subtitle": subtitle,
            "plainHow": plain_how,
            "fileCount": len(m_files),
            "lineCount": sum(x["lines"] for x in m_files),
            "anchors": anchors,
        })

    role_ids = {r["id"] for r in roles}
    edge_weights = Counter()
    for be in snap.get("buildEdges", []):
        if be["source"] in role_ids and be["target"] in role_ids and be["source"] != be["target"]:
            edge_weights[(be["source"], be["target"])] += 10
    file_to_mod = {f["path"]: f["module"] for f in prod_files}
    for ie in snap.get("importEdges", []):
        sm, tm = file_to_mod.get(ie["source"]), file_to_mod.get(ie["target"])
        if sm in role_ids and tm in role_ids and sm != tm:
            edge_weights[(sm, tm)] += 1

    role_flows = []
    for (src, dst), _ in edge_weights.most_common(10):
        dst_key = dst.split(".")[-1].lower()
        action, detail = EDGE_ACTIONS.get(dst_key, ("传递业务指令与上下文数据", "上游环节完成准备后，交由下游功能区继续处理"))
        role_flows.append({"from": src, "to": dst, "action": action, "detail": detail})

    # Storylines: combine curated scenario (if any) + top auto-discovered orchestrator flows.
    all_funcs = [s for f in prod_files for s in f["symbols"] if s["kind"] == "function"]
    func_by_name = {s["name"]: s for s in all_funcs} | {s["qualified"]: s for s in all_funcs}
    storylines = []
    used_func_ids = set()

    scenario = profile.get("scenario")
    if scenario and scenario.get("function") in func_by_name:
        target_sym = func_by_name[scenario["function"]]
        used_func_ids.add(target_sym["id"])
        order = scenario.get("afterOrder") or list(range(len(scenario.get("steps", []))))
        flat_nodes = []
        def _collect(items):
            for n in items:
                flat_nodes.append(n)
                _collect(n.get("children") or [])
                for b in n.get("branches") or []:
                    _collect(b.get("items") or [])
        _collect(target_sym.get("flow") or [])

        sc_steps = []
        for idx, step_idx in enumerate(order, 1):
            raw_step = scenario["steps"][step_idx]
            matched = [n for n in flat_nodes if any(k in (n.get("code") or "") for k in raw_step.get("contains", []))]
            line = min((n["line"] for n in matched), default=target_sym["line"])
            end = max((n["end"] for n in matched), default=min(target_sym["end"], line + 15))
            step_why = _plain_step_from_node(matched[0], idx)[1] if matched else "对齐本阶段状态后交由下一步继续执行"
            sc_steps.append({
                "stepNo": idx,
                "what": raw_step["label"],
                "why": step_why,
                "howPlain": f"在 {target_sym['path'].rsplit('/', 1)[-1]} 第 {line}–{end} 行完成这一步的数据读取与状态同步。",
                "moduleId": target_sym["module"],
                "anchors": [{"path": target_sym["path"], "line": line, "end": end, "label": raw_step["label"]}],
            })
        if sc_steps:
            storylines.append({
                "id": "story-curated",
                "title": scenario["title"],
                "when": "用户选定目标账号、准备启动自动化流程之前触发",
                "outcome": "账号档案、本机凭据与运行策略同步就绪",
                "steps": sc_steps,
            })

    ranked_funcs = sorted(
        [s for s in all_funcs if s["id"] not in used_func_ids and s["lines"] >= 6],
        key=lambda s: (bool(s.get("flow")) * 20 + min(len(s["calls"]), 20) * 2 + min(s["branches"], 20)),
        reverse=True,
    )
    seen_topics = set()
    for sym in ranked_funcs:
        if len(storylines) >= 4:
            break
        topic = _split_words(sym["qualified"])
        if topic in seen_topics and len(ranked_funcs) > 4:
            continue
        seen_topics.add(topic)
        used_func_ids.add(sym["id"])
        role_title = next((r["title"] for r in roles if r["id"] == sym["module"]), sym["module"])
        storylines.append({
            "id": f"story-{len(storylines) + 1}",
            "title": f"{topic}主流程" if topic != "核心步骤" else f"{role_title}核心执行流",
            "when": f"当程序进入「{role_title}」执行关键业务处理时触发",
            "outcome": "完成状态判读、数据读写或向下游发出操作指令",
            "steps": _summarize_symbol_steps(sym),
        })

    # Data cards
    entities = [e for f in prod_files for e in f.get("entities", [])]
    data_cards = []
    for ent in entities[:12]:
        rels = [f"关联到「{_plain_table_name(fk['target'])}」" for fk in ent.get("foreignKeys", [])]
        data_cards.append({
            "id": ent["id"],
            "plainName": _plain_table_name(ent["table"]),
            "rawName": ent["table"],
            "purpose": f"保存与 {_plain_table_name(ent['table']).replace('表', '')} 相关的 {len(ent.get('fields', []))} 项核心数据字段",
            "fieldCount": len(ent.get("fields", [])),
            "relations": rels,
            "anchors": [{"path": ent["path"], "line": ent["line"], "end": ent["end"], "label": ent["table"]}],
        })

    # Maintenance hotspots (Tech Debt Radar)
    caller_counts = Counter()
    for s in all_funcs:
        for c in s["calls"]:
            for tid in c.get("targets", []):
                caller_counts[tid] += 1

    hotspots = []
    risky_funcs = sorted(all_funcs, key=lambda s: s["branches"] * 4 + s["lines"], reverse=True)
    for sym in risky_funcs[:4]:
        if sym["lines"] < 25 and sym["branches"] < 5 and len(all_funcs) > 5:
            continue
        topic = _split_words(sym["qualified"])
        fan_in = caller_counts.get(sym["id"], 0)
        severity = "high" if (sym["lines"] >= 250 or sym["branches"] >= 35) else "medium"
        hotspots.append({
            "id": f"hotspot-{len(hotspots) + 1}",
            "title": f"「{topic}」处理逻辑较为集中，改动时需格外留意回归影响",
            "whyHard": (
                f"这一处连续写了 {sym['lines']} 行代码、包含 {sym['branches']} 个条件/循环分支"
                + (f"，且被仓库内 {fan_in} 处流程调用。" if fan_in else "，多种分支情况交织在一起。")
            ),
            "splitIdea": "建议将“状态判断”与“具体执行动作”拆成独立小步骤，每次修改前先对照右侧依赖列表核对上下游。",
            "severity": severity,
            "metrics": f"{sym['lines']} 行 · {sym['branches']} 个分支" + (f" · {fan_in} 处被调" if fan_in else ""),
            "moduleId": sym["module"],
            "anchors": [{"path": sym["path"], "line": sym["line"], "end": sym["end"], "label": sym["qualified"]}],
        })

    role_names = "、".join(f"「{r['title']}」" for r in roles[:4])
    if {"device", "ocr"} <= {r["id"] for r in roles}:
        headline = f"{repo_name} 是一个连接外部设备抓图、通过画面识别自动判断状态并执行操作的桌面总控系统。"
        narrative = (
            f"程序运行时由 {role_names} 分工配合：先准备好账号与本地配置账本，"
            "随后循环抓取设备画面交给识别模块看懂当前页面，再由核心业务规则决定下一步点击动作并记录进度。"
        )
    else:
        headline = f"{repo_name} 由 {len(roles)} 个分工明确的功能角色协同运转，围绕核心数据流完成接收输入、规则处理与结果保存。"
        narrative = (
            f"整体由 {role_names} 串联配合：上游入口接收请求并校验条件，"
            "中间核心层完成业务判断与状态加工，最后交由底层存储或外部协作模块落盘返回。"
        )

    overview = {
        "repoName": repo_name,
        "revision": snap["revision"],
        "commit": snap["commit"],
        "language": language,
        "sourceMode": "heuristic",
        "modelName": "",
        "headline": headline,
        "narrative": narrative,
        "roles": roles,
        "roleFlows": role_flows,
        "storylines": storylines,
        "dataCards": data_cards,
        "hotspots": hotspots,
        "stats": snap["metrics"],
    }

    llm_pack = {
        "repoName": repo_name,
        "language": language,
        "description": profile.get("description", ""),
        "stats": snap["metrics"],
        "modules": [
            {"id": r["id"], "defaultTitle": r["title"], "files": r["fileCount"], "lines": r["lineCount"], "anchors": r["anchors"]}
            for r in roles
        ],
        "moduleEdges": role_flows,
        "candidateFlows": [
            {"title": st["title"], "steps": [{"what": sp["what"], "anchors": sp["anchors"]} for sp in st["steps"]]}
            for st in storylines
        ],
        "dataTables": [{"table": d["rawName"], "fields": d["fieldCount"], "relations": d["relations"]} for d in data_cards[:8]],
        "hotspots": [{"metrics": h["metrics"], "anchors": h["anchors"]} for h in hotspots],
    }
    return overview, valid_paths, llm_pack


def _unified_hunk(old_text: str, new_text: str, path: str, max_lines: int = 80) -> str:
    diff_lines = list(difflib.unified_diff(
        old_text.splitlines(), new_text.splitlines(),
        fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="", n=2,
    ))
    if len(diff_lines) > max_lines:
        return "\n".join(diff_lines[:max_lines]) + f"\n... 其余 {len(diff_lines) - max_lines} 行差异已折叠，可点击源码锚点查看全文 ..."
    return "\n".join(diff_lines)


def analyze_change(repo: Path, repo_name: str, base_ref: str, head_ref: str,
                   user_prompt: str = "", llm_cfg: dict | None = None, use_llm: bool = False) -> dict:
    lang, profile = detect_repo_profile(repo, head_ref)
    if lang == "kotlin" and profile.get("sourceRoots"):
        raw = code_graph.analyze(repo, profile, base_ref, head_ref)
        before_snap, after_snap = raw["before"], raw["after"]
        old_sources, new_sources = raw["sources"]["before"], raw["sources"]["after"]
        changes = raw["changes"]
    else:
        before_snap = python_graph.snapshot_python(repo, base_ref)
        after_snap = python_graph.snapshot_python(repo, head_ref)
        old_sources = before_snap.pop("_sources")
        new_sources = after_snap.pop("_sources")
        changes = []
        for p in sorted(set(old_sources) | set(new_sources)):
            old_t, new_t = old_sources.get(p, ""), new_sources.get(p, "")
            if old_t.splitlines() == new_t.splitlines():
                continue
            a, b = code_graph.line_changes(old_t, new_t)
            changes.append({
                "path": p,
                "status": "added" if p not in old_sources else "deleted" if p not in new_sources else "modified",
                "before": a, "after": b,
                "additions": sum(j - i + 1 for i, j in b),
                "deletions": sum(j - i + 1 for i, j in a),
            })
        changed_map = {c["path"]: c for c in changes}
        old_syms = {s["id"]: s for f in before_snap["files"] for s in f["symbols"]}
        new_syms = {s["id"]: s for f in after_snap["files"] for s in f["symbols"]}
        for snap, other_syms, side in ((before_snap, new_syms, "before"), (after_snap, old_syms, "after")):
            for f in snap["files"]:
                f["status"] = changed_map.get(f["path"], {}).get("status", "unchanged")
                for s in f["symbols"]:
                    other = other_syms.get(s["id"])
                    s["status"] = ("deleted" if side == "before" else "added") if other is None else (
                        "modified" if other["fingerprint"] != s["fingerprint"] else "unchanged"
                    )

    old_syms = {s["id"]: s for f in before_snap["files"] for s in f["symbols"] if s["kind"] == "function"}
    new_syms = {s["id"]: s for f in after_snap["files"] for s in f["symbols"] if s["kind"] == "function"}
    # Match renamed/signature-tweaked functions in same file by qualified name fallback.
    old_by_qual = {(s["path"], s["qualified"]): s for s in old_syms.values()}
    changed_pairs = []
    seen_old = set()
    for sid, after_s in new_syms.items():
        if after_s["status"] == "unchanged":
            continue
        before_s = old_syms.get(sid) or old_by_qual.get((after_s["path"], after_s["qualified"]))
        if before_s:
            seen_old.add(before_s["id"])
        changed_pairs.append((before_s, after_s, "modified" if before_s else "added"))
    for sid, before_s in old_syms.items():
        if before_s["status"] == "deleted" and sid not in seen_old:
            changed_pairs.append((before_s, None, "deleted"))

    # Plain-language Before vs After flow comparisons!
    change_by_path = {c["path"]: c for c in changes}
    flow_comparisons = []
    for before_s, after_s, status in changed_pairs[:10]:
        ref = after_s or before_s
        if ref.get("test"):
            continue
        topic = _split_words(ref["qualified"])
        b_steps = _summarize_symbol_steps(before_s, 6) if before_s else []
        a_steps = _summarize_symbol_steps(after_s, 6) if after_s else []
        file_diff = change_by_path.get(ref["path"], {})
        for st in b_steps:
            anc = st["anchors"][0]
            hit = any(x <= anc["end"] and y >= anc["line"] for x, y in file_diff.get("before", []))
            st["changeTag"] = "deleted" if status == "deleted" else ("modified" if hit else "unchanged")
        for st in a_steps:
            anc = st["anchors"][0]
            hit = any(x <= anc["end"] and y >= anc["line"] for x, y in file_diff.get("after", []))
            st["changeTag"] = "added" if status == "added" else ("modified" if hit else "unchanged")

        flow_comparisons.append({
            "id": ref["id"],
            "plainTitle": f"「{topic}」执行流程" if topic != "核心步骤" else f"「{ref['name']}」处理流程",
            "symbolName": ref["qualified"],
            "moduleId": ref["module"],
            "status": status,
            "path": ref["path"],
            "beforeSteps": b_steps,
            "afterSteps": a_steps,
        })

    # Reverse BFS Impact Radius (up to depth 3, cycle-safe)
    reverse_calls = defaultdict(set)
    sym_lookup = {**old_syms, **new_syms}
    for snap in (after_snap, before_snap):
        for f in snap["files"]:
            for s in f["symbols"]:
                if s["kind"] != "function":
                    continue
                for c in s["calls"]:
                    for tid in c.get("targets", []):
                        if tid != s["id"]:
                            reverse_calls[tid].add(s["id"])

    changed_ids = {(after_s or before_s)["id"] for before_s, after_s, _ in changed_pairs}
    if before_s_ids := {before_s["id"] for before_s, _, _ in changed_pairs if before_s}:
        changed_ids |= before_s_ids

    visited = set(changed_ids)
    queue = deque((cid, 0, [sym_lookup[cid]["qualified"]]) for cid in changed_ids if cid in sym_lookup)
    impacts = []
    while queue and len(impacts) < 25:
        curr, depth, chain = queue.popleft()
        if depth >= 3:
            continue
        for caller_id in sorted(reverse_calls.get(curr, ())):
            caller = sym_lookup.get(caller_id)
            if not caller:
                continue
            next_chain = [*chain, caller["qualified"]]
            if caller_id not in visited:
                visited.add(caller_id)
                queue.append((caller_id, depth + 1, next_chain))
                if not caller.get("test"):
                    topic = _split_words(caller["qualified"])
                    impacts.append({
                        "id": caller_id,
                        "plainName": f"「{topic}」环节" if topic != "核心步骤" else caller["qualified"],
                        "symbolName": caller["qualified"],
                        "moduleId": caller["module"],
                        "distance": depth + 1,
                        "alsoChanged": caller_id in changed_ids,
                        "chain": " → ".join(next_chain),
                        "reason": (
                            f"{'直接' if depth == 0 else f'经 {depth + 1} 层间接'}调用了本次被修改的逻辑，需确认入参假设与返回值处理仍然兼容。"
                        ),
                        "anchor": {"path": caller["path"], "line": caller["line"], "end": caller["end"], "label": caller["qualified"]},
                    })

    # Discover related existing test files/functions
    related_tests = []
    for f in after_snap["files"]:
        if not f["test"]:
            continue
        for s in f["symbols"]:
            if s["kind"] == "function" and (
                s.get("status") != "unchanged"
                or any(t in changed_ids for c in s["calls"] for t in c.get("targets", []))
            ):
                related_tests.append(f"{f['path']} :: {s['name']}（{'本次同步修改' if s.get('status') != 'unchanged' else '调用了变更逻辑'}）")

    file_changes = []
    for c in changes[:40]:
        p = c["path"]
        file_changes.append({
            **c,
            "diff": _unified_hunk(old_sources.get(p, ""), new_sources.get(p, ""), p),
        })

    touched_mods = sorted({(after_s or before_s)["module"] for before_s, after_s, _ in changed_pairs if not (after_s or before_s).get("test")})
    if not changes:
        plain_summary = {
            "mode": "heuristic",
            "model": "",
            "headline": "所选两个版本之间没有检测到源码变化。",
            "beforeVsAfter": "两侧快照中的受管源码行一致，程序运行流程未发生改变。",
            "riskPoints": [],
            "testSuggestions": ["无需额外回归测试。"],
        }
    else:
        mod_titles = "、".join(_plain_role(m, profile, [])[0] for m in touched_mods[:3]) or "测试与配置文件"
        plain_summary = {
            "mode": "heuristic",
            "model": "",
            "headline": f"本次变更涉及 {len(changes)} 个文件，主要调整了 {mod_titles} 中的 {len(flow_comparisons)} 处程序执行流程。",
            "beforeVsAfter": (
                "已将底层代码行差异映射为下方的「修改前 vs 修改后」步骤卡片：红色代表旧版中被调整或移除的原步骤，琥珀色/绿色代表新版修改或新增步骤。"
                + (f" 同时发现仓库内有 {len(impacts)} 处上下游环节调用了被改逻辑。" if impacts else "")
            ),
            "riskPoints": [
                {
                    "title": f"核对 {fc['plainTitle']} 的分支与状态一致性",
                    "detail": f"位于 {fc['path'].rsplit('/', 1)[-1]} 的核心步骤发生{ {'added': '新增', 'deleted': '删除', 'modified': '修改'}[fc['status']] }，建议重点确认中途异常或提前返回时的状态收尾。",
                    "anchors": [{"path": fc["path"], "line": (fc["afterSteps"] or fc["beforeSteps"])[0]["anchors"][0]["line"], "end": (fc["afterSteps"] or fc["beforeSteps"])[-1]["anchors"][0]["end"], "label": fc["symbolName"]}],
                }
                for fc in flow_comparisons[:3]
            ],
            "testSuggestions": related_tests[:4] or ["建议针对下方列出的变更流程与直接受牵连的上游环节做一次冒烟验证。"],
        }

    llm_status = "not_requested"
    valid_paths = set(old_sources) | set(new_sources)
    if use_llm and changes:
        if not llm_cfg or not llm_cfg.get("api_key"):
            llm_status = "not_configured"
        else:
            change_pack = {
                "repoName": repo_name,
                "userPrompt": user_prompt,
                "changedFiles": [{"path": c["path"], "status": c["status"], "additions": c["additions"], "deletions": c["deletions"], "diff": c["diff"][:1500]} for c in file_changes[:8]],
                "changedFlows": [{"title": fc["plainTitle"], "symbol": fc["symbolName"], "path": fc["path"], "status": fc["status"]} for fc in flow_comparisons[:6]],
                "impactedCallers": [{"symbol": im["symbolName"], "chain": im["chain"], "anchor": im["anchor"]} for im in impacts[:8]],
                "existingTests": related_tests[:6],
            }
            try:
                plain_summary = llm_service.explain_change_with_llm(llm_cfg, change_pack, valid_paths)
                llm_status = "generated"
            except llm_service.LLMError as exc:
                plain_summary["llmError"] = str(exc)
                llm_status = "failed"

    parse_gaps = after_snap["metrics"].get("parseErrorFiles", 0)
    task_status = "partial" if (parse_gaps > 0 or llm_status == "failed") else "completed"
    return {
        "baseSha": before_snap["commit"],
        "headSha": "WORKTREE" if head_ref == "WORKTREE" else after_snap["commit"],
        "headCommit": after_snap["commit"],
        "language": lang,
        "status": task_status,
        "llmStatus": llm_status,
        "plainSummary": plain_summary,
        "flowComparisons": flow_comparisons,
        "impactRadius": impacts,
        "fileChanges": file_changes,
        "diagnostics": {
            "changedFileCount": len(changes),
            "changedFlowCount": len(flow_comparisons),
            "impactCount": len(impacts),
            "parseErrorFiles": parse_gaps,
        },
    }


def ask_repository(repo: Path, repo_name: str, question: str, revision: str = "HEAD",
                   target_path: str = "", target_line: int = 0, target_label: str = "",
                   notes: list[dict] | None = None, llm_cfg: dict | None = None) -> dict:
    lang, profile, snap = load_snapshot(repo, revision)
    sources = snap.get("_sources", {})
    valid_paths = {f["path"] for f in snap["files"]}
    all_syms = [s for f in snap["files"] if not f["test"] for s in f["symbols"]]

    matched_syms = []
    if target_path and target_path in valid_paths:
        for s in all_syms:
            if s["path"] == target_path and (not target_line or (s["line"] <= target_line <= s["end"])):
                matched_syms.append(s)
        matched_syms.sort(key=lambda s: (s["kind"] != "function", s["lines"]))
    q_tokens = [tok.lower() for tok in re.findall(r"[A-Za-z_]{3,}|[\u4e00-\u9fff]{2,}", question + " " + target_label)]
    if not matched_syms:
        scored = []
        for s in all_syms:
            hay = f"{s['qualified']} {s['path']} {_split_words(s['qualified'])}".lower()
            score = sum(2 if tok in hay else 0 for tok in q_tokens)
            if score > 0:
                scored.append((score, s))
        scored.sort(key=lambda x: (-x[0], -x[1]["lines"]))
        matched_syms = [s for _, s in scored[:4]]
    if not matched_syms and all_syms:
        matched_syms = sorted(all_syms, key=lambda s: -len(s["calls"]))[:3]

    snippets = []
    anchors = []
    if target_path and target_path in sources:
        lines = sources[target_path].splitlines()
        start = max(1, (target_line or 1) - 5)
        end = min(len(lines), start + 45)
        snippets.append({"path": target_path, "line": start, "end": end, "code": "\n".join(lines[start - 1:end])})
        anchors.append({"path": target_path, "line": target_line or 1, "end": end, "label": target_label or target_path.rsplit("/", 1)[-1]})

    for s in matched_syms[:3]:
        lines = sources.get(s["path"], "").splitlines()
        end = min(s["end"], s["line"] + 35)
        snippets.append({"path": s["path"], "symbol": s["qualified"], "line": s["line"], "end": end, "code": "\n".join(lines[s["line"] - 1:end])})
        anchors.append({"path": s["path"], "line": s["line"], "end": s["end"], "label": s["qualified"]})

    # Find callers of primary matched symbol
    caller_names = []
    if matched_syms:
        primary_id = matched_syms[0]["id"]
        for s in all_syms:
            if any(primary_id in c.get("targets", []) for c in s.get("calls", [])):
                caller_names.append(f"{_split_words(s['qualified'])}（{s['qualified']}）")

    note_items = [
        {"title": n["title"], "content": n["content"], "target": n["target_label"]}
        for n in (notes or [])[:6]
    ]

    if llm_cfg and llm_cfg.get("api_key"):
        pack = {
            "repoName": repo_name,
            "language": lang,
            "question": question,
            "focusTarget": {"path": target_path, "line": target_line, "label": target_label},
            "snippets": snippets[:4],
            "upstreamCallers": caller_names[:8],
            "maintenanceNotes": note_items,
        }
        try:
            return llm_service.answer_question_with_llm(llm_cfg, pack, valid_paths)
        except llm_service.LLMError as exc:
            fallback_err = str(exc)
    else:
        fallback_err = ""

    # Rich local static context answer when API key is not configured yet (or if LLM call fails)
    focus_desc = f"围绕「{target_label or target_path or repo_name}」"
    key_points = []
    if matched_syms:
        top = matched_syms[0]
        role_title, _ = _plain_role(top["module"], profile, [])
        steps_preview = " → ".join(st["what"] for st in _summarize_symbol_steps(top, 4))
        answer = (
            f"{focus_desc}的本地静态图谱线索已定位：核心处理位于「{role_title}」模块（{top['path']}），"
            f"主要执行步骤为：{steps_preview}。"
        )
        if caller_names:
            key_points.append(f"上游调用它的环节：{', '.join(caller_names[:4])}")
        callees = list(dict.fromkeys(c["name"] for c in top.get("calls", [])[:6]))
        if callees:
            key_points.append(f"它向下游调用的动作：{', '.join(callees)}")
    else:
        answer = f"已在仓库 {repo_name}（共 {snap['metrics']['files']} 个生产源码文件）中完成静态检索。"

    if note_items:
        key_points.append(f"关联的维护便签提醒：{note_items[0]['title']} —— {note_items[0]['content'][:80]}")
    if fallback_err:
        key_points.append(f"AI 深度生成暂未成功（{fallback_err}），以上为静态代码证据速览。")
    else:
        key_points.append("提示：当前尚未填入 API Key，展示的是本地静态结构速览；在右上角「AI 模型设置」填入密钥后即可获得针对任意问题的自由白话解答。")

    return {
        "mode": "heuristic",
        "model": "",
        "answer": answer,
        "keyPoints": key_points,
        "anchors": llm_service.sanitize_anchors(anchors, valid_paths),
    }
