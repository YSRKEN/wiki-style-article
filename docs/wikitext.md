# ウィキテキストの書き出し

読み取った記事（[原稿の書き方](source-format.md)）を、MediaWiki のウィキテキストに書き出す。HTML とウィキテキストは、どちらも原稿から書き出す（[ADR 0001](adr/0001-article-source-generates-both-outputs.md)）。

```python
from wikiskill import read_article_file
from wikiskill.types import load_default_registry
from wikiskill.wikitext import write_wikitext

article = read_article_file("article.md")
article_type = load_default_registry()[article.settings.type_id]
text = write_wikitext(article, article_type)  # 本家の形（既定）
plain = write_wikitext(article, article_type, style="plain")  # 素の記法
```

実装は `skills/wiki/scripts/wikiskill/wikitext.py`（全体の組み立てと本文）、`wikitext_cite.py`（出典）、`wikitext_infobox.py`（Infobox）、`wikitext_escape.py`（文字の逃がし方）。

## 二つの書き方

| | 本家の形（`style="wikipedia"`、既定） | 素の記法（`style="plain"`） |
| --- | --- | --- |
| 使う場面 | 日本語版 Wikipedia に貼る。日本語版と同じテンプレートが描く | テンプレートの無い MediaWiki に貼る。素の MediaWiki と Cite 拡張だけで描ける |
| 出典 | `<ref>{{Cite web …}}</ref>`（`Cite book`・`Cite news` も） | `<ref>` の中に書誌を地の文で書く |
| 脚注の一覧 | `{{Reflist}}`・`{{Reflist\|group="注釈"}}` | `<references />`・`<references group="注釈" />` |
| Infobox | 類型ごとのテンプレート（`{{Infobox 人物 …}}` など） | `{\| class="infobox" …` の表。項目名は日本語のまま |
| 注釈の中の出典 | `{{Efn\|1=…}}` | `{{#tag:ref\|…}}`（MediaWiki 本体の関数） |

どちらの書き方も、見出し、`'''太字'''`、`[[内部リンク]]`、`[URL 表示]`、`* 箇条書き`、`{{DEFAULTSORT:}}`、`[[Category:]]`、`<ref>`、`<ref name>`、`<ref group>` は共通で使う。

素の記法で使う `{{…}}` は `{{DEFAULTSORT:}}`（マジックワード）と、注釈の中に出典が入るときの `{{#tag:ref|…}}`（パーサー関数）だけ。どちらも MediaWiki 本体の機能で、テンプレートのページは要らない。

## ページの並び

```text
Infobox                            （値のある項目が一つもなければ書かない）
導入部                             （見出しなし）
== 節 == …                         （原稿の節をそのまま。## → ==、### → ===、#### → ====）
== 脚注 ==
=== 注釈 ===                       （注釈を使ったときだけ）
=== 出典 ===                       （出典を使ったときだけ）
== 関連項目 ==                     （related があるときだけ）
== 外部リンク ==                   （external_links があるときだけ）
{{DEFAULTSORT:読み}}               （defaultsort があるときだけ）
[[Category:名前]] …                （categories）
```

- 値のない部分は、節も行も書かない。「脚注」の下の小節は、注釈だけなら「注釈」だけ、出典だけなら「出典」だけを作る
- 目次は MediaWiki が見出しから作るので書かない。ページ名は本文に書かない（投稿先の題名で決まる）
- 並べ替えの読みは `defaultsort` だけを使う。`reading` は流用しない（`reading` は平仮名のままで、濁音を清音にするなど日本語版の規則を通っていないため）

## 原稿の各部分の写し方

| 原稿 | 本家の形 | 素の記法 |
| --- | --- | --- |
| 導入部の第一文の `'''記事名'''` | `'''記事名'''` | 同じ |
| 読み仮名 | 書き出さない。原稿の本文に書いたとおり（第一文の `（よみ、…）`） | 同じ |
| `[[記事名]]`・`[[記事名\|表示]]` | そのまま | 同じ |
| 記事名への自己リンク | 加えない（原稿に書かれていればそのまま） | 同じ |
| `[^キー]`（出典の印） | 最初の印で `<ref>{{Cite …}}</ref>`。二回目から `<ref name="キー" />` | 最初の印で `<ref>地の文</ref>`。二回目から `<ref name="キー" />` |
| `[^n:キー]`（注釈の印） | 最初の印で `<ref group="注釈">本文</ref>`。二回目から `<ref group="注釈" name="キー" />` | 同じ |
| 注釈の本文に出典の印がある | `{{Efn\|1=本文<ref>…</ref>}}` | `{{#tag:ref\|本文{{#tag:ref\|…}}\|group="注釈"}}` |
| `-` の箇条書き | `* 項目` | 同じ |
| `[infobox]` | 類型の `[[type.infobox]]` ごとのテンプレート | 一つの表 |
| `related` | `== 関連項目 ==` の `* [[記事名]]` | 同じ |
| `external_links` | `== 外部リンク ==` の `* [URL 題名]` | 同じ |
| `defaultsort` | `{{DEFAULTSORT:読み}}` | 同じ |
| `categories` | `[[Category:名前]]` | 同じ |

### 出典の名前

名前（`name`）は、同じ出典を二回以上使うときだけ付ける。一度きりの出典は `<ref>…</ref>` のまま。名前は設定欄のキーを使う。数字だけの名前は `<ref>` で使えないので、`":1"` のようにコロンを前に付ける（キーにコロンは使えないので、ほかのキーとぶつからない）。

出典と注釈は、本文で最初に使われた場所で定義する。節の順ではなく、本文に現れる順（導入部、節の順。注釈の中の出典は、その注釈を最初に使った場所）。使われない出典・注釈は書き出さない。

### 出典テンプレートの引数（本家の形）

第 1 引数は `和書`。原稿に言語の欄が無いので、すべての出典を和書として書く（`Cite web` は `和書` の有無で出力が変わらない）。

| 原稿の項目 | `Cite web` | `Cite book` | `Cite news` |
| --- | --- | --- | --- |
| `url` | `url` | `url` | `url` |
| `title` | `title` | `title` | `title` |
| `author` | `author` | `author` | `author` |
| `work` | `website` | `series` | `newspaper` |
| `publisher` | `publisher` | `publisher` | `publisher` |
| `date` | `date` | `date` | `date` |
| `pages` | `page`／`pages` | 同左 | 同左 |
| `isbn` | `isbn` | `isbn` | `isbn` |
| `access_date` | `access-date` | `access-date` | `access-date` |
| `note` | テンプレートの直後に文として添える | 同左 | 同左 |

引数はこの順に並べ、空の項目は書かない。`pages` は、`-`・`,`・`、`などを含む（範囲や列記）ときだけ `pages`、それ以外は `page`。値の `|` は `&#124;` に直す。日付は原稿のまま渡す（日本語の形にするのはテンプレートの仕事）。

### 出典の地の文（素の記法）

形は「著者「[URL 題名]」媒体、発行者、日付、ページ、ISBN、閲覧日。備考」。

| 種類 | 例 |
| --- | --- |
| web | `著者「[https://e.com/a 題]」サイト、発行、2020年4月、2026年11月1日閲覧。` |
| book | `著者『書名』例文社、2020年9月1日、3-20頁、ISBN 978-4-00-000000-0。` |
| news | `記者「見出し」『架空新聞』発行元、2020年4月1日、5面。` |

- 題は web・news が「」、book が『』。`url` があれば題をリンクにする
- news の `work` は題の直後に『』で書く。web の `work` は媒体として先頭に書く
- 日付は `2020-09-01` → `2020年9月1日`、`2020-09` → `2020年9月`、`2020` → `2020年` に直す。直せない書き方（`2020年春` など）はそのまま
- ページの単位は book・web が「頁」、news が「面」
- `ISBN 978-…` の書き方は、`ISBN` のマジックリンクが有効な MediaWiki では自動でリンクになる。日本語版 Wikipedia ではリンクにならないが、追跡用の隠しカテゴリが付く

## Infobox

### 本家の形

- 類型の `[[type.infobox]]` ごとにテンプレートを一つ書く。漫画のように Header・本体・Footer を重ねる型は三つ重ねる（どれかに値があれば全部書く。引数が一つも無い部品は `{{Infobox animanga/Footer}}` の一行）
- 原稿の日本語の項目名を、定義の `fields` に従って引数名に写す。引数は定義の順に並べる（原稿の順ではない）
- `title_field` の項目が原稿に無ければ、記事名を入れる
- `placement = "lead"` の型（法令）は、導入部の最初の段落の直前に置く。`"top"`（既定）は記事の最上部。いまのところ、どちらの置き方も出力は「Infobox、導入部」の順で同じ（`top` に注意枠などを足すときに差が出る）
- Infobox を持たない型（`no_infobox`）には書かない
- 値のある項目が一つも無ければ、テンプレートを書かない（`title_field` の既定値だけの箱は作らない）
- 値は、ウィキテキストとしてそのまま渡す（`[[リンク]]`・`{{テンプレート}}`・`<br />` も使える）。ただし、リンクとテンプレートの外にある `|` は引数の区切りと区別がつかないので `&#124;` に直す

### 素の記法

- 全部品の項目を、原稿に書いた順に並べた一つの表にする。見出しの行に記事名、各行の見出しセルに日本語の項目名、データセルに値
- 項目名は定義と照らさない（定義にあるかどうかに関わらず表の行にする）。Infobox を持たない型は表を作らない
- 表は `float: right` の `style` を直に持つ。`class="infobox"` だけでは、素の MediaWiki には右寄せの定義が無いため
- 値の `|` は本家の形と同じ規則で直す（セルの区切り `||` と区別がつかないため）

### 空の項目・定義にない項目

- 値が空（空白だけを含む）の項目は「書かれていない」ものとして扱う。引数も行も書かず、`title_field` の既定値も効く
- Infobox に書き出せない項目は、捨てずに HTML コメントで残す。
  - 本家の形で、類型の定義に無い項目名（例: 漫画の `連載期間`。漫画の定義は `発表期間`）
  - 本家の形と素の記法の両方で、Infobox を持たない型に書かれた項目

  ```text
  <!-- Infobox に書き出せなかった項目:
  連載期間 = 2020年4月 - 2023年3月
  -->
  ```

  コメントは最後のテンプレートの直後（Infobox の無い型は記事の最上部）に置く。値の中の `--` はコメントを閉じてしまうので `- -` に直す。どの項目が残ったかは `unknown_infobox_labels(article, article_type)` でも分かる（検査や入口で警告に使える）

## 文字の逃がし方

原稿の本文の文字には記法が入っていない（読み取りで部品に分けてある）ので、そのまま書くとウィキテキストの記法に読まれる文字だけを逃がす。

| 文字 | 書き出し |
| --- | --- |
| `<` | `&lt;` |
| `{`・`}` | `&#123;`・`&#125;` |
| URL の前の `[`（`[https://…`） | `&#91;` |
| 段落・箇条書きの項目の先頭の `*` `#` `:` `;` `=` 空白 | 前に `<nowiki/>` を付ける |
| テンプレート・`{{#tag:}}` の引数の中の `|` | `&#124;` |

`&` は逃がさない（原稿に `&amp;` と書けば、そのまま `&amp;` になる）。

## 例外

どれも `wikiskill.wikitext.WikitextError`（`ValueError` の仲間）。

| 例外 | 原因 |
| --- | --- |
| `WikitextError` | 記事の `type` と渡した類型の `id` が違う |
| `UnknownReferenceError` | 本文の印が指す出典・注釈が、設定欄の `[refs]`・`[notes]` に無い |
| `NestedNoteError` | 注釈の本文に、別の注釈への印がある（注釈は入れ子にできない） |

## 本家の形の確認

見本（`tests/fixtures/sample_article.md`）ほか、人物・法令・概念・映画の架空の原稿を書き出し、日本語版 Wikipedia の `action=parse`（保存しない描画だけの呼び出し）に通して、`class="error"`・`scribunto-error`・赤リンクの `Template:` が無いことを確かめた（2026-11-02）。素の記法も同じ日本語版に通したが、これは Cite 拡張が動くことの確認で、テンプレートの無い MediaWiki での確認ではない。試験には入れていない（外部へ送る確認のため）。出力の期待値は `tests/test_wikitext.py` と `tests/fixtures/sample_article.wikipedia.wikitext`。
