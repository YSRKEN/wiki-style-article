import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "skills" / "wiki" / "scripts"
WIKI_SH = SCRIPTS / "wiki.sh"
SAMPLE = Path(__file__).parent / "fixtures" / "sample_article.md"
SH = shutil.which("sh")

pytestmark = pytest.mark.skipif(SH is None, reason="sh が無い")

# 版の確かめ（-c）には ok で答え、それ以外は呼ばれた引数をそのまま出す偽の Python。
_FAKE = """#!/bin/sh
if [ "$1" = "-c" ] || [ "$2" = "-c" ]; then exit {probe}; fi
printf '%s\\n' "{name} $*"
"""


def _fake_bin(tmp_path: Path, **commands: bool) -> Path:
    """偽のコマンドを置いたフォルダを作る。

    値が False のコマンドは、版の確かめで落ちる（古い版や、中身の無いものの代わり）。
    """
    folder = tmp_path / "bin"
    folder.mkdir(parents=True)
    for name, works in commands.items():
        path = folder / name
        path.write_bytes(_FAKE.format(name=name, probe=0 if works else 1).encode())
        path.chmod(0o755)
    return folder


def _run(path_env: str, *args: str) -> subprocess.CompletedProcess[str]:
    assert SH is not None
    return subprocess.run(
        [SH, str(WIKI_SH), *args],
        env={"PATH": path_env},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _called(result: subprocess.CompletedProcess[str]) -> str:
    """偽のコマンドが出した 1 行から、入口のパスを ``<wiki.py>`` に置き換えたもの。"""
    line = result.stdout.strip()
    command, _, rest = line.partition(" ")
    words = rest.split(" ")
    entry = next(word for word in words if word.endswith("wiki.py"))
    assert Path(entry).name == "wiki.py"
    return " ".join([command, *("<wiki.py>" if w == entry else w for w in words)])


def test_python3_を最初に使う(tmp_path: Path) -> None:
    folder = _fake_bin(tmp_path, python3=True, python=True, py=True, uv=True)

    result = _run(str(folder), "build", "原稿.md")

    assert result.returncode == 0, result.stderr
    assert _called(result) == "python3 <wiki.py> build 原稿.md"


def test_版の確かめで落ちた_python3_は飛ばす(tmp_path: Path) -> None:
    # 古い版や、Windows のストアへ案内する python3 の代わり
    folder = _fake_bin(tmp_path, python3=False, python=True)

    assert _called(_run(str(folder), "check", "x.md")) == "python <wiki.py> check x.md"


def test_py_の次に_uv_を使う(tmp_path: Path) -> None:
    py_only = _fake_bin(tmp_path / "a", py=True)
    uv_only = _fake_bin(tmp_path / "b", python=False, uv=True)

    assert _called(_run(str(py_only), "check", "x.md")) == "py -3 <wiki.py> check x.md"
    assert (
        _called(_run(str(uv_only), "check", "x.md"))
        == "uv run --no-project --python >=3.11 python <wiki.py> check x.md"
    )


def test_どれも無ければ入れ方を案内して終了コード_3(tmp_path: Path) -> None:
    folder = _fake_bin(tmp_path, python3=False, python=False)

    result = _run(str(folder), "check", "x.md")

    assert result.returncode == 3
    assert "Python 3.11" in result.stderr
    assert "uv" in result.stderr


def test_本物の_Python_で検査まで流れる() -> None:
    import os

    result = _run(os.environ["PATH"], "check", str(SAMPLE))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "INFOBOX-UNKNOWN-FIELD" in result.stdout
