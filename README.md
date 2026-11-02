# wiki-style-article

題材を幅広く調べ、日本語版 Wikipedia の記事の型と作法で書いた記事を作る、AI のコーディング道具（Claude Code・Codex など）向けのスキルです。「/wiki 月ノ美兎」のように呼ぶと、調べた結果から、導入部・Infobox・目次・節・脚注・関連項目・カテゴリを備えた記事を、HTML 1 枚とウィキテキストで書き出します。

**非公式の道具です。** ウィキペディア（Wikipedia）およびウィキメディア財団とは関係がなく、公認・提携もありません。「Wikipedia」はウィキメディア財団の商標です。

## できること

- 題材の類型（人物・漫画・出来事・場所・製品・概念など 19 の基本型と 29 の細かい種類）を決め、類型ごとの節の並びと Infobox で書く
- 観点ごとに調べものの担当（サブエージェント）を最大 8 人並べ、出典つきの事実を集める
- 日本語版の作法（評価語を足さない、言葉を濁さない、常体、表記ガイドなど）に沿って書き、書き出す前にスクリプトで検査する
- 信頼できる資料で確かめられなかった事実も落とさず、本家と同じ `[要出典]`・`[信頼性要検証]` の印を付けて載せる。印のある記事には、冒頭に警告の枠が付く
- 本家がよく引くインターネットアーカイブ（web.archive.org）の保存版も取って確かめる
- 出力は、本家の今の見た目に寄せた HTML 1 枚（外部の資源を読まない）と、本家のテンプレートの形のウィキテキスト

記事は日本語だけで書きます。

## 要るもの

- Python 3.11 以上。無ければ [uv](https://docs.astral.sh/uv/) があれば足ります（uv が Python を取ってきます）
- Web の検索とページの取得ができる道具

## 入れ方

### Claude Code

```bash
claude plugin marketplace add YSRKEN/wiki-style-article
claude plugin install wiki-style-article@wiki-style-article
```

会話の中なら `/plugin marketplace add YSRKEN/wiki-style-article` と `/plugin install wiki-style-article@wiki-style-article` でも入れられます。更新は `claude plugin update wiki-style-article@wiki-style-article` です（自動では更新されません）。

### Codex

`plugins/wiki-style-article/skills/` の下の `wiki/`・`wiki-with-rumor/`・`wiki-both/` の 3 つのフォルダを、使うリポジトリの `.agents/skills/` にコピーします（`wiki-with-rumor` と `wiki-both` は隣の `wiki` のファイルを使うので、並べて置きます）。自分の全体で使うなら `~/.agents/skills/` に置きます（Codex の文書による）。呼ぶときは `$wiki`・`$wiki-with-rumor`・`$wiki-both`、または `/skills` です。

Codex には調べものの担当の定義を同梱していないので、設定の `[agents]` で既定のモデルを決めていなければ、担当は呼んだ会話と同じモデルで動きます。Codex の Web の検索は既定で索引から返す方式（`web_search = "cached"`）です。最新のページを取りたいときは、設定の `web_search` を `"live"` にします。

## 使い方

```text
/wiki 月ノ美兎
```

- 今いるフォルダの下に `月ノ美兎/` を作り、調べた材料（`材料/`）、原稿（`月ノ美兎.md`）、記事（`月ノ美兎.html` と `月ノ美兎.wikitext`）を置きます
- 題材の類型を決めかねたときは、書く前に一問だけ聞きます
- 本家の記事を読んだあと、調べ始める前に、扱う範囲・調べる広さ（さっと／ふつう／念入り）・ネタバレ（物語のある作品だけ）・冒頭の警告の枠の出し方を、1 問ずつ聞きます。`/wiki 月ノ美兎 念入り` のように呼ぶときに書いた項目は聞きません。「残りは推奨で」を選ぶと、以降の問いは推奨の答えで進みます
- 渡すときに、類型、印を付けて載せた事実の数、探しても何も見つからなかった観点、検査の結果を伝えます

調べた結果や手元の資料を渡して「百科事典みたいな記事にして」と頼むこともできます。

### 噂や考察も載せる

```text
/wiki-style-article:wiki-with-rumor 宝鐘マリン
```

`/wiki` は、本家の方針どおり、信頼できる資料に無い噂や利用者の考察（見方・推測・非難）を載せません。騒動や反響のように噂も含めてまとめたいときは、`wiki-with-rumor` を使います。

- 噂や考察を、関わる節の中に、誰の見方か（インターネット上の声、まとめサイトなど）を示して載せます
- 出どころの脚注と、`[信頼性要検証]`・`[独自研究?]` の印を付け、記事の冒頭に「観点」（中立性）などの警告の枠を付けます
- 特定の人や会社への非難のような強い主張は、互いに写しでない出どころが 2 つ以上あるときだけ載せます

### 通常の記事と噂込みの記事を 1 回で作る

```text
/wiki-style-article:wiki-both しぐれうい
```

調べものを 1 回だけ行い、通常の記事（`/wiki` と同じ）と噂込みの記事（`wiki-with-rumor` と同じ）の両方を作ります。`wiki` と `wiki-with-rumor` を別々に流すと調べものが 2 回走るので、両方を読みたいときはこちらを使います。

- HTML は 1 枚です。開いたときは通常の記事で、記事名の下のボタンで噂込みの記事に切り替わります
- ウィキテキストは `しぐれうい.wikitext`（通常）と `しぐれうい.噂込み.wikitext`（噂込み）の 2 本です

## 注意

- **出力は AI が生成した文章で、内容は検証されていません。** 事実には出典が付くので、使う前に出典を開いて確かめてください
- **ウィキペディア本体への投稿には使わないでください。** 英語版のガイドラインは AI で記事の文を作ることを禁じ、日本語版のガイドラインは AI が生成した文章を検証せずにそのまま投稿しないよう求めています
- **生成したページは手元で読むためのものです。Web に公開しないでください。** ページは本家の見た目に寄せてあり、ウィキメディア財団の商標方針は、本家の見た目をまねたサイトを作らないよう求めています（§5.1）。ページのフッタにも同じことを書いています
- 本家の記事の文を写す・訳す・近い言い換えをすると、CC BY-SA 4.0 の帰属表示と継承の義務が生じます。このスキルは本家の文を写さないように作っていますが、保証はしません
- 本家への負担を抑えるため、本家の記事は 1 題材につき 5 本までしか読みません。本家そのものは出典にしません
- `wiki-with-rumor` の記事には、確かめられていない噂や、実在の人や会社への非難が含まれることがあります。中立的ではなく、事実として扱えません
- ページの取得は、まず道具の Web の取得を使い、取れなければ同梱の取得のコマンド（Python の標準ライブラリ、証明書の検証に失敗したときは curl）、それでも取れなければ鍵なしの Jina の Reader（`r.jina.ai`）を使います。Jina を使うと、取るページの URL が Jina のサーバーを通ります。PDF は同梱のコマンドで作業フォルダの下の `資料/` に保存し、道具のファイルの読み取りで読みます
- Claude Code では、スキルが動いている間、Web の検索・ページの取得・ファイルの読み取りと書き込みと書き換え・同梱のスクリプト（`sh …wiki.sh …`）の実行を確認なしで許します（SKILL.md の `allowed-tools`）。調べものの担当が取得や書き込みのたびに確認を出さないようにするためです。書き込みと書き換えの許可は作業フォルダに限っていません
- 調べものの担当を並べるので、1 本の記事で使う量は、ふつうの会話より多くなります。2026年11月の試し（「カップヌードル」、主の会話も担当も Sonnet、担当 6 人）では、1 本に約 6 分かかり、API の料金に換算して約 5 ドル分でした。0.4.0 からは担当が出典の全文（PDF を含む）を読み、ページを開く回数の上限も 40 回に広げたので、これより多くかかることがあります（0.4.0 では測っていません）

## ライセンス

- コード（スクリプト・SKILL.md・雛形・担当の定義・試験・docs）: [MIT License](LICENSE)
- `plugins/wiki-style-article/skills/wiki/references/` の文書: [CC BY-SA 4.0](plugins/wiki-style-article/skills/wiki/references/LICENSE.md)。日本語版ウィキペディアの方針・ガイドラインのページを読み、自分の言葉で要約して書いたものです

## 開発

```bash
uv sync
uv run scripts/check.py
```

`check.py` は ruff・ruff format・pyright（strict）・pytest をまとめて流します。clone し直したら、次も流してください。

```bash
git config core.hooksPath .githooks
git config branch.main.mergeoptions --no-ff
git config pull.ff only
git config push.followTags true
```

`plugins/wiki-style-article/` の中身を変えたら、`plugins/wiki-style-article/.claude-plugin/plugin.json` の `version` を上げ、`git tag -a v<版> -m "v<版>"` でタグを打ちます（版を上げ忘れたり、版のタグが無かったりすると、main への push を pre-push のフックが止めます）。main へのマージの前には、pre-merge-commit のフックが `scripts/check.py` を流し、落ちたらマージを止めます。設計の記録は `docs/` にあります。

## English

wiki-style-article is an unofficial skill for AI coding tools (Claude Code, Codex, and others) that researches a topic and writes a Japanese article in the style and conventions of the Japanese Wikipedia, output as a single HTML page and as wikitext. It writes **Japanese articles only**. It is not affiliated with or endorsed by Wikipedia or the Wikimedia Foundation; "Wikipedia" is a trademark of the Wikimedia Foundation. The output is AI-generated and unverified: do not post it to Wikipedia, and do not publish the generated pages on the web.

Install in Claude Code:

```bash
claude plugin marketplace add YSRKEN/wiki-style-article
claude plugin install wiki-style-article@wiki-style-article
```

Then run `/wiki <topic>`. Before researching, it asks a few questions one at a time (scope, research depth, spoilers for works with a story, and when to show the warning banners); you can skip the rest with the recommended answers. Code is under the MIT License; the documents under `plugins/wiki-style-article/skills/wiki/references/` are under CC BY-SA 4.0.
