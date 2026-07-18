/**
 * 课程页交互逻辑
 * - 主页：卡片渲染、时间轴、路线切换、预约表单
 * - 详情页：动态渲染、Tab切换、折叠展开
 */

(function () {
  'use strict';

  // ========== 工具函数 ==========
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function getIconClass(stage) {
    const prefix = stage.iconPrefix || 'fas';
    return `${prefix} fa-${stage.icon}`;
  }

  function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  // ========== 主页逻辑 ==========
  function isMainPage() {
    return !!$('#courseCards');
  }

  function renderTimeline() {
    const el = $('#heroTimeline');
    if (!el) return;
    const nodes = [
      { label: '3岁', dot: '3', color: '#42A5F5' },
      { label: '4岁', dot: '4', color: '#2196F3' },
      { label: '5岁', dot: '5', color: '#1E88E5' },
      { label: '6岁', dot: '6', color: '#1976D2' },
      { label: '7-10岁', dot: '7+', color: '#1565C0' },
      { label: '10岁+', dot: '10+', color: '#0D47A1' },
      { label: '竞赛', dot: '赛', color: '#0D47A1' },
      { label: 'AI', dot: 'AI', color: '#283593' }
    ];
    el.innerHTML = nodes.map((n, i) =>
      (i > 0 ? '<div class="timeline-line"></div>' : '') +
      `<div class="timeline-node">
        <div class="timeline-dot" style="background:${n.color}">${n.dot}</div>
        <div class="timeline-label">${n.label}</div>
      </div>`
    ).join('');
  }

  // 课程配图映射（有实拍图的课程用真实图，其余用精美渐变+图标）
  const COURSE_IMAGES = {
    'lego-big': 'images/lego-course.webp',
    'small-block': 'images/challenge4.webp',
    'wedo': 'images/community3.webp',
    'scratch': 'images/literacy4.webp',
    'python': 'images/python-course.webp',
    'cpp': 'images/cpp-course.webp',
    'ai-camp': 'images/challenge2.webp'
  };

  function renderCourseCards() {
    const el = $('#courseCards');
    if (!el) return;
    el.innerHTML = COURSE_DATA.stages.map(stage => {
      const img = COURSE_IMAGES[stage.id];
      const imgHtml = img
        ? `<div class="course-card-img"><img src="${img}" alt="${stage.name}" loading="lazy"></div>`
        : `<div class="course-card-img-fallback" style="background:linear-gradient(135deg, ${stage.color} 0%, ${hexToRgba(stage.color, 0.78)} 50%, ${hexToRgba(stage.color, 0.55)} 100%)">
            <svg class="fallback-decor" viewBox="0 0 400 160" xmlns="http://www.w3.org/2000/svg">
              <circle cx="360" cy="10" r="90" fill="rgba(255,255,255,0.06)"/>
              <circle cx="30" cy="155" r="110" fill="rgba(255,255,255,0.04)"/>
              <path d="M0 110 Q100 70 200 95 Q300 120 400 80" stroke="rgba(255,255,255,0.1)" fill="none" stroke-width="1.2"/>
              <path d="M0 140 Q150 100 300 125 Q380 145 400 115" stroke="rgba(255,255,255,0.06)" fill="none" stroke-width="1"/>
              <rect x="285" y="8" width="36" height="36" rx="8" transform="rotate(18 303 26)" fill="rgba(255,255,255,0.04)"/>
              <rect x="50" y="18" width="26" height="26" rx="5" transform="rotate(-15 63 31)" fill="rgba(255,255,255,0.035)"/>
              <circle cx="180" cy="28" r="4" fill="rgba(255,255,255,0.12)"/>
              <circle cx="270" cy="68" r="3" fill="rgba(255,255,255,0.1)"/>
              <circle cx="115" cy="88" r="3.5" fill="rgba(255,255,255,0.08)"/>
            </svg>
            <i class="${getIconClass(stage)}"></i>
          </div>`;
      return `
      <div class="course-card" onclick="window.location.href='course-detail.html?id=${stage.id}'" style="--card-accent:${stage.color};border-top:4px solid ${stage.color};">
        ${imgHtml}
        <div class="course-card-top">
          <div class="course-card-icon" style="background:${stage.color}">
            <i class="${getIconClass(stage)}"></i>
          </div>
          <h3>${stage.name}</h3>
          <div class="course-card-age"><i class="fas fa-user-graduate"></i> ${stage.ageRange}</div>
          <p class="course-card-tagline">${stage.tagline}</p>
          <div class="course-card-highlights">
            ${stage.highlights.map(h => `<span style="background:${hexToRgba(stage.color, 0.1)};color:${stage.color}">${h}</span>`).join('')}
          </div>
          <a href="course-detail.html?id=${stage.id}" class="course-card-btn" style="background:${stage.color}">
            查看详情 <i class="fas fa-arrow-right"></i>
          </a>
        </div>
      </div>`;
    }).join('');
  }

  function renderRoutes() {
    ['basic', 'advanced'].forEach(key => {
      const el = $(`#route-${key}`);
      if (!el) return;
      const route = COURSE_DATA.routes[key];
      const stageMap = {};
      COURSE_DATA.stages.forEach(s => stageMap[s.id] = s);

      el.innerHTML = `
        <p style="text-align:center;color:var(--gray);margin-bottom:24px;font-size:0.9rem">${route.description}</p>
        <div class="route-flow">
          ${route.milestones.map((m, i) => {
            const s = stageMap[m.stage];
            const color = s ? s.color : '#3570B5';
            const icon = s ? getIconClass(s) : 'fas fa-star';
            return (i > 0 ? '<div class="route-arrow"></div>' : '') +
              `<div class="route-step" onclick="window.location.href='course-detail.html?id=${m.stage}'" style="cursor:pointer">
                <div class="route-step-icon" style="background:${color}"><i class="${icon}"></i></div>
                <div class="route-step-info">
                  <h4>${m.label}</h4>
                  <p>${m.desc}</p>
                </div>
              </div>`;
          }).join('')}
        </div>`;
    });

    // Tab switching
    $$('.route-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        $$('.route-tab').forEach(t => t.classList.remove('active'));
        $$('.route-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        $(`#route-${tab.dataset.route}`).classList.add('active');
      });
    });
  }

  function initBookingForm() {
    const form = $('#courseBookingForm');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = $('#bookingName').value.trim();
      const phone = $('#bookingPhone').value.trim();
      const message = $('#bookingMessage').value.trim();

      if (!name || !phone) {
        showMessage('请填写姓名和联系电话', 'warning');
        return;
      }
      if (!/^1\d{10}$/.test(phone)) {
        showMessage('请输入正确的手机号码', 'warning');
        return;
      }

      const btn = form.querySelector('.booking-submit');
      btn.disabled = true;
      btn.textContent = '提交中...';

      try {
        await submitBooking({
          name,
          phone,
          message: message || '来自课程体系页',
          source: 'courses_page'
        });
        showMessage('预约成功！我们将尽快与您联系', 'success');
        form.reset();
      } catch (err) {
        showMessage('提交失败，请稍后重试或直接拨打 18164173640', 'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-paper-plane" style="margin-right:6px"></i>提交预约';
      }
    });
  }

  // ========== 详情页逻辑 ==========
  function isDetailPage() {
    return !!$('#detailHero');
  }

  function getUrlParams() {
    const params = new URLSearchParams(window.location.search);
    return { id: params.get('id'), age: params.get('age') };
  }

  function renderDetailPage() {
    const { id, age } = getUrlParams();
    const stage = COURSE_DATA.stages.find(s => s.id === id);
    if (!stage) {
      document.body.innerHTML = '<div style="text-align:center;padding:100px 20px"><h2>课程未找到</h2><p><a href="courses.html" style="color:#1a73e8">返回课程体系</a></p></div>';
      return;
    }

    // Hero
    const hero = $('#detailHero');
    hero.style.background = `linear-gradient(135deg, ${stage.color} 0%, ${hexToRgba(stage.color, 0.7)} 100%)`;
    $('#detailTitle').textContent = stage.name;
    $('#detailAge').textContent = stage.ageRange;
    $('#detailDesc').textContent = stage.description;

    // Tabs & Content
    const tabsEl = $('#detailTabs');
    const contentEl = $('#detailContent');
    let tabs = [];

    if (stage.id === 'lego-big') {
      // Lego: tabs per age
      const targetAge = age ? parseInt(age) : null;
      stage.subCourses.forEach(sc => {
        sc.terms.forEach(term => {
          tabs.push({
            label: `${sc.age}岁 ${term.termName}`,
            id: `age${sc.age}-${term.termName}`,
            type: 'lego',
            data: { lessons: term.lessons, coreGoal: sc.coreGoal, summary: sc.summary, age: sc.age, color: stage.color }
          });
        });
      });
      // Auto-select matching age tab
      if (targetAge) {
        const idx = tabs.findIndex(t => t.data.age === targetAge);
        if (idx > 0) tabs[idx]._autoSelect = true;
      }
    } else if (stage.id === 'small-block' || stage.id === 'wedo') {
      // Semester-based
      stage.subCourses.forEach(sc => {
        tabs.push({
          label: sc.semester,
          id: sc.semester.replace(/\s/g, '-'),
          type: 'semester',
          data: { ...sc, color: stage.color }
        });
      });
    } else if (stage.id === 'ai-camp') {
      // Single tab
      const sc = stage.subCourses[0];
      tabs.push({
        label: sc.semester,
        id: 'ai-7day',
        type: 'programming',
        data: { ...sc, color: stage.color }
      });
    } else {
      // Programming courses: group by route
      const basic = stage.subCourses.filter(sc => sc.route === '基础');
      const adv = stage.subCourses.filter(sc => sc.route === '高阶');
      [...basic, ...adv].forEach(sc => {
        tabs.push({
          label: `${sc.semester} ${sc.theme.split('·')[0]}`,
          id: sc.semester,
          type: 'programming',
          data: { ...sc, color: stage.color }
        });
      });
    }

    // Render tabs
    let autoIdx = tabs.findIndex(t => t._autoSelect);
    if (autoIdx < 0) autoIdx = 0;

    // #6 Fix: 仅渲染初始激活 Tab；其余 Tab 打上 data-lazy-pending 按需渲染
    const tabDataMap = {};
    tabs.forEach(t => { tabDataMap[t.id] = t; });

    tabsEl.innerHTML = tabs.map((t, i) =>
      `<button class="detail-tab${i === autoIdx ? ' active' : ''}" data-tab="${t.id}">${t.label}</button>`
    ).join('');

    contentEl.innerHTML = tabs.map((t, i) => {
      const isActive = i === autoIdx;
      return `<div class="tab-content${isActive ? ' active' : ''}" id="tab-${t.id}"${!isActive ? ' data-lazy-pending="1"' : ''}>${
        isActive ? renderTabContent(t) : ''
      }</div>`;
    }).join('');

    // Tab click — 点击时如果内容尚未渲染则就地渲染
    $$('.detail-tab', tabsEl).forEach(tab => {
      tab.addEventListener('click', () => {
        $$('.detail-tab', tabsEl).forEach(t => t.classList.remove('active'));
        $$('.tab-content', contentEl).forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        const pane = $(`#tab-${tab.dataset.tab}`, contentEl);
        if (pane.dataset.lazyPending) {
          pane.innerHTML = renderTabContent(tabDataMap[tab.dataset.tab]);
          delete pane.dataset.lazyPending;
        }
        pane.classList.add('active');
      });
    });

    // Fold/expand
    contentEl.addEventListener('click', (e) => {
      const header = e.target.closest('.lesson-header');
      if (!header) return;
      const detail = header.nextElementSibling;
      const toggle = header.querySelector('.lesson-toggle');
      if (detail && detail.classList.contains('lesson-detail')) {
        detail.classList.toggle('show');
        if (toggle) toggle.classList.toggle('expanded');
      }
    });
  }

  function renderTabContent(tab) {
    const d = tab.data;
    const color = d.color || '#3570B5';
    let html = '';

    // Core goal (for lego)
    if (tab.type === 'lego' && d.coreGoal) {
      html += `<div class="detail-core-goal" style="background:${hexToRgba(color, 0.06)};margin:0 5% 16px">
        <strong style="color:${color}">核心目标：</strong>${d.coreGoal}
      </div>`;
    }

    // Theme (for programming/semester)
    if (d.theme) {
      html += `<div style="padding:12px 5%;font-size:0.9rem;color:var(--gray)"><i class="fas fa-bookmark" style="color:${color};margin-right:6px"></i>主题：${d.theme}</div>`;
    }

    // Lessons
    html += '<div class="lessons-container">';
    d.lessons.forEach((lesson, i) => {
      const num = lesson.num || (i + 1);

      if (tab.type === 'lego') {
        // Lego: expandable with skill/building/social
        html += `<div class="lesson-card">
          <div class="lesson-header">
            <div class="lesson-num" style="background:${color}">${num}</div>
            <div class="lesson-title">${lesson.title}</div>
            <i class="fas fa-chevron-down lesson-toggle"></i>
          </div>
          <div class="lesson-detail">
            ${lesson.skill ? `<div class="lesson-detail-item"><span class="label">知识目标</span><span>${lesson.skill}</span></div>` : ''}
            ${lesson.building ? `<div class="lesson-detail-item"><span class="label">搭建要点</span><span>${lesson.building}</span></div>` : ''}
            ${lesson.social ? `<div class="lesson-detail-item"><span class="label">能力培养</span><span>${lesson.social}</span></div>` : ''}
          </div>
        </div>`;
    } else {
        // Other types: expandable knowledge/project/ability detail
        const hasDetail = lesson.knowledge || lesson.project || lesson.ability;
        // #13 Fix: 对缺少 project/ability 字段的课程，展开后显示友好提示，避免空白落差
        const projectHtml = lesson.project
          ? `<div class="lesson-detail-item"><span class="label">项目实践</span><span>${lesson.project}</span></div>`
          : '<div class="lesson-detail-item lesson-detail-pending"><span class="label">项目实践</span><span style="color:var(--gray,#999);font-style:italic">详细内容展示中</span></div>';
        const abilityHtml = lesson.ability
          ? `<div class="lesson-detail-item"><span class="label">能力培养</span><span>${lesson.ability}</span></div>`
          : '<div class="lesson-detail-item lesson-detail-pending"><span class="label">能力培养</span><span style="color:var(--gray,#999);font-style:italic">详细内容展示中</span></div>';
        html += `<div class="lesson-card">
          <div class="lesson-header">
            <div class="lesson-num" style="background:${color}">${num}</div>
            <div class="lesson-title">${lesson.title}</div>
            ${hasDetail ? '<i class="fas fa-chevron-down lesson-toggle"></i>' : ''}
          </div>
          ${hasDetail ? `<div class="lesson-detail">
            ${lesson.knowledge ? `<div class="lesson-detail-item"><span class="label">知识点</span><span>${lesson.knowledge}</span></div>` : ''}
            ${projectHtml}
            ${abilityHtml}
          </div>` : ''}
        </div>`;
      }
    });
    html += '</div>';

    // Stage output
    if (d.stageOutput) {
      html += `<div class="stage-output">
        <h4><i class="fas fa-star" style="margin-right:6px"></i>阶段产出</h4>
        <p>${d.stageOutput}</p>
      </div>`;
    }

    // Semester summary
    if (d.semesterSummary) {
      const ss = d.semesterSummary;
      html += `<div class="semester-summary">
        <h3><i class="fas fa-chart-bar" style="margin-right:6px"></i>学期总结</h3>
        ${ss.structures ? `<p style="font-size:0.85rem;margin-bottom:10px"><strong>核心结构：</strong>${ss.structures}</p>` : ''}
        ${ss.hardware ? `<p style="font-size:0.85rem;margin-bottom:10px"><strong>硬件：</strong>${ss.hardware}</p>` : ''}
        ${ss.programming ? `<p style="font-size:0.85rem;margin-bottom:10px"><strong>编程模块：</strong>${ss.programming}</p>` : ''}
        ${ss.abilities ? `<div class="summary-tags">${ss.abilities.map(a => `<span class="summary-tag">${a}</span>`).join('')}</div>` : ''}
      </div>`;
    }

    // Summary (for lego sub)
    if (tab.type === 'lego' && d.summary) {
      html += `<div class="semester-summary">
        <h3><i class="fas fa-flag-checkered" style="margin-right:6px"></i>学期总结</h3>
        <p style="font-size:0.85rem;line-height:1.7">${d.summary}</p>
      </div>`;
    }

    return html;
  }

  // ========== 通用功能 ==========
  window.toggleMenu = function () {
    const nav = $('#navLinks');
    if (nav) nav.classList.toggle('open');
  };

  // Close mobile menu on link click
  document.addEventListener('click', (e) => {
    if (e.target.closest('.nav-links a')) {
      const nav = $('#navLinks');
      if (nav) nav.classList.remove('open');
    }
  });

  // Scroll animations with staggered delays
  function initScrollAnimations() {
    if (!('IntersectionObserver' in window)) return;

    // 卡片和功能区渐入
    const fadeObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animate-in');
          fadeObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });

    $$('.course-card, .ai-feature-card, .route-step, .gallery-section .section-header, .booking-card').forEach(el => {
      fadeObserver.observe(el);
    });

    // 时间轴节点弹出动画
    const popObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const nodes = entry.target.querySelectorAll('.timeline-node');
          nodes.forEach((node, i) => {
            node.style.animationDelay = `${i * 0.1}s`;
            node.classList.add('animate-pop');
          });
          popObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.3 });

    const timeline = $('#heroTimeline');
    if (timeline) popObserver.observe(timeline);
  }

  // ========== Init ==========
  document.addEventListener('DOMContentLoaded', () => {
    if (isMainPage()) {
      renderTimeline();
      renderCourseCards();
      renderRoutes();
      initBookingForm();
      setTimeout(initScrollAnimations, 100);
    } else if (isDetailPage()) {
      renderDetailPage();
    }
  });
})();
