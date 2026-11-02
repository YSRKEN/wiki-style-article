# wiki-style-article

題材を幅広く調べ、日本語版 Wikipedia の記事の型と作法で書いた記事を作る、AI のコーディング道具（Claude Code・Codex など）向けのスキルです。「/wiki 東京タワー」のように呼ぶと、調べた結果から、導入部・Infobox・目次・節・脚注・関連項目・カテゴリを備えた記事を、HTML 1 枚とウィキテキストで書き出します。

**非公式の道具です。** ウィキペディア（Wikipedia）およびウィキメディア財団とは関係がなく、公認・提携もありません。「Wikipedia」はウィキメディア財団の商標です。

## できること

- 題材の類型（人物・漫画・出来事・場所・製品・概念など 19 の基本型と 29 の細かい種類）を決め、類型ごとの節の並びと Infobox で書く
- 観点ごとに調べものの担当（サブエージェント）を最大 8 人並べ、出典つきの事実を集める
- 日本語版の作法（評価語を足さない、言葉を濁さない、常体、表記ガイドなど）に沿って書き、書き出す前にスクリプトで検査する
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

`plugins/wiki-style-article/skills/wiki/` のフォルダを、`~/.agents/skills/wiki/`（自分の全体）か、使うリポジトリの `.agents/skills/wiki/` にコピーします。`$wiki` か `/skills` で呼びます。

Codex には調べものの担当の定義を同梱していないので、担当は呼んだ会話と同じモデルで動きます。Codex の Web の検索は既定で索引から返す方式（`web_search = "cached"`）です。最新のページを取りたいときは、設定の `web_search` を `"live"` にします。

## 使い方

```text
/wiki 東京タワー
```

- 今いるフォルダの下に `東京タワー/` を作り、調べた材料（`材料/`）、原稿（`東京タワー.md`）、記事（`東京タワー.html` と `東京タワー.wikitext`）を置きます
- 題材の類型を決めかねたときは、書く前に一問だけ聞きます
- 渡すときに、類型、資料が無くて書かなかった観点、検査の結果を伝えます

調べた結果や手元の資料を渡して「百科事典みたいな記事にして」と頼むこともできます。

## 注意

- **出力は AI が生成した文章で、内容は検証されていません。** 事実には出典が付くので、使う前に出典を開いて確かめてください
- **ウィキペディア本体への投稿には使わないでください。** 日本語版・英語版とも、AI が生成した記事の文の投稿を制限・禁止しています
- **生成したページは手元で読むためのものです。Web に公開しないでください。** ページは本家の見た目に寄せてあり、本家の見た目をまねたサイトはウィキメディア財団の商標方針に触れえます。ページのフッタにも同じことを書いています
- 本家の記事の文を写す・訳す・近い言い換えをすると、CC BY-SA 4.0 の帰属表示と継承の義務が生じます。このスキルは本家の文を写さないように作っていますが、保証はしません
- 本家への負担を抑えるため、本家の記事は 1 題材につき 5 本までしか読みません。本家そのものは出典にしません
- Claude Code では、スキルが動いている間、Web の検索・ページの取得・ファイルの書き込みを確認なしで許します（SKILL.md の `allowed-tools`）。調べものの担当が取得や書き込みのたびに確認を出さないようにするためです。書き込みの許可は作業フォルダに限っていません
- 調べものの担当を並べるので、1 本の記事で使う量は、ふつうの会話より多くなります

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
```

`plugins/wiki-style-article/` の中身を変えたら、`plugins/wiki-style-article/.claude-plugin/plugin.json` の `version` を上げます（上げずに main へ push しようとすると、pre-push のフックが止めます）。設計の記録は `docs/` にあります。

## English

wiki-style-article is an unofficial skill for AI coding tools (Claude Code, Codex, and others) that researches a topic and writes a Japanese article in the style and conventions of the Japanese Wikipedia, output as a single HTML page and as wikitext. It writes **Japanese articles only**. It is not affiliated with or endorsed by Wikipedia or the Wikimedia Foundation; "Wikipedia" is a trademark of the Wikimedia Foundation. The output is AI-generated and unverified: do not post it to Wikipedia, and do not publish the generated pages on the web.

Install in Claude Code:

```bash
claude plugin marketplace add YSRKEN/wiki-style-article
claude plugin install wiki-style-article@wiki-style-article
```

Then run `/wiki <topic>`. Code is under the MIT License; the documents under `plugins/wiki-style-article/skills/wiki/references/` are under CC BY-SA 4.0.
