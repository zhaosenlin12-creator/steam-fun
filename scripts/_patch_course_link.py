import pathlib
p = pathlib.Path(r'D:\kaifa\.worktrees\steam_fun-20260718-114353-1\src\steamfun_mirror\site_assets\courses\js\courses.js')
text = p.read_text(encoding='utf-8')

old_link = '<a href="#course-detail-panel" onclick="event.stopPropagation();openCourseDetail(\'${stage.id}\')" class="course-card-btn" style="background:${stage.color}">'
new_link = '<a href="course-detail.html?id=${stage.id}" onclick="event.stopPropagation();" class="course-card-btn" style="background:${stage.color}">'
assert old_link in text, 'course card btn link not found'
text = text.replace(old_link, new_link, 1)

old_card_onclick = '<div class="course-card" onclick="openCourseDetail(\'${stage.id}\')" style="--card-accent:${stage.color};border-top:4px solid ${stage.color};">'
new_card_onclick = '<a class="course-card" href="course-detail.html?id=${stage.id}" style="--card-accent:${stage.color};border-top:4px solid ${stage.color};">'
assert old_card_onclick in text, 'card root link not found'
text = text.replace(old_card_onclick, new_card_onclick, 1)

# find the matching closing tag pattern just below the </a> for course-card-btn
# The "course-card" closing tag needs to swap from </div> to </a>. There is exactly one such wrapper in cardHtml.
closing_old = """        </div>
      </div>`;"""
# that closing pattern is for course-card, but we shouldn't rely on heuristic. Instead, find the start position and count trailing </>
start = text.find('<a class="course-card" href="course-detail.html?id=${stage.id}" style="--card-accent:${stage.color};border-top:4px solid ${stage.color};">')
assert start >= 0, 'start not found'

# Replace the FIRST  </div>\n      </div>`;  that closes the course-card container. Be careful: the rendered template:
#       <div class="course-card-top">
#         <div class="course-card-icon" style="background:${stage.color}"> ... </div>
#         <h3>${stage.name}</h3>
#         ...
#         <a class="course-card-btn" ...> 查看详情 </a>
#       </div>
#     </div>`;
# So we need to change the final </div>\n      </div>`; into </a>`; (closing <a class="course-card" ...>).
# Find this pattern from start position.
needle = "        </div>\n      </div>`;"
idx = text.find(needle, start)
assert idx >= 0, 'closing tail not found'
text = text[:idx] + "      </a>`;" + text[idx + len(needle):]

p.write_text(text, encoding='utf-8')
print('courses.js link updated')
