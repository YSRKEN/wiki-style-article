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
| `election` | 選挙 | `event` | なし | ― |
| `castle` | 城 | `place` | `日本の城郭概要表` | 都道府県 |
| `river` | 河川 | `place` | `Infobox 河川` | 水源、河口 |
| `mountain` | 山 | `place` | `Infobox 山` | 標高、所在地 |
| `island` | 島 | `place` | `Infobox 島` | 面積、所在地 |
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
- **選挙**: 国政選挙の本家テンプレート（`Infobox 衆議院議員総選挙`・`Infobox 参議院議員通常選挙`）は、内閣・公示日・投票日などを回から別のテンプレートで引き、党ごとの行が `1党名`〜`14党首` の番号つき引数になっている。番号つきの引数は収録しない方針なので、代わりに汎用の `Infobox Election` を `election` に付け、国政選挙では選挙名・投票日・選挙制度・改選数・有権者数・投票率だけを入れ、内閣・公示日・解散日と党別の議席・得票は本文の節で補う。
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

| キー | 必須 | 内容 |
| --- | --- | --- |
| `template` | 必須 | 本家のテンプレート名（`Template:` は付けない） |
| `[type.infobox.fields]` | 必須 | 項目の並び。`"日本語の項目名" = "テンプレートの引数名"`。書いた順が表示の順。一つ以上 |
| `required` | 任意 | 原稿に必ず書く項目の、日本語の項目名の配列。`fields` にある名前だけ |
| `title_field` | 任意 | 記事名を既定値にする項目の項目名。原稿に書かれていなければ、書き出しは記事名を入れる。`required` にはできない |
| `placement` | 任意 | `"top"`（記事の最上部。既定）か `"lead"`（導入部の中） |
| `unverified` | 任意 | 引数名を本家のテンプレートで確かめられていない項目の項目名の配列 |

### 検査される誤り

読み込みで次を弾く。すべて `wikiskill.types.TypeRegistryError` の仲間の例外になる。

| 例外 | 原因 |
| --- | --- |
| `TypeSchemaError` | TOML として読めない、キーが足りない・未知（書き間違いを見つけるため）、値の型や書式が合わない、`id` が使えない、`placement` が不正、`parents` が空・重複 |
| `DuplicateTypeError` | `id` の重複 |
| `UnknownParentError` | `parents` の型が定義にない |
| `ParentNotBaseError` | `parents` の型が基本型でない（細かい種類、または自分自身） |
| `InfoboxError` | `required`・`unverified`・`title_field` が `fields` にない、`required` に重複がある、`title_field` が `required`、項目名が部品をまたいで重複、同じ部品で引数名が重複、`fields` が空、`no_infobox` と `[[type.infobox]]` の矛盾（どちらも無い場合も） |
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

## 根拠と方針

- テンプレート名と引数名は、2026-11-02 に ja.wikipedia.org の `Template:` の本文（MediaWiki API）を取り、定義の引数がすべて本文の引数として現れることを機械で照合した。そのため確かめられなかった引数はない（`unverified` は将来の追加用の印で、いま使っている型はない）。確かめたのは、引数の名前が存在することで、その値の書式の細部までではない。2026-11-03 に足した `election`・`mountain`・`island`・`lake`・`peninsula`・`road`・`railway-station` は、日本語の引数を最小限だけ渡して MediaWiki API の `action=parse` で描画し、項目が出ることを確かめた。描画を確かめていない引数は定義に入れていない。
- 必須の項目は、本家で多くの記事が埋めている、題材を一目で掴める項目に絞る。テンプレート自身が必須とする項目（`TemplateData` の `required` やテンプレート本文）を土台にし、迷ったら必須にしない。選んだ理由は `types.toml` の各型のコメントにある。
- 記事名と同じになる項目（名称・タイトルなど）は `title_field` にして必須にしない。人物の氏名だけは、記事名に「(8代目)」のような曖昧さ回避が付くので `title_field` にせず必須にしている。
- 日本語の項目名は、テンプレートが日本語の引数を持つ型ではその名前、英語の引数だけの型（`author`・`game`・`aviation-accident` など）では英語の引数に対応する日本語を付けた。
