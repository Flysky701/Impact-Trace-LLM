import subprocess
from unittest.mock import patch

import pytest

from app.git_service import RepositoryError, git, history, repository_path, resolve_revision, source, tree


def test_git_reads_versions_without_changing_worktree(repository, tmp_path):
    repo, base, head = repository
    before = (repo / "sample.py").read_text()
    assert repository_path(repo, (tmp_path,)) == repo
    assert resolve_revision(repo, "HEAD~1") == base
    assert history(repo, base)["total"] == 1
    assert tree(repo, head)["truncated"] is False
    assert source(repo, base, "中文.py")["content"] == "message = '你好'\n"
    assert (repo / "sample.py").read_text() == before


@pytest.mark.parametrize("revision", ["--help", "HEAD:sample.py", "HEAD;whoami", "", "a" * 201])
def test_bad_revision_rejected(repository, revision):
    with pytest.raises(RepositoryError):
        resolve_revision(repository[0], revision)


def test_path_and_git_failures(repository, tmp_path):
    repo = repository[0]
    sub = repo / "sub"
    sub.mkdir()
    with pytest.raises(RepositoryError, match="根目录"):
        repository_path(sub, (tmp_path,))
    with pytest.raises(RepositoryError):
        repository_path(tmp_path, (tmp_path,))
    for name in ("", "a\\b", "a\0b"):
        with pytest.raises(RepositoryError):
            source(repo, "HEAD", name)
    for error in (OSError(), subprocess.TimeoutExpired("git", 15)):
        with patch("app.git_service.subprocess.run", side_effect=error), pytest.raises(RepositoryError, match="超时"):
            git(repo, "log")


def test_tree_excludes_symlinks_and_limits_files(repository):
    listing = b"120000 blob a\tlink\0" + b"".join(
        f"100644 blob {i:040x}\tfile{i}.py\0".encode() for i in range(1001)
    )
    with patch("app.git_service.resolve_revision", return_value="a" * 40), patch("app.git_service.git", return_value=listing):
        result = tree(repository[0], "HEAD")
        assert result["truncated"] and len(result["files"]) == 1000
        with pytest.raises(RepositoryError):
            source(repository[0], "HEAD", "link")
