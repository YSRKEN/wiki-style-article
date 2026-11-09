# 記事の類型

記事は題材の種類（類型）ごとに、節の並びと Infobox の項目が変わる。原稿の `type` に類型の ID を書く（[原稿の書き方](source-format.md)）。類型の定義は `plugins/wiki-style-article/skills/wiki/assets/types.toml` にあり、`plugins/wiki-style-article/skills/wiki/scripts/wikiskill/types.py` が読む。

## 二層の構成

- **基本型**（19）: 節の並びや書き方が決まる型。`parents` を持たない。
- **細かい種類**（36）: 基本型の一つ以上に「寄せる」型。節の並びは寄せ先に従い、Infobox だけを自分のものに差し替える。声優・スポーツ選手・歌手は人物へ、バンド・お笑いコンビ・スポーツクラブ・行政機関・学術団体は組織へ、鉄道車両・航空機・自動車・ソフトウェア・Web サービスは製品へ、判例・選挙は出来事へ、山・島・湖・半島・道路・鉄道駅は場所へ寄せている。

原稿の `type` には、基本型か細かい種類のどちらの ID も書ける。人物は存命と故人で基本型が分かれるので、細かい種類（声優など）は両方に寄せてある。どちらの節の並びを使うかは、書き手が `type` の寄せ先（`parents`）と題材から決める。

## 類型の一覧

必須の項目は、原稿の `[infobox]` に必ず書く項目（書いていなければ検査で指摘する）。

### 基本型

| ID | 日本語名 | Infobox のテンプレート | 必須の項目 |
| --- | --- | --- | --- |
| `person-living` | 人物（存命） | `Infobox 人物` | 名前、生年月日、職業 |
| `person-deceased` | 人物（故人） | `Infobox 人物` | 名前、生年月日、没年月日、職業 |
| `manga` | 漫画 | `Infobox animanga/Header` ＋ `Infobox animanga/Manga` ＋ `Infobox animanga/Footer` | 作者、出版社 |
| `anime` | アニメ | `Infobox animanga/Header` ＋ `Infobox animanga/TVAnime` ＋ `Infobox animanga/Footer` | 放送局、放送開始 |
| `game` | ゲーム | `コンピュータゲーム` | ジャンル、対応機種、開発元 |
| `film` | 映画 | `Infobox Film` | 監督、公開、製作国 |
| `novel-drama` | 小説・ドラマ | `基礎情報 文学作品` | 作者、国 |
| `music-work` | 音楽作品（曲・アルバム） | `Infobox Single` | アーティスト、リリース |
| `event` | 出来事（事故・災害・事件） | `Infobox 事件・事故` | 場所、日付 |
| `place` | 場所 | なし | ― |
| `organization` | 組織・企業・団体 | `基礎情報 会社` | 種類、業種 |
| `product` | 製品 | `Infobox product` | 種類、会社名 |
| `concept` | 概念 | なし | ― |
| `meme` | ネットミーム | なし | ― |
| `racehorse` | 競走馬 | `競走馬` | 性別、生年月日、父、母、競走成績 |
| `country-municipality` | 国・自治体 | `基礎情報 国` | 日本語国名、公式国名、首都 |
| `law` | 法令 | `日本の法令`（導入部の中） | 種類、効力 |
| `species` | 動植物 | `生物分類表` | 科、学名 |
| `festival` | 祭礼・宗教行事 | `イベントインフォメーション` | 開催時期、会場 |

### 細かい種類

| ID | 日本語名 | 寄せ先 | Infobox のテンプレート | 必須の項目 |
| --- | --- | --- | --- | --- |
| `voice-actor` | 声優 | `person-living`、`person-deceased` | `声優` | 名前 |
| `singer` | 歌手 | `person-living`、`person-deceased` | `Infobox Musician` | 名前、ジャンル |
| `baseball-player` | 野球選手 | `person-living`、`person-deceased` | `Infobox baseball player` | 選手名、生年月日、守備位置 |
| `soccer-player` | サッカー選手 | `person-living`、`person-deceased` | `サッカー選手` | 名前、生年月日、ポジション |
| `pro-wrestler` | プロレスラー | `person-living`、`person-deceased` | `Infobox プロレスラー` | 名前 |
| `actor` | 俳優 | `person-living`、`person-deceased` | `ActorActress` | 芸名 |
| `author` | 作家 | `person-living`、`person-deceased` | `Infobox 作家` | 名前、職業 |
| `manga-artist` | 漫画家 | `person-living`、`person-deceased` | `Infobox 漫画家` | 名前 |
| `light-novel` | ライトノベル | `novel-drama` | `Infobox animanga/Header` ＋ `Infobox animanga/Novel` ＋ `Infobox animanga/Footer` | 著者、出版社 |
| `tv-drama` | テレビドラマ | `novel-drama` | `基礎情報 テレビ番組` | ジャンル、放送局、放送期間 |
| `album` | アルバム | `music-work` | `Infobox Album` | 種別、アーティスト、リリース |
| `aviation-accident` | 航空事故 | `event` | `Infobox aircraft occurrence` | 日付、場所、機種 |
| `battle` | 戦闘 | `event` | `Battlebox` | 日付、場所、結果 |
| `court-case` | 判例 | `event` | なし | ― |
| `election` | 選挙 | `event` | `Infobox Election` | 投票日 |
| `castle` | 城 | `place` | `日本の城郭概要表` | 都道府県 |
| `river` | 河川 | `place` | `Infobox 河川` | 水源、河口 |
| `mountain` | 山 | `place` | `Infobox 山` | 標高、所在地 |
| `island` | 島 | `place` | `Infobox 島` | 所在地、面積 |
| `lake` | 湖 | `place` | `Infobox 湖` | 所在地、面積 |
| `peninsula` | 半島 | `place` | `Infobox 半島` | 面積、所属国・地域 |
| `road` | 道路 | `place` | `Infobox road` | 起点、終点 |
| `railway-station` | 鉄道駅 | `place` | `駅情報` | 所在地、所属事業者 |
| `band` | バンド | `organization` | `Infobox Musician` | ジャンル、メンバー |
| `comedy-duo` | お笑いコンビ | `organization` | `Infobox お笑いコンビ` | メンバー、結成年 |
| `soccer-club` | サッカークラブ | `organization` | `サッカークラブ` | リーグ、ホームタウン |
| `government-agency` | 行政機関 | `organization` | `行政官庁` | 国名 |
| `academic-body` | 学術団体 | `organization` | `基礎情報 非営利団体` | 団体種類、設立 |
| `food-drink` | 食品・飲料 | `product` | `基礎情報 食品・飲料` | 販売会社、販売開始年 |
| `railcar` | 鉄道車両 | `product` | `鉄道車両` | 運用者、製造年 |
| `aircraft` | 航空機 | `product` | `Infobox 航空機` | 用途、製造者 |
| `automobile` | 自動車 | `product` | `Infobox 自動車のスペック表` | 販売期間、ボディタイプ |
| `software` | ソフトウェア | `product` | `Infobox Software` | 開発元、種別 |
| `web-service` | Web サービス | `product` | `Infobox Website` | タイプ、運営者 |
| `japan-city` | 日本の市 | `country-municipality` | `日本の市` | 都道府県、所在地 |
| `foreign-festival` | 外国の祭り・祝日 | `festival` | `Infobox holiday` | 日付 |

### 例外と使い分け

- **Infobox を持たない型**: `place`・`concept`・`meme`・`court-case`。概念とネットミームは、秀逸・良質の記事が Infobox を付けていない。場所は城・河川・山などで本家のテンプレートがばらばらなので、基本型は持たず、`castle`・`river`・`mountain` のように種類で選ぶ。民事の判例は Infobox を持たない（刑事事件は `event` の Infobox 事件・事故が使える）。
- **導入部の中に置くテンプレート**: `law` の `日本の法令` は、記事の最上部ではなく導入部の中に置く（`placement = "lead"`）。外国の法令は `{{Law}}` を使うが、まだ収録していない。
- **音楽作品**: 曲とアルバムを `music-work` にまとめ、基本型の Infobox は曲（`Infobox Single`）、アルバムは `album` で差し替える。
- **収録していない種類**: 騎手、野球球団、議会（`Infobox Legislature`）、機関車（`機関車情報表`）、海外の会社（`Infobox Company`）、外国の自治体（`Infobox settlement`）、まだ型の無い場所（博物館・競馬場・世界の市など）。必要になったら `types.toml` に細かい種類として足す。
- **選挙**: 国政選挙の本家テンプレート（`Infobox 衆議院議員総選挙`・`Infobox 参議院議員通常選挙`）は、内閣・公示日・投票日などを回から別のテンプレートで引き、党ごとの行が `1党名`〜`14党首` の番号つき引数になっている。番号つきの引数は収録しない方針なので、代わりに汎用の `Infobox Election` を `election` に付け、国政選挙では選挙名・投票日・選挙制度・改選数・有権者数・投票率だけを入れ、内閣・公示日・解散日と党別の議席・得票は本文の節で補う。開票結果の地図は「地図」の項目（`map_image`）に書く。本家の `map_image` は `File:` を付けない素のファイル名を取るので、この項目の書式は `name` にしてある（原稿には本文の画像と同じ `![キャプション](相対の道)` を書き、書き出しがファイル名だけにする）。
- **収録していない引数**: 番号を付けて行を増やす引数（サッカー選手の `クラブ1`・`出場1`、戦闘の `combatant1`、国政選挙の `1党名`、鉄道駅の `隣の駅` など）と、書式の指定用の引数。

## 定義の書き方（`types.toml`）

```toml
[[type]]
id = "manga"
name = "漫画"

[[type.infobox]]
template = "Infobox animanga/Header"
title_field = "タイトル"
[type.infobox.fields]
"タイトル" = "タイトル"
"ジャンル" = "ジャンル"

[[type.infobox]]
template = "Infobox animanga/Manga"
required = ["作者", "出版社"]
[type.infobox.fields]
"作者" = "作者"
"出版社" = "出版社"
```

`[[type]]` が一つの型で、順に読まれる。

| キー | 必須 | 内容 |
| --- | --- | --- |
| `id` | 必須 | 原稿の `type` に書く値。英小文字とハイフンだけ（数字は不可）。定義の中で一意 |
| `name` | 必須 | 日本語名 |
| `parents` | 任意 | 細かい種類のとき、寄せ先の基本型の ID の配列。空にはできない。基本型は書かない |
| `no_infobox` | どちらか | Infobox を持たない型は `true` と明示する |
| `[[type.infobox]]` | どちらか | Infobox を持つ型は、テンプレート一つにつき一つ書く。`no_infobox = true` とは同時に書けない |

`[[type.infobox]]` は Infobox のテンプレート一つ分で、書いた順に重ねる。漫画のように Header・本体・Footer の三部を重ねる型は、三つ書く。

画像の項目は `[type.infobox.image_fields]` で項目ごとに宣言する。本家のテンプレートが `[[File:{{{引数}}}]]` と包む型は `"name"`、原稿の記法をそのまま引数に入れる型は `"file"` にする。同じ「生物分類表」でも、生息図は `name`、画像は `file` のように、テンプレートと項目の組で決める。宣言していない項目に `![キャプション](道)` を書くと `INFOBOX-IMAGE-UNDECLARED` の警告になる（[checks.md](checks.md)）。

| キー | 必須 | 内容 |
| --- | --- | --- |
| `template` | 必須 | 本家のテンプレート名（`Template:` は付けない） |
| `[type.infobox.fields]` | 必須 | 項目の並び。`"日本語の項目名" = "テンプレートの引数名"`。書いた順が表示の順。一つ以上 |
| `required` | 任意 | 原稿に必ず書く項目の、日本語の項目名の配列。`fields` にある名前だけ |
| `title_field` | 任意 | 記事名を既定値にする項目の項目名。原稿に書かれていなければ、書き出しは記事名を入れる。`required` にはできない |
| `placement` | 任意 | `"top"`（記事の最上部。既定）か `"lead"`（導入部の中） |
| `unverified` | 任意 | 引数名を本家のテンプレートで確かめられていない項目の項目名の配列 |
| `[type.infobox.image_fields]` | 任意 | 画像の項目。`"日本語の項目名" = "書式"`。書式は `"name"`（本家の引数が素のファイル名）か `"file"`（`[[ファイル:名前\|thumb\|キャプション]]`）。項目は `fields` にある名前だけ |

### 検査される誤り

読み込みで次を弾く。すべて `wikiskill.types.TypeRegistryError` の仲間の例外になる。

| 例外 | 原因 |
| --- | --- |
| `TypeSchemaError` | TOML として読めない、キーが足りない・未知（書き間違いを見つけるため）、値の型や書式が合わない、`id` が使えない、`placement` が不正、`parents` が空・重複 |
| `DuplicateTypeError` | `id` の重複 |
| `UnknownParentError` | `parents` の型が定義にない |
| `ParentNotBaseError` | `parents` の型が基本型でない（細かい種類、または自分自身） |
| `InfoboxError` | `required`・`unverified`・`title_field` が `fields` にない、`required` に重複がある、`title_field` が `required`、項目名が部品をまたいで重複、同じ部品で引数名が重複、`fields` が空、`image_fields` の項目名が `fields` にない、`title_field` が画像の項目、`no_infobox` と `[[type.infobox]]` の矛盾（どちらも無い場合も） |
| `UnknownTypeError` | 定義にない型の ID を引いた |

### 使い方

```python
from wikiskill.types import load_default_registry

registry = load_default_registry()  # 同梱の types.toml
manga = registry["manga"]  # ID から引く（なければ UnknownTypeError）
[p.template for p in manga.infobox]  # 部品の並び
[f.label for f in manga.required_fields]  # 必須の項目名
registry.kinds_of("organization")  # 組織に寄せている細かい種類
```

別のファイルは `read_registry_file(path)`、文字列は `parse_registry(text)` で読む。結果はすべて変更できないデータ（`TypeRegistry`・`ArticleType`・`InfoboxPart`・`InfoboxField`）。

## 任意のテンプレートと TemplateData

型の定義に無いテンプレートは、原稿の `[infobox]` に `_template = "Infobox 人物"` と書いて呼べる（[原稿の書き方](source-format.md)）。このとき項目名は本家の引数名としてそのまま書き出され、型の定義による必須の検査も受けない。そこで、本家の TemplateData（テンプレートの引数定義）を同梱し、この呼び方に効かせている。データは `plugins/wiki-style-article/skills/wiki/assets/templatedata.toml`、読み込みは `plugins/wiki-style-article/skills/wiki/scripts/wikiskill/templatedata.py`。

```toml
[infobox]
_template = "Infobox 人物"
"氏名" = "甲野 乙女"
"画像" = "![顔](images/顔.png)"
```

### 効くこと

| 何を | どうする |
| --- | --- |
| 引数名とラベルの両受け | 原稿の項目名は、引数名・別名（`aliases`）・ラベル（`label`）のどれでもよい。ウィキテキストには必ず引数名で書き出す。上の `氏名` の別名は `名前`・`name` なので、`"name" = …` と書いても `| 氏名 = …` になる |
| 未知の項目名 | 引数名・別名・ラベルのどれにも当たらない項目名は `INFOBOX-UNKNOWN-FIELD`（警告） |
| 必須の引数 | TemplateData が `required = true` とする引数が原稿に無ければ `INFOBOX-MISSING`（エラー）。型の定義の必須と同じ ID・同じ重み |
| 画像の項目 | `type = "wiki-file-name"` の引数は、本家が `[[File:]]` で包んで受け取る。`_image_fields` を書いていないときは、その引数を自動で `"name"` の書式（素のファイル名）として扱う |

- 同じ項目名が複数の引数に当たるとき（引数名の完全一致が無く、別名とラベルが別の引数を指すとき）は、どちらか決めずに原稿の項目名のまま書き出す。引数名の完全一致が一つあれば、それを優先する
- `_image_fields` を書いたときは、自動の判定よりそちらが優先する。自動の判定は、原稿の項目名を引数名に直した後で行うので、引数名でもラベルでも効く
- HTML の見出しは、引数に決まったらそのラベル（無ければ引数名）、決まらなければ原稿の項目名にする

### 同梱の範囲

- 2026-11-05 に MediaWiki API（`action=templatedata`）から取った 86 件。内訳は、`types.toml` が参照するテンプレートのうち TemplateData があるもの 31 件と、`Category:基礎情報テンプレート` の直下と直下のサブカテゴリにあるもの 61 件（重なり 6 件）
- 本家に TemplateData が無いテンプレート（`基礎情報 国`・`生物分類表`・`Infobox お笑いコンビ` など、`types.toml` の参照先で 20 件）は載せていない。載せられないものは検査しない（従来どおり素通し）
- 同梱に無いテンプレートも検査しない。引数が 0 件の TemplateData（`Infobox Officeholder`）は「引数なし」として扱い、未知の項目名とは言わない
- 引数ごとに持つのは、引数名・別名・ラベル・必須か・画像か・説明。引数の説明文は落としてある（解決に使わないため）
- 86 件と少ないのは、「TemplateData を持つものだけ載せる」方針のため。本家の Infobox は数千あるが、TemplateData を持つのはその一部

### 使い方

```python
from wikiskill.templatedata import load_default_templatedata

registry = load_default_templatedata()  # 同梱の templatedata.toml（無ければ空の登録簿）
data = registry.find("Infobox 人物")  # 無ければ None（呼び出し側は素通しにする）
param = data.resolve("名前")  # 引数（TemplateParam）。決められなければ None
param.name  # "氏名"（ウィキテキストに出す引数名）
param.heading  # 表示に使う名前（ラベル、無ければ引数名）
```

`registry.find` は `Template:`・`テンプレート:` の接頭辞と `_` を落として名前をそろえる。TOML は `parse_templatedata(text)`、ファイルは `read_templatedata_file(path)` でも読める。結果は変更できないデータ（`TemplateDataRegistry`・`TemplateData`・`TemplateParam`）。

### 取り直し

```bash
sh plugins/wiki-style-article/skills/wiki/scripts/wiki.sh templatedata
sh plugins/wiki-style-article/skills/wiki/scripts/wiki.sh templatedata --from-types
sh plugins/wiki-style-article/skills/wiki/scripts/wiki.sh templatedata --fetch
sh plugins/wiki-style-article/skills/wiki/scripts/wiki.sh templatedata --fetch --template "Infobox 城"
```

- 引数なし: 同梱の件数とテンプレート名の一覧。`--template` を付けると、その名前だけを出す（同梱に無ければ標準エラーに出す）
- `--from-types`: `types.toml` が参照するテンプレートのうち、同梱にあるものと、TemplateData が無くて載せられないもの
- `--fetch`: 本家から取り直して同梱の TOML を書き換える。対象は同梱の名前と `types.toml` の参照先（`--from-types` を付けると `types.toml` の参照先だけ）。`--template` で足せる。`--out` で別の道に書ける
- `--fetch` はネットワークに出る。`build` と `check` は同梱だけで動くので、ふだんは取り直さない
- 取り直しは 1 回 40 件ずつ、間を 1〜3 秒あけて叩く。429 は待って取り直す。全件だと数分かかる
- TOML は `[[template]]` の並びで、`name`・`description`・`params` を持つ。`params` の各要素は `name`・`label`・`required`・`image`・`aliases`・`description`。並びはテンプレートが名前順、引数が API の宣言順なので、同じ中身なら同じファイルになる
- 読めない TOML とテンプレート名の重複は `TemplateDataError` の仲間の例外（`TemplateDataSchemaError`・`DuplicateTemplateError`）で止まる

## 根拠と方針

- テンプレート名と引数名は、2026-11-02 に ja.wikipedia.org の `Template:` の本文（MediaWiki API）を取り、定義の引数がすべて本文の引数として現れることを機械で照合した。そのため確かめられなかった引数はない（`unverified` は将来の追加用の印で、いま使っている型はない）。確かめたのは、引数の名前が存在することで、その値の書式の細部までではない。2026-11-03 に足した `election`・`mountain`・`island`・`lake`・`peninsula`・`road`・`railway-station` は、日本語の引数を最小限だけ渡して MediaWiki API の `action=parse` で描画し、項目が出ることを確かめた。描画を確かめていない引数は定義に入れていない。
- 必須の項目は、本家で多くの記事が埋めている、題材を一目で掴める項目に絞る。テンプレート自身が必須とする項目（`TemplateData` の `required` やテンプレート本文）を土台にし、迷ったら必須にしない。選んだ理由は `types.toml` の各型のコメントにある。
- 記事名と同じになる項目（名称・タイトルなど）は `title_field` にして必須にしない。人物の氏名だけは、記事名に「(8代目)」のような曖昧さ回避が付くので `title_field` にせず必須にしている。
- 日本語の項目名は、テンプレートが日本語の引数を持つ型ではその名前、英語の引数だけの型（`author`・`game`・`aviation-accident` など）では英語の引数に対応する日本語を付けた。
