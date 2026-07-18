from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from fastapi import Request

HOMEPAGE_ASSET_PREFIX = "/_site/homepage"
HOMEPAGE_ASSET_ROOT = Path(__file__).resolve().parent / "site_assets" / "homepage"

HOMEPAGE_TITLE = "乐启享机器人"
HOMEPAGE_SUBTITLE = "从乐高启蒙到 AI 创造，系统培养孩子的科技素养与创造力"
HOMEPAGE_DESCRIPTION = "面向青少儿的乐高、机器人、编程与 AI 科技素养成长平台。"

NAV_ITEMS: list[dict[str, str]] = [
    {"href": "#brand", "label": "品牌理念"},
    {"href": "#faculty", "label": "师资团队"},
    {"href": "#gallery", "label": "学员展示"},
    {"href": "#courses", "label": "课程体系"},
    {"href": "#contact", "label": "校区联系"},
]

HERO_METRICS: list[dict[str, str]] = [
    {"value": "3-16岁", "label": "系统成长路径"},
    {"value": "4大方向", "label": "乐高 机器人 编程 AI"},
    {"value": "线下优先", "label": "校区体验与成果共建"},
]

TEACHERS: list[dict[str, str]] = [
    {
        "name": "刘老师",
        "role": "校长 / 创始人",
        "description": "负责品牌与课程总方向，把机构方法论落到孩子可持续成长上。",
        "image": "media/teacher-liu.jpg",
    },
    {
        "name": "森林老师",
        "role": "副校长 / 合伙人",
        "description": "把活动策划、项目展示与家校沟通整合成完整的成长体验。",
        "image": "media/teacher-senlin.jpg",
    },
    {
        "name": "杨老师",
        "role": "教学主管",
        "description": "把控课程节奏、课堂质量与阶段成果，让每一次学习都看得见进步。",
        "image": "media/teacher-yang.jpg",
    },
    {
        "name": "向老师",
        "role": "乐高专家",
        "description": "聚焦乐高启蒙、机械结构与动手表达，帮助孩子从搭建进入创造。",
        "image": "media/teacher-xiang.jpg",
    },
    {
        "name": "周老师",
        "role": "硬件专家",
        "description": "负责机器人、传感器与硬件创客课，把抽象原理变成真实装置。",
        "image": "media/teacher-zhou.jpg",
    },
    {
        "name": "赵老师",
        "role": "教务 / 财务",
        "description": "连接课程安排、家长服务与线下到校体验，保证学习旅程稳定顺畅。",
        "image": "media/teacher-zhao.jpg",
    },
]

STUDENT_GALLERY: list[dict[str, str]] = [
    {"title": "课堂高光", "image": "media/student-1.webp"},
    {"title": "项目展示", "image": "media/student-2.webp"},
    {"title": "营地体验", "image": "media/student-3.webp"},
    {"title": "机器人实践", "image": "media/student-4.webp"},
    {"title": "成长纪念", "image": "media/student-5.webp"},
    {"title": "互动现场", "image": "media/student-6.webp"},
    {"title": "团队协作", "image": "media/student-7.webp"},
    {"title": "作品讲述", "image": "media/student-8.webp"},
]

COURSE_CARDS: list[dict[str, str]] = [
    {
        "title": "乐高启蒙",
        "ages": "3-6岁",
        "description": "从大颗粒到机械启蒙，先建立空间感、规则感和表达欲。",
        "image": "media/course-lego.webp",
    },
    {
        "title": "机器人工程",
        "ages": "6-10岁",
        "description": "用结构、动力与传感器把动手能力升级为工程思维。",
        "image": "media/course-robot.webp",
    },
    {
        "title": "编程创造",
        "ages": "8-14岁",
        "description": "Scratch 到 Python 的系统路径，让孩子真正从会玩走向会做。",
        "image": "media/course-python.webp",
    },
    {
        "title": "AI 科技素养",
        "ages": "10-16岁",
        "description": "把创客、竞赛和 AI 场景结合，面向更高阶的解决问题能力。",
        "image": "media/course-ai.webp",
    },
]

HONORS: list[dict[str, str]] = [
    {"title": "赛事领奖", "image": "media/honor-1.webp"},
    {"title": "证书成果", "image": "media/honor-2.webp"},
    {"title": "大型展演", "image": "media/honor-3.webp"},
    {"title": "项目荣誉", "image": "media/honor-4.webp"},
]

CAMPUS: list[dict[str, str]] = [
    {
        "title": "校区外部形象",
        "description": "孩子愿意走进来，家长也能一眼感受到机构气质。",
        "image": "media/campus-1.webp",
    },
    {
        "title": "真实课堂空间",
        "description": "从课程墙到教室布局，强化到校体验和学习氛围。",
        "image": "media/campus-2.webp",
    },
    {
        "title": "活动与营地现场",
        "description": "让品牌不只停留在网页，而是能被真实感知和参与。",
        "image": "media/campus-3.webp",
    },
]

CONTACT_ITEMS: list[dict[str, str]] = [
    {
        "title": "微信咨询",
        "body": "一对一了解课程规划、试听安排与到校体验建议。",
    },
    {
        "title": "电话咨询",
        "body": "适合家长快速确认年龄段、课程方向与线下班型节奏。",
    },
    {
        "title": "校区地址",
        "body": "线下体验更重要，可先咨询后获取最近校区与到访指引。",
    },
]


def homepage_asset_url(asset_path: str) -> str:
    return f"{HOMEPAGE_ASSET_PREFIX}/{asset_path.lstrip('/')}"


def homepage_asset_path(asset_path: str) -> Path | None:
    normalized = asset_path.strip().lstrip("/").replace("\\", "/")
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


def _render_nav() -> str:
    return "".join(
        f'<a class="site-nav__link" href="{escape(item["href"])}">{escape(item["label"])}</a>'
        for item in NAV_ITEMS
    )


def _render_metrics() -> str:
    return "".join(
        (
            '<li class="hero-metric">'
            f'<span class="hero-metric__value">{escape(item["value"])}</span>'
            f'<span class="hero-metric__label">{escape(item["label"])}</span>'
            "</li>"
        )
        for item in HERO_METRICS
    )


def _render_teachers() -> str:
    cards: list[str] = []
    for teacher in TEACHERS:
        cards.append(
            (
                '<article class="teacher-card reveal">'
                f'<img class="teacher-card__image" src="{escape(homepage_asset_url(teacher["image"]))}" alt="{escape(teacher["name"])}">'
                '<div class="teacher-card__body">'
                f'<p class="teacher-card__role">{escape(teacher["role"])}</p>'
                f'<h3>{escape(teacher["name"])}</h3>'
                f'<p>{escape(teacher["description"])}</p>'
                "</div>"
                "</article>"
            )
        )
    return "".join(cards)


def _render_gallery_cards() -> str:
    cards: list[str] = []
    for item in STUDENT_GALLERY:
        cards.append(
            (
                '<button class="dome-card" type="button">'
                f'<img src="{escape(homepage_asset_url(item["image"]))}" alt="{escape(item["title"])}">'
                f'<span>{escape(item["title"])}</span>'
                "</button>"
            )
        )
    return "".join(cards)


def _render_course_cards() -> str:
    cards: list[str] = []
    for course in COURSE_CARDS:
        cards.append(
            (
                '<article class="course-card reveal">'
                f'<img class="course-card__image" src="{escape(homepage_asset_url(course["image"]))}" alt="{escape(course["title"])}">'
                '<div class="course-card__content">'
                f'<p class="course-card__ages">{escape(course["ages"])}</p>'
                f'<h3>{escape(course["title"])}</h3>'
                f'<p>{escape(course["description"])}</p>'
                "</div>"
                "</article>"
            )
        )
    return "".join(cards)


def _render_honors() -> str:
    cards: list[str] = []
    for item in HONORS:
        cards.append(
            (
                '<article class="media-tile reveal">'
                f'<img src="{escape(homepage_asset_url(item["image"]))}" alt="{escape(item["title"])}">'
                f'<span>{escape(item["title"])}</span>'
                "</article>"
            )
        )
    return "".join(cards)


def _render_campus() -> str:
    cards: list[str] = []
    for item in CAMPUS:
        cards.append(
            (
                '<article class="campus-card reveal">'
                f'<img class="campus-card__image" src="{escape(homepage_asset_url(item["image"]))}" alt="{escape(item["title"])}">'
                '<div class="campus-card__content">'
                f'<h3>{escape(item["title"])}</h3>'
                f'<p>{escape(item["description"])}</p>'
                "</div>"
                "</article>"
            )
        )
    return "".join(cards)


def _render_contact_items() -> str:
    cards: list[str] = []
    for item in CONTACT_ITEMS:
        cards.append(
            (
                '<article class="contact-card reveal">'
                f'<h3>{escape(item["title"])}</h3>'
                f'<p>{escape(item["body"])}</p>'
                "</article>"
            )
        )
    return "".join(cards)


def render_marketing_homepage(request: Request) -> str:
    _ = request
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(HOMEPAGE_TITLE)}</title>
    <meta name="description" content="{escape(HOMEPAGE_SUBTITLE)}">
    <link rel="stylesheet" href="{escape(homepage_asset_url('styles.css'))}">
  </head>
  <body>
    <div class="page-shell">
      <header class="site-header">
        <a class="brand-lockup" href="#brand" aria-label="{escape(HOMEPAGE_TITLE)}">
          <img class="brand-lockup__logo" src="{escape(homepage_asset_url('media/logo.png'))}" alt="{escape(HOMEPAGE_TITLE)}">
          <span class="brand-lockup__text">
            <strong>{escape(HOMEPAGE_TITLE)}</strong>
            <small>LEQIXIANG ROBOTICS</small>
          </span>
        </a>
        <nav class="site-nav" aria-label="首页导航">
          {_render_nav()}
        </nav>
        <a class="site-login" href="/login">登录</a>
      </header>

      <main>
        <section class="hero reveal reveal--visible" id="brand">
          <div class="hero__backdrop">
            <video class="hero__video" autoplay muted loop playsinline poster="{escape(homepage_asset_url('media/campus-1.webp'))}">
              <source src="{escape(homepage_asset_url('media/hero-video.mp4'))}" type="video/mp4">
            </video>
            <div class="hero__veil"></div>
            <div class="hero__grid"></div>
          </div>
          <div class="hero__content">
            <p class="hero__eyebrow">乐高 / 机器人 / 编程 / AI 科技素养</p>
            <h1 class="hero__title">{escape(HOMEPAGE_SUBTITLE)}</h1>
            <p class="hero__description">{escape(HOMEPAGE_DESCRIPTION)} 先让孩子被未来感吸引，再让家长看见体系、师资、成果与线下可达性。</p>
            <div class="hero__actions">
              <a class="button button--primary" href="https://codebn.cn/courses.html" target="_blank" rel="noreferrer">查看完整课程体系</a>
              <a class="button button--ghost" href="#gallery">进入成长穹顶</a>
            </div>
            <ul class="hero__metrics">
              {_render_metrics()}
            </ul>
          </div>
          <aside class="hero-panel">
            <p class="hero-panel__label">品牌主张</p>
            <h2>不是把课程摆满首页，而是把成长路径做成孩子和家长都愿意停留的展厅。</h2>
            <p>首页保留单一登录入口，教学系统仍按原路径运行；公开首页只负责建立品牌记忆、真实感和到校意愿。</p>
          </aside>
        </section>

        <section class="section section--faculty" id="faculty">
          <div class="section-copy reveal">
            <p class="section-copy__eyebrow">真实团队</p>
            <h2>让“高级感”后面立刻接上“可信任”</h2>
            <p>师资不是抽象海报，而是把创始、教学、乐高、硬件和教务服务都真实摆在首页前半段。</p>
          </div>
          <div class="teacher-grid">
            {_render_teachers()}
          </div>
        </section>

        <section class="section section--gallery" id="gallery">
          <div class="section-copy reveal">
            <p class="section-copy__eyebrow">成长穹顶</p>
            <h2>把学员展示墙做成可以旋转、拖拽、记住孩子成长瞬间的 3D 穹顶</h2>
            <p>交互方向参考本地 `prisma-web` 的 DomeGallery，表达不做普通照片墙，而是面向未来感的成长装置。</p>
          </div>
          <div class="dome-stage reveal">
            <div class="dome-focus-ring"></div>
            <div class="dome-orbit" data-tilt="-12">
              {_render_gallery_cards()}
            </div>
          </div>
        </section>

        <section class="section section--courses" id="courses">
          <div class="section-copy reveal">
            <p class="section-copy__eyebrow">课程入口</p>
            <h2>从乐高启蒙到 AI 创造，形成完整而清晰的成长台阶</h2>
            <p>首页只展示主路径和方向，完整课程体系直接承接到现有官网内容，避免在首页重复堆叠。</p>
          </div>
          <div class="course-grid">
            {_render_course_cards()}
          </div>
          <div class="section-actions reveal">
            <a class="button button--primary" href="https://codebn.cn/courses.html" target="_blank" rel="noreferrer">查看完整课程体系</a>
          </div>
        </section>

        <section class="section section--honors" id="honors">
          <div class="section-copy reveal">
            <p class="section-copy__eyebrow">赛事成果</p>
            <h2>不只展示课程，更展示孩子已经走到哪里</h2>
            <p>赛事领奖、证书成果、展演和项目记录共同构成家长最关心的“真实结果”。</p>
          </div>
          <div class="media-grid">
            {_render_honors()}
          </div>
        </section>

        <section class="section section--campus" id="campus">
          <div class="section-copy reveal">
            <p class="section-copy__eyebrow">校区环境</p>
            <h2>线下体验更重要，所以必须把空间、课堂和氛围讲清楚</h2>
            <p>校区外立面、教学空间与活动现场共同承担“到店前预体验”的作用。</p>
          </div>
          <div class="campus-grid">
            {_render_campus()}
          </div>
        </section>

        <section class="section section--showreel" id="showreel">
          <div class="showreel-card reveal">
            <div class="showreel-card__copy">
              <p class="section-copy__eyebrow">品牌视频</p>
              <h2>让家长和孩子先感受到现场，而不是先看长篇说明</h2>
              <p>这里保留视频氛围表达，后续可以继续替换为更完整的机构 showreel 与活动素材。</p>
            </div>
            <div class="showreel-card__media">
              <video controls playsinline preload="metadata" poster="{escape(homepage_asset_url('media/student-3.webp'))}">
                <source src="{escape(homepage_asset_url('media/hero-video.mp4'))}" type="video/mp4">
              </video>
            </div>
          </div>
        </section>

        <section class="section section--contact" id="contact">
          <div class="section-copy reveal">
            <p class="section-copy__eyebrow">校区联系</p>
            <h2>把咨询方式并列摆出来，让线下到校和课程沟通都自然发生</h2>
            <p>联系方式先用结构化展示承接，后续可以再替换为机构确定的具体微信、电话和校区地址。</p>
          </div>
          <div class="contact-grid">
            {_render_contact_items()}
          </div>
        </section>
      </main>
    </div>

    <div class="gallery-modal" aria-hidden="true">
      <button class="gallery-modal__scrim" type="button" aria-label="关闭预览"></button>
      <div class="gallery-modal__panel">
        <button class="gallery-modal__close" type="button" aria-label="关闭">×</button>
        <img class="gallery-modal__image" src="" alt="">
        <p class="gallery-modal__caption"></p>
      </div>
    </div>

    <script src="{escape(homepage_asset_url('app.js'))}" defer></script>
  </body>
</html>
"""


__all__ = [
    "homepage_asset_path",
    "homepage_asset_url",
    "render_marketing_homepage",
]
