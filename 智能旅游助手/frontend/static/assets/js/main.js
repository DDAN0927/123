/* ==========================================================================
   旅游智能助手 · 官网交互脚本
   光标 / 滚动 reveal / 计数 / 磁吸 / 页面过渡 / 移动端菜单
   ========================================================================== */
(function () {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- 页面进入过渡 ---------- */
  function pageEnter() {
    const pt = document.createElement("div");
    pt.className = "page-transition active";
    document.body.appendChild(pt);
    setTimeout(() => pt.remove(), 950);
  }
  document.addEventListener("DOMContentLoaded", pageEnter);

  /* ---------- 自定义光标 ---------- */
  function initCursor() {
    if (window.matchMedia("(pointer: coarse)").matches || reduceMotion) return;
    const dot = document.createElement("div");
    const ring = document.createElement("div");
    dot.className = "cursor-dot";
    ring.className = "cursor-ring";
    const label = document.createElement("span");
    label.textContent = "查看";
    ring.appendChild(label);
    document.body.appendChild(dot);
    document.body.appendChild(ring);

    let mx = 0, my = 0, rx = 0, ry = 0;
    window.addEventListener("mousemove", (e) => {
      mx = e.clientX; my = e.clientY;
      dot.style.transform = `translate(${mx}px, ${my}px) translate(-50%,-50%)`;
    });
    (function loop() {
      rx += (mx - rx) * 0.16;
      ry += (my - ry) * 0.16;
      ring.style.transform = `translate(${rx}px, ${ry}px) translate(-50%,-50%)`;
      requestAnimationFrame(loop);
    })();

    const hoverables = "a, button, .agent, .feat-card, .stat, .chip, input, textarea, .tbtn";
    document.addEventListener("mouseover", (e) => {
      if (e.target.closest(hoverables)) { ring.classList.add("hover"); label.textContent = "查看"; }
    });
    document.addEventListener("mouseout", (e) => {
      if (e.target.closest(hoverables) && !e.relatedTarget?.closest(hoverables)) ring.classList.remove("hover");
    });
    document.querySelectorAll(".stat").forEach((s) => {
      s.addEventListener("mouseenter", () => { label.textContent = "数据"; });
      s.addEventListener("mouseleave", () => { label.textContent = "查看"; });
    });
  }

  /* ---------- 滚动 reveal ---------- */
  function initReveal() {
    const els = document.querySelectorAll(".reveal");
    if (reduceMotion) { els.forEach((el) => el.classList.add("in-view")); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) { en.target.classList.add("in-view"); io.unobserve(en.target); }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    els.forEach((el) => io.observe(el));
  }

  /* ---------- 导航滚动状态 + 移动端菜单 ---------- */
  function initNav() {
    const header = document.querySelector(".site-header");
    if (!header) return;
    const onScroll = () => header.classList.toggle("scrolled", window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    const burger = document.querySelector(".nav-burger");
    const links = document.querySelector(".nav-links");
    if (!burger || !links) return;

    // 移除可能已存在的旧菜单（app.js 注入导航后需重建）
    document.querySelectorAll(".mobile-menu").forEach((m) => m.remove());

    const menu = document.createElement("div");
    menu.className = "mobile-menu";
    menu.innerHTML = `<div class="mobile-menu-inner">${links.innerHTML}</div>`;
    document.body.appendChild(menu);

    burger.addEventListener("click", () => {
      const open = document.body.classList.toggle("menu-open");
      burger.setAttribute("aria-expanded", open);
    });
    menu.addEventListener("click", () => {
      // 菜单是整屏遮罩，除了链接没有别的可点内容 —— 点哪里都关闭（点链接时
      // 不 preventDefault，浏览器照常跳转）。挂在同一个监听上，不另造事件体系。
      document.body.classList.remove("menu-open");
      burger.setAttribute("aria-expanded", "false");
    });
  }

  /* ---------- 数字滚动 ---------- */
  function initCounters() {
    const nums = document.querySelectorAll("[data-count]");
    if (!nums.length) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        const el = en.target;
        const target = parseFloat(el.dataset.count);
        const dec = el.dataset.decimals ? parseInt(el.dataset.decimals, 10) : 0;
        const dur = 1600;
        const start = performance.now();
        const step = (t) => {
          const p = Math.min((t - start) / dur, 1);
          const eased = 1 - Math.pow(1 - p, 3);
          el.textContent = (target * eased).toFixed(dec);
          if (p < 1) requestAnimationFrame(step);
          else el.textContent = target.toFixed(dec);
        };
        requestAnimationFrame(step);
        io.unobserve(el);
      });
    }, { threshold: 0.6 });
    nums.forEach((n) => io.observe(n));
  }

  /* ---------- 磁吸按钮 / 卡片倾斜 ---------- */
  function initMagnetic() {
    if (reduceMotion) return;
    document.querySelectorAll(".btn, .brand").forEach((el) => {
      el.addEventListener("mousemove", (e) => {
        const r = el.getBoundingClientRect();
        const x = e.clientX - r.left - r.width / 2;
        const y = e.clientY - r.top - r.height / 2;
        el.style.transform = `translate(${x * 0.16}px, ${y * 0.22}px)`;
      });
      el.addEventListener("mouseleave", () => { el.style.transform = ""; });
    });

    document.querySelectorAll(".feat-card, .agent, .split-media").forEach((card) => {
      card.addEventListener("mousemove", (e) => {
        const r = card.getBoundingClientRect();
        const rx = ((e.clientY - r.top) / r.height - 0.5) * -6;
        const ry = ((e.clientX - r.left) / r.width - 0.5) * 6;
        card.style.transform = `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg) translateY(-6px)`;
      });
      card.addEventListener("mouseleave", () => { card.style.transform = ""; });
    });
  }

  /* ---------- 内部链接页面过渡 ---------- */
  function initLinkTransitions() {
    if (reduceMotion) return;
    document.addEventListener("click", (e) => {
      const a = e.target.closest("a[href]");
      if (!a) return;
      const href = a.getAttribute("href") || "";
      // 外链 / 锚点 / 新窗口 / 下载 / data: / blob: / mailto: / tel: 一律交给浏览器原生处理
      if (!href || href.startsWith("http") || href.startsWith("#") || a.target === "_blank") return;
      if (a.hasAttribute("download")) return;
      if (/^(data|blob|mailto|tel|javascript):/i.test(href)) return;
      e.preventDefault();
      const pt = document.createElement("div");
      pt.className = "page-transition active";
      pt.style.transform = "translateY(101%)";
      document.body.appendChild(pt);
      requestAnimationFrame(() => pt.classList.add("active"));
      setTimeout(() => { window.location.href = href; }, 430);
    });
  }

  /* ---------- 阅读进度条 ---------- */
  function initScrollProgress() {
    const bar = document.createElement("div");
    bar.className = "scroll-progress";
    document.body.appendChild(bar);
    const onScroll = () => {
      const h = document.documentElement;
      const max = h.scrollHeight - h.clientHeight;
      bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + "%";
    };
    document.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---------- 纸纹理颗粒层 ---------- */
  function initGrain() {
    if (reduceMotion) return;
    const g = document.createElement("div");
    g.className = "grain-overlay";
    g.setAttribute("aria-hidden", "true");
    document.body.appendChild(g);
  }

  /* ---------- 智能导航：下滑隐藏 / 上滑出现 ---------- */
  function initSmartNav() {
    const header = document.querySelector(".site-header");
    if (!header) return;
    let lastY = window.scrollY;
    document.addEventListener("scroll", () => {
      const y = window.scrollY;
      if (y > lastY + 6 && y > 340) header.classList.add("nav-hidden");
      else if (y < lastY - 4 || y < 120) header.classList.remove("nav-hidden");
      lastY = y;
    }, { passive: true });
  }

  /* ---------- 图片视差（背景位移动，避免与 hover 缩放冲突） ---------- */
  function initParallax() {
    if (reduceMotion) return;
    const medias = [...document.querySelectorAll(".split-media")];
    if (!medias.length) return;
    let ticking = false;
    const update = () => {
      const vh = window.innerHeight;
      medias.forEach((m) => {
        const img = m.querySelector(".img");
        if (!img) return;
        const r = m.getBoundingClientRect();
        const p = Math.max(-1, Math.min(1, (r.top + r.height / 2 - vh / 2) / (vh / 2)));
        img.style.backgroundPosition = `center ${50 + p * 14}%`;
      });
      ticking = false;
    };
    document.addEventListener("scroll", () => {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
    update();
  }

  /* ---------- 图片懒加载：进入视口前 200px 才真正取图 ----------
     以前这里对每个 .img 立刻 `new Image()` 并 `pre.src = url` —— 那是**预加载**，
     等于把 features.html / about.html 的 8 张图（约 1.3MB）全塞进首屏，
     与「懒加载」正好相反。

     现在分两步：
     1) 脚本执行时先把图片地址摘下来（内联 background-image 直接置 none），
        避免浏览器在首次布局时就去取；
     2) 元素进入视口前 200px 再赋回背景图，并在真正加载完成后关掉骨架屏。
     `loaded` class 的骨架屏逻辑保持不变，只是延后触发。

     地址两种写法都支持：`data-bg="..."`（推荐，解析期就不会发请求）
     或原有的内联 `style="background-image:url(...)"`。 */
  function initImgLoad() {
    const imgs = [...document.querySelectorAll(".split-media .img")];
    if (!imgs.length) return;

    const sourceOf = (el) => {
      const dataBg = el.getAttribute("data-bg");
      if (dataBg) return dataBg;
      const m = (el.getAttribute("style") || "").match(/url\(['"]?([^'")]+)['"]?\)/);
      return m ? m[1] : null;
    };

    const reveal = (el, url) => {
      if (!url) { el.classList.add("loaded"); return; }
      el.style.backgroundImage = `url('${url}')`;
      const pre = new Image();
      pre.onload = () => el.classList.add("loaded");
      pre.onerror = () => el.classList.add("loaded");
      pre.src = url;
      if (pre.complete) el.classList.add("loaded");
    };

    // 老浏览器没有 IntersectionObserver：退回「立刻加载」，至少不缺图
    if (typeof window.IntersectionObserver !== "function") {
      imgs.forEach((el) => reveal(el, sourceOf(el)));
      return;
    }

    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        reveal(en.target, en.target.dataset.bgUrl);
      });
    }, { rootMargin: "200px 0px", threshold: 0 });

    imgs.forEach((el) => {
      const url = sourceOf(el);
      if (url && el.style.backgroundImage) el.style.backgroundImage = "none";
      el.dataset.bgUrl = url || "";
      io.observe(el);
    });
  }

  /* ---------- 应用直达链接：官网内功能页 ---------- */
  function initAppLinks() {
    const pageMap = { "": "chat.html", chat: "chat.html", map: "map.html",
      transit: "transit.html", trips: "trips.html", kb: "kb.html", fav: "favorites.html", admin: "admin.html" };
    document.querySelectorAll("a[data-app]").forEach((a) => {
      const page = a.getAttribute("data-app");
      a.setAttribute("href", pageMap[page] || "chat.html");
      a.setAttribute("data-cursor", "进入");
    });
  }

  initCursor();
  initReveal();
  initCounters();
  initMagnetic();
  initLinkTransitions();
  initScrollProgress();
  initGrain();
  initSmartNav();
  initParallax();
  initImgLoad();

  /* 导航必须在 app.js 注入完导航栏之后初始化：
     app.js 先注册 DOMContentLoaded，故其注入逻辑先于本回调执行。 */
  function bootNav() {
    initAppLinks();
    initNav();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootNav);
  } else {
    bootNav();
  }

  /* 移动端菜单样式（动态注入，避免每个页面重复） */
  const style = document.createElement("style");
  style.textContent = `
    /* 应用页导航有 9~11 项，375×667 下全部排开是 745px，比视口还高：
       原来 align-items:center + overflow:visible，首项被切在屏幕上方、末项切在下方，
       且没有任何滚动容器可以够到它们。改成「顶部对齐 + 可滚 + 首尾留白」。 */
    .mobile-menu { position: fixed; inset: 0; z-index: 99; background: var(--ink);
      display: flex; align-items: flex-start; justify-content: center;
      overflow-y: auto; overscroll-behavior: contain; padding-block: 80px;
      opacity: 0; pointer-events: none; transition: opacity .4s var(--ease); }
    body.menu-open .mobile-menu { opacity: 1; pointer-events: auto; }
    .mobile-menu-inner { display: flex; flex-direction: column; gap: 8px; text-align: center; width: 100%; margin: auto 0; }
    /* 菜单项原来只有 38px 高。align-self:center 保持收缩宽度（hover 胶囊仍包着文字），
       min-height 补到 44，文字靠 flex 居中而不是靠 padding 猜。 */
    .mobile-menu a { display: flex; align-items: center; justify-content: center; align-self: center;
      min-height: 44px; font-family: var(--font-display); font-size: 2rem;
      color: var(--paper); padding: 6px 26px; border-radius: var(--r-pill); }
    .mobile-menu a:hover { color: var(--amber); }
    /* 菜单是 ink 底，汉堡的三条线也是 --ink（近黑）—— 打开后「关闭」的 ✕ 直接看不见，
       右上角只剩一个空方框。开态把线改成纸色。 */
    body.menu-open .nav-burger span { background: var(--paper); }
    body.menu-open .nav-burger span:nth-child(1) { transform: translateY(5px) rotate(45deg); }
    body.menu-open .nav-burger span:nth-child(2) { opacity: 0; }
    body.menu-open .nav-burger span:nth-child(3) { transform: translateY(-5px) rotate(-45deg); }
  `;
  document.head.appendChild(style);
})();