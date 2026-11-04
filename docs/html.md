# HTML の書き出し

読み取った記事（[原稿の書き方](source-format.md)）を、ブラウザで開けば日本語版 Wikipedia のように読める HTML 1 枚に書き出し、その HTML を機械で検査する。HTML とウィキテキストは、どちらも原稿から書き出す（[ADR 0001](adr/0001-article-source-generates-both-outputs.md)）。

```python
from wikiskill import read_article_file
from wikiskill.types import load_default_registry
from wikiskill.html_writer import write_html
from wikiskill.html_check import check_html

article = read_article_file("article.md")
article_type = load_default_registry()[article.settings.type_id]
html = write_html(article, article_type, updated="2026年11月2日 (月) 12:00 (JST)")
for finding in check_html(html):
    print(finding)  # HTML-FOOTNOTE-PLAIN: 脚注番号 [3] がリンクにならず文字のまま残っている
```

噂のある原稿（[原稿の書き方](source-format.md#噂)）は `write_html_both` で、通常の記事と噂込みの記事を一枚に入れる（下の「噂のある原稿（二つの版）」）。噂のある原稿を `write_html` に渡すと `HtmlError` になる。

最終更新の日時は呼ぶ側が文字列で渡す（関数の中で現在時刻を取らない）。冒頭の警告の枠に添える日付も、キーワード引数 `mark_date`（例 `"2026年11月"`）で渡す。省くか `None` なら日付を出さない。実装は `plugins/wiki-style-article/skills/wiki/scripts/wikiskill/` の次のファイル。

| ファイル | 役割 |
| --- | --- |
| `html_writer.py` | 全体の組み立て（冒頭の警告の枠・見出し・目次・節・脚注欄・末尾）と、雛形への差し込み。二つの版を入れる `write_html_both` も |
| `html_switch.py` | 二つの版を切り替えるボタン・CSS・スクリプト |
| `html_inline.py` | 文中の部品（太字・内部リンク・脚注の印・点と範囲の印）、脚注の番号づけ、例外 |
| `notices.py` | 冒頭の警告の枠の決め方（ウィキテキストの書き出しと共用） |
| `html_cite.py` | 出典の書誌 |
| `html_infobox.py` | Infobox |
| `html_escape.py` | 文字の逃がし方、リンク先の組み立て |
| `html_check.py` | 書き出した HTML の検査 |
| `../assets/page-template.html` | 雛形（CSS を中に持つ） |

## 見た目の方針

見た目は、日本語版 Wikipedia の現行の外装（Vector 2022）に寄せる（2026-11-02、作者の決定。見た目の試作 3 案から選んだ）。

- 全面白。高さ 50px の上部バー（文字のロゴ「W」と小さく「WIKIPEDIA風」、検索欄の見た目）、記事名の帯の下に文字だけのタブ
- 左に付いてくる目次の列（1120px 未満では、記事名の左の浮き窓に変わる）。記事の列は最大 948px
- 本文は 16px・行の高さ 1.625 の sans-serif。見出しも sans-serif（h1 28.8px、h2 24px で下線、h3 19.2px 太字、h4 16px 太字）
- Infobox は背景 `#f8f9fa`・枠 `#a2a9b1`。脚注は上付きの `[1]` と戻りリンク。カテゴリ欄。箱の外のフッタ

CSS は本家から写していない。本家の記事ページの HTML と CSS を取って、その宣言から引いた値（色・余白・文字の大きさ）をもとに書き起こした試作の CSS を土台にしている。値は画面で測ったものではない。

### 本物と取り違えないための細工

- 記事名の下の副題「出典: フリー百科事典『ウィキペディア（Wikipedia）』風のページ」
- 上部バーのロゴは文字の「W」と「WIKIPEDIA風」。Wikimedia のロゴの画像は使わない
- フッタの「このページは Wikipedia そのものではなく、その見た目に寄せて作った Wikipedia風のページです。」
- フッタの「このページは AI が生成した文章で、内容は検証されていません。手元で読むためのもので、Web に公開したりウィキペディアに投稿したりしないでください。」（生成したページを Web に上げたり本家に投稿したりしないよう、ページの中でも伝える）
- `<title>` は「記事名 - Wikipedia風ページ」

### 押しても動かない部品

検索欄、アカウント作成、ログイン、他の言語版、上部のタブ（ページ・ノート・閲覧・編集・履歴を表示・ツール）、各見出しの「編集」は、見た目だけの部品。リンク（`<a>`）にせず `<span class="nop">` にするので、押しても何も起きない。マウスを載せると「この部品は見た目だけで、押しても動きません」と出る。動くのは、記事の本文・目次・脚注・外部リンクの `<a>` と、狭い画面の目次の浮き窓（`<details>`）だけ。

### 一枚で開ける

外部の CSS・JS・フォント・画像を読まない（オフラインで開ける）。`lang="ja"`、UTF-8。JavaScript は、左の目次で今読んでいる節を強調するための小さな一つだけで、なくても読める。二つの版を入れたページには、切り替えのスクリプトがもう一つ入る（下の「噂のある原稿（二つの版）」）。

## ページの並び

```text
上部バー
記事名の帯（狭い画面では目次の浮き窓）
タブ
副題
冒頭の警告の枠                     （印か notices があるときだけ）
Infobox                            （値のある項目が一つもなければ出さない）
導入部                             （見出しなし）
節 …                               （原稿の節をそのまま。## → h2、### → h3、#### → h4）
脚注
  注釈                             （注釈を使ったときだけ）
  出典                             （出典を使ったときだけ）
関連項目                           （related があるときだけ）
外部リンク                         （external_links があるときだけ）
カテゴリ欄                         （categories があるときだけ）
フッタ                             （最終更新の日時、取り違え防止の断り書き）
```

値のない部分は、節も欄も作らない。「脚注」の下の小節は、注釈だけなら「注釈」だけ、出典だけなら「出典」だけ（ウィキテキストの書き出しと同じ）。

## 原稿の各部分の写し方

| 原稿 | HTML |
| --- | --- |
| `title` | `<title>`、記事名の帯の `<h1>`、Infobox の見出し（`title_field` の項目があればそちら） |
| 導入部の第一文の `'''記事名'''` | `<b>記事名</b>` |
| 読み仮名（`reading`） | 書き出さない。原稿の本文に書いたとおり |
| `[[記事名]]`・`[[記事名\|表示]]` | `https://ja.wikipedia.org/wiki/記事名` への `<a>`。スペースは `_`、日本語などはパーセントエンコード、`#節` は分けて付ける。本家には問い合わせず、赤リンクも作らない |
| `[^キー]`（出典の印） | `<sup id="cite_ref-N-K" class="reference"><a href="#cite_note-N">[N]</a></sup>` |
| `[^n:キー]`（注釈の印） | `<sup id="cite_ref-note-N-K" class="reference"><a href="#cite_note-note-N">[注 N]</a></sup>` |
| `[!要出典]`・`[!信頼性要検証]`（点の印） | `<sup class="fix-mark">[要出典]</sup>`・`<sup class="fix-mark">[信頼性要検証]</sup>` |
| `[!要出典範囲\|範囲の文]`（範囲の印） | `<span class="fix-range">範囲の文</span><sup class="fix-mark">[要出典]</sup>`。独自研究範囲の印の文字は本家と同じ `[独自研究?]` |
| `[!仮リンク\|言語タグ\|本家の記事名]`（表示つきも可） | `<a href="https://ja.wikipedia.org/wiki/表示" title="表示" class="new">表示</a><span class="interlanguage-note">（<a href="https://en.wikipedia.org/wiki/本家の記事名" class="external" lang="en">英語</a>）</span>`。赤字の内部リンクと、日本語の言語名の外部リンク |
| `[!言語\|言語タグ]` | 言語名の文字（`en` → `英語`）。知らないタグはタグのまま |
| `[!節スタブ]`（行に単独で置く） | `<div class="section-stub">この節は書きかけです。</div>` |
| `-` の箇条書き | `<ul><li>…</li></ul>` |
| `![キャプション](画像の道)` | 右寄せの `<figure class="thumb"><img src="data:…"><figcaption>…</figcaption></figure>`。画像そのものを data: の URI として埋め込む（下の「一枚で開ける」） |
| `[infobox]` | 右寄せの表 `<table class="infobox">`（次節） |
| `related` | 「関連項目」の `<ul>`。各項目は本家の記事へのリンク |
| `external_links` | 「外部リンク」の `<ul>`。`http://`・`https://` 以外のアドレスはリンクにせず題だけ書く |
| `categories` | カテゴリ欄。各項目は `https://ja.wikipedia.org/wiki/Category:名前` へのリンク |
| `defaultsort` | 書き出さない（並べ替えは HTML では使わない） |
| `[coord]`（設定欄） | 導入部の先頭に `<div class="coordinates">座標: <a href="https://geohack.toolforge.org/geohack.php?…" class="external">北緯35度40分52秒 東経139度46分02秒</a></div>`。リンクは GeoHack |
| `[[navbox]]`（設定欄） | 外部リンクの欄の後ろに `<table class="navbox"><caption>題</caption>…` を書いた順に |
| `stub`（設定欄） | カテゴリ欄の前に `<div class="stub">この記事は書きかけです。</div>` |

`<` `>` `&` `"` と `{` `}` は、本文・見出し・属性・出典・最終更新の日時のすべてで文字参照に直す（`{` `}` を直すのは、本文の `{{…}}` が雛形の差し込み口と取り違えられないようにするため）。

### 見出しと目次

- 見出しは `<h2 id="section-1">`・`<h3 id="section-2-1">`・`<h4 id="section-2-1-1">` のように、節の番号から作った英数字の id を付ける。日本語の見出しでも安全で、同じ見出しが二つあっても重ならない
- 目次は見出しから作り、番号（1・2.1・2.1.1）を付ける。原稿の節に加えて、脚注・注釈・出典・関連項目・外部リンクの見出しも入る。左の列と、狭い画面の浮き窓に同じ内容を入れる
- 先頭に「ページ先頭」の項目がある

### 脚注

- 番号は本文に現れる順（導入部、節の順）。出典は `[1]`、注釈は `[注 1]` で、別々に数える。同じ出典・注釈の再利用は同じ番号になる
- 注釈の中の出典の印は、その注釈を最初に使った場所で数える。注釈の本文は注釈欄に一度だけ書くので、中の印も一度だけ数える（注釈を何度使っても、中の出典の戻りリンクは増えない）
- 使われない出典・注釈は書き出さない
- 脚注欄の各項目に戻りリンクを付ける。印が一回なら `↑`、複数なら `↑ a b …`（文書に現れる順。注釈の中の印は注釈欄にあるので、本文より後になる）
- 注釈の本文の中に別の注釈への印があるときは `NestedFootnoteError`、設定欄にない出典・注釈を指す印は `UnknownFootnoteError`

### 冒頭の警告の枠

貼る枠は `wikiskill.notices.article_notices` で決める（[原稿の書き方](source-format.md) の「警告の枠」）。Infobox より前、記事の本文の先頭に `<div class="ambox" role="note"><div class="ambox-text">…</div></div>` を置く。文面は本家の枠の文を写さず、次の自作の文にした。

| 枠 | 文 |
| --- | --- |
| 出典の明記 | この記事には、出典が示されていない記述や、信頼性の確かめられていない出典に頼る記述があります。 |
| 独自研究 | この記事には、出典で確かめられていない見方や推測が含まれています。 |
| 観点 | この記事には、中立的な観点を欠くおそれのある噂や利用者の見方が含まれています。 |

- 枠が一つなら、その文と（`mark_date` を渡したとき）`（2026年11月）`
- 二つ以上なら一つの枠に、見出しの文「この記事には次の問題があります。」と、各文の箇条（各項目に日付）を入れる
- 見た目は雛形の CSS で持つ。本家の枠の値に合わせて、枠線 `1px solid #a2a9b1`、左の縁 `10px solid #f28500`、背景 `#fbfbfb`、文は 90%、内側の余白 `.25em .5em`、幅 720px 以上で左右の外側の余白 10%。範囲の印の範囲は点線の下線（`border-bottom:1px dashed`）
- 印の `<sup>` はリンクにしない。文字が `[要出典]` のように数字でないので、`HTML-FOOTNOTE-PLAIN` には引っかからない

### 座標・ナビゲーションの箱・スタブ

- 座標は導入部の先頭（見出しの無い最初の文より前・Infobox より後）に置く。文字は本家と同じ `座標: 北緯35度40分52秒 東経139度46分02秒`（秒は整数二桁に丸める）。南緯・西経は `南緯`・`西経` と書き、度分秒は絶対値で出す
- 座標のリンクは GeoHack への外部リンク（`https://geohack.toolforge.org/geohack.php?language=ja&params=緯度_N_経度_E_type:種類&pagename=記事名`）。南緯は `S`、西経は `W` で、記事名はパーセントエンコードする。`type` を書かなければ `params` は緯度・経度だけ
- ナビゲーションの箱は「外部リンク」の箇条の後ろ、カテゴリ欄の前に、原稿に書いた順で並べる。表は `<table class="navbox"><caption>題</caption><tbody><tr><td><ul><li>項目</li>…</ul></td></tr></tbody></table>`。見出しの行き先（`name`）と、畳むかどうか（`state`）は HTML では使わない
- スタブはカテゴリ欄の前に `<div class="stub">この記事は書きかけです。</div>` を一つだけ置く。原稿の `stub` の値（本家のテンプレート名）は HTML では使わず、ウィキテキストにだけ出す
- 仮リンクは、赤字の内部リンク（`class="new"`。本家の赤リンクと同じ見た目）と、その後ろの `（英語）` の外部リンクにする。言語名は本家と同じく日本語（`en` → `英語`）で、知らないタグはそのまま出す
- 節スタブは、`[!節スタブ]` を書いた位置に `<div class="section-stub">この節は書きかけです。</div>` を出す。段落の中には書けない（行に単独で置く）
- 見た目は雛形の CSS で持つ（`.coordinates`・`.navbox`・`.stub`・`.section-stub`・`.new`・`.interlanguage-note`）。色や線は本家の値を写さず、こちらの配色に合わせた
### 出典の書式

ウィキテキストの素の記法（[wikitext.md](wikitext.md) の「出典の地の文」）と同じ。形は「著者「[題名のリンク]」媒体、発行者、日付、ページ、ISBN、閲覧日。備考」。

| 種類 | 例 |
| --- | --- |
| web | `著者「題」サイト、発行、2020年4月、2026年11月1日閲覧。` |
| book | `著者『書名』例文社、2020年9月1日、3-20頁、ISBN 978-4-00-000000-0。` |
| news | `記者「見出し」『架空新聞』発行元、2020年4月1日、5面。` |

題は web・news が「」、book が『』。`url` があれば題を外部リンクにする。日付は `2020-09-01` → `2020年9月1日` に直す（直せない書き方はそのまま）。

## 噂のある原稿（二つの版）

`write_html_both(article, article_type, updated, *, template=None, mark_date=None)` は、通常の版（`normal_view`）と噂込みの版（`rumor_view`）を一枚の HTML に入れ、記事名の下のボタンで切り替えて読めるようにする（2026-11-02、作者の決定。スキル `wiki-both`）。

```text
記事名の帯
[通常の記事][噂込みの記事]  噂込みの記事には、確かめられていない噂や利用者の見方が含まれます。
タブ
副題
<div class="variant" data-variant="normal">        通常の版の本文（枠・Infobox・導入部・節・脚注・関連項目・外部リンク・カテゴリ）
<div class="variant" data-variant="rumor" hidden>  噂込みの版の本文（同じ並び）
```

- 切り替えのボタンは記事名の帯のすぐ下（タブの上）に置く。二つの `<button type="button" data-show="…">` を並べ、今の版のボタンが `aria-pressed="true"` で押された見た目（青い枠と文字、内側の影）になる。横に断り書き「噂込みの記事には、確かめられていない噂や利用者の見方が含まれます。」（自作の文）を置く
- 開いたときは通常の版。噂込みの版の本文は `hidden` で隠す。スクリプトが動かない環境でも通常の版が見える（ボタンは押しても変わらない）
- ボタンを押すと、本文と目次（左の列と浮き窓の両方）が、その版のものに切り替わる。目次の一段目の項目に `data-variant` を付け、噂込みの版の項目は `hidden` にする。子の項目は親の項目ごと隠れるので印を付けない
- 脚注の番号は版ごとに振る（通常の版では使われない出典も、噂込みの版で使えばそちらで番号が付く）
- 噂込みの版の id（見出し・脚注の項目・脚注の印・戻りリンク・目次のリンク先）には接頭辞 `rumor-` を付ける（`rumor-section-2`・`rumor-cite_note-1`・`rumor-cite_ref-1-1`）。通常の版の id は噂の無い記事と同じ形
- 冒頭の警告の枠は版ごとに決める。噂込みの版には `観点` の枠が付き、通常の版には付かない
- 切り替えは、外部の資源を読まないインラインのスクリプトと CSS（`html_switch.py`）。雛形の目次の強調のスクリプトは、隠れた版の見出しも数えてしまう（隠れた見出しの位置は 0 になる）ので、切り替えのスクリプトが見えている見出しだけで強調を付け直す。雛形のスクリプトより後に置くので、同じ描画の中で後から上書きする
- 版を包む要素の閉じには `<!-- /variant -->` を添える

雛形は、噂の無い記事と同じものを使う。切り替えの差し込み口（下の「雛形」）は、`write_html` では空になって行ごと消えるので、噂の無い記事の HTML は変わらない。

## Infobox

- 類型が Infobox を持たない（`no_infobox`）なら出さない。値のある項目が一つもなければ出さない（値が空白だけの項目は「書かれていない」ものとする）
- 行は類型の定義の項目の順（部品をまたいで、定義に書いた順）で、項目名は日本語のまま表の見出しセル（`<th scope="row">`）に出す
- **定義にない項目は、定義の項目の後ろに、原稿に書いた順で並べる**（捨てない）。ウィキテキストの書き出し（本家の形）は定義にない項目を HTML コメントに残すが、HTML では画面に出す。定義にあるかどうかは `unknown_infobox_labels(article, article_type)`（`wikiskill.wikitext`）でも分かるので、入口で警告に使える
- `title_field`（定義が「記事名を既定値にする項目」とした項目）は行にしない。原稿に書かれていればその値が表の見出し（`<caption>`）になり、書かれていなければ記事名が見出しになる（ウィキテキストの書き出しが記事名で埋めるのと同じ結果）。その項目だけが書かれていても Infobox は出す（見出しだけの表になる）
- 値はウィキテキストの記法で書かれうるので、`[[リンク]]`・`'''太字'''`・`<br />`（改行）だけを HTML にし、ほかは文字のまま出す。`{{…}}`・壊れた記法も文字のまま。値の中の `[^キー]` は脚注にせず、書かれたままの文字で出す（ウィキテキストの書き出しも同じ）
- 狭い画面（640px 未満）では全幅になり、本文の前に積まれる

## 検査

`check_html(html)` は `HtmlFinding(rule, message)` の並びを返す（規則ごとにまとめ、同じ規則の中では文書に現れる順）。何もなければ空。書き出した HTML は、`write_html` の出力であれば通る。

| ID | 内容 |
| --- | --- |
| `HTML-PLACEHOLDER` | 雛形の差し込み口 `{{名前}}` が残っている |
| `HTML-TAG` | タグの開き閉じが合わない（閉じ忘れ・開始タグのない終了タグ・入れ子の食い違い・空要素の終了タグ）。`html.parser` で読む |
| `HTML-ID-DUPLICATE` | `id` が重なっている |
| `HTML-ANCHOR-MISSING` | `#…` のリンク先（目次・戻りリンクなど）に対応する `id` がない。リンク先が `#` だけのものは見ない |
| `HTML-FOOTNOTE-MISSING` | 本文から存在しない脚注（`#cite_note-…`）への参照がある |
| `HTML-FOOTNOTE-UNREFERENCED` | どこからも参照されない脚注の項目がある |
| `HTML-FOOTNOTE-PLAIN` | 脚注番号（`[3]`・`[注 1]`）がリンクにならず文字のまま残っている（リンクの外の文字だけを見る。`lang` 属性つきの `<span>`＝外国語の原文の中は見ない） |
| `HTML-FOOTNOTE-NUMBER` | 脚注への参照の表示（`[3]`）とリンク先（`#cite_note-3`）の番号が合わない。脚注の一覧の n 番目の項目の `id` が `cite_note-n` でない |
| `HTML-EXTERNAL-RESOURCE` | 外部の CSS・JS・画像などを読む部品がある（`<link>`、`src` 付きの `<script>`、外部アドレスの `<img>` など、`@import`、`url(外部のアドレス)`）。`data:` の画像は外部ではない |

脚注の項目の id は `cite_note-N`・`cite_note-note-N` で、前に英小文字とハイフンの接頭辞（噂込みの版の `rumor-`）が付いたものも脚注とみなす。`HTML-FOOTNOTE-MISSING`・`HTML-FOOTNOTE-UNREFERENCED`・`HTML-FOOTNOTE-NUMBER` は接頭辞の付いた脚注も見る。二つの版を入れた HTML では脚注欄（`ol.references`）が版ごとに分かれるので、一覧の n 番目の項目の番号は版ごとの脚注欄の中で見る。`write_html_both` の出力も、すべての規則を通る。

脚注番号の検査（`HTML-FOOTNOTE-PLAIN`）は、本文にたまたま `[1]` と書かれた文字も拾う。それは脚注と取り違えられる書き方なので、直すのが正しい。

## 例外

どれも `wikiskill.html_writer.HtmlError`（`ValueError` の仲間）。

| 例外 | 原因 |
| --- | --- |
| `HtmlError` | 記事の `type` と渡した類型の `id` が違う。雛形に知らない差し込み口がある |
| `UnknownFootnoteError` | 本文の印が指す出典・注釈が、設定欄の `[refs]`・`[notes]` に無い |
| `NestedFootnoteError` | 注釈の本文に、別の注釈への印がある |

## 雛形

`plugins/wiki-style-article/skills/wiki/assets/page-template.html`。差し込み口は `{{名前}}`（英大文字と下線）で、次の 17 種。差し込み口だけの行は、値が空ならその行ごと消える。

| 差し込み口 | 内容 |
| --- | --- |
| `{{PAGE_TITLE}}` | 記事名（`<title>` と `<h1>`） |
| `{{TOC}}` | 目次の項目（`<li>` の並び。左の列と浮き窓の二か所） |
| `{{NOTICES}}` | 冒頭の警告の枠 |
| `{{INFOBOX}}` | Infobox の表 |
| `{{LEAD}}` | 導入部 |
| `{{SECTIONS}}` | 原稿の節 |
| `{{FOOTNOTES}}` | 「脚注」の節 |
| `{{RELATED}}` | 「関連項目」の節 |
| `{{EXTERNAL_LINKS}}` | 「外部リンク」の節 |
| `{{CATEGORIES}}` | カテゴリ欄 |
| `{{UPDATED}}` | 最終更新の日時 |
| `{{VARIANT_STYLE}}` | 切り替えの部品の CSS（`<style>` の中） |
| `{{VARIANT_SWITCH}}` | 切り替えのボタンと断り書き（記事名の帯の直後） |
| `{{VARIANT_OPEN}}` | 通常の版を包む要素の開き（`{{NOTICES}}` の前） |
| `{{VARIANT_CLOSE}}` | 通常の版を包む要素の閉じ（`{{CATEGORIES}}` の後） |
| `{{RUMOR_VARIANT}}` | 噂込みの版の本文を包んだ要素（`{{VARIANT_CLOSE}}` の後） |
| `{{VARIANT_SCRIPT}}` | 切り替えのスクリプト（雛形のスクリプトの後） |

`VARIANT_` で始まる差し込み口と `{{RUMOR_VARIANT}}` は、`write_html_both` だけが値を入れる。`write_html` では空なので行ごと消える。

置き換えは一度の走査で行うので、値に含まれる `{{…}}` が再び置き換わることはない。

## 注意

書き出しのモジュールを `html.py` ではなく `html_writer.py` にしているのは、標準ライブラリの `html` と同じ名前にすると、`wikiskill/` の中を `sys.path` の先頭にして実行したときに標準ライブラリを隠してしまうため。
