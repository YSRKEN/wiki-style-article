""".githooks/pre-push が、版の上げ忘れと、版のタグの打ち忘れを止めるかを見る。"""

import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).parents[1] / ".githooks" / "pre-push"
SH = shutil.which("sh")
GIT = shutil.which("git")
ZERO = "0" * 40
MANIFEST = "plugins/wiki-style-article/.claude-plugin/plugin.json"

pytestmark = pytest.mark.skipif(SH is None or GIT is None, reason="sh か git が無い")


def _git(repo: Path, *args: str) -> str:
    assert GIT is not None
    done = subprocess.run(
        [GIT, "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return done.stdout.strip()


def _commit(repo: Path, files: dict[str, str]) -> str:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "chore: 試し")
    return _git(repo, "rev-parse", "HEAD")


def _tag(repo: Path, version: str, commit: str) -> None:
    _git(repo, "tag", "-a", f"v{version}", commit, "-m", f"v{version}")


def _manifest(version: str) -> str:
    return f'{{\n  "name": "wiki-style-article",\n  "version": "{version}"\n}}\n'


def _push(
    repo: Path, local: str, remote: str, ref: str = "refs/heads/main"
) -> subprocess.CompletedProcess[str]:
    assert SH is not None
    # git は LF で渡す。text=True だと Windows で CRLF に化けるので、バイト列で渡す
    line = f"{ref} {local} {ref} {remote}\n".encode()
    done = subprocess.run(
        [SH, str(HOOK), "origin", "https://example.com/repo.git"],
        cwd=repo,
        input=line,
        capture_output=True,
        check=False,
    )
    return subprocess.CompletedProcess(
        done.args, done.returncode, done.stdout.decode(), done.stderr.decode()
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "試し")
    _git(tmp_path, "config", "user.email", "test@example.com")
    return tmp_path


def test_中身を変えて版が同じなら止める(repo: Path) -> None:
    base = _commit(repo, {MANIFEST: _manifest("0.1.0"), "plugins/wiki-style-article/a.md": "前\n"})
    head = _commit(repo, {"plugins/wiki-style-article/a.md": "後\n"})

    result = _push(repo, head, base)

    assert result.returncode == 1
    assert "0.1.0" in result.stderr
    assert "version" in result.stderr


def test_中身を変えて版を上げれば通す(repo: Path) -> None:
    base = _commit(repo, {MANIFEST: _manifest("0.1.0"), "plugins/wiki-style-article/a.md": "前\n"})
    head = _commit(repo, {MANIFEST: _manifest("0.1.1"), "plugins/wiki-style-article/a.md": "後\n"})
    _tag(repo, "0.1.1", head)

    assert _push(repo, head, base).returncode == 0


def test_版のタグが無ければ止める(repo: Path) -> None:
    base = _commit(repo, {MANIFEST: _manifest("0.1.0"), "plugins/wiki-style-article/a.md": "前\n"})
    head = _commit(repo, {MANIFEST: _manifest("0.1.1"), "plugins/wiki-style-article/a.md": "後\n"})

    result = _push(repo, head, base)

    assert result.returncode == 1
    assert "v0.1.1" in result.stderr
    assert "git tag" in result.stderr


def test_版のタグが送るコミットより後を指していれば止める(repo: Path) -> None:
    base = _commit(repo, {MANIFEST: _manifest("0.1.0"), "plugins/wiki-style-article/a.md": "前\n"})
    head = _commit(repo, {MANIFEST: _manifest("0.1.1"), "plugins/wiki-style-article/a.md": "後\n"})
    later = _commit(repo, {"docs/a.md": "さらに後\n"})
    _tag(repo, "0.1.1", later)

    assert _push(repo, head, base).returncode == 1


def test_プラグインの外だけを変えたなら版はそのままでよい(repo: Path) -> None:
    base = _commit(repo, {MANIFEST: _manifest("0.1.0"), "docs/a.md": "前\n"})
    _tag(repo, "0.1.0", base)
    head = _commit(repo, {"docs/a.md": "後\n"})

    assert _push(repo, head, base).returncode == 0


def test_初めての_push_と_main_以外のブランチは見ない(repo: Path) -> None:
    base = _commit(repo, {MANIFEST: _manifest("0.1.0"), "plugins/wiki-style-article/a.md": "前\n"})
    head = _commit(repo, {"plugins/wiki-style-article/a.md": "後\n"})
    _tag(repo, "0.1.0", head)

    assert _push(repo, head, ZERO).returncode == 0
    assert _push(repo, head, base, ref="refs/heads/feature/x").returncode == 0


def test_ブランチを消す_push_は見ない(repo: Path) -> None:
    base = _commit(repo, {MANIFEST: _manifest("0.1.0")})

    assert _push(repo, ZERO, base).returncode == 0


def _tag_with(repo: Path, tag: str, commit: str, message: str | None) -> str:
    """注記を決めてタグを打ち、タグの名前が指すもの（注釈つきならタグの対象）を返す。"""
    if message is None:
        _git(repo, "tag", tag, commit)
    else:
        _git(repo, "tag", "-a", tag, commit, "-m", message)
    return _git(repo, "rev-parse", f"refs/tags/{tag}")


@pytest.mark.parametrize("message", ["0.1.1", "リリース", None], ids=["版だけ", "別の文", "軽いタグ"])
def test_版のタグの注記が_v版_で始まらなければ止める(repo: Path, message: str | None) -> None:
    base = _commit(repo, {MANIFEST: _manifest("0.1.0"), "plugins/wiki-style-article/a.md": "前\n"})
    head = _commit(repo, {MANIFEST: _manifest("0.1.1"), "plugins/wiki-style-article/a.md": "後\n"})
    _tag_with(repo, "v0.1.1", head, message)

    result = _push(repo, head, base)

    assert result.returncode == 1
    assert "v0.1.1" in result.stderr
    assert "注記" in result.stderr


def test_注記が_v版_と要点なら通す(repo: Path) -> None:
    base = _commit(repo, {MANIFEST: _manifest("0.1.0"), "plugins/wiki-style-article/a.md": "前\n"})
    head = _commit(repo, {MANIFEST: _manifest("0.1.1"), "plugins/wiki-style-article/a.md": "後\n"})
    _tag_with(repo, "v0.1.1", head, "v0.1.1: 要点を書く")

    assert _push(repo, head, base).returncode == 0


@pytest.mark.parametrize(
    ("message", "code"), [("0.1.1", 1), (None, 1), ("v0.1.1: 要点", 0), ("v0.1.1", 0)]
)
def test_タグだけの_push_でも注記を見る(repo: Path, message: str | None, code: int) -> None:
    head = _commit(repo, {MANIFEST: _manifest("0.1.1")})
    target = _tag_with(repo, "v0.1.1", head, message)

    assert _push(repo, target, ZERO, ref="refs/tags/v0.1.1").returncode == code
