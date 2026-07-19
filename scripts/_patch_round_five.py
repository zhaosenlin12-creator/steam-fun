import pathlib
p = pathlib.Path(r'D:\kaifa\.worktrees\steam_fun-20260718-114353-1\src\steamfun_mirror\homepage.py')
text = p.read_text(encoding='utf-8')

# Replace the bottom rail block with a top-right QR card. Keep the four-line signal title as-is.
old_rail = (
    "    parts.append('<div class=\"social-rail liquid-glass\">' + rail_html + '</div></div></div></section>')\n"
)
new_rail = (
    "    parts.append('<aside class=\"signal-qr-card liquid-glass\" aria-label=\"扫码预约体验课\">'\n"
    "        + '<p class=\"signal-qr-card__title font-condiment\">\\u52a0\\u5165\\u4e50\\u542f\\u4eab</p>'\n"
    "        + '<p class=\"signal-qr-card__lede font-mono\">\\u626b\\u7801\\u9884\\u7ea6\\u4f53\\u9a8c\\u8bfe</p>'\n"
    "        + '<figure class=\"signal-qr-card__figure\">'\n"
    "        + '<img class=\"signal-qr-card__image\" src=\"' + homepage_asset_url('media/qr-liuteacher.png') + '\" alt=\"\\u5218\\u8001\\u5e08\\u5fae\\u4fe1\\u4e8c\\u7ef4\\u7801\">'\n"
    "        + '<figcaption class=\"signal-qr-card__caption font-mono\">\\u5218\\u8001\\u5e08 \\u00b7 \\u5fae\\u4fe1 18164173640</figcaption>'\n"
    "        + '</figure>'\n"
    "        + '<p class=\"signal-qr-card__phone font-grotesk\">\\u6216\\u62e8\\u6253 <a href=\"tel:18164173640\">18164173640</a></p>'\n"
    "        + '</aside></div></div></section>')\n"
)
assert old_rail in text, 'rail line not found'
text = text.replace(old_rail, new_rail, 1)
p.write_text(text, encoding='utf-8')
print('signal rail replaced with QR card')
