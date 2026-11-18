"""Generate the offline Demo from a Git snapshot pair, without executing input code."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.code_graph import analyze  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--profile", type=Path, default=ROOT / "analysis/profiles/limingjie.json")
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--head", default="WORKTREE")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/generated/limingjie-demo")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == args.repository.resolve() or output.is_relative_to(args.repository.resolve()):
        parser.error("输出目录必须位于被分析仓库之外。")
    profile = json.loads(args.profile.read_text(encoding="utf-8-sig"))
    result = analyze(args.repository, profile, args.base, args.head)
    output.mkdir(parents=True, exist_ok=True)
    (output / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for name in ("index.html", "explorer.css", "explorer.js"):
        source = ROOT / "frontend/demo" / name
        if source.exists():
            shutil.copyfile(source, output / name)
    print(json.dumps({"output": str(output), "base": result["before"]["commit"],
                      "head": result["after"]["revision"], "metrics": result["after"]["metrics"],
                      "changedFiles": len(result["changes"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
