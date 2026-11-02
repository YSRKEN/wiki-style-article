""".githooks/pre-merge-commit が、検査の落ちたマージを main へ入れないかを見る。"""

import shutil
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).parents[1] / ".githooks"
GIT = shutil.which("git")
UV = shutil.which("uv")

pytestmark = pytest.mark.skipif(GIT is None or UV is None, reason="git か uv が無い")

# 本物の check.py の代わり。同じフォルダの code に書いた終了コードで終わる
_FAKE_CHECK = "import pathlib, sys\nsys.exit(int(pathlib.Path('code').read_text()))\n"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    assert GIT is not None
    return subprocess.run(
        [GIT, "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=check,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "試し")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "core.hooksPath", str(HOOKS))
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check.py").write_text(_FAKE_CHECK, encoding="utf-8")
    (tmp_path / "code").write_text("0", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("code\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "chore: 初期構成を追加")
    _git(tmp_path, "switch", "-q", "-c", "feature/x")
    (tmp_path / "a.md").write_text("中身\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "docs: 中身を足す")
    _git(tmp_path, "switch", "-q", "main")
    return tmp_path


def _merge(repo: Path) -> subprocess.CompletedProcess[str]:
    return _git(
        repo, "merge", "--no-ff", "feature/x", "-m", "docs: 中身を足す (feature/x)", check=False
    )


def test_検査が落ちたら_main_へマージしない(repo: Path) -> None:
    (repo / "code").write_text("1", encoding="utf-8")

    result = _merge(repo)

    assert result.returncode != 0
    assert "check.py" in result.stderr
    # マージコミットは作られていない
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"


def test_検査が通れば_main_へマージする(repo: Path) -> None:
    result = _merge(repo)

    assert result.returncode == 0, result.stderr
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "3"


def test_main_以外へのマージでは検査しない(repo: Path) -> None:
    (repo / "code").write_text("1", encoding="utf-8")
    _git(repo, "switch", "-q", "-c", "feature/y")
    (repo / "b.md").write_text("別\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "docs: 別の中身を足す")

    assert _merge(repo).returncode == 0
