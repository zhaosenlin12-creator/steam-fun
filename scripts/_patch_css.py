import pathlib
p = pathlib.Path(r'D:\kaifa\.worktrees\steam_fun-20260718-114353-1\src\steamfun_mirror\site_assets\homepage\styles.css')
text = p.read_text(encoding='utf-8')

block = (
    ".hero-title__char {\n"
    "  display: inline-block;\n"
    "  opacity: 0;\n"
    "  transform: translateY(0.4em);\n"
    "  transition: opacity 360ms ease, transform 420ms ease;\n"
    "}\n"
    ".hero-title__row { display: inline-flex; flex-wrap: wrap; align-items: baseline; gap: 0.04em; }\n"
    ".hero-title__space { display: inline-block; width: 0.6em; }\n"
    "html.is-loaded .hero-title__char { /* JS toggles -- fallback friendly */ }\n"
)
if '.hero-title__char' not in text:
    # Insert after .hero-title rule.
    marker = ".hero-title {\n  margin: 0;\n  font-size: clamp(2.5rem, 7vw, 5.625rem);\n  line-height: 1.05;\n  letter-spacing: 0.02em;\n}"
    if marker in text:
        text = text.replace(marker, marker + "\n\n" + block, 1)
    else:
        text = text.rstrip() + "\n\n" + block
    p.write_text(text, encoding='utf-8')
    print('CSS char style inserted')
else:
    print('CSS char style already present')
