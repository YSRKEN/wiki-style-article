# 同梱の画像の形

原稿から決まった画像を短く呼べるように、よく使う国旗の SVG を目録（`manifest.toml`）付きで置く。

## 原稿での書き方

```markdown
![日本の国旗](bundle:flags/jp.svg)
```

`bundle:` の後ろは目録の `key`。HTML には今までどおり data: の URI として埋め込み、
ウィキテキストには目録の `file`（本家 Commons のファイル名）で
`[[ファイル:Flag of Japan.svg|thumb|日本の国旗]]` と書く。

目録に無いキーを指すと、今までどおり `IMAGE-MISSING`（「画像が無い」）になる。
原稿からの相対の道（`zu.png` など）は今までどおり使える。

## 目録（manifest.toml）

1 件は次の 6 つ。`author` だけは任意。

| 項目 | 意味 |
| --- | --- |
| `key` | 原稿に書く名前（`bundle:` の後ろ）。重複は許さない |
| `path` | このフォルダからの同梱ファイルの道（`..` と絶対パスは許さない） |
| `file` | 本家 Commons のファイル名。ウィキテキストにこの名前で書く |
| `license` | `PD` か `CC0` だけ |
| `source` | 出典の Commons のファイルページの URL |
| `author` | 作者。上流に書かれていなければ省く（表では「—」） |

目録が壊れている（TOML として読めない、キーが重複、実ファイルが無い、など）と、
読み込みの時点で `BundleError` で止まる。黙って空の画像を出すことはしない。

## なぜ PD と CC0 だけなのか

この repo はコードが MIT、文書が CC-BY-SA-4.0 で配っている。CC BY は表示、CC BY-SA は
表示に加えて継承（同じライセンスでの配布）を求めるので、同梱した画像をそのまま再配布する
ときに条件が増える。PD（パブリックドメイン）と CC0（権利の放棄・献呈）は条件が無いため、
コードや文書のライセンスと混ぜても配布条件が濁らない。**迷ったら入れない。**

採用した 60 件は、Wikimedia Commons の API（`action=query&prop=imageinfo&iiprop=url|extmetadata`、
2026-11-05 に取得）で `LicenseShortName` が `Public domain`、`Copyrighted` が `False` で
あることを 1 件ずつ確かめた。目録の `license` はこの監査結果を `PD` に正規化したもの。
ファイルは取得したまま同梱し、改変していない（合計 369,059 バイト）。

## 同梱の一覧

| キー | 本家のファイル名 | ライセンス | 出典 | 作者 |
| --- | --- | --- | --- | --- |
| `flags/ae.svg` | Flag of the United Arab Emirates.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_the_United_Arab_Emirates.svg> | Abdulla Mohammed Al Maainah |
| `flags/ar.svg` | Flag of Argentina.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Argentina.svg> | Manuel Belgrano |
| `flags/at.svg` | Flag of Austria.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Austria.svg> | Bundesministerium für Landesverteidigung |
| `flags/au.svg` | Flag of Australia.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Australia.svg> | Original: Ivor Evans, Leslie John Hawkins, Egbert John Nuttall, Annie Dorrington and William Stevens Vector: Ian Fieggen |
| `flags/bd.svg` | Flag of Bangladesh.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Bangladesh.svg> | — |
| `flags/be.svg` | Flag of Belgium.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Belgium.svg> | Dbenbenn and others |
| `flags/br.svg` | Flag of Brazil.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Brazil.svg> | Raimundo Teixeira Mendes |
| `flags/ca.svg` | Flag of Canada.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Canada.svg> | Created by George F. G. Stanley / E Pluribus Anthony / User:Mzajac |
| `flags/ch.svg` | Flag of Switzerland.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Switzerland.svg> | Original: Unknown Vector: User:Marc Mongenet Credits: User:-xfi- User:Zscout370 |
| `flags/cl.svg` | Flag of Chile.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Chile.svg> | — |
| `flags/cn.svg` | Flag of the People's Republic of China.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_the_People%27s_Republic_of_China.svg> | Zeng Liansong |
| `flags/co.svg` | Flag of Colombia.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Colombia.svg> | — |
| `flags/cu.svg` | Flag of Cuba.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Cuba.svg> | Miguel Teurbe Tolón and Narciso López |
| `flags/cz.svg` | Flag of the Czech Republic.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_the_Czech_Republic.svg> | Jaroslav Kursa |
| `flags/de.svg` | Flag of Germany.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Germany.svg> | User:SKopp, User:Madden, and other users |
| `flags/dk.svg` | Flag of Denmark.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Denmark.svg> | Madden and others |
| `flags/eg.svg` | Flag of Egypt.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Egypt.svg> | — |
| `flags/es.svg` | Flag of Spain.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Spain.svg> | RelShot 263, Echando una mano; earlier version was Pedro A. Gracia Fajardo, escudo de Manual de Imagen Institucional de la Administración General del Estado |
| `flags/eu.svg` | Flag of Europe.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Europe.svg> | User:Verdy p, User:-xfi-, User:Paddu, User:Nightstallion, User:Funakoshi, User:Jeltz, User:Dbenbenn, User:Zscout370 |
| `flags/fi.svg` | Flag of Finland.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Finland.svg> | — |
| `flags/fr.svg` | Flag of France.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_France.svg> | Original: Unknown Vector: SKopp |
| `flags/gb.svg` | Flag of the United Kingdom (3-5).svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_the_United_Kingdom_(3-5).svg> | Original: Acts of Union 1800 Vector: Yaddah |
| `flags/gr.svg` | Flag of Greece.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Greece.svg> | — |
| `flags/hu.svg` | Flag of Hungary.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Hungary.svg> | SKopp |
| `flags/id.svg` | Flag of Indonesia.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Indonesia.svg> | Jayakatwang |
| `flags/ie.svg` | Flag of Ireland.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Ireland.svg> | Éire |
| `flags/il.svg` | Flag of Israel.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Israel.svg> | Israel Belkind and Fanny Abramovitch (original) |
| `flags/in.svg` | Flag of India.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_India.svg> | Government of India |
| `flags/iq.svg` | Flag of Iraq.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Iraq.svg> | — |
| `flags/ir.svg` | Flag of Iran.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Iran.svg> | SVG: SiBr4、設計: Hamid Nadimi、制作: ISIRI |
| `flags/is.svg` | Flag of Iceland.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Iceland.svg> | Original: Matthías Þórðarson Vector: Árni Dagur and Magasjukur2 |
| `flags/it.svg` | Flag of Italy.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Italy.svg> | — |
| `flags/jp.svg` | Flag of Japan.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Japan.svg> | Various |
| `flags/ke.svg` | Flag of Kenya.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Kenya.svg> | User:Pumbaa80 |
| `flags/kp.svg` | Flag of North Korea.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_North_Korea.svg> | Original: Unknown author Vector: Zscout370 |
| `flags/kr.svg` | Flag of South Korea.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_South_Korea.svg> | Original: Government of the Republic of Korea Vector: Great Brightstar and others |
| `flags/ma.svg` | Flag of Morocco.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Morocco.svg> | Denelson83, Zscout370 |
| `flags/mx.svg` | Flag of Mexico.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Mexico.svg> | Omar Alejandro Covarrubias Neri, 9 April 2006. Based on the 1968 arms by Francisco Eppens Helguera and Juan Manuel Gabino Villascán. |
| `flags/my.svg` | Flag of Malaysia.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Malaysia.svg> | MapGrid (old version SKopp, Zscout370 and Ranking Update) |
| `flags/ng.svg` | Flag of Nigeria.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Nigeria.svg> | Jon Harald Søby. |
| `flags/nl.svg` | Flag of the Netherlands.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_the_Netherlands.svg> | Zscout370 |
| `flags/no.svg` | Flag of Norway.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Norway.svg> | Original: Fredrik Meltzer Vector: Gutten på Hemsen |
| `flags/nz.svg` | Flag of New Zealand.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_New_Zealand.svg> | Original: Albert Hastings Markham Vector: Zscout370, Hugh Jass, s. File history |
| `flags/pe.svg` | Flag of Peru.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Peru.svg> | David Benbennick |
| `flags/ph.svg` | Flag of the Philippines.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_the_Philippines.svg> | — |
| `flags/pk.svg` | Flag of Pakistan.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Pakistan.svg> | User:Zscout370 |
| `flags/pl.svg` | Flag of Poland.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Poland.svg> | — |
| `flags/pt.svg` | Flag of Portugal.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Portugal.svg> | Original: Columbano Bordalo Pinheiro (1910; generic design) Vector: Vítor Luís Rodrigues; António Martins-Tuválkin (2004; this specific vector set: see sources) |
| `flags/ro.svg` | Flag of Romania.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Romania.svg> | AdiJapan |
| `flags/ru.svg` | Flag of Russia.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Russia.svg> | Peter the Great |
| `flags/sa.svg` | Flag of Saudi Arabia.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Saudi_Arabia.svg> | The Shura Council |
| `flags/se.svg` | Flag of Sweden.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Sweden.svg> | Jon Harald Søby and others. |
| `flags/sg.svg` | Flag of Singapore.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Singapore.svg> | Original: Government of Singapore Vector: Zscout370 |
| `flags/th.svg` | Flag of Thailand.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Thailand.svg> | Zscout370 |
| `flags/tr.svg` | Flag of Turkey.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Turkey.svg> | David Benbennick (original author) |
| `flags/tw.svg` | Flag of the Republic of China.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_the_Republic_of_China.svg> | Sun Yat-sen |
| `flags/ua.svg` | Flag of Ukraine.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Ukraine.svg> | Government of Ukraine |
| `flags/us.svg` | Flag of the United States.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_the_United_States.svg> | Uploaded by Dbenbenn; edited by users such as Zscout370, Jacobolus, Indolences, and Technion. |
| `flags/vn.svg` | Flag of Vietnam.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_Vietnam.svg> | — |
| `flags/za.svg` | Flag of South Africa.svg | PD | <https://commons.wikimedia.org/wiki/File:Flag_of_South_Africa.svg> | Flag design by Frederick Brownell, image by Wikimedia Commons users |

作者が「—」のものは、Commons の `Artist` が `See below.` や `See file history below for
details.` などで、作者名として書ける値が無かったもの。出典の URL だけを載せる。
`flags/ir.svg` は上流の `Artist` がラベルの区切りごと潰れていた（`SVG file: SiBr4Designer: …`）ので、
区切りだけ補って読める形にした。

## 地図を入れていない理由

世界地図・位置図も候補に調べたが、同梱は見送った。

- PD か CC0 の世界地図は 1 点が 0.6〜1 MB あり（`Blank world map.svg` は CC0 で 957 KB、
  `World location map.svg` は PD で 609 KB）、同梱の合計 1 MB の目安を 1 枚で使い切る。
  HTML に埋め込む data: の URI も約 1.3 倍に膨らむ。
- 日本の位置図（`Japan location map.svg` など）はすべて CC BY-SA 3.0 で、上の方針で入れられない。

足すときは、上の「なぜ PD と CC0 だけなのか」を満たすものだけを、この目録と表に 1 件ずつ足す。

## 取り直すとき

```
https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo
  &iiprop=url|extmetadata&titles=File:Flag_of_Japan.svg
```

User-Agent は `wsa-template-audit/1.0`、`maxlag=5`、間隔は 1 秒以上あける。実体は
`Special:FilePath` か `upload.wikimedia.org` の直リンクから取り、SVG として読めること
（XML として正しい、根が `svg`、`<script>` を含まない）を確かめてから置く。
