# コマンドの入口

原稿（[原稿の書き方](source-format.md)）を読み、検査し、HTML とウィキテキストを書き出すまでを 1 回のコマンドで流す。

```bash
sh plugins/wiki-style-article/skills/wiki/scripts/wiki.sh build 原稿.md
sh plugins/wiki-style-article/skills/wiki/scripts/wiki.sh check 原稿.md
```

- `build`: 検査して、エラーが無ければ原稿と同じフォルダに `<原稿の名前>.html` と `<原稿の名前>.wikitext` を書き出す。同じ名前のファイルがあれば上書きする
- `check`: 検査だけして、何も書き出さない
- `type`: 類型の一覧を出す。`type manga` のように ID を渡すと、原稿の設定欄に貼る `type` と `[infobox]` の雛形を出す（下記）
- `fetch`: Web のページを取り、題と本文の文字を出す（下記）。調べものの担当が使う
- `wikipedia`: 本家の記事の節の並びと出典の一覧を出す（下記）。調べる工程の最初に書き手が使う

`build` には次の指定を付けられる。

| 指定 | 意味 | 省いたとき |
| --- | --- | --- |
| `--style plain` | ウィキテキストを素の記法で書く（[二つの書き方](wikitext.md#二つの書き方)） | 本家の形（`wikipedia`） |
| `--out-dir 出力先` | 書き出し先のフォルダ。無ければ作る | 原稿と同じフォルダ |
| `--updated 日時` | フッタの最終更新の日時の文字列。そのまま入れる | 今の現地時刻（下記） |

実装は `plugins/wiki-style-article/skills/wiki/scripts/wiki.sh`（Python を探す）、`wiki.py`（入口のファイル）、`wikiskill/cli.py`（中身）。

## Python の探し方

`wiki.sh` は Python 3.11 以上を、`python3`・`python`・`py`（`py -3`）・`uv` の順に探す。

- 見つかっても、3.11 以上かの確かめが通らないもの（3.10 以下の版など）は飛ばす。Windows のストアへ案内する `python3` も、この確かめが通らなければ飛ばす
- `uv` だけがあるときは `uv run --no-project --python '>=3.11' python` で流す。合う版の Python が無ければ、uv の既定の設定では uv が取ってくる（[uv の文書](https://docs.astral.sh/uv/concepts/python-versions/)）。`python-downloads` を `manual`・`never` にしていれば取ってこず、uv がエラーを出す
- どれも無ければ、Python と uv の入れ方を標準エラーに出して終了コード 3 で終わる

Python が分かっているなら、`wiki.sh` を通さずに `python plugins/wiki-style-article/skills/wiki/scripts/wiki.py build 原稿.md` でも流せる。

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

## ページの取得

`fetch URL` は、Web のページを取って題と本文の文字を出す。Claude Code の WebFetch は web.archive.org を取れず、Jina の Reader も鍵なしでは web.archive.org を止めている（2026-11-02 に確かめた）ので、標準ライブラリだけで取る。

```text
題: 日清食品グループ
URL: https://web.archive.org/web/2016/https://www.nissin.com/jp/
取った URL: https://web.archive.org/web/2016id_/https://www.nissin.com/jp/
本文: 全 132 字のうち 0〜132 字目
---
（本文。見出しは # 、箇条は - で始まる行）
```

- web.archive.org の保存版は、Wayback の飾りの無い形（`/web/<時刻>id_/<URL>`）に直して取る
- 同じホストへは間を空ける（web.archive.org は 15 秒、ほかは 1 秒）。間の記録は環境変数 `WIKISKILL_FETCH_STATE` のフォルダ（無ければ一時フォルダの `wiki-style-article-fetch`）に置き、並んだ担当で分け合う
- 429・503 なら、間を空けて一度だけ取り直す
- 元のページが 403・404・410・451 か、相手に届かない（名前解決の失敗など）か、深い階層の URL がサイトの根へ転送された（消えたページをトップへ送るサイト）なら、web.archive.org の保存版（`/web/<年>id_/<元の URL>`）を取る。年は `--archive-year` で選び、省くと今年に近い保存版。保存版を取ったら「取った URL: …（元のページが HTTP 404 のため保存版を取った）」と出す。500 のような一時的な誤りでは試さない
- 証明書の検証で失敗したら、検証を外さずに curl で取り直す。2026-11-02 に、Windows の Python（3.13）では example.com だけが検証に失敗し、同じ PC の curl では取れた。原因は、OS の証明書置き場にまだ無い根の証明書を、Python が取ってこないためと見ている（確かめてはいない）
- 本文は `--max-chars`（既定 30000 字）で区切る。続きは、出力の最後に出る `--offset` を付けて流し直す
- 取れない（HTTP の誤り・通信の失敗・HTML でない）ときは、標準エラーに理由と、鍵なしの Jina（`https://r.jina.ai/<URL>` を WebFetch で取る）の案内を出して終了コード 1

## 本家の記事の節と出典

`wikipedia 記事名` は、本家（ja.wikipedia.org）の記事の生のウィキテキストを 1 回だけ取り、節の並びと出典の一覧を出す。WebFetch で生のウィキテキストを読むと、小さなモデルが要約して返すので、長い URL（とくに保存版の URL）が途中で切れる（2026-11-02 の試運転で起きた）。このコマンドは出典を機械で取り出し、URL を切らずに出す。本家の本文は出さない。

```text
記事: カップヌードル（https://ja.wikipedia.org/wiki/カップヌードル）
出典 146 件（保存版つき 35 件）。
…
## 節の並び
- 歴史
  - 開発
## 出典（節ごと）
### 歴史
- 日清食品グループ（日清食品株式会社） ｜ リクナビ
  元: http://job.rikunabi.com/2013/company/top/r136500053/
  保存版: https://web.archive.org/web/20111203215709/http://job.rikunabi.com/2013/company/top/r136500053/
```

- 出典は、`<ref>` の中身（名前つきの再掲は一つと数える）と、`<ref>` の外の Cite 系のテンプレート（参考文献の節など）。テンプレートの無い `<ref>` は、角括弧のリンクか裸の URL を拾う
- 値の中の内部リンクの記法（`[[…|…]]`）は文字だけにする。日付の形はそろえない
- 「関連項目」の節の内部リンクの記事名を「関連項目（関連の記事の候補）」として出す
- 転送のページなら、転送先を一度だけ読み直す（本家への問い合わせは 2 回になる）
- 記事が無ければ、標準エラーに「本家に記事が無い」を出して終了コード 1

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
| 1 | 原稿にエラーがあって書き出していない（`fetch` ではページを取れなかった） | 指摘の行を直して流し直す |
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

## 印の日付

`build` は、文中の印（`[!要出典]` など）と冒頭の警告の枠に、今の現地時刻の年月（`2026年11月`、月は 0 詰めしない）を添える。HTML では枠の各文の後ろに `（2026年11月）`、本家の形のウィキテキストでは `{{要出典|date=2026年11月}}`・`{{出典の明記|date=2026年11月}}` のように入る。`--updated` とは別で、日付を変える引数は無い。書き方は [原稿の書き方](source-format.md) の「印」の節。
