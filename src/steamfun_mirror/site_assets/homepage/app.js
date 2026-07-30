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

  // -- mobile hero navigation ------------------------------------------
  const heroHeader = document.querySelector('.hero-header');
  const heroMenuToggle = heroHeader ? heroHeader.querySelector('.hero-menu-toggle') : null;
  const heroNav = document.getElementById('heroNav');
  if (heroHeader && heroMenuToggle && heroNav) {
    const menuClass = 'is-menu-open';
    const setMenuOpen = (open) => {
      heroHeader.classList.toggle(menuClass, open);
      heroMenuToggle.setAttribute('aria-expanded', String(open));
      document.body.classList.toggle('hero-nav-open', open);
    };

    setMenuOpen(false);

    heroMenuToggle.addEventListener('click', () => {
      setMenuOpen(!heroHeader.classList.contains(menuClass));
    });

    heroNav.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target.closest('.nav-link') : null;
      if (!target || !window.matchMedia('(max-width: 1023.98px)').matches) return;
      setMenuOpen(false);
    });

    document.addEventListener('click', (event) => {
      if (!heroHeader.classList.contains(menuClass)) return;
      if (heroHeader.contains(event.target)) return;
      setMenuOpen(false);
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') setMenuOpen(false);
    });

    window.addEventListener('resize', () => {
      if (window.innerWidth >= 1024) setMenuOpen(false);
    });
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

  const removeCarouselCards = (rootSel, removeNeedles, countText) => {
    const root = document.querySelector(rootSel);
    if (!root) return;
    const cards = Array.from(root.querySelectorAll('[data-lightbox-src]'));
    cards.forEach((card) => {
      const source = card.getAttribute('data-lightbox-src') || '';
      if (removeNeedles.some((needle) => source.includes(needle))) card.remove();
    });
    const remaining = root.querySelectorAll('[data-lightbox-src]').length;
    root.dataset.count = String(remaining);
    const countLabel = root.querySelector('.honor-carousel__count, .campus-carousel__count');
    if (countLabel && countText) countLabel.textContent = countText(remaining);
  };

  removeCarouselCards(
    '#campusCarousel',
    ['home/2.webp', 'home/3.webp', 'campus-02.webp', 'campus-classroom-3.webp', 'campus-classroom-6.webp', 'campus-space-1.webp', 'campus-space-2.webp'],
    (count) => `${count} 张实拍 . 真实可感的校区空间`
  );
  removeCarouselCards(
    '#honorCarousel',
    [
      '3c4b1c9a2f99fd3aedb86712b709b6a2.webp',
      '47cdc27feee3d1ca5a1c2de341202475.webp',
      '6e43b26aa8d461efbe6bfd108898c4bf.webp',
      'c61cbbd3848e84e3ef947fb05a6ea4e4.webp',
      'd3112f025a571be58aa80e2ee73623d2.webp'
    ],
    (count) => `${count} 项荣誉 . 见证成长的关键时刻`
  );

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


  // -- hero title large typewriter ---------------------------------
  (function () {
    const title = document.getElementById('heroTitle');
    if (!title) return;
    title.classList.add('hero-title--typing');
    const defaultPhrases = '从乐高启蒙 到 AI 创造|让好奇心 在指尖生长|不止于搭建 · 更创造未来|把每一个奇思妙想 · 都变成作品|与未来同行 · 从第一块积木开始';
    const phrases = (title.dataset.heroTitlePhrases || defaultPhrases)
      .split('|')
      .map((phrase) => phrase.trim())
      .filter(Boolean);
    if (!phrases.length) return;
    const reduced = false;
    const escapeHtml = (value) => value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
    const renderText = (value) => escapeHtml(value).replace(/AI/g, '<span class="hero-title__ai">AI</span>');
    const splitRows = (value) => {
      const toIndex = value.indexOf(' 到 ');
      if (toIndex !== -1) {
        const tail = value.slice(toIndex + 3);
        if (!tail.trim()) return [{ prefix: '', text: value.trim() }];
        return [
          { prefix: '', text: value.slice(0, toIndex) },
          { prefix: '<span class="hero-title__space" aria-hidden="true">&nbsp;</span>到 ', text: tail }
        ];
      }
      const dotIndex = value.indexOf(' · ');
      if (dotIndex !== -1) {
        const tail = value.slice(dotIndex + 3);
        if (!tail.trim()) return [{ prefix: '', text: value.trim() }];
        return [
          { prefix: '', text: value.slice(0, dotIndex) },
          { prefix: '<span class="hero-title__mark" aria-hidden="true">·</span> ', text: tail }
        ];
      }
      const spaceIndex = value.indexOf(' ');
      if (spaceIndex !== -1) {
        return [
          { prefix: '', text: value.slice(0, spaceIndex) },
          { prefix: '', text: value.slice(spaceIndex + 1) }
        ];
      }
      return [{ prefix: '', text: value }];
    };
    const renderTitle = (value, showCursor) => {
      const cursor = showCursor ? '<span class="hero-title__cursor" aria-hidden="true"></span>' : '';
      const rows = splitRows(value);
      title.innerHTML = rows.map((row, rowIndex) => {
        const suffix = rowIndex === rows.length - 1 ? cursor : '';
        return '<span class="hero-title__row">' + row.prefix + renderText(row.text) + suffix + '</span>';
      }).join('');
      title.setAttribute('aria-label', value.replace(/\s+/g, ''));
    };
    if (reduced) {
      renderTitle(phrases[0], false);
      return;
    }
    const splitUnits = (phrase) => {
      const units = [];
      for (let index = 0; index < phrase.length;) {
        if (phrase.startsWith('AI', index)) {
          units.push('AI');
          index += 2;
        } else if (phrase.startsWith('STEAM', index)) {
          units.push('STEAM');
          index += 5;
        } else {
          units.push(phrase[index]);
          index += 1;
        }
      }
      return units;
    };
    const typedPhrases = phrases.map((phrase) => ({
      text: phrase,
      units: splitUnits(phrase)
    }));
    let phraseIndex = 0;
    let unitIndex = 0;
    let deleting = false;
    const typeDelay = 48;
    const deleteDelay = 26;
    const holdDelay = 850;
    renderTitle('', true);
    const tick = () => {
      const current = typedPhrases[phraseIndex % typedPhrases.length];
      renderTitle(current.units.slice(0, unitIndex).join(''), true);
      if (!deleting && unitIndex < current.units.length) {
        unitIndex += 1;
        setTimeout(tick, typeDelay);
        return;
      }
      if (!deleting) {
        deleting = true;
        setTimeout(tick, holdDelay);
        return;
      }
      if (unitIndex > 0) {
        unitIndex -= 1;
        setTimeout(tick, deleteDelay);
        return;
      }
      deleting = false;
      phraseIndex = (phraseIndex + 1) % typedPhrases.length;
      setTimeout(tick, 220);
    };
    setTimeout(tick, 120);
  })();

  // -- signal section big typewriter (right-side copy) ------------
  (function () {
    const target = document.getElementById('signalTitle');
    if (!target) return;
    target.classList.add('signal-title--typing');
    const fallback = '加入乐启享 · 扫码预约体验课 | 7 年深耕 · STEAM 教育 | 乐高启蒙 · 机器人工程 · 编程思维 | 让每一次好奇 · 都被认真对待 | 扫码 · 让孩子的未来 提前开始';
    const phrases = (target.dataset.signalTitlePhrases || fallback)
      .split('|')
      .map((value) => value.trim())
      .filter(Boolean);
    if (!phrases.length) return;
    const reduced = false;
    const escapeHtml = (value) => value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
    const renderText = (value) => escapeHtml(value);
    const renderTitle = (value, showCursor) => {
      const cursor = showCursor ? '<span class="hero-title__cursor" aria-hidden="true"></span>' : '';
      target.innerHTML = '<span class="hero-title__row">' + renderText(value) + cursor + '</span>';
      target.setAttribute('aria-label', value.replace(/\s+/g, ''));
    };
    if (reduced) {
      renderTitle(phrases[0], false);
      return;
    }
    let pIdx = 0;
    let uIdx = 0;
    let deleting = false;
    const typeDelay = 44;
    const deleteDelay = 24;
    const holdDelay = 850;
    renderTitle('', true);
    const tick = () => {
      const current = phrases[pIdx % phrases.length];
      renderTitle(current.slice(0, uIdx), true);
      if (!deleting && uIdx < current.length) {
        uIdx += 1;
        setTimeout(tick, typeDelay);
        return;
      }
      if (!deleting) {
        deleting = true;
        setTimeout(tick, holdDelay);
        return;
      }
      if (uIdx > 0) {
        uIdx -= 1;
        setTimeout(tick, deleteDelay);
        return;
      }
      deleting = false;
      pIdx = (pIdx + 1) % phrases.length;
      setTimeout(tick, 220);
    };
    setTimeout(tick, 120);
  })();
})();
