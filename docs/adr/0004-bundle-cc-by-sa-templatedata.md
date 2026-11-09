# 本家の TemplateData は、説明文ごと CC BY-SA 4.0 の表示を付けて同梱する

任意の本家テンプレートを原稿から呼ぶ（`_template`）とき、項目名を本家の引数名に寄せ、必須の引数の欠けを検査するために、日本語版ウィキペディアのテンプレートの TemplateData を `assets/templatedata.toml` に同梱する（PR #12）。TemplateData には引数名のほかに、テンプレートと引数の説明文（`description`）と表示名（`label`）が入る。TemplateData はテンプレートのページか、その `/doc` の下位ページに書かれていて、日本語版ウィキペディアのサイトの許諾は CC BY-SA 4.0 である（2026-11-10 に API の `siteinfo` の `rightsinfo` で確かめた）。説明文と表示名は、その許諾に従う文として扱う。

説明文を落とさずに同梱し、ファイルの冒頭と README に出典と許諾（CC BY-SA 4.0）を書き、このファイルだけはリポジトリの MIT License の対象外とする（2026-11-09 に依頼者が「帰属を付けて残す」と決めた）。HTML の見出しに本家の表示名を使うので、表示名を落とすと見た目が本家から離れる。表示は `format_templatedata` が書き出すので、`templatedata --fetch` で取り直しても消えない。

## Considered Options

- **説明文と表示名を外し、引数名・別名・必須・画像の印だけを同梱する**: 引数名は事実の並びで、許諾の心配はほぼ消える。ただし、HTML の見出しに本家の表示名を使えなくなる。
- **同梱しない**: 使う人が `--fetch` で手元に取る。取るまで、任意のテンプレートの引数の検査が効かない。

## Consequences

- リポジトリの中に、MIT ではないファイルが `references/` の文書のほかにもう一つ増える。README の「ライセンス」に両方を挙げる。
- `templatedata.toml` を写して別の所で使う人は、CC BY-SA 4.0 の表示と継承の条件に従う。
- 同梱の画像（`assets/images/`）は、これと違い PD と CC0 だけにしている。配布の条件を増やさないため（`assets/images/README.md` の「なぜ PD と CC0 だけなのか」）。
