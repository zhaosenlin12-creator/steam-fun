(() => {
  // -- nav highlight ----------------------------------------------------
  const links = [...document.querySelectorAll('.nav-link')];
  const sections = [...document.querySelectorAll('main section[id]')];
  if (links.length && sections.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const target = `#${entry.target.id}`;
          for (const link of links) {
            link.classList.toggle('is-active', link.getAttribute('href') === target);
          }
        }
      },
      { threshold: 0.4 }
    );
    sections.forEach((section) => observer.observe(section));
  }

  // -- cinema wall + thumbs + lightbox ----------------------------------
  const cinemaWall = document.getElementById('cinemaWall');
  const cinemaThumbs = document.querySelectorAll('.cinema-thumb');
  const cinemaVideo = cinemaWall ? cinemaWall.querySelector('.cinema-wall__video') : null;
  const cinemaEnter = cinemaWall ? cinemaWall.querySelector('.cinema-wall__enter') : null;

  const switchCinema = (thumb) => {
    if (!cinemaWall || !cinemaVideo) return;
    const src = thumb.dataset.video;
    const poster = thumb.dataset.poster;
    cinemaWall.dataset.video = src || '';
    cinemaWall.dataset.poster = poster || '';
    cinemaVideo.src = src || '';
    cinemaVideo.poster = poster || '';
    try { cinemaVideo.currentTime = 0; cinemaVideo.play(); } catch (e) {}
    cinemaThumbs.forEach((t) => t.classList.toggle('is-active', t === thumb));
  };

  cinemaThumbs.forEach((thumb) => {
    thumb.addEventListener('click', () => switchCinema(thumb));
  });

  const cinemaLightbox = document.getElementById('cinemaLightbox');
  const cinemaCloseBtn = cinemaLightbox ? cinemaLightbox.querySelector('.cinema-lightbox__close') : null;
  const cinemaLightboxVideo = cinemaLightbox ? cinemaLightbox.querySelector('.cinema-lightbox__video') : null;

  const openLightbox = () => {
    if (!cinemaLightbox || !cinemaWall || !cinemaLightboxVideo) return;
    const src = cinemaWall.dataset.video;
    cinemaLightboxVideo.src = src || '';
    // IMPORTANT: fullscreen video plays WITH sound (unmuted).
    cinemaLightboxVideo.muted = false;
    try { cinemaLightboxVideo.currentTime = 0; cinemaLightboxVideo.play(); } catch (e) {}
    cinemaLightbox.hidden = false;
    document.body.style.overflow = 'hidden';
  };
  const closeLightbox = () => {
    if (!cinemaLightbox || !cinemaLightboxVideo) return;
    cinemaLightbox.hidden = true;
    cinemaLightboxVideo.pause();
    cinemaLightboxVideo.removeAttribute('src');
    cinemaLightboxVideo.load();
    document.body.style.overflow = '';
  };

  if (cinemaEnter) cinemaEnter.addEventListener('click', openLightbox);
  if (cinemaCloseBtn) cinemaCloseBtn.addEventListener('click', closeLightbox);
  if (cinemaLightbox) {
    cinemaLightbox.addEventListener('click', (e) => { if (e.target === cinemaLightbox) closeLightbox(); });
  }
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && cinemaLightbox && !cinemaLightbox.hidden) closeLightbox();
    if (e.key === 'Escape' && imageLightbox && !imageLightbox.hidden) closeImageLightbox();
  });

  // -- honor / campus carousels ----------------------------------------
  const initCarousel = (rootSel, viewportSel, trackSel, prevSel, nextSel) => {
    const root = document.querySelector(rootSel);
    if (!root) return;
    const viewport = root.querySelector(viewportSel);
    const track = root.querySelector(trackSel);
    const prev = root.querySelector(prevSel);
    const next = root.querySelector(nextSel);
    if (!viewport || !track || !track.firstElementChild) return;
    let index = 0;
    let paused = false;
    let resumeTimer = 0;
    const cardStep = () => {
      const first = track.firstElementChild;
      const style = getComputedStyle(track);
      const gap = parseFloat(style.columnGap || style.gap || '0') || 0;
      return first.getBoundingClientRect().width + gap;
    };
    const maxIndex = () => Math.max(0, Math.ceil(Math.max(0, track.scrollWidth - viewport.clientWidth) / Math.max(1, cardStep())));
    const render = (animate = true) => {
      const max = maxIndex();
      index = max ? ((index % (max + 1)) + (max + 1)) % (max + 1) : 0;
      track.style.transition = animate ? '' : 'none';
      const maxOffset = Math.max(0, track.scrollWidth - viewport.clientWidth);
      const offset = index === max ? maxOffset : Math.min(maxOffset, index * cardStep());
      track.style.transform = `translate3d(${-offset}px, 0, 0)`;
      if (!animate) requestAnimationFrame(() => { track.style.transition = ''; });
    };
    const move = (direction) => { index += direction; render(true); };
    const resumeLater = () => {
      paused = true;
      clearTimeout(resumeTimer);
      resumeTimer = window.setTimeout(() => { paused = false; }, 4500);
    };
    prev?.addEventListener('click', () => { resumeLater(); move(-1); });
    next?.addEventListener('click', () => { resumeLater(); move(1); });
    viewport.addEventListener('mouseenter', () => { paused = true; clearTimeout(resumeTimer); });
    viewport.addEventListener('mouseleave', () => { paused = false; });
    window.addEventListener('resize', () => render(false));
    window.setInterval(() => { if (!paused) move(1); }, 3200);
    render(false);
  };

  initCarousel('#honorCarousel', '.honor-carousel__viewport', '.honor-carousel__track', '.honor-carousel__nav--prev', '.honor-carousel__nav--next');
  initCarousel('#campusCarousel', '.campus-carousel__viewport', '.campus-carousel__track', '.campus-carousel__nav--prev', '.campus-carousel__nav--next');
  initCarousel('#teacherStrip', '.teacher-strip__viewport', '.teacher-strip__track', '.teacher-strip__nav--prev', '.teacher-strip__nav--next');

  // -- dome rAF 3D sphere ----------------------------------------------
  const dome = document.getElementById('domeWall');
  if (dome) {
    const cells = [...dome.querySelectorAll('.dome-cell')];
    if (cells.length) {
      const R = 22; // rem
      const baseRems = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
      const radiusPx = R * baseRems;
      const parseVar = (str, name) => {
        const m = str && str.match(new RegExp('--' + name + ':\\s*(-?[0-9.]+)'));
        return m ? parseFloat(m[1]) : 0;
      };
      const layout = cells.map((cell) => {
        const styleStr = cell.getAttribute('style') || '';
        const latDeg = parseVar(styleStr, 'dome-lat');
        const lonDeg = parseVar(styleStr, 'dome-lon');
        const lat = (latDeg * Math.PI) / 180;
        const lon = (lonDeg * Math.PI) / 180;
        const x = radiusPx * Math.cos(lat) * Math.sin(lon);
        const y = radiusPx * Math.sin(lat);
        const z = radiusPx * Math.cos(lat) * Math.cos(lon);
        const i = parseInt(cell.getAttribute('data-index') || '0', 10);
        cell.style.opacity = '0';
        setTimeout(() => { cell.style.opacity = '1'; }, 200 + i * 12);
        return { cell, x, y, z };
      });
      let angle = -0.45;
      let paused = false;
      const render = () => {
        const cosA = Math.cos(angle);
        const sinA = Math.sin(angle);
        for (const { cell, x, y, z } of layout) {
          const rx = x * cosA - z * sinA;
          const rz = x * sinA + z * cosA;
          const depth = (rz + radiusPx) / (2 * radiusPx);
          const scale = 0.78 + 0.32 * depth;
          cell.style.transform = 'translate3d(' + rx + 'px, ' + (-y) + 'px, ' + rz + 'px) translate(-50%, -50%) scale(' + scale.toFixed(3) + ')';
          cell.style.zIndex = String(Math.round(rz + radiusPx));
        }
        if (!paused) angle += 0.0019;
        requestAnimationFrame(render);
      };
      requestAnimationFrame(render);
      dome.addEventListener('mouseenter', () => { paused = true; });
      dome.addEventListener('mouseleave', () => { paused = false; });
    }
  }

  // -- shared image lightbox for dome / honor / campus ------------------
  const imageLightbox = document.getElementById('imageLightbox');
  const imageLightboxImg = imageLightbox ? imageLightbox.querySelector('.image-lightbox__image') : null;
  const imageLightboxCap = imageLightbox ? imageLightbox.querySelector('.image-lightbox__caption') : null;
  const imageLightboxClose = imageLightbox ? imageLightbox.querySelector('.image-lightbox__close') : null;

  const openImageLightbox = (el) => {
    if (!imageLightbox || !imageLightboxImg) return;
    const src = el.getAttribute('data-lightbox-src');
    const cap = el.getAttribute('data-lightbox-caption') || '';
    if (!src) return;
    imageLightboxImg.src = src;
    imageLightboxImg.alt = cap;
    if (imageLightboxCap) imageLightboxCap.textContent = cap;
    imageLightbox.hidden = false;
    document.body.style.overflow = 'hidden';
  };
  const closeImageLightbox = () => {
    if (!imageLightbox || !imageLightboxImg) return;
    imageLightbox.hidden = true;
    imageLightboxImg.removeAttribute('src');
    if (imageLightboxCap) imageLightboxCap.textContent = '';
    document.body.style.overflow = '';
  };

  document.querySelectorAll('[data-lightbox-src]').forEach((el) => {
    el.addEventListener('click', (e) => {
      // For dome, ignore clicks while the cell is rotating (allow tap on canvas)
      openImageLightbox(el);
    });
  });
  if (imageLightboxClose) imageLightboxClose.addEventListener('click', closeImageLightbox);
  if (imageLightbox) {
    imageLightbox.addEventListener('click', (e) => { if (e.target === imageLightbox) closeImageLightbox(); });
  }
  // Course cards keep the original size; only their image layer rotates.
  document.querySelectorAll('[data-course-carousel]').forEach((carousel) => {
    const slides = Array.from(carousel.querySelectorAll('[data-course-slide]'));
    const dots = Array.from(carousel.querySelectorAll('[data-course-dot]'));
    const prev = carousel.querySelector('[data-course-prev]');
    const next = carousel.querySelector('[data-course-next]');
    if (slides.length < 2) return;
    let index = 0;
    let timer = 0;
    const show = (target) => {
      index = (target + slides.length) % slides.length;
      slides.forEach((slide, i) => slide.classList.toggle('is-active', i === index));
      dots.forEach((dot, i) => dot.classList.toggle('is-active', i === index));
    };
    const start = () => { clearInterval(timer); timer = window.setInterval(() => show(index + 1), 4200); };
    prev?.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); show(index - 1); start(); });
    next?.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); show(index + 1); start(); });
    dots.forEach((dot, i) => dot.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); show(i); start(); }));
    carousel.addEventListener('mouseenter', () => clearInterval(timer));
    carousel.addEventListener('mouseleave', start);
    start();
  });


  // -- hero typewriter (Senlin-style sequential phrase) -----------
  const heroTarget = document.getElementById('hero-typewriter-text');
  if (heroTarget) {
    const heroLines = [
      '乐高启蒙 · 机器人工程 · 编程思维',
      'NOI 竞赛指导 / 1000+ 学员成果',
      '乐启享教育 / 校长 / 合伙人',
      'Python / C++ / Web / AI 教学实践'
    ];
    let hi = 0;
    let ci = 0;
    let deleting = false;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const tick = () => {
      const current = heroLines[hi % heroLines.length];
      heroTarget.textContent = current.slice(0, ci);
      if (!deleting) {
        if (ci < current.length) {
          ci += 1;
        } else {
          deleting = true;
          setTimeout(tick, 1800);
          return;
        }
      } else if (ci > 0) {
        ci -= 1;
      } else {
        deleting = false;
        hi = (hi + 1) % heroLines.length;
      }
      setTimeout(tick, deleting ? 36 : (reduced ? 80 : 60));
    };
    tick();
  }
})();
