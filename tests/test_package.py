import wikiskill


def test_公開する名前を取り込める() -> None:
    article = wikiskill.read_article('+++\ntitle = "題"\ntype = "meme"\n+++\n')
    assert isinstance(article, wikiskill.Article)
    assert issubclass(wikiskill.MarkupError, wikiskill.SourceError)


def test_類型の定義と検査の入口を取り込める() -> None:
    registry = wikiskill.load_default_registry()
    assert isinstance(registry["manga"], wikiskill.ArticleType)
    article = wikiskill.read_article('+++\ntitle = "題"\ntype = "meme"\n+++\n')
    findings = wikiskill.check_article(article)
    assert all(isinstance(f, wikiskill.Finding) for f in findings)
    assert issubclass(wikiskill.UnknownTypeError, wikiskill.TypeRegistryError)


def test_書き出しと_HTML_の検査の入口を取り込める() -> None:
    article = wikiskill.read_article('+++\ntitle = "題"\ntype = "meme"\n+++\n本文。\n')
    article_type = wikiskill.load_default_registry()["meme"]
    page = wikiskill.write_html(article, article_type, "2026年11月2日 (月) 12:00 (JST)")
    assert wikiskill.check_html(page) == ()
    assert "本文。" in wikiskill.write_wikitext(article, article_type)


def test_噂のある原稿の入口を取り込める() -> None:
    article = wikiskill.read_article('+++\ntitle = "題"\ntype = "meme"\n+++\n本文。[!噂|噂。]\n')
    article_type = wikiskill.load_default_registry()["meme"]
    assert wikiskill.has_rumor(article)
    assert wikiskill.check_article_variants(article) == wikiskill.check_article_variants(article)
    page = wikiskill.write_html_both(article, article_type, "2026年11月2日 (月) 12:00 (JST)")
    assert wikiskill.check_html(page) == ()
    assert "噂。" in wikiskill.write_wikitext(wikiskill.rumor_view(article), article_type)
    assert "噂。" not in wikiskill.write_wikitext(wikiskill.normal_view(article), article_type)
