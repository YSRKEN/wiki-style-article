"""原稿を検査・書き出すコマンドの入口。``python wiki.py build 原稿.md`` のように流す。

このファイルの隣にある ``wikiskill`` を読み込む（スクリプトのフォルダは自動で探す先に入る）。
Python を探すところから任せるなら ``sh wiki.sh`` を使う。使い方は :mod:`wikiskill.cli`。
"""

from wikiskill.cli import run

if __name__ == "__main__":
    run()
