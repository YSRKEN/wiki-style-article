# コマンドの入口

原稿（[原稿の書き方](source-format.md)）を読み、検査し、HTML とウィキテキストを書き出すまでを 1 回のコマンドで流す。

```bash
sh skills/wiki/scripts/wiki.sh build 原稿.md
sh skills/wiki/scripts/wiki.sh check 原稿.md
```

- `build`: 検査して、エラーが無ければ原稿と同じフォルダに `<原稿の名前>.html` と `<原稿の名前>.wikitext` を書き出す。同じ名前のファイルがあれば上書きする
- `check`: 検査だけして、何も書き出さない
- `type`: 類型の一覧を出す。`type manga` のように ID を渡すと、原稿の設定欄に貼る `type` と `[infobox]` の雛形を出す（下記）

`build` には次の指定を付けられる。

| 指定 | 意味 | 省いたとき |
| --- | --- | --- |
| `--style plain` | ウィキテキストを素の記法で書く（[二つの書き方](wikitext.md#二つの書き方)） | 本家の形（`wikipedia`） |
| `--out-dir 出力先` | 書き出し先のフォルダ。無ければ作る | 原稿と同じフォルダ |
| `--updated 日時` | フッタの最終更新の日時の文字列。そのまま入れる | 今の現地時刻（下記） |

実装は `skills/wiki/scripts/wiki.sh`（Python を探す）、`wiki.py`（入口のファイル）、`wikiskill/cli.py`（中身）。

## Python の探し方

`wiki.sh` は Python 3.11 以上を、`python3`・`python`・`py`（`py -3`）・`uv` の順に探す。

- 見つかっても、3.11 以上かの確かめが通らないもの（3.10 以下の版など）は飛ばす。Windows のストアへ案内する `python3` も、この確かめが通らなければ飛ばす
- `uv` だけがあるときは `uv run --no-project --python '>=3.11' python` で流す。合う版の Python が無ければ、uv の既定の設定では uv が取ってくる（[uv の文書](https://docs.astral.sh/uv/concepts/python-versions/)）。`python-downloads` を `manual`・`never` にしていれば取ってこず、uv がエラーを出す
- どれも無ければ、Python と uv の入れ方を標準エラーに出して終了コード 3 で終わる

Python が分かっているなら、`wiki.sh` を通さずに `python skills/wiki/scripts/wiki.py build 原稿.md` でも流せる。

## 出力の形

標準出力に 1 行 1 件で、検査の指摘、件数のまとめ、書き出したファイルの順に出す。

```text
13 行目 [警告] INFOBOX-UNKNOWN-FIELD: Infobox の項目「連載期間」は定義にないので、ウィキテキストに書き出せない（定義の項目名に直すか、本文に移すか、消す）
エラー 0 件、警告 1 件。
警告は前後を読み直し、直すか残すかを決める。
書き出した: /path/to/星屑ラーメン.html
書き出した: /path/to/星屑ラーメン.wikitext
```

- 検査の指摘は `check_article` の結果（[検査の規則](checks.md)）。類型の定義を渡すので、`TYPE-UNKNOWN`・`INFOBOX-MISSING`・`INFOBOX-UNKNOWN-FIELD` も検査する
- 原稿を読み取れないとき（設定欄の枠が壊れている、TOML が読めない、記法が閉じていないなど）は、`5 行目 [エラー] READ: …` の 1 件を出す。読み取りは最初の誤りで止まるので、直したら流し直す
- エラーがあると「エラーを直すまで書き出していない。」で終わり、何も書き出さない
- 書き出した HTML は `check_html`（[HTML の検査](html.md)）に通す。引っかかったら `[エラー] HTML-…` を出して書き出さない。これは原稿ではなくスクリプトの不具合の恐れがある
- 出力は、`PYTHONUTF8` などの設定によらず UTF-8 で出す（Windows で cp932 になり、AI が読むと文字化けするのを避ける）。書き出すファイルも UTF-8 で、改行は Windows でも LF

## 類型の雛形

`type <ID>` は、類型の定義（[記事の類型](types.md)）から、原稿の設定欄に貼る部分を出す。項目は定義の順で、値は空。

```text
# 漫画（manga）
# 節の並びと書き方: references/types/manga.md
type = "manga"
# Infobox: Infobox animanga/Header ＋ Infobox animanga/Manga ＋ Infobox animanga/Footer
# 「必須」の項目は必ず埋める。ほかは分かる項目だけ埋め、分からない項目は行ごと消す。

[infobox]
"タイトル" = ""  # 書かなければ記事名
"作者" = ""  # 必須
…
```

- 細かい種類（`voice-actor` など）では、節の並びの案内が寄せ先の基本型のファイルになる
- Infobox を持たない類型（`concept` など）では `[infobox]` を出さない
- 知らない ID なら標準エラーに「類型が見つからない」を出して終了コード 2

## 終了コード

| コード | 意味 | 次の一手 |
| --- | --- | --- |
| 0 | 書き出した（`check` ではエラーが無かった）。警告があっても 0。`--help` も 0 | 警告を読み直す |
| 1 | 原稿にエラーがあって書き出していない | 指摘の行を直して流し直す |
| 2 | 呼び方の誤り（引数が足りない・違う、原稿のファイルが無い、知らない類型の ID） | 呼び方を直す |
| 3 | Python 3.11 以上が見つからない（`wiki.sh` だけ） | 案内に従って Python か uv を入れる |

## 最終更新の日時

`--updated` を省くと、今の現地時刻を本家のフッタの形で入れる。

| 現地の時差 | 例 |
| --- | --- |
| UTC+9 | `2026年11月2日 (月) 12:00 (JST)` |
| UTC+0 | `2026年1月4日 (日) 03:05 (UTC)` |
| ほか | `2026年11月7日 (土) 23:59 (UTC+05:30)` |

UTC+9 はすべて `JST` と書く（日本語版の記事を作るスキルなので、同じ時差の別の地域の呼び名は考えない）。
