from steamfun_mirror.discovery import (
    extract_api_paths,
    extract_referenced_urls,
    extract_routes,
    extract_shell_assets,
)


def test_extract_api_paths_collects_api_and_java_api_paths() -> None:
    script = """
    function a(){return {url:"/api/get/student/list"}}
    function b(){return {url:"/java-api/student/stu/login"}}
    function c(){return {url:"/api/get/student/list"}}
    """

    assert extract_api_paths(script) == [
        "/api/get/student/list",
        "/java-api/student/stu/login",
    ]


def test_extract_routes_reads_router_path_literals() -> None:
    script = """
    path:"/login"
    path:"/background/login"
    path:"/competitionCenter/questionBankCenter/matchDetail/:id"
    """

    assert extract_routes(script) == [
        "/background/login",
        "/competitionCenter/questionBankCenter/matchDetail/:id",
        "/login",
    ]


def test_extract_shell_assets_collects_same_origin_and_external_assets() -> None:
    html = """
    <link href="/css/app.css" rel="stylesheet">
    <script src="/js/app.js"></script>
    <script src="https://res2.wx.qq.com/open/js/jweixin-1.6.0.js"></script>
    """

    assert extract_shell_assets(html) == [
        "/css/app.css",
        "/js/app.js",
        "https://res2.wx.qq.com/open/js/jweixin-1.6.0.js",
    ]


def test_extract_referenced_urls_collects_embedded_course_assets() -> None:
    base_url = "https://wugecdn.steam.fun/course/index.html"
    html = """
    <iframe src="slides/index.html"></iframe>
    <audio src="audio/intro.mp3"></audio>
    <video poster="images/poster.png">
      <source src="video/lesson.mp4" type="video/mp4">
    </video>
    <div style="background-image:url('images/bg.png')"></div>
    <script src="data/player.js"></script>
    <link href="styles/lesson.css" rel="stylesheet">
    <script>fetch("manifests/lesson.json")</script>
    <script>fetch("runtime/config.wasm")</script>
    """

    assert extract_referenced_urls(base_url, html) == [
        "https://wugecdn.steam.fun/course/audio/intro.mp3",
        "https://wugecdn.steam.fun/course/data/player.js",
        "https://wugecdn.steam.fun/course/images/bg.png",
        "https://wugecdn.steam.fun/course/images/poster.png",
        "https://wugecdn.steam.fun/course/manifests/lesson.json",
        "https://wugecdn.steam.fun/course/runtime/config.wasm",
        "https://wugecdn.steam.fun/course/slides/index.html",
        "https://wugecdn.steam.fun/course/styles/lesson.css",
        "https://wugecdn.steam.fun/course/video/lesson.mp4",
    ]


def test_extract_referenced_urls_ignores_regex_like_url_fragments() -> None:
    base_url = "https://wugecdn.steam.fun/course/index.html"
    text = """
    const pattern = "https://huewq7h021.feishu.cn/docs/(.*)";
    const realAsset = "https://wugecdn.steam.fun/course/data/slide1.js";
    """

    assert extract_referenced_urls(base_url, text) == [
        "https://wugecdn.steam.fun/course/data/slide1.js",
    ]
