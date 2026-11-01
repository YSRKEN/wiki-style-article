import wikiskill


def test_公開する名前を取り込める() -> None:
    article = wikiskill.read_article('+++\ntitle = "題"\ntype = "meme"\n+++\n')
    assert isinstance(article, wikiskill.Article)
    assert issubclass(wikiskill.MarkupError, wikiskill.SourceError)
