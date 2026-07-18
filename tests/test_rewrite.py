from steamfun_mirror.rewrite import LOCAL_EXTERNAL_PREFIX, rewrite_external_urls


def test_rewrite_external_urls_replaces_external_hosts_and_keeps_same_origin_urls() -> None:
    original = (
        "https://steam.fun/js/app.js "
        "https://wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg "
        "//res2.wx.qq.com/open/js/jweixin-1.6.0.js"
    )

    rewritten = rewrite_external_urls(original)

    assert "https://steam.fun/js/app.js" not in rewritten
    assert "https://wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg" not in rewritten
    assert "//res2.wx.qq.com/open/js/jweixin-1.6.0.js" not in rewritten
    assert "/js/app.js" in rewritten
    assert f"{LOCAL_EXTERNAL_PREFIX}/wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg" in rewritten
    assert f"{LOCAL_EXTERNAL_PREFIX}/res2.wx.qq.com/open/js/jweixin-1.6.0.js" in rewritten


def test_rewrite_external_urls_rewrites_www_same_origin_host_to_local_path() -> None:
    original = "https://www.steam.fun/login?redirect=school-curriculum#top"

    rewritten = rewrite_external_urls(original)

    assert rewritten == "/login?redirect=school-curriculum#top"


def test_rewrite_external_urls_ignores_non_url_protocol_like_fragments() -> None:
    original = 'var pattern = "//,{relevance:0,contains:[{scope:";'

    rewritten = rewrite_external_urls(original)

    assert rewritten == original


def test_rewrite_external_urls_keeps_comment_style_console_calls() -> None:
    original = '//console.log("debug")'

    rewritten = rewrite_external_urls(original)

    assert rewritten == original


def test_rewrite_external_urls_keeps_w3c_namespace_urls() -> None:
    original = 'document.createElementNS("http://www.w3.org/2000/svg", "svg")'

    rewritten = rewrite_external_urls(original)

    assert rewritten == original
