#!/bin/sh
# Python 3.11 以上を探して、原稿を検査・書き出すコマンド（wiki.py）を流す。
#
#   sh wiki.sh build 原稿.md [--style plain] [--out-dir 出力先] [--updated 日時]
#   sh wiki.sh check 原稿.md
#
# 探す順は python3・python・py・uv。見つかっても版の確かめで落ちるもの（古い版、
# Windows のストアへ案内するだけの python3）は飛ばす。どれも無ければ入れ方を案内し、
# 終了コード 3 で終わる。ほかの終了コードは wiki.py のもの（docs/cli.md）。
#
# dirname などの外のコマンドは使わない（PATH を絞った試験でも動くように）。

here=${0%[/\\]*}
[ "$here" = "$0" ] && here=.
entry="$here/wiki.py"
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
  # uv は合う版が無ければ取ってくる。
  exec uv run --no-project --python '>=3.11' python "$entry" "$@"
fi

printf '%s\n' \
  'Python 3.11 以上が見つからない（python3・python・py・uv を探した）。' \
  '次のどれかで入れてから、もう一度流す。' \
  '  - https://www.python.org/downloads/ から Python 3.11 以上を入れる' \
  '  - uv を入れる（https://docs.astral.sh/uv/getting-started/installation/）。' \
  '    uv があれば、合う版の Python はこのスクリプトが uv に取ってこさせる' >&2
exit 3
