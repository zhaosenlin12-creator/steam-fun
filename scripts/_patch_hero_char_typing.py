import pathlib
p = pathlib.Path(r'D:\kaifa\.worktrees\steam_fun-20260718-114353-1\src\steamfun_mirror\site_assets\homepage\app.js')
text = p.read_text(encoding='utf-8')

addition = (
    "\n  // -- hero title per-character typing -----------------------------\n"
    "  (function () {\n"
    "    var title = document.getElementById('heroTitle');\n"
    "    if (!title) return;\n"
    "    var chars = title.querySelectorAll('.hero-title__char');\n"
    "    if (!chars.length) return;\n"
    "    chars.forEach(function (c) { c.style.opacity = '0'; c.style.transform = 'translateY(0.35em)'; });\n"
    "    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;\n"
    "    var stepDelay = reduced ? 0 : 130;\n"
    "    function revealAll() {\n"
    "      chars.forEach(function (c) { c.style.opacity = '1'; c.style.transform = 'none'; });\n"
    "    }\n"
    "    if (reduced) { revealAll(); return; }\n"
    "    chars.forEach(function (c, idx) {\n"
    "      window.setTimeout(function () {\n"
    "        c.style.transition = 'opacity 360ms ease, transform 420ms ease';\n"
    "        c.style.opacity = '1';\n"
    "        c.style.transform = 'none';\n"
    "      }, idx * stepDelay);\n"
    "    });\n"
    "  })();\n"
)
marker = "})();\n"
assert text.count(marker) == 1, "IIFE closing marker not unique"
text = text.replace(marker, addition + marker, 1)
p.write_text(text, encoding='utf-8')
print('app.js hero typing inserted')
