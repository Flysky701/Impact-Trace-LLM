import difflib
import os
import re
import subprocess
from pathlib import Path

MAX_SOURCE_BYTES = 1024 * 1024


class RepositoryError(ValueError):
    pass


def git(path, *args, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    try:
        result = subprocess.run(
            ["git", "--no-pager", "-c", "core.fsmonitor=false", "-c", "core.quotepath=false", "-C", str(path), *args],
            capture_output=True, timeout=15, env=env, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepositoryError("Git 不可用或读取超时，请检查本机环境。") from exc
    if check and result.returncode:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RepositoryError(stderr.splitlines()[0][:180] if stderr else "无法读取仓库或指定版本，请检查路径、访问权限和提交引用。")
    return result.stdout if check else result


def _validate_relpath(filename: str) -> str:
    clean = (filename or "").strip().replace("\\", "/")
    if not clean or len(clean) > 500 or "\0" in clean or clean.startswith(("/", "-")):
        raise RepositoryError("文件路径无效。")
    parts = clean.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise RepositoryError("文件路径无效。")
    return clean


def repository_path(value, roots):
    path = Path(value).expanduser().resolve()
    if not any(path.is_relative_to(root.resolve()) for root in roots):
        raise RepositoryError("仓库路径不在允许的目录内，请放入 data/local 或配置允许目录。")
    if not path.is_dir():
        raise RepositoryError("仓库目录不存在。")
    top = Path(git(path, "rev-parse", "--show-toplevel").decode("utf-8", errors="replace").strip()).resolve()
    if top != path:
        raise RepositoryError("请填写 Git 仓库根目录。")
    resolve_revision(path, "HEAD")
    return path


def resolve_revision(path, revision):
    if not re.fullmatch(r"[A-Za-z0-9_./~^@{}-]{1,200}", revision) or revision.startswith("-"):
        raise RepositoryError("提交引用格式无效。")
    return git(path, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}").decode().strip()


def refs(path):
    head_sha = resolve_revision(path, "HEAD")
    sym = git(path, "symbolic-ref", "--short", "-q", "HEAD", check=False)
    current_branch = sym.stdout.decode("utf-8", errors="replace").strip() if sym.returncode == 0 else ""

    branch_raw = git(
        path, "for-each-ref", "--sort=-committerdate",
        "--format=%(refname:short)%00%(objectname)%00%(committerdate:short)%00%(subject)",
        "refs/heads",
    ).decode("utf-8", errors="replace")
    branches = []
    for row in branch_raw.splitlines():
        if not row.strip():
            continue
        name, sha, date, subject = (row.split("\0") + ["", "", "", ""])[:4]
        branches.append({
            "name": name, "sha": sha, "short_sha": sha[:7],
            "date": date, "subject": subject, "current": name == current_branch,
        })

    tag_raw = git(
        path, "for-each-ref", "--sort=-creatordate",
        "--format=%(refname:short)%00%(objectname:short)%00%(creatordate:short)",
        "refs/tags",
    ).decode("utf-8", errors="replace")
    tags = []
    for row in tag_raw.splitlines()[:50]:
        if not row.strip():
            continue
        name, short_sha, date = (row.split("\0") + ["", "", ""])[:3]
        tags.append({"name": name, "short_sha": short_sha, "date": date})

    return {
        "current_branch": current_branch,
        "head_sha": head_sha,
        "branches": branches,
        "tags": tags,
    }


def history(path, revision="HEAD", offset=0, limit=20):
    sha = resolve_revision(path, revision)
    raw = git(
        path, "log", "--format=%H%x00%h%x00%an%x00%cs%x00%s",
        f"--skip={offset}", f"--max-count={limit}", sha, "--",
    ).decode("utf-8", errors="replace")
    commits = []
    for row in raw.splitlines():
        full, short, author, date, subject = row.split("\0", 4)
        commits.append({
            "sha": full, "short_sha": short, "author": author,
            "date": date, "subject": subject,
        })
    return {"revision": sha, "total": int(git(path, "rev-list", "--count", sha)), "commits": commits}


def commit_detail(path, revision: str):
    sha = resolve_revision(path, revision)
    meta = git(
        path, "show", "-s", "--format=%H%x00%h%x00%an%x00%ae%x00%ci%x00%P%x00%s%x00%b", sha,
    ).decode("utf-8", errors="replace")
    full, short, author, email, date, parents_str, subject, body = (meta.split("\0", 7) + [""] * 8)[:8]
    parents = [p for p in parents_str.split() if p]

    numstat_raw = git(
        path, "diff-tree", "--root", "--no-commit-id", "--numstat", "-r", "-M", sha,
    ).decode("utf-8", errors="replace")
    status_raw = git(
        path, "diff-tree", "--root", "--no-commit-id", "--name-status", "-r", "-M", sha,
    ).decode("utf-8", errors="replace")

    status_map = {}
    for line in status_raw.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            code = parts[0][0]
            file_path = parts[-1]
            status_map[file_path] = {"A": "added", "D": "deleted", "R": "renamed"}.get(code, "modified")

    patch_raw = git(
        path, "show", "--format=", "--unified=3", "-M", sha,
    ).decode("utf-8", errors="replace")
    patches_by_file = _split_git_patches(patch_raw)

    files = []
    for line in numstat_raw.splitlines()[:80]:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_s, del_s, fpath = parts[0], parts[1], parts[-1]
        # Handle rename notation like dir/{old => new}
        clean_path = re.sub(r"\{[^}]* => ([^}]*)\}", r"\1", fpath)
        if " => " in clean_path:
            clean_path = clean_path.split(" => ")[-1]
        additions = int(add_s) if add_s.isdigit() else 0
        deletions = int(del_s) if del_s.isdigit() else 0
        files.append({
            "path": clean_path,
            "status": status_map.get(clean_path, "modified"),
            "additions": additions,
            "deletions": deletions,
            "diff": patches_by_file.get(clean_path, "")[:12000],
        })

    return {
        "sha": full,
        "short_sha": short,
        "author": author,
        "email": email,
        "date": date[:19],
        "parents": parents,
        "subject": subject.strip(),
        "body": body.strip(),
        "files": files,
        "stats": {
            "files": len(files),
            "additions": sum(f["additions"] for f in files),
            "deletions": sum(f["deletions"] for f in files),
        },
    }


def _split_git_patches(patch_text: str) -> dict[str, str]:
    result = {}
    chunks = re.split(r"(?=^diff --git )", patch_text, flags=re.M)
    for chunk in chunks:
        if not chunk.startswith("diff --git "):
            continue
        header = chunk.splitlines()[0]
        match = re.search(r" b/(.+)$", header)
        if match:
            result[match.group(1)] = chunk.strip()
    return result


def worktree_status(path):
    info = refs(path)
    raw = git(path, "status", "--porcelain=v1", "-z", "-uall")
    tokens = raw.split(b"\0")
    staged, unstaged, untracked = [], [], []
    i = 0
    while i < len(tokens):
        entry = tokens[i]
        i += 1
        if not entry or len(entry) < 4:
            continue
        xy = entry[:2].decode("ascii", errors="replace")
        filepath = entry[3:].decode("utf-8", errors="replace")
        if xy[0] in ("R", "C") and i < len(tokens):
            i += 1  # Skip original path entry in porcelain -z rename format
        x, y = xy[0], xy[1]
        if xy == "??":
            untracked.append({"path": filepath, "status": "untracked"})
        else:
            if x not in (" ", "?"):
                staged.append({"path": filepath, "status": _status_word(x)})
            if y not in (" ", "?"):
                unstaged.append({"path": filepath, "status": _status_word(y)})

    return {
        "branch": info["current_branch"] or f"DETACHED@{info['head_sha'][:7]}",
        "head_sha": info["head_sha"],
        "clean": not (staged or unstaged or untracked),
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
    }


def _status_word(code: str) -> str:
    return {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}.get(code, "modified")


def worktree_diff(path, filename: str, staged: bool = False) -> dict:
    clean = _validate_relpath(filename)
    root = Path(path).resolve()
    if staged:
        out = git(path, "diff", "--cached", "--unified=3", "--", clean).decode("utf-8", errors="replace")
        return {"path": clean, "staged": True, "diff": out[:20000]}

    out = git(path, "diff", "--unified=3", "--", clean).decode("utf-8", errors="replace")
    if out.strip():
        return {"path": clean, "staged": False, "diff": out[:20000]}

    # Untracked file preview as unified addition diff
    target = root / clean
    if target.is_file() and not target.is_symlink() and target.resolve().is_relative_to(root):
        if target.stat().st_size > MAX_SOURCE_BYTES:
            return {"path": clean, "staged": False, "diff": "文件超过 1 MiB，暂不预览。"}
        raw = target.read_bytes()
        if b"\0" in raw:
            return {"path": clean, "staged": False, "diff": "二进制文件，暂不预览。"}
        text = raw.decode("utf-8-sig", errors="replace")
        diff_lines = list(difflib.unified_diff(
            [], text.splitlines(), fromfile="/dev/null", tofile=f"b/{clean}", lineterm="",
        ))
        return {"path": clean, "staged": False, "diff": "\n".join(diff_lines[:300])}
    return {"path": clean, "staged": False, "diff": ""}


def stage_files(path, files: list[str] | None = None, all_changes: bool = False):
    if all_changes:
        git(path, "add", "-A")
        return worktree_status(path)
    if not files:
        raise RepositoryError("请选择要暂存的文件。")
    cleaned = [_validate_relpath(f) for f in files[:200]]
    git(path, "add", "--", *cleaned)
    return worktree_status(path)


def unstage_files(path, files: list[str] | None = None, all_changes: bool = False):
    if all_changes:
        git(path, "reset", "-q", "HEAD")
        return worktree_status(path)
    if not files:
        raise RepositoryError("请选择要取消暂存的文件。")
    cleaned = [_validate_relpath(f) for f in files[:200]]
    git(path, "reset", "-q", "HEAD", "--", *cleaned)
    return worktree_status(path)


def create_commit(path, message: str):
    msg = (message or "").strip()
    if not msg:
        raise RepositoryError("请填写提交说明（Commit Message）。")
    has_staged = git(path, "diff", "--cached", "--quiet", check=False)
    if has_staged.returncode == 0:
        raise RepositoryError("暂存区为空，请先暂存（Stage）要提交的文件。")
    git(path, "commit", "-m", msg)
    return commit_detail(path, "HEAD")


def tree(path, revision, limit: int = 1000):
    if revision == "WORKTREE":
        resolve_revision(path, "HEAD")
        raw = git(path, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
        root = Path(path).resolve()
        files = []
        for item in sorted(set(raw.decode("utf-8", errors="replace").split("\0"))):
            if not item:
                continue
            target = root / item
            if target.is_file() and not target.is_symlink() and target.resolve().is_relative_to(root):
                files.append({"path": item, "oid": "WORKTREE"})
        return {"revision": "WORKTREE", "files": files[:limit], "truncated": len(files) > limit}
    sha = resolve_revision(path, revision)
    raw = git(path, "ls-tree", "-r", "-z", sha)
    files = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        meta, name = item.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        if kind == "blob" and mode in ("100644", "100755"):
            files.append({"path": name.decode("utf-8", errors="replace"), "oid": oid})
    return {"revision": sha, "files": files[:limit], "truncated": len(files) > limit}


def source(path, revision, filename):
    if not filename or len(filename) > 500 or any(c in filename for c in ("\0", "\\")):
        raise RepositoryError("文件路径无效。")
    if revision == "WORKTREE":
        resolve_revision(path, "HEAD")
        root = Path(path).resolve()
        target = root / filename
        if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(root):
            raise RepositoryError("工作区中没有可读取的普通文件。")
        if target.stat().st_size > MAX_SOURCE_BYTES:
            raise RepositoryError("文件超过 1 MiB，暂不显示。")
        raw = target.read_bytes()
        if b"\0" in raw:
            raise RepositoryError("该文件是二进制文件，暂不显示。")
        return {"revision": "WORKTREE", "path": filename, "content": raw.decode("utf-8-sig", errors="replace")}
    sha = resolve_revision(path, revision)
    listing = git(path, "ls-tree", "-r", "-z", sha)
    oid = None
    for item in listing.split(b"\0"):
        if not item:
            continue
        meta, name = item.split(b"\t", 1)
        mode, kind, object_id = meta.decode().split()
        if name.decode("utf-8", errors="replace") == filename and mode in ("100644", "100755"):
            oid = object_id if kind == "blob" else None
            break
    if not oid:
        raise RepositoryError("该版本中没有可读取的普通文件。")
    if int(git(path, "cat-file", "-s", oid)) > MAX_SOURCE_BYTES:
        raise RepositoryError("文件超过 1 MiB，暂不显示。")
    raw = git(path, "cat-file", "blob", oid)
    if b"\0" in raw:
        raise RepositoryError("该文件是二进制文件，暂不显示。")
    return {"revision": sha, "path": filename, "content": raw.decode("utf-8", errors="replace")}
