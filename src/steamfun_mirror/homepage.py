from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import Request

HOMEPAGE_ASSET_PREFIX = "/_site/homepage"
HOMEPAGE_ASSET_ROOT = Path(__file__).resolve().parent / "site_assets" / "homepage"
COURSES_ASSET_PREFIX = "/_site/courses"
COURSES_ASSET_ROOT = Path(__file__).resolve().parent / "site_assets" / "courses"
GOOGLE_FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=Anton&family=Condiment&family=Noto+Sans+SC:wght@400;600&display=swap"
)

HERO_VIDEO_FILE = "hero-video.mp4"
ABOUT_VIDEO_FILE = "showreel-birthday.mp4"
SIGNAL_VIDEO_FILE = "showreel-dance.mp4"

CINEMA_ITEMS = [
    ("showreel-birthday.mp4", "showreel-01.webp", "\u5b66\u5458\u751f\u65e5\u4f1a \u00b7 \u5171\u4eab\u6b22\u4e50\u65f6\u5149"),
    ("showreel-dance.mp4", "showreel-02.webp", "\u8d5b\u524d\u96c6\u8bad \u00b7 \u673a\u5668\u4eba\u8e48\u821e\u6f14\u7ec3"),
    ("hero-video.mp4", "campus-01.webp", "\u521b\u5ba2\u5de5\u574a \u00b7 \u4e50\u9ad8\u642d\u5efa\u73b0\u573a"),
]

ABOUT_COPY = (
    "\u4e50\u542f\u4eab\u673a\u5668\u4eba\u4e13\u6ce8 3-16 \u5c81\u5c11\u513f\u79d1\u6280\u7d20\u517b\u6559\u80b2\uff0c"
    "\u4ee5\u5de5\u7a0b\u5b9e\u8df5\u4e0e\u9879\u76ee\u5236\u5b66\u4e60\uff0c"
    "\u8ba9\u5b69\u5b50\u5728\u642d\u5efa\u3001\u8c03\u8bd5\u3001\u534f\u4f5c\u3001\u5c55\u793a\u4e2d\u771f\u6b63\u5b66\u4f1a\u521b\u9020\u3002"
)
BRAND_SUBTITLE = "\u7cfb\u7edf\u57f9\u517b\u5b69\u5b50\u7684\u79d1\u6280\u7d20\u517b\u4e0e\u521b\u9020\u529b"
BRAND_PHONE = "18164173640"
BRAND_ADDRESS = "\u5b9c\u660c\u5e02\u7307\u4ead\u533a\u91d1\u5cad\u8def59-1\u53f7"
BRAND_COURSE_URL = "/_site/courses/"
LOGIN_HREF = "/login"

NAV_ITEMS = [
    ("#hero", "\u9996\u9875"),
    ("#about", "\u673a\u6784"),
    ("#collection", "\u8bfe\u7a0b\u77e9\u9635"),
    ("#collection", "\u6210\u957f\u7a79\u9876"),
    ("#signal", "\u8054\u7cfb\u6211\u4eec"),
]

SIGNAL_ITEMS = [
    ("wechat", "\u5fae\u4fe1\uff1alqxszls", "weixin://"),
    ("phone", "\u7535\u8bdd\uff1a18164173640", "tel:18164173640"),
    ("pin", "\u6821\u533a\uff1a\u5b9c\u660c\u5e02\u7307\u4ead\u533a\u91d1\u5cad\u8def59-1\u53f7", "#signal"),
]

COURSE_PATH = [
    ("course-lego.png", "\u4e50\u9ad8\u542f\u8499", "3-6 \u5c81 \u00b7 \u79ef\u6728\u642d\u5efa\u4e0e\u7a7a\u95f4\u60f3\u8c61", "Wedo"),
    ("course-robot.png", "\u673a\u5668\u4eba\u5de5\u7a0b", "7-10 \u5c81 \u00b7 \u7ed3\u6784 \u00b7 \u52a8\u529b \u00b7 \u7f16\u7a0b", "Ev3 / Spike"),
    ("course-python.png", "Python \u7f16\u7a0b", "10-14 \u5c81 \u00b7 \u7b97\u6cd5 \u00b7 \u9879\u76ee\u5f00\u53d1", "Code \u00b7 AI"),
    ("course-ai.png", "AI \u521b\u9020", "12 \u5c81+ \u00b7 \u5927\u6a21\u578b \u00b7 \u89c6\u89c9 \u00b7 \u667a\u80fd\u4f53", "LLM \u00b7 Vision"),
]

TEACHER_POSTERS = [
    ("teacher-senlin.png", "\u68ee\u6797\u8001\u5e08", "\u521b\u59cb\u4eba \u00b7 \u8bfe\u7a0b\u603b\u8bbe\u8ba1\u5e08",
     "https://senlin-c1n.pages.dev/", "\u4e50\u9ad8\u00b7\u673a\u5668\u4eba\u00b7Python\u00b7AI \u5168\u6846\u67b6\u8bfe\u7a0b\u4f53\u7cfb\u8bbe\u8ba1\u8005\uff0c\u8ddf\u968f\u5b69\u5b50\u4e00\u8def\u4ece\u79ef\u6728\u8d70\u5230\u667a\u80fd\u4f53\u3002"),
    ("teacher-xiang.png", "\u5411\u8001\u5e08", "\u4e50\u9ad8\u542f\u8499\u6559\u7814\u4e3b\u7ba1",
     "https://xiangmin-lego.pages.dev/", "\u4ece\u4e50\u9ad8\u5927\u9897\u7c92\u5230\u5c0f\u9897\u7c92\u673a\u68b0\uff0c\u8ba9\u8eab\u4f53\u52a8\u4f5c\u4e0e\u7a7a\u95f4\u601d\u8003\u540c\u6b65\u53d1\u751f\u3002"),
    ("teacher-liu.png", "\u5218\u8001\u5e08", "\u673a\u5668\u4eba\u5de5\u7a0b\u6559\u7814\u7ec4\u957f",
     "https://zhaoyu-2h8.pages.dev/", "Ev3 / Spike \u673a\u68b0\u3001\u52a8\u529b\u3001\u4f20\u611f\u5668\u4e0e\u7f16\u7a0b\u8de8\u5b66\u79d1\u8005\uff0c\u70b9\u4eae\u5b69\u5b50\u7684\u5de5\u7a0b\u68a6\u3002"),
    ("teacher-zhou.png", "\u5468\u8001\u5e08", "Python \u7f16\u7a0b\u5bfc\u5e08",
     "https://main.zhouyufeng-website.pages.dev", "\u4ece\u53d8\u91cf\u5230\u51fd\u6570\uff0c\u4ece\u6e38\u620f\u5230\u5c0f\u5de5\u5177\uff0c\u5e26\u5b69\u5b50\u8d70\u5b8c\u7b2c\u4e00\u4e2a\u771f\u6b63\u7684\u9879\u76ee\u3002"),
    ("teacher-yang.png", "\u6768\u8001\u5e08", "AI \u79d1\u6280\u7d20\u517b\u5bfc\u5e08",
     "https://yangtao-c8u.pages.dev/", "\u7528 LLM\u3001\u8ba4\u77e5\u3001\u8bed\u97f3\u6280\u672f\u70b9\u4eae\u5b69\u5b50\u7684\u672a\u6765\u5b66\u4e60\u65b9\u5f0f\u3002"),
    ("teacher-zhao.png", "\u8d75\u8001\u5e08", "\u8d5b\u4e8b\u4e0e\u8fd0\u8425\u603b\u8d1f\u8d23",
     "https://zhaoyu-2h8.pages.dev/", "\u5168\u7a0b\u8ddf\u8fdb WRO\u3001\u84dd\u6865\u676f\u3001\u9752\u5c11\u5e74\u673a\u5668\u4eba\u7ade\u8d5b\uff0c\u8d4b\u80fd\u6bcf\u4e00\u4e2a\u4e50\u8da3\u3002"),
]

HONOR_CARDS = [
    ("honors/3c4b1c9a2f99fd3aedb86712b709b6a2.webp", "全国青少年机器人竞赛", "一等奖 2024"),
    ("honors/3eec15d34062bf6ef680de67fb74689f.webp", "WRO 中国总决赛", "亚军 2024"),
    ("honors/415738909ed8cf9eb1594535c8e3537e.webp", "湖北省创客大赛", "冠军 2023"),
    ("honors/47cdc27feee3d1ca5a1c2de341202475.webp", "宜昌市科技教育基地", "授牌 2023"),
    ("honors/4be2d8ed8c0608e5a76aaff44fea0b86.webp", "蓝桥杯青少组", "省赛一等奖 2024"),
    ("honors/4c034334db22d80ecae7cd665b142e62.webp", "中国电子学会考评", "优秀考点 2024"),
    ("honors/57b76a27feb1167ff4387a3bcb517eae.webp", "校区授牌", "乐启享 2023"),
    ("honors/6e43b26aa8d461efbe6bfd108898c4bf.webp", "优秀考点", "全国电子学会"),
    ("honors/8f227f5af1a8258132ca7a181cb5f8c7.webp", "创赛营一等奖", "Python 创赛"),
    ("honors/9f553117006eb7273508fce3e103dc84.webp", "机器人主题赛", "蓝桥杯专项"),
    ("honors/c61cbbd3848e84e3ef947fb05a6ea4e4.webp", "蓝桥杯省赛一等奖", "青少组"),
    ("honors/cert1.webp", "全国总决赛亚军", "WRO 2024"),
    ("honors/cert4.webp", "机器人省赛冠军", "湖北赛区"),
    ("honors/cert5.webp", "营地优秀学员", "2024 夏令营"),
    ("honors/certer3.webp", "省赛二等奖", "Scratch 创意编程"),
    ("honors/d3112f025a571be58aa80e2ee73623d2.webp", "市赛金奖", "乐高搭建"),
    ("honors/ebe03b95c25fec9d8b86d3108992b09f.webp", "学员表彰", "校区荣誉"),
    ("honors/festival4.webp", "节日活动", "中秋 / 国庆 / 元旦"),
]

CAMPUS_CARDS = [
    ("home/1.webp", "宜昌旗舰校区", "180 m^2 创客空间"),
    ("home/2.webp", "乐高搭建教室", "6 间主题工坊"),
    ("home/3.webp", "机器人实验室", "Ev3 / Spike 全套教具"),
    ("home/birsiday.webp", "季度生日会", "共享欢乐时光"),
    ("home/camp2.webp", "星际探索 VR 体验", "沉浸式互动学习"),
    ("home/classroom3.webp", "乐高搭建教室", "主题工坊 / 项目路演"),
    ("home/classroom6.webp", "真实课堂", "学员专注 / 老师陪伴"),
    ("home/dance.webp", "赛队蹈舞", "赛前集训"),
    ("home/robot-camp.webp", "机器人营地", "主题营 / 项目实战"),
]

STUDENT_FILES = [f"students/student-{i:03d}.webp" for i in range(1, 153)]
GALLERY_FILES = STUDENT_FILES


def homepage_asset_url(asset_path: str) -> str:
    return f"{HOMEPAGE_ASSET_PREFIX}/{asset_path.lstrip(chr(47))}"


def homepage_asset_path(asset_path: str):
    normalized = asset_path.strip().lstrip(chr(47)).replace(chr(92), chr(47))
    if not normalized:
        return None
    candidate = (HOMEPAGE_ASSET_ROOT / normalized).resolve()
    try:
        candidate.relative_to(HOMEPAGE_ASSET_ROOT.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def courses_asset_url(asset_path: str) -> str:
    return f"{COURSES_ASSET_PREFIX}/{asset_path.lstrip(chr(47))}"


def courses_asset_path(asset_path: str):
    normalized = asset_path.strip().lstrip(chr(47)).replace(chr(92), chr(47))
    if not normalized:
        return None
    candidate = (COURSES_ASSET_ROOT / normalized).resolve()
    try:
        candidate.relative_to(COURSES_ASSET_ROOT.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _icon_svg(name: str) -> str:
    paths = {
        "mail": (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M4 6h16v12H4z"></path>'
            '<path d="m4 7 8 6 8-6"></path>'
            "</svg>"
        ),
        "twitter": (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M22 5.9c-.7.3-1.5.6-2.2.7.8-.5 1.4-1.3 1.7-2.3-.8.5-1.6.8-2.5 1'
            '-1.5-1.6-4-1.7-5.6-.2-1.1 1-1.5 2.5-1.1 3.9-3.2-.2-6.1-1.7-8-4.2-1 1.8-.5 4 1.2 5.1'
            '-.6 0-1.2-.2-1.8-.5 0 2.1 1.5 3.9 3.6 4.3-.6.2-1.3.2-1.9.1.5 1.8 2.2 3.1 4.1 3.1'
            'A8.3 8.3 0 0 1 2 18.1 11.8 11.8 0 0 0 8.4 20c7.7 0 12-6.7 11.8-12.7.8-.6 1.4-1.2 1.8-2"></path>'
            "</svg>"
        ),
        "github": (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.9c-2.9.7-3.6-1.2-3.6-1.2'
            '-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 .1 1.6 1 1.6 1 .9 1.6 2.4 1.1 3 .8.1-.7.4-1.1.7-1.4'
            '-2.3-.3-4.7-1.2-4.7-5.2 0-1.1.4-2 1-2.8-.1-.2-.4-1.3.1-2.8 0 0 .8-.3 2.9 1a10 10 0 0 1 5.2 0c2-1.3'
            ' 2.9-1 2.9-1 .6 1.5.2 2.6.1 2.8.7.8 1 1.7 1 2.8 0 4.1-2.4 5-4.7 5.2.4.4.8 1 .8 2v3'
            'c0 .3.2.6.7.5A10 10 0 0 0 12 2"></path>'
            "</svg>"
        ),
        "arrow": (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="m9 6 6 6-6 6"></path>'
            "</svg>"
        ),
        "wechat": (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M9 4C5 4 2 6.7 2 10c0 1.7.8 3.2 2.1 4.3L3 17l3-1.4c.9.3 1.9.5 3 .5h.6"></path>'
            '<path d="M22 14.5c0-2.8-2.7-5-6-5s-6 2.2-6 5 2.7 5 6 5c.8 0 1.6-.1 2.3-.4L21 20l-.7-1.9c1-.9 1.7-2.1 1.7-3.6z"></path>'
            '<circle cx="7.5" cy="9.5" r=".7" fill="currentColor"></circle>'
            '<circle cx="10.5" cy="9.5" r=".7" fill="currentColor"></circle>'
            '<circle cx="14.5" cy="14" r=".6" fill="currentColor"></circle>'
            '<circle cx="17.5" cy="14" r=".6" fill="currentColor"></circle>'
            "</svg>"
        ),
        "phone": (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M5 4h3l2 5-2 1c1 2 3 4 5 5l1-2 5 2v3c0 .6-.4 1-1 1A14 14 0 0 1 4 5c0-.6.4-1 1-1z"></path>'
            "</svg>"
        ),
        "pin": (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M12 2c-4 0-7 3-7 7 0 5 7 13 7 13s7-8 7-13c0-4-3-7-7-7z"></path>'
            '<circle cx="12" cy="9" r="2.5"></circle>'
            "</svg>"
        ),
    }
    return paths[name]


def _render_nav() -> str:
    items = "".join(
        f'<a class="nav-link font-grotesk" href="{escape(href)}">{escape(label)}</a>'
        for href, label in NAV_ITEMS
    )
    login = (
        f'<a class="nav-link nav-link--login font-grotesk" href="{escape(LOGIN_HREF)}">'
        f'<span>\u767b\u5f55</span>'
        f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"></path></svg>'
        f'</a>'
    )
    return items + login


def _render_signal_buttons(button_class: str) -> str:
    return "".join(
        (
            f'<a class="{button_class} liquid-glass" href="{escape(url)}" aria-label="{escape(label)}">'
            f'{_icon_svg(icon)}'
            f'<span class="{button_class}__label font-grotesk">{escape(label)}</span>'
            f'</a>'
        )
        for icon, label, url in SIGNAL_ITEMS
    )


def _render_signal_rail_items() -> str:
    rows = []
    for index, (icon, label, url) in enumerate(SIGNAL_ITEMS):
        divider = '<span class="social-rail__divider" aria-hidden="true"></span>' if index < len(SIGNAL_ITEMS) - 1 else ''
        rows.append(
            (
                '<div class="social-rail__row">'
                f'<a class="social-rail__button" href="{escape(url)}" aria-label="{escape(label)}">'
                f'<span class="social-rail__icon">{_icon_svg(icon)}</span>'
                f'<span class="font-grotesk social-rail__label">{escape(label)}</span>'
                f'</a>'
                f'{divider}'
                f'</div>'
            )
        )
    return "".join(rows)


def _render_cinema_stage() -> str:
    # Single ambient video wall: an auto-mute looping background video. Three thumbnails below
    # let the visitor switch to a specific reel. Click anywhere on the wall to open the
    # fullscreen lightbox; the lightbox video is unmuted and starts with sound on.
    default_video, default_poster, default_label = CINEMA_ITEMS[0]
    default_video_url = homepage_asset_url('media/' + default_video)
    default_poster_url = homepage_asset_url('media/' + default_poster)
    thumbs = []
    for index, (video, poster, label) in enumerate(CINEMA_ITEMS):
        video_url = homepage_asset_url('media/' + video)
        poster_url = homepage_asset_url('media/' + poster)
        is_active = 'is-active' if index == 0 else ''
        thumbs.append(
            '<button class="cinema-thumb ' + is_active + '" type="button" '
            'data-index="' + str(index) + '" '
            'data-video="' + escape(video_url) + '" '
            'data-poster="' + escape(poster_url) + '" '
            'aria-label="' + escape(label) + '">'
            '<img class="cinema-thumb__image" loading="lazy" decoding="async" '
            'src="' + escape(poster_url) + '" alt="' + escape(label) + '">'
            '<span class="cinema-thumb__label font-grotesk">' + escape(label) + '</span>'
            '</button>'
        )
    thumbs_html = ''.join(thumbs)
    return (
        '<section class="cinema-stage" id="cinema">'
        '<div class="container cinema-stage__container">'
        '<div class="collection-header">'
        '<div class="collection-heading">'
        '<h2 class="collection-title font-grotesk">全屏</h2>'
        '<div class="collection-title-line">'
        '<span class="collection-accent font-condiment">现场</span>'
        '<span class="collection-objects font-grotesk">视频</span>'
        '</div>'
        '</div>'
        '<p class="collection-sub font-mono">默认静音循环播放 · 点击进入全屏后取消静音</p>'
        '</div>'
        '<div class="cinema-wall" id="cinemaWall" '
        'data-video="' + escape(default_video_url) + '" '
        'data-poster="' + escape(default_poster_url) + '">'
        '<video class="cinema-wall__video" autoplay loop muted playsinline '
        'poster="' + escape(default_poster_url) + '" '
        'src="' + escape(default_video_url) + '"></video>'
        '<button class="cinema-wall__enter font-grotesk" type="button" aria-label="点击进入全屏">'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5l14 7-14 7z"></path></svg>'
        '<span>点击进入全屏</span>'
        '</button>'
        '<span class="cinema-wall__hint font-mono">默认静音·全屏后可听到声音</span>'
        '</div>'
        '<div class="cinema-thumbs" id="cinemaThumbs">' + thumbs_html + '</div>'
        '</div>'
        '</section>'
        '<div class="cinema-lightbox" id="cinemaLightbox" hidden role="dialog" aria-modal="true" aria-label="全屏视频">'
        '<button class="cinema-lightbox__close" type="button" aria-label="关闭">'
        '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"></path></svg>'
        '</button>'
        '<video class="cinema-lightbox__video" controls playsinline autoplay></video>'
        '</div>'
    )

def _render_course_card(image: str, title: str, blurb: str, tag: str) -> str:
    src = homepage_asset_url("media/" + image)
    return (
        '<article class="nft-card liquid-glass">'
        '<div class="nft-card__video-wrap">'
        f'<img class="nft-card__image" loading="lazy" decoding="async" src="{escape(src)}" alt="{escape(title)}">'
        f'</div>'
        '<div class="nft-card__overlay">'
        '<div class="nft-card__meta">'
        f'<span class="nft-card__label font-mono">{escape(tag)}</span>'
        f'<span class="nft-card__score font-grotesk">{escape(title)}</span>'
        f'<span class="nft-card__blurb font-mono">{escape(blurb)}</span>'
        f'</div>'
        f'<a class="nft-card__arrow" href="{escape(BRAND_COURSE_URL)}" target="_blank" rel="noreferrer" aria-label="\u67e5\u770b\u5b8c\u6574\u8bfe\u7a0b\u4f53\u7cfb">'
        f'{_icon_svg("arrow")}'
        f'</a>'
        f'</div>'
        f'</article>'
    )


def _render_cards() -> str:
    return "".join(_render_course_card(*card) for card in COURSE_PATH)


def _render_teacher_strip() -> str:
    cells = []
    for image, name, role, site, blurb in TEACHER_POSTERS:
        src = homepage_asset_url("media/" + image)
        cells.append(
            (
                '<article class="teacher-cell liquid-glass">'
                f'<a class="teacher-cell__link" href="{escape(site)}" target="_blank" rel="noreferrer" aria-label="{escape(name)} \u4e2a\u4eba\u4e3b\u9875">'
                f'<img class="teacher-cell__image" loading="lazy" decoding="async" src="{escape(src)}" alt="{escape(name)}">'
                '<div class="teacher-cell__overlay">'
                f'<span class="teacher-cell__name font-grotesk">{escape(name)}</span>'
                f'<span class="teacher-cell__role font-mono">{escape(role)}</span>'
                f'<span class="teacher-cell__blurb font-mono">{escape(blurb)}</span>'
                '<span class="teacher-cell__cta font-grotesk">'
                '\u67e5\u770b\u4e2a\u4eba\u4e3b\u9875'
                '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8"></path></svg>'
                '</span>'
                '</div>'
                f'</a>'
                f'</article>'
            )
        )
    return '<div class="teacher-strip">' + "".join(cells) + '</div>'


def _render_gallery_wall() -> str:
    cells = []
    total = len(GALLERY_FILES)
    for index, filename in enumerate(GALLERY_FILES):
        src = homepage_asset_url("media/" + filename)
        # Spread the photos on a tilted sphere using CSS variables consumed by styles.css.
        # Lat / lon (in degrees) computed from a deterministic pseudo random so reloads are stable.
        # golden-angle distribution on a sphere
        import math
        lat = -80 + (index * 137.508) % 160
        lon = (index * 137.508) % 360 - 180
        cells.append(
            (
                f'<figure class="dome-cell" '
                f'style="--dome-index:{index};--dome-lat:{lat}deg;--dome-lon:{lon}deg;" '
                f'data-index="{index}" data-lightbox-src="{escape(src)}" data-lightbox-caption="学员作品 {index + 1}">'
                f'<img loading="lazy" decoding="async" src="{escape(src)}" alt="\u5b66\u5458\u4f5c\u54c1 {index + 1}">'
                f'</figure>'
            )
        )
    count_label = f"{total} \u4f4d\u5b66\u5458\u00b7\u771f\u5b9e\u53ef\u611f\u7684\u6210\u957f\u8f68\u8ff9"
    return (
        f'<div class="dome-wall" id="domeWall" data-count="{total}">'
        + "".join(cells)
        + f'<span class="dome-wall__count font-mono">{count_label}</span>'
        + '</div>'
    )


def _render_honor_grid() -> str:
    # Honor carousel: auto-scroll horizontally; click any card to open lightbox.
    cells = []
    for image, title, sub in HONOR_CARDS:
        src_url = '/_site/courses/images/' + image
        cells.append(
            (
                '<figure class="honor-card liquid-glass" data-lightbox-src="' + escape(src_url) + '" data-lightbox-caption="' + escape(title + ' . ' + sub) + '">'
                + '<img class="honor-card__image" loading="lazy" decoding="async" src="' + escape(src_url) + '" alt="' + escape(title) + '">'
                + '<div class="honor-card__body">'
                + '<span class="honor-card__title font-grotesk">' + escape(title) + '</span>'
                + '<span class="honor-card__sub font-mono">' + escape(sub) + '</span>'
                + '</div>'
                + '<span class="honor-card__zoom font-grotesk" aria-hidden="true">+</span>'
                + '</figure>'
            )
        )
    track = ''.join(cells)
    return (
        '<div class="honor-carousel" id="honorCarousel" data-count="' + str(len(HONOR_CARDS)) + '">'
        + '<button class="honor-carousel__nav honor-carousel__nav--prev font-grotesk" type="button" aria-label="上一张">&#8249;</button>'
        + '<div class="honor-carousel__viewport">'
        + '<div class="honor-carousel__track">' + track + '</div>'
        + '</div>'
        + '<button class="honor-carousel__nav honor-carousel__nav--next font-grotesk" type="button" aria-label="下一张">&#8250;</button>'
        + '<span class="honor-carousel__count font-mono">' + str(len(HONOR_CARDS)) + ' 项荣誉 . 见证成长的关键时刻</span>'
        + '</div>'
    )

def _render_campus_row() -> str:
    # Campus carousel: auto-scroll horizontally; hover pauses; click any card to open lightbox.
    cells = []
    for image, title, sub in CAMPUS_CARDS:
        src_url = '/_site/courses/images/' + image
        cells.append(
            (
                '<figure class="campus-card liquid-glass" data-lightbox-src="' + escape(src_url) + '" data-lightbox-caption="' + escape(title + ' . ' + sub) + '">'
                + '<img class="campus-card__image" loading="lazy" decoding="async" src="' + escape(src_url) + '" alt="' + escape(title) + '">'
                + '<div class="campus-card__overlay">'
                + '<span class="campus-card__title font-grotesk">' + escape(title) + '</span>'
                + '<span class="campus-card__sub font-mono">' + escape(sub) + '</span>'
                + '</div>'
                + '<span class="campus-card__zoom font-grotesk" aria-hidden="true">+</span>'
                + '</figure>'
            )
        )
    track = ''.join(cells)
    return (
        '<div class="campus-carousel" id="campusCarousel" data-count="' + str(len(CAMPUS_CARDS)) + '">'
        + '<button class="campus-carousel__nav campus-carousel__nav--prev font-grotesk" type="button" aria-label="上一张">&#8249;</button>'
        + '<div class="campus-carousel__viewport">'
        + '<div class="campus-carousel__track">' + track + '</div>'
        + '</div>'
        + '<button class="campus-carousel__nav campus-carousel__nav--next font-grotesk" type="button" aria-label="下一张">&#8250;</button>'
        + '<span class="campus-carousel__count font-mono">' + str(len(CAMPUS_CARDS)) + ' 张实拍 . 真实可感的校区空间</span>'
        + '</div>'
    )

def render_marketing_homepage(request: Request) -> str:
    _ = request
    stylesheet_url = homepage_asset_url("styles.css")
    script_url = homepage_asset_url("app.js")
    hero_video_url = homepage_asset_url("media/" + HERO_VIDEO_FILE)
    about_video_url = homepage_asset_url("media/" + ABOUT_VIDEO_FILE)
    signal_video_url = homepage_asset_url("media/" + SIGNAL_VIDEO_FILE)
    nav_html = _render_nav()
    signal_buttons_html = _render_signal_buttons("signal-square")
    cards_html = _render_cards()
    teachers_html = _render_teacher_strip()
    dome_html = _render_gallery_wall()
    honor_html = _render_honor_grid()
    campus_html = _render_campus_row()
    rail_html = _render_signal_rail_items()
    about_text = escape(ABOUT_COPY)
    subtitle = escape(BRAND_SUBTITLE)
    course_url = escape(BRAND_COURSE_URL)
    parts = []
    parts.append('<!doctype html><html lang="zh-CN"><head>')
    parts.append('<meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append('<title>\u4e50\u542f\u4eab\u673a\u5668\u4eba | \u4ece\u4e50\u9ad8\u542f\u8499\u5230 AI \u521b\u9020</title>')
    parts.append('<meta name="description" content="' + subtitle + '">')
    parts.append('<link rel="preconnect" href="https://fonts.googleapis.com">')
    parts.append('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    parts.append('<link rel="stylesheet" href="' + escape(GOOGLE_FONTS_URL) + '">')
    parts.append('<link rel="stylesheet" href="' + escape(stylesheet_url) + '">')
    parts.append('</head><body><main class="page">')
    parts.append('<section class="hero-stage" id="hero">')
    parts.append('<img class="hero-stage__image" src="/_site/courses/images/home/camp2.webp" alt="乐启享机器人 · 从乐高启蒙到 AI 创造" decoding="async">')
    parts.append('<div class="hero-stage__shade"></div>')
    parts.append('<div class="container hero-stage__container">')
    parts.append('<header class="hero-header">')
    parts.append('<a class="hero-logo font-grotesk" href="#hero">')
    parts.append('<span class="hero-logo__mark" aria-hidden="true"></span>')
    parts.append('<span>\u4e50\u542f\u4eab</span>')
    parts.append('</a>')
    parts.append('<nav class="hero-nav liquid-glass" aria-label="Primary">' + nav_html + '</nav>')
    parts.append('</header>')
    parts.append('<div class="hero-body">')
    parts.append('<div class="hero-copy">')
    parts.append('<span class="hero-eyebrow font-condiment">\u4e50\u542f\u4eab \u00b7 STEAM \u6559\u80b2</span>')
    parts.append('<h1 class="hero-title font-grotesk">\u4ece\u4e50\u9ad8\u542f\u8499<br>\u5230 <span class="hero-title__parenthetical">( AI )</span> \u521b\u9020</h1>')
    parts.append('<p class="hero-accent font-condiment">\u4e50\u542f\u4eab\u673a\u5668\u4eba</p>')
    parts.append('<p class="hero-tagline font-mono">' + subtitle + '</p>')
    parts.append('<div class="hero-cta-row">')
    parts.append('<a class="hero-cta hero-cta--primary font-grotesk" href="' + course_url + '" target="_blank" rel="noreferrer">\u67e5\u770b\u5b8c\u6574\u8bfe\u7a0b\u4f53\u7cfb</a>')
    parts.append('<a class="hero-cta hero-cta--ghost font-grotesk" href="#signal">\u9884\u7ea6\u4f53\u9a8c\u8bfe</a>')
    parts.append('</div>')
    parts.append('</div>')
    parts.append('<div class="hero-social hero-social--desktop" aria-label="\u8054\u7cfb\u65b9\u5f0f">' + signal_buttons_html + '</div>')
    parts.append('</div>')
    parts.append('<div class="hero-social hero-social--mobile" aria-label="\u8054\u7cfb\u65b9\u5f0f">' + signal_buttons_html + '</div>')
    parts.append('<ul class="hero-metric-row" aria-label="\u673a\u6784\u6307\u6807">')
    parts.append('<li><span class="hero-metric__num font-grotesk">1200+</span><span class="hero-metric__label font-mono">\u5728\u8bfb\u5b66\u5458</span></li>')
    parts.append('<li><span class="hero-metric__num font-grotesk">6 \u5e74</span><span class="hero-metric__label font-mono">\u672c\u5730\u6df1\u8015</span></li>')
    parts.append('<li><span class="hero-metric__num font-grotesk">40+</span><span class="hero-metric__label font-mono">\u8d5b\u4e8b\u5956\u9879</span></li>')
    parts.append('<li><span class="hero-metric__num font-grotesk">3-16</span><span class="hero-metric__label font-mono">\u5168\u9f84\u6bb5</span></li>')
    parts.append('</ul>')
    parts.append('</div></section>')
    parts.append('<section class="about-stage" id="about">')
    parts.append('<video class="about-stage__video" autoplay loop muted playsinline src="' + escape(about_video_url) + '"></video>')
    parts.append('<div class="about-stage__shade"></div>')
    parts.append('<div class="container about-stage__container">')
    parts.append('<div class="about-top">')
    parts.append('<div class="about-title-wrap">')
    parts.append('<h2 class="about-title font-grotesk">\u4e50\u9ad8 \u00b7 \u673a\u5668\u4eba<br>\u7f16\u7a0b \u00b7 AI</h2>')
    parts.append('<p class="about-accent font-condiment">\u4e50\u542f\u4eab</p>')
    parts.append('</div>')
    parts.append('<p class="about-intro font-mono">' + about_text + '</p>')
    parts.append('</div>')
    parts.append('<div class="about-bottom">')
    parts.append('<div class="about-fade about-fade--left"><p class="font-mono">\u4e50\u9ad8\u542f\u8499 \u00b7 \u673a\u5668\u4eba\u5de5\u7a0b \u00b7 Python \u7f16\u7a0b \u00b7 AI \u79d1\u6280\u7d20\u517b</p><p class="font-mono">\u6bcf\u4e00\u8282\u8bfe\u90fd\u662f\u4e00\u4e2a\u53ef\u89e6\u6478\u7684\u5c0f\u9879\u76ee\uff0c\u6bcf\u4e00\u6b21\u521b\u4f5c\u90fd\u662f\u5b69\u5b50\u5bf9\u672a\u6765\u7684\u56de\u7b54\u3002</p></div>')
    parts.append('<div class="about-fade about-fade--right"><p class="font-mono">\u4e3b\u9898\u5de5\u574a \u00b7 \u53cc\u5e08\u8bfe\u5802 \u00b7 \u9879\u76ee\u8def\u6f14 \u00b7 \u8d5b\u4e8b\u96c6\u8bad</p><p class="font-mono">\u8ba9\u5b66\u4e60\u53d1\u751f\u5728\u642d\u5efa\u3001\u8c03\u8bd5\u3001\u534f\u4f5c\u3001\u5c55\u793a\u7684\u771f\u5b9e\u8fc7\u7a0b\u91cc\u3002</p></div>')
    parts.append('</div>')
    parts.append(teachers_html)
    parts.append('</div></section>')
    parts.append(_render_cinema_stage())
    parts.append('<section class="collection-stage" id="collection">')
    parts.append('<div class="container collection-stage__container">')
    parts.append('<div class="collection-header"><div class="collection-heading"><h2 class="collection-title font-grotesk">\u5b8c\u6574\u8bfe\u7a0b</h2><div class="collection-title-line"><span class="collection-accent font-condiment">\u9636\u68af</span><span class="collection-objects font-grotesk">\u77e9\u9635</span></div></div>')
    parts.append('<a class="see-all" href="' + course_url + '" target="_blank" rel="noreferrer"><div class="see-all__text"><span class="see-all__see font-grotesk">SEE</span><span class="see-all__stack font-grotesk"><span>\u5b8c\u6574</span><span>\u8bfe\u7a0b\u4f53\u7cfb</span></span></div><span class="see-all__full-text">\u67e5\u770b\u5b8c\u6574\u8bfe\u7a0b\u4f53\u7cfb</span><span class="see-all__bar" aria-hidden="true"></span></a>')
    parts.append('</div><div class="nft-grid">' + cards_html + '</div></div>')
    parts.append('<div class="container collection-stage__container">')
    parts.append('<div class="collection-header collection-header--dome"><div class="collection-heading"><h2 class="collection-title font-grotesk">\u5b66\u5458</h2><div class="collection-title-line"><span class="collection-accent font-condiment">\u6210\u957f</span><span class="collection-objects font-grotesk">\u7a79\u9876</span></div></div><p class="collection-sub font-mono">\u5341\u4e8c\u4f4d\u5b69\u5b50\u7684\u4f5c\u54c1 \u00b7 \u771f\u5b9e\u53ef\u611f\u7684\u6210\u957f\u8f68\u8ff9</p></div>')
    parts.append(dome_html)
    parts.append('</div>')
    parts.append('<div class="container collection-stage__container">')
    parts.append('<div class="collection-header"><div class="collection-heading"><h2 class="collection-title font-grotesk">\u8363\u8a89</h2><div class="collection-title-line"><span class="collection-accent font-condiment">\u73b0\u573a</span><span class="collection-objects font-grotesk">\u77ac\u95f4</span></div></div><p class="collection-sub font-mono">\u8d5b\u4e8b \u00b7 \u8bc4\u7ea7 \u00b7 \u57fa\u5730\u6388\u724c</p></div>')
    parts.append(honor_html)
    parts.append('</div>')
    parts.append('<div class="container collection-stage__container">')
    parts.append('<div class="collection-header"><div class="collection-heading"><h2 class="collection-title font-grotesk">\u6821\u533a</h2><div class="collection-title-line"><span class="collection-accent font-condiment">\u73b0\u573a</span><span class="collection-objects font-grotesk">\u7a7a\u95f4</span></div></div><p class="collection-sub font-mono">\u4e3b\u9898\u5de5\u574a \u00b7 \u673a\u5668\u4eba\u5b9e\u9a8c\u5ba4 \u00b7 \u8d5b\u4e8b\u96c6\u8bad\u8425</p></div>')
    parts.append(campus_html)
    parts.append('</div></section>')
    parts.append('<section class="signal-stage" id="signal"><div class="container signal-stage__container"><div class="signal-stage__media">')
    parts.append('<video class="signal-stage__video" autoplay loop muted playsinline src="' + escape(signal_video_url) + '"></video>')
    parts.append('<div class="signal-copy"><p class="signal-accent font-condiment">\u52a0\u5165\u4e50\u542f\u4eab</p>')
    parts.append('<h2 class="signal-title font-grotesk"><span class="signal-title__lead">\u9884\u7ea6\u4f53\u9a8c\u8bfe.</span><span>\u8d70\u8fdb\u4e50\u9ad8\u5de5\u574a.</span><span>\u8ba9\u5b69\u5b50\u4eb2\u624b\u521b\u9020.</span><span>\u627e\u5230\u5c5e\u4e8e\u4ed6\u7684\u4fe1\u53f7.</span></h2></div>')
    parts.append('<div class="social-rail liquid-glass">' + rail_html + '</div></div></div></section>')
    parts.append('<footer class="site-footer">'
        + '<div class="container site-footer__container">'
        + '<div class="site-footer__brand">'
        + '<span class="site-footer__logo font-grotesk">乐启享机器人</span>'
        + '<span class="font-mono site-footer__tagline">从乐高启蒙 · 到 AI 创造</span>'
        + '</div>'
        + '<div class="site-footer__contact font-mono">'
        + '<span>微信：lqxszls</span>'
        + '<span>电话：18164173640</span>'
        + '<span>校区：宜昌市猇亭区金岭路59-1号</span>'
        + '</div>'
        + '<div class="site-footer__legal font-mono">'
        + '<span>&copy; 2025-2026 乐启享机器人 · 所有权利保留</span>'
        + '<a href="https://beian.miit.gov.cn/" target="_blank" rel="nofollow">鄂ICP备2025149404号-1</a>'
        + '</div>'
        + '</div>'
        + '</footer>'
    )
    parts.append('<div class="image-lightbox" id="imageLightbox" hidden role="dialog" aria-modal="true" aria-label="图片放大">'
        + '<button class="image-lightbox__close" type="button" aria-label="关闭">'
        + '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"></path></svg>'
        + '</button>'
        + '<figure class="image-lightbox__figure">'
        + '<img class="image-lightbox__image" alt="">'
        + '<figcaption class="image-lightbox__caption font-mono"></figcaption>'
        + '</figure>'
        + '</div>'
    )
    parts.append('<script src="' + escape(script_url) + '" defer></script></body></html>')
    return ''.join(parts)
