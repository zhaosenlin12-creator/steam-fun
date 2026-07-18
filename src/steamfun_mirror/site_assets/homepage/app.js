(() => {
  const links = [...document.querySelectorAll(".nav-link")];
  const sections = [...document.querySelectorAll("main section[id]")];
  if (!links.length || !sections.length || !("IntersectionObserver" in window)) {
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) {
          continue;
        }
        const target = `#${entry.target.id}`;
        for (const link of links) {
          link.classList.toggle("is-active", link.getAttribute("href") === target);
        }
      }
    },
    { threshold: 0.55 }
  );

  sections.forEach((section) => observer.observe(section));
})();
