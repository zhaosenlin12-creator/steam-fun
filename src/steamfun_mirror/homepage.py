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

HERO_VIDEO_FILE = "hero-cloudfront-20260331-045634.mp4"
ABOUT_VIDEO_FILE = "about-cloudfront-20260331-151551.mp4"
SIGNAL_VIDEO_FILE = "signal-cloudfront-20260331-055729.mp4"

CINEMA_ITEMS = [
    ("showreel-birthday.mp4", "showreel-01.webp", "学员生日会 · 共享欢乐时光"),
    ("ai-camp-clip.mp4", "showreel-02.webp", "特色课 · AI 创赛营课程片段"),
    ("huodong.mp4", "showreel-huodong.webp", "校区活动 · 学员日常实录"),
    ("camp1.mp4", "showreel-camp1.webp", "特色课 · 夏令营集训"),
    ("camp2.mp4", "showreel-camp2.webp", "特色课 · VR 沉浸体验"),
    ("camp3.mp4", "showreel-camp3.webp", "特色课 · WRO 备赛实录"),
    ("hero-cloudfront-20260331-045634.mp4", "campus-01.webp", "创客工坊 · 乐高搭建现场"),
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
    ("wechat", "\u5fae\u4fe1\uff1a18164173640", "weixin://"),
    ("phone", "\u7535\u8bdd\uff1a18164173640", "tel:18164173640"),
    ("pin", "\u6821\u533a\uff1a\u5b9c\u660c\u5e02\u7307\u4ead\u533a\u91d1\u5cad\u8def59-1\u53f7", "#signal"),
]

COURSE_PATH = [
    ("乐高启蒙", "3-6 岁 · 积木搭建与空间想象", "Wedo", ["course-gallery/lego-1.webp", "course-gallery/lego-2.webp", "course-gallery/visual-1.webp", "course-gallery/visual-2.webp"]),
    ("机器人工程", "7-10 岁 · 结构 · 动力 · 编程", "Ev3 / Spike", ["course-gallery/robot-1.webp", "course-gallery/robot-2.webp", "course-gallery/robot-3.webp", "course-gallery/robot-4.webp", "course-gallery/robot-5.webp"]),
    ("Python 编程", "10-14 岁 · 算法 · 项目开发", "Code · AI", ["course-gallery/python-1.webp", "course-gallery/python-2.webp", "course-gallery/python-3.webp", "course-gallery/python-4.webp", "course-gallery/python-5.webp", "course-gallery/python-6.webp"]),
    ("创赛与特色课", "8 岁+ · 图形化 · Python · 航模", "Competition", ["course-gallery/competition-1.webp", "course-gallery/competition-2.webp", "course-gallery/competition-3.webp", "course-gallery/scratch-1.webp", "course-gallery/aircraft-1.webp"]),
]

TEACHER_POSTERS = [
    ("teacher-liu.png", "刘海涵", "乐启享创始人 · 校长", "https://zhaoyu-2h8.pages.dev/", "7 年校区经营与课程管理经验，负责乐启享整体发展与教学品质。"),
    ("teacher-senlin.png", "森林老师", "副校长 · 合伙人", "https://senlin-c1n.pages.dev/", "资深编程教研，负责课程研发、教师培养与项目式课堂设计。"),
    ("teacher-xiang.png", "向敏", "资深乐高 + 编程双导师", "https://xiangmin-lego.pages.dev/", "5 年一线教学经验，覆盖乐高搭建、机械结构与编程启蒙。"),
    ("teacher-zhou.png", "周玉锋", "资深图形化 + 硬件导师", "https://main.zhouyufeng-website.pages.dev", "5 年教学经验，专注图形化编程、硬件控制与机器人项目。"),
    ("teacher-yang.png", "杨陶", "教学主管", "https://yangtao-c8u.pages.dev/", "6 年教学与教研经验，负责课程实施、课堂质量与教师协作。"),
    ("teacher-zhao.png", "赵玉", "教务 · 财务", "https://zhaoyu-2h8.pages.dev/", "6 年教务运营经验，负责学员服务、排课与校区日常管理。"),
]

HONOR_CARDS = [
    ("honors/3c4b1c9a2f99fd3aedb86712b709b6a2.webp", "全国青少年机器人竞赛颁奖合影", "一等奖 2024"),
    ("honors/3eec15d34062bf6ef680de67fb74689f.webp", "WRCC2025 宜昌锦标赛 BoxBot 小学组 颁奖", "冠军 2025"),
    ("honors/415738909ed8cf9eb1594535c8e3537e.webp", "WRCC2025 北京锦标赛 三学员合影", "参赛 2025"),
    ("honors/47cdc27feee3d1ca5a1c2de341202475.webp", "全国青少年机器人竞赛颁奖合影", "获奖 2024"),
    ("honors/4be2d8ed8c0608e5a76aaff44fea0b86.webp", "第四届乐高机器人大赛颁奖合影", "获奖 2024"),
    ("honors/4c034334db22d80ecae7cd665b142e62.webp", "WRCC2025 北京锦标赛 乐博士队合影", "参赛 2025"),
    ("honors/57b76a27feb1167ff4387a3bcb517eae.webp", "WRCC2025 宜昌锦标赛 BoxBot 中学组 颁奖", "冠军 2025"),
    ("honors/6e43b26aa8d461efbe6bfd108898c4bf.webp", "WRCC2025 北京锦标赛 三学员合影", "参赛 2025"),
    ("honors/8f227f5af1a8258132ca7a181cb5f8c7.webp", "第四届乐高机器人编程大赛合影", "获奖 2024"),
    ("honors/9f553117006eb7273508fce3e103dc84.webp", "第四届乐高机器人编程大赛颁奖合影", "获奖 2024"),
    ("honors/c61cbbd3848e84e3ef947fb05a6ea4e4.webp", "第四届乐高机器人编程大赛颁奖合影", "获奖 2024"),
    ("honors/cert1.webp", "WRCT2024 世界机器人大赛选拔赛一等奖证书", "森林队3 2024"),
    ("honors/cert4.webp", "WRCC2024 世界机器人大赛锦标赛冠军证书", "奇思妙想 2024"),
    ("honors/cert5.webp", "WRCF2023 世界机器人大赛总决赛一等奖证书", "宜昌乐博士一队 2023"),
    ("honors/certer3.webp", "第八届全国青少年无人机大赛二等奖证书", "冯智远 2024"),
    ("honors/d3112f025a571be58aa80e2ee73623d2.webp", "WRCC2025 宜昌锦标赛 BoxBot 中学组 颁奖", "冠军 2025"),
    ("honors/ebe03b95c25fec9d8b86d3108992b09f.webp", "第四届乐高机器人编程大赛颁奖合影", "获奖 2024"),
    ("honors/festival4.webp", "WRCC2025 宜昌锦标赛 BoxBot 小学组 颁奖", "冠军 2025"),
]

CAMPUS_CARDS = [
    ("home/1.webp", "乐启享校区门面", "金岭路校区 · 做有温度的教育"),
    ("home/2.webp", "乐高搭建教室", "真实教学空间 · 分组实践区"),
    ("home/3.webp", "创客工坊 · 设备齐备", "真实工坊 · 独立操作台"),
    ("campus-02.webp", "乐高搭建教室", "搭建与调试 · 项目实践"),
    ("campus-03.webp", "竞赛集训空间", "竞赛集训 · 团队协作"),
    ("campus-04.webp", "编程课堂", "Scratch / Python / C++ 教学现场"),
    ("campus-05.webp", "学员作品展区", "作品发表 · 公开展示"),
    ("campus-classroom-3.webp", "机器人课堂", "课堂实拍 · 搭建与调试"),
    ("campus-classroom-6.webp", "编程教学现场", "真实课堂 · 项目式学习"),
    ("campus-space-1.webp", "校区活动空间", "开放交流 · 学员展示"),
    ("campus-space-2.webp", "创客工坊", "器材齐备 · 动手实践"),
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

def _render_course_card(title: str, blurb: str, tag: str, images: list[str]) -> str:
    slides = []
    dots = []
    for index, image in enumerate(images):
        src = homepage_asset_url("media/" + image)
        active = " is-active" if index == 0 else ""
        slides.append(f'<img class="nft-card__image nft-card__slide{active}" data-course-slide loading="lazy" decoding="async" src="{escape(src)}" alt="{escape(title)}课程图片 {index + 1}">')
        dots.append(f'<button class="nft-card__dot{active}" type="button" data-course-dot="{index}" aria-label="查看第 {index + 1} 张课程图片"></button>')
    return (
        '<article class="nft-card liquid-glass" data-course-carousel>'
        '<div class="nft-card__video-wrap">' + ''.join(slides)
        + '<button class="nft-card__slide-nav nft-card__slide-nav--prev" type="button" data-course-prev aria-label="上一张">&#8249;</button>'
        + '<button class="nft-card__slide-nav nft-card__slide-nav--next" type="button" data-course-next aria-label="下一张">&#8250;</button>'
        + '<div class="nft-card__dots">' + ''.join(dots) + '</div></div>'
        '<div class="nft-card__overlay"><div class="nft-card__meta">'
        + '<span class="nft-card__label font-mono">' + escape(tag) + ' · ' + str(len(images)) + ' 张课程实拍</span>'
        + '<span class="nft-card__score font-grotesk">' + escape(title) + '</span>'
        + '<span class="nft-card__blurb font-mono">' + escape(blurb) + '</span></div>'
        + '<a class="nft-card__arrow" href="' + escape(BRAND_COURSE_URL) + '" target="_blank" rel="noreferrer" aria-label="查看完整课程体系">'
        + _icon_svg("arrow") + '</a></div></article>'
    )

def _render_cards() -> str:
    return "".join(_render_course_card(*card) for card in COURSE_PATH)


def _render_teacher_strip() -> str:
    """Teacher strip rendered as a horizontal scroller using the
    same pattern as the honor / campus carousels. The poster
    image opens the shared image-lightbox on click; the
    "view personal page" entry is an explicit external link
    styled as a button."""
    cells = []
    for image, name, role, site, blurb in TEACHER_POSTERS:
        src_url = homepage_asset_url("media/" + image)
        cap = escape(name) + " . " + escape(role)
        home_label_aria = escape(name) + " " + "个人主页"
        cell_html = (
            "<figure class=" + chr(34) + "teacher-cell liquid-glass" + chr(34) + " "
            + "data-lightbox-src=" + chr(34) + escape(src_url) + chr(34) + " "
            + "data-lightbox-caption=" + chr(34) + cap + chr(34) + ">"
            + "<img class=" + chr(34) + "teacher-cell__image" + chr(34)
            + " loading=" + chr(34) + "lazy" + chr(34)
            + " decoding=" + chr(34) + "async" + chr(34) + " "
            + "src=" + chr(34) + escape(src_url) + chr(34)
            + " alt=" + chr(34) + escape(name) + chr(34) + ">"
            + "<figcaption class=" + chr(34) + "teacher-cell__overlay" + chr(34) + ">"
            + "<span class=" + chr(34) + "teacher-cell__name font-grotesk" + chr(34)
            + ">" + escape(name) + "</span>"
            + "<span class=" + chr(34) + "teacher-cell__role font-mono" + chr(34)
            + ">" + escape(role) + "</span>"
            + "<span class=" + chr(34) + "teacher-cell__blurb font-mono" + chr(34)
            + ">" + escape(blurb) + "</span>"
            + "<a class=" + chr(34) + "teacher-cell__home font-grotesk" + chr(34)
            + " href=" + chr(34) + escape(site) + chr(34)
            + " target=" + chr(34) + "_blank" + chr(34)
            + " rel=" + chr(34) + "noreferrer noopener" + chr(34)
            + " aria-label=" + chr(34) + home_label_aria + chr(34) + ">"
            + "查看个人主页"
            + "<svg viewBox=" + chr(34) + "0 0 24 24" + chr(34)
            + " aria-hidden=" + chr(34) + "true" + chr(34) + ">"
            + "<path d=" + chr(34) + "m9 6 6 6-6 6" + chr(34) + "></path></svg>"
            + "</a>"
            + "</figcaption>"
            + "</figure>"
        )
        cells.append(cell_html)
    track = "".join(cells)
    prev_aria = "上一位"
    next_aria = "下一位"
    team_label = "位老师 · 师资团队介绍"
    return (
        "<div class=" + chr(34) + "teacher-strip" + chr(34)
        + " id=" + chr(34) + "teacherStrip" + chr(34) + " "
        + "data-count=" + chr(34) + str(len(TEACHER_POSTERS)) + chr(34) + ">"
        + "<button class=" + chr(34)
        + "teacher-strip__nav teacher-strip__nav--prev font-grotesk" + chr(34) + " "
        + "type=" + chr(34) + "button" + chr(34)
        + " aria-label=" + chr(34) + prev_aria + chr(34)
        + ">" + chr(38) + "#8249;</button>"
        + "<div class=" + chr(34) + "teacher-strip__viewport" + chr(34) + ">"
        + "<div class=" + chr(34) + "teacher-strip__track" + chr(34)
        + ">" + track + "</div></div>"
        + "<button class=" + chr(34)
        + "teacher-strip__nav teacher-strip__nav--next font-grotesk" + chr(34) + " "
        + "type=" + chr(34) + "button" + chr(34)
        + " aria-label=" + chr(34) + next_aria + chr(34)
        + ">" + chr(38) + "#8250;</button>"
        + "<span class=" + chr(34) + "teacher-strip__count font-mono" + chr(34)
        + ">" + str(len(TEACHER_POSTERS)) + " " + team_label + "</span>"
        + "</div>"
    )


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
                f'data-index="{index}" data-lightbox-src="{escape(src)}" data-lightbox-caption="学员风采 {index + 1}">'
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
        src_url = homepage_asset_url('media/' + image)
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
    hero_video_url = homepage_asset_url('media/' + HERO_VIDEO_FILE)
    parts.append('<video class="hero-stage__video" autoplay muted loop playsinline '
                  'poster="/_site/courses/images/home/camp2.webp" '
                  'preload="metadata" aria-hidden="true">')
    parts.append('<source src="' + escape(hero_video_url) + '" type="video/mp4">')
    parts.append('</video>')
    parts.append('<div class="hero-stage__shade"></div>')
    parts.append('<div class="container hero-stage__container">')
    parts.append('<header class="hero-header">')
    parts.append('<a class="hero-logo font-grotesk" href="#hero">')
    parts.append('<img class="hero-logo__image" src="' + homepage_asset_url('media/brand-logo.png') + '" alt="\u4e50\u542f\u4eab">')
    parts.append('</a>')
    parts.append('<nav class="hero-nav liquid-glass" aria-label="Primary">' + nav_html + '</nav>')
    parts.append('</header>')
    parts.append('<div class="hero-body">')
    parts.append('<div class="hero-copy">')
    parts.append('<span class="hero-eyebrow font-condiment">\u4e50\u542f\u4eab \u00b7 STEAM \u6559\u80b2</span>')
    parts.append('<h1 class="hero-title font-grotesk" id="heroTitle"><span class="hero-title__row"><span class="hero-title__char" aria-hidden="true">从</span><span class="hero-title__char" aria-hidden="true">乐</span><span class="hero-title__char" aria-hidden="true">高</span><span class="hero-title__char" aria-hidden="true">启</span><span class="hero-title__char" aria-hidden="true">蒙</span></span><span class="hero-title__row"><span class="hero-title__space" aria-hidden="true">&nbsp;</span>\u5230 <span class="hero-title__ai">AI</span> <span class="hero-title__char" aria-hidden="true">创</span><span class="hero-title__char" aria-hidden="true">造</span></span></h1>')
    parts.append('<p class="hero-accent font-condiment">\u4e50\u542f\u4eab\u673a\u5668\u4eba</p>')
    parts.append('<p class="hero-tagline font-mono">' + subtitle + '</p>')
    parts.append('<div class="hero-typewriter" aria-live="polite">' + '<span id="hero-typewriter-text" class="hero-typewriter__text font-mono"></span>' + '<span class="hero-typewriter__cursor" aria-hidden="true"></span></div>')
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
    parts.append('<li><span class="hero-metric__num font-grotesk">7 \u5e74</span><span class="hero-metric__label font-mono">\u672c\u5730\u6df1\u8015</span></li>')
    parts.append('<li><span class="hero-metric__num font-grotesk">100+</span><span class="hero-metric__label font-mono">\u8d5b\u4e8b\u5956\u9879</span></li>')
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
    parts.append('<aside class="signal-qr-card liquid-glass" aria-label="扫码预约体验课">'
        + '<p class="signal-qr-card__title font-condiment">\u4e50\u542f\u4eab</p>'
        + '<p class="signal-qr-card__lede font-mono">\u626b\u7801 / \u5bfc\u822a / \u62e8\u6253</p>'
        + '<figure class="signal-qr-card__figure">'
        + '<img class="signal-qr-card__image" src="' + homepage_asset_url('media/qr-liuteacher.png') + '" alt="\u5218\u8001\u5e08\u5fae\u4fe1\u4e8c\u7ef4\u7801">'
        + '</figure>'
        + '<a class="signal-qr-card__map" target="_blank" rel="noreferrer" href="https://uri.amap.com/marker?markers=110.708018,30.58667,%E4%B9%90%E5%90%AF%E4%BA%AB%E6%9C%BA%E5%99%A8%E4%BA%BA">'
        + '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2c-4 0-7 3-7 7 0 5 7 13 7 13s7-8 7-13c0-4-3-7-7-7z"></path><circle cx="12" cy="9" r="2.5"></circle></svg>'
        + '<span class="font-mono">\u91d1\u5cad\u8def59-1\u53f7 \u00b7 \u7307\u4ead\u533a</span></a>'
        + '<a class="signal-qr-card__phone font-grotesk" href="tel:18164173640">\u62e8\u6253 18164173640</a>'
        + '</aside></div></div></section>')
    parts.append('<footer class="site-footer">'
        + '<div class="container site-footer__container">'
        + '<div class="site-footer__brand">'
        + '<span class="site-footer__logo font-grotesk">乐启享机器人</span>'
        + '<span class="font-mono site-footer__tagline">从乐高启蒙 · 到 AI 创造</span>'
        + '</div>'
        + '<div class="site-footer__contact font-mono">'
        + '<span>微信：18164173640</span>'
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
