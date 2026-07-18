from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import Request

HOMEPAGE_ASSET_PREFIX = "/_site/homepage"
HOMEPAGE_ASSET_ROOT = Path(__file__).resolve().parent / "site_assets" / "homepage"
GOOGLE_FONTS_URL = "https://fonts.googleapis.com/css2?family=Anton&family=Condiment&display=swap"

HERO_VIDEO_URL = (
    "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/"
    "hf_20260331_045634_e1c98c76-1265-4f5c-882a-4276f2080894.mp4"
)
ABOUT_VIDEO_URL = (
    "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/"
    "hf_20260331_151551_992053d1-3d3e-4b8c-abac-45f22158f411.mp4"
)
CTA_VIDEO_URL = (
    "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/"
    "hf_20260331_055729_72d66327-b59e-4ae9-bb70-de6ccb5ecdb0.mp4"
)

ABOUT_COPY = "A digital object fixed beyond time and place. An exploration of distance, form, and silence in space"

NAV_ITEMS = [
    ("#hero", "Homepage"),
    ("#collection", "Gallery"),
    ("#collection", "Buy NFT"),
    ("#about", "FAQ"),
    ("#signal", "Contact"),
]

SOCIAL_ITEMS = [
    ("mail", "Mail", "mailto:signal@orbis.nft"),
    ("twitter", "Twitter", "https://twitter.com"),
    ("github", "Github", "https://github.com"),
]

NFT_CARDS = [
    (
        "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/"
        "hf_20260331_053923_22c0a6a5-313c-474c-85ff-3b50d25e944a.mp4",
        "8.7/10",
    ),
    (
        "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/"
        "hf_20260331_054411_511c1b7a-fb2f-42ef-bf6c-32c0b1a06e79.mp4",
        "9/10",
    ),
    (
        "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/"
        "hf_20260331_055427_ac7035b5-9f3b-4289-86fc-941b2432317d.mp4",
        "8.2/10",
    ),
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
    }
    return paths[name]


def _render_nav() -> str:
    return "".join(
        f'<a class="nav-link font-grotesk" href="{escape(href)}">{escape(label)}</a>'
        for href, label in NAV_ITEMS
    )


def _render_social_buttons(button_class: str) -> str:
    return "".join(
        (
            f'<a class="{button_class} liquid-glass" href="{escape(url)}" aria-label="{escape(label)}" target="_blank" rel="noreferrer">'
            f"{_icon_svg(icon)}"
            "</a>"
        )
        for icon, label, url in SOCIAL_ITEMS
    )


def _render_social_rail_items() -> str:
    rows: list[str] = []
    for index, (icon, label, url) in enumerate(SOCIAL_ITEMS):
        divider = '<span class="social-rail__divider" aria-hidden="true"></span>' if index < len(SOCIAL_ITEMS) - 1 else ""
        rows.append(
            (
                '<div class="social-rail__row">'
                f'<a class="social-rail__button" href="{escape(url)}" aria-label="{escape(label)}" target="_blank" rel="noreferrer">'
                f'<span class="social-rail__icon">{_icon_svg(icon)}</span>'
                f'<span class="font-grotesk social-rail__label">{escape(label)}</span>'
                "</a>"
                f"{divider}"
                "</div>"
            )
        )
    return "".join(rows)


def _render_cards() -> str:
    cards: list[str] = []
    for video_url, score in NFT_CARDS:
        cards.append(
            (
                '<article class="nft-card liquid-glass">'
                '<div class="nft-card__video-wrap">'
                f'<video class="nft-card__video" autoplay loop muted playsinline src="{escape(video_url)}"></video>'
                "</div>"
                '<div class="nft-card__overlay liquid-glass">'
                '<div class="nft-card__meta">'
                '<span class="nft-card__label">RARITY SCORE:</span>'
                f'<span class="nft-card__score">{escape(score)}</span>'
                "</div>"
                f'<button class="nft-card__arrow" type="button" aria-label="Open creator">{_icon_svg("arrow")}</button>'
                "</div>"
                "</article>"
            )
        )
    return "".join(cards)


def render_marketing_homepage(request: Request) -> str:
    _ = request
    texture_url = homepage_asset_url("texture.png")
    stylesheet_url = homepage_asset_url("styles.css")
    script_url = homepage_asset_url("app.js")
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Orbis.Nft</title>
    <meta name="description" content="{escape(ABOUT_COPY)}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="{escape(GOOGLE_FONTS_URL)}">
    <link rel="stylesheet" href="{escape(stylesheet_url)}">
  </head>
  <body>
    <div class="texture-overlay" aria-hidden="true" style="background-image:url('{escape(texture_url)}');"></div>
    <main class="page">
      <section class="hero-stage" id="hero">
        <video class="hero-stage__video" autoplay loop muted playsinline src="{escape(HERO_VIDEO_URL)}"></video>
        <div class="hero-stage__shade"></div>
        <div class="container hero-stage__container">
          <header class="hero-header">
            <a class="hero-logo font-grotesk" href="#hero">Orbis.Nft</a>
            <nav class="hero-nav liquid-glass" aria-label="Primary">
              {_render_nav()}
            </nav>
          </header>
          <div class="hero-body">
            <div class="hero-copy">
              <h1 class="hero-title font-grotesk">
                Beyond earth
                <br>
                and <span class="hero-title__parenthetical">( its )</span> familiar boundaries
              </h1>
              <p class="hero-accent font-condiment">Nft collection</p>
            </div>
            <div class="hero-social hero-social--desktop" aria-label="Social links">
              {_render_social_buttons("social-square")}
            </div>
          </div>
          <div class="hero-social hero-social--mobile" aria-label="Social links">
            {_render_social_buttons("social-square")}
          </div>
        </div>
      </section>

      <section class="about-stage" id="about">
        <video class="about-stage__video" autoplay loop muted playsinline src="{escape(ABOUT_VIDEO_URL)}"></video>
        <div class="about-stage__shade"></div>
        <div class="container about-stage__container">
          <div class="about-top">
            <div class="about-title-wrap">
              <h2 class="about-title font-grotesk">
                Hello!
                <br>
                I'm orbis
              </h2>
              <p class="about-accent font-condiment">Orbis</p>
            </div>
            <p class="about-intro font-mono">{escape(ABOUT_COPY)}</p>
          </div>
          <div class="about-bottom">
            <div class="about-fade about-fade--left">
              <p class="font-mono">{escape(ABOUT_COPY)}</p>
              <p class="font-mono">{escape(ABOUT_COPY)}</p>
            </div>
            <div class="about-fade about-fade--right">
              <p class="font-mono">{escape(ABOUT_COPY)}</p>
              <p class="font-mono">{escape(ABOUT_COPY)}</p>
            </div>
          </div>
        </div>
      </section>

      <section class="collection-stage" id="collection">
        <div class="container collection-stage__container">
          <div class="collection-header">
            <div class="collection-heading">
              <h2 class="collection-title font-grotesk">Collection of</h2>
              <div class="collection-title-line">
                <span class="collection-accent font-condiment">Space</span>
                <span class="collection-objects font-grotesk">objects</span>
              </div>
            </div>
            <a class="see-all" href="#signal">
              <div class="see-all__text">
                <span class="see-all__see font-grotesk">SEE</span>
                <span class="see-all__stack font-grotesk">
                  <span>ALL</span>
                  <span>CREATORS</span>
                </span>
              </div>
              <span class="see-all__full-text">SEE ALL CREATORS</span>
              <span class="see-all__bar" aria-hidden="true"></span>
            </a>
          </div>
          <div class="nft-grid">
            {_render_cards()}
          </div>
        </div>
      </section>

      <section class="signal-stage" id="signal">
        <div class="container signal-stage__container">
          <div class="signal-stage__media">
            <video class="signal-stage__video" autoplay loop muted playsinline src="{escape(CTA_VIDEO_URL)}"></video>
            <div class="signal-copy">
              <p class="signal-accent font-condiment">Go beyond</p>
              <h2 class="signal-title font-grotesk">
                <span class="signal-title__lead">JOIN US.</span>
                <span>REVEAL WHAT'S HIDDEN.</span>
                <span>DEFINE WHAT'S NEXT.</span>
                <span>FOLLOW THE SIGNAL.</span>
              </h2>
            </div>
            <div class="social-rail liquid-glass">
              {_render_social_rail_items()}
            </div>
          </div>
        </div>
      </section>
    </main>
    <script src="{escape(script_url)}" defer></script>
  </body>
</html>
"""


__all__ = ["homepage_asset_path", "homepage_asset_url", "render_marketing_homepage"]
