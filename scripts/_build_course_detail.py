import pathlib
target = pathlib.Path(r'D:\kaifa\.worktrees\steam_fun-20260718-114353-1\src\steamfun_mirror\site_assets\courses\course-detail.html')
if target.is_file():
    target.unlink()

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
  <title>课程详情 - 乐启享编程教育</title>
  <meta name="description" content="乐启享编程教育课程详情，包含完整课程大纲、学期内容和学习目标">
  <link rel="icon" href="/favicon.ico">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&family=Roboto:wght@300;400;700&family=Poppins:wght@700;800;900&display=swap">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="css/courses.css">
  <base href="/_site/courses/">
  <script>window.__LQ_COURSES_LOCAL__=true;</script>
</head>
<body class="course-detail-page">
  <nav class="courses-nav">
    <a href="index.html" class="nav-logo">
      <img src="images/logo111.png" alt="乐启享">
      <div class="nav-logo-text">
        <span class="text-blue">乐创未来</span><br>
        <span class="text-orange">启享编程</span>
      </div>
    </a>
    <a href="index.html" class="nav-back font-grotesk">&lsaquo; 返回课程体系</a>
  </nav>

  <main class="course-detail-shell">
    <section class="detail-hero" id="detailHero">
      <div class="breadcrumb">
        <a href="index.html"><i class="fas fa-arrow-left" style="margin-right:4px"></i>课程体系</a> / <span id="detailTitle">课程名称</span>
      </div>
      <h1 id="detailTitle2"></h1>
      <div class="detail-meta">
        <span><i class="fas fa-user-graduate"></i> <span id="detailAge"></span></span>
      </div>
      <div class="detail-core-goal" id="detailDesc" style="margin-top:16px"></div>
    </section>
    <div class="detail-tabs" id="detailTabs"></div>
    <div id="detailContent"></div>
    <section class="detail-cta">
      <h3>想深入了解这门课程？</h3>
      <p>可直接扫码添加老师进行一对一咨询</p>
      <a class="detail-cta-btn" href="tel:18164173640">
        <i class="fas fa-phone"></i> 拨打 18164173640
      </a>
    </section>
  </main>

  <footer class="courses-footer">
    <p>&copy; 2025-2026 乐启享编程教育 版权所有 · <a href="https://beian.miit.gov.cn/" target="_blank" rel="nofollow">鄂ICP备2025149404号-1</a></p>
  </footer>

  <script src="/_site/courses/js/course-data.js"></script>
  <script src="/_site/courses/js/courses.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', function () {
      var params = new URLSearchParams(window.location.search);
      var id = params.get('id');
      if (!id) return;
      if (typeof COURSE_DATA === 'undefined') return;
      var stage = COURSE_DATA.stages.find(function (item) { return item.id === id; });
      if (!stage) {
        document.body.innerHTML = '<main class="course-detail-shell"><h2 style="padding:80px;text-align:center;">课程未找到</h2><p style="text-align:center;"><a href="index.html">返回课程体系</a></p></main>';
        return;
      }
      document.title = stage.name + ' - 乐启享编程教育';
      if (typeof openCourseDetail === 'function') openCourseDetail(stage.id);
      var t2 = document.getElementById('detailTitle2');
      if (t2) t2.textContent = stage.name;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  </script>
</body>
</html>
"""

target.write_text(html, encoding='utf-8')
print('course-detail.html written', target)
