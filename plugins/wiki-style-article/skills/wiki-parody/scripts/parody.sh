#!/bin/sh
# Python 3.11 以上を探して、パロディ百科の原稿を検査・書き出す（parody.py）を流す。
#
#   sh parody.sh check 原稿.md
#   sh parody.sh build 原稿.md [--out-dir 出力先] [--updated 2026-11-02]
#   sh parody.sh type [型の ID]
#
# 探す順は python3・python・py・uv。どれも無ければ入れ方を案内し、終了コード 3 で終わる。
# ほかの終了コードは parody.py のもの（0=通った、1=エラー、2=呼び方の誤り）。
#
# dirname などの外のコマンドは使わない（PATH を絞った試験でも動くように）。

here=${0%[/\\]*}
[ "$here" = "$0" ] && here=.
entry="$here/parody.py"
probe='import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'

for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "$probe" >/dev/null 2>&1; then
    exec "$candidate" "$entry" "$@"
  fi
done
if command -v py >/dev/null 2>&1 && py -3 -c "$probe" >/dev/null 2>&1; then
  exec py -3 "$entry" "$@"
fi
if command -v uv >/dev/null 2>&1; then
  exec uv run --no-project --python '>=3.11' python "$entry" "$@"
fi

printf '%s\n' \
  'Python 3.11 以上が見つからない（python3・python・py・uv を探した）。' \
  'https://www.python.org/downloads/ から入れるか、uv を入れてから、もう一度流す。' >&2
exit 3
