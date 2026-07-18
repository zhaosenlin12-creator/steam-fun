(() => {
  const revealNodes = [...document.querySelectorAll(".reveal")];
  if ("IntersectionObserver" in window) {
    const revealObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("reveal--visible");
            revealObserver.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.16 }
    );
    revealNodes.forEach((node) => revealObserver.observe(node));
  } else {
    revealNodes.forEach((node) => node.classList.add("reveal--visible"));
  }

  const sections = [...document.querySelectorAll("main section[id]")];
  const navLinks = [...document.querySelectorAll(".site-nav__link")];
  if (sections.length && navLinks.length && "IntersectionObserver" in window) {
    const sectionObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }
          const targetId = `#${entry.target.id}`;
          navLinks.forEach((link) => {
            link.classList.toggle("is-active", link.getAttribute("href") === targetId);
          });
        });
      },
      { threshold: 0.45 }
    );
    sections.forEach((section) => sectionObserver.observe(section));
  }

  const orbit = document.querySelector(".dome-orbit");
  if (orbit) {
    const cards = [...orbit.querySelectorAll(".dome-card")];
    const modal = document.querySelector(".gallery-modal");
    const modalImage = modal?.querySelector(".gallery-modal__image");
    const modalCaption = modal?.querySelector(".gallery-modal__caption");
    const closeButtons = modal
      ? [...modal.querySelectorAll(".gallery-modal__close, .gallery-modal__scrim")]
      : [];
    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
    let radius = 240;
    let rotationX = -12;
    let rotationY = 0;
    let velocityX = 0;
    let velocityY = 0.18;
    let dragging = false;
    let pointerId = null;
    let lastPoint = { x: 0, y: 0 };

    const layoutCards = () => {
      const stage = orbit.parentElement;
      const stageWidth = stage ? stage.clientWidth : window.innerWidth;
      radius = clamp(stageWidth * 0.26, 150, 290);
      const total = cards.length || 1;
      cards.forEach((card, index) => {
        const phi = Math.acos(1 - (2 * (index + 0.5)) / total);
        const theta = Math.PI * (1 + Math.sqrt(5)) * (index + 0.5);
        const x = Math.cos(theta) * Math.sin(phi);
        const y = Math.cos(phi);
        const z = Math.sin(theta) * Math.sin(phi);
        card.style.transform = `translate3d(${Math.round(x * radius)}px, ${Math.round(y * radius)}px, ${Math.round(z * radius)}px)`;
      });
    };

    const render = () => {
      rotationX = clamp(rotationX + velocityX, -26, 26);
      rotationY += velocityY;
      velocityX *= 0.94;
      velocityY = velocityY * 0.985 + 0.018;
      orbit.style.transform = `translate3d(-50%, -50%, 0) rotateX(${rotationX}deg) rotateY(${rotationY}deg)`;
      window.requestAnimationFrame(render);
    };

    const openModal = (card) => {
      if (!modal || !modalImage || !modalCaption) {
        return;
      }
      const image = card.querySelector("img");
      const caption = card.querySelector("span");
      if (!image || !caption) {
        return;
      }
      modalImage.src = image.currentSrc || image.src;
      modalImage.alt = image.alt;
      modalCaption.textContent = caption.textContent || "";
      modal.classList.add("is-open");
      modal.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    };

    const closeModal = () => {
      if (!modal) {
        return;
      }
      modal.classList.remove("is-open");
      modal.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    };

    orbit.addEventListener("pointerdown", (event) => {
      dragging = true;
      pointerId = event.pointerId;
      lastPoint = { x: event.clientX, y: event.clientY };
      velocityX = 0;
      velocityY = 0;
      orbit.classList.add("is-dragging");
      orbit.setPointerCapture(event.pointerId);
    });

    orbit.addEventListener("pointermove", (event) => {
      if (!dragging || event.pointerId !== pointerId) {
        return;
      }
      const deltaX = event.clientX - lastPoint.x;
      const deltaY = event.clientY - lastPoint.y;
      lastPoint = { x: event.clientX, y: event.clientY };
      velocityY = deltaX * 0.08;
      velocityX = -deltaY * 0.06;
    });

    const endDrag = (event) => {
      if (!dragging || event.pointerId !== pointerId) {
        return;
      }
      dragging = false;
      pointerId = null;
      orbit.classList.remove("is-dragging");
      try {
        orbit.releasePointerCapture(event.pointerId);
      } catch (error) {
        void error;
      }
    };

    orbit.addEventListener("pointerup", endDrag);
    orbit.addEventListener("pointercancel", endDrag);
    orbit.addEventListener("pointerleave", (event) => {
      if (dragging) {
        endDrag(event);
      }
    });

    cards.forEach((card) => {
      card.addEventListener("click", () => {
        if (dragging) {
          return;
        }
        openModal(card);
      });
    });
    closeButtons.forEach((button) => button.addEventListener("click", closeModal));
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeModal();
      }
    });
    window.addEventListener("resize", layoutCards);

    layoutCards();
    render();
  }
})();
