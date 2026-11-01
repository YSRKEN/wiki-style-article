"""開発用の検査（ruff・pyright・pytest）をまとめて流す。

使い方は ``uv run scripts/check.py``。途中で落ちても残りの検査は流し、
最後に結果を一覧して、一つでも落ちていれば終了コード 1 で終わる。
"""

from __future__ import annotations

import subprocess
import sys

_STEPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ruff check", ("ruff", "check", ".")),
    ("ruff format --check", ("ruff", "format", "--check", ".")),
    ("pyright", ("pyright",)),
    ("pytest", ("pytest",)),
)


def main() -> int:
    """検査を順に流し、結果を一覧して終了コードを返す。

    Returns
    -------
    int
        すべて通れば 0、一つでも落ちれば 1。
    """
    results: list[tuple[str, bool]] = []
    for name, args in _STEPS:
        print(f"\n=== {name} ===", flush=True)
        completed = subprocess.run([sys.executable, "-m", *args], check=False)
        results.append((name, completed.returncode == 0))

    print("\n=== 結果 ===")
    for name, ok in results:
        print(f"{'OK  ' if ok else 'FAIL'} {name}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
