(function () {
  "use strict";
  var root = document.documentElement;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canHover = window.matchMedia && window.matchMedia("(hover: hover)").matches;
  var $ = function (sel, el) { return (el || document).querySelector(sel); };
  var $$ = function (sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); };
  // Browser storage is only a per-visitor convenience (theme, palette, motion choice); it may be unavailable.
  function load(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function save(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} }
  function once(k) {
    try { if (sessionStorage.getItem(k)) return false; sessionStorage.setItem(k, "1"); } catch (e) {}
    return true;
  }
  function motionOn() { return root.classList.contains("motion"); }
  function css(name) { return getComputedStyle(root).getPropertyValue(name).trim(); }

  // ------------------------------------------------------------ tooltips
  // Heatmap cells, journey segments and stepper nodes carry data-tip (each cell's <title> is the no-JS fallback).
  var tip = $("#tip");
  if (tip) {
    $$("[data-tip]").forEach(function (el) {
      var t = el.querySelector("title");
      if (t) { el.setAttribute("aria-label", t.textContent); t.remove(); }
      function show() {
        var r = el.getBoundingClientRect();
        tip.textContent = el.getAttribute("data-tip");
        tip.style.left = r.left + r.width / 2 + "px";
        tip.style.top = r.top + "px";
        tip.hidden = false;
      }
      function hide() { tip.hidden = true; }
      el.addEventListener("pointerenter", show);
      el.addEventListener("pointerleave", hide);
      el.addEventListener("focus", show);
      el.addEventListener("blur", hide);
    });
    window.addEventListener("scroll", function () { tip.hidden = true; }, { passive: true });
  }

  // ------------------------------------------------------------ scroll progress + back to top
  var sprog = $(".sprog"), topBtn = $("#top-btn"), ticking = false;
  function onScroll() {
    ticking = false;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    if (sprog) sprog.style.setProperty("--p", max > 0 ? Math.min(1, window.scrollY / max) : 0);
    if (topBtn) topBtn.classList.toggle("show", window.scrollY > 600);
  }
  window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  onScroll();
  if (topBtn) topBtn.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: motionOn() ? "smooth" : "auto" }); });

  // ------------------------------------------------------------ theme + colour palette (circular reveal)
  function reveal(e, apply) {
    if (!motionOn() || !document.startViewTransition) { apply(); return; }
    var x = e && e.clientX ? e.clientX : window.innerWidth - 40, y = e && e.clientY ? e.clientY : window.innerHeight - 40;
    var r = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    var tr = document.startViewTransition(apply);
    tr.ready.then(function () {
      root.animate({ clipPath: ["circle(0px at " + x + "px " + y + "px)", "circle(" + r + "px at " + x + "px " + y + "px)"] },
                   { duration: 650, easing: "cubic-bezier(.4, 0, .2, 1)", pseudoElement: "::view-transition-new(root)" });
    }).catch(function () {});
  }
  var themeBtn = $("#theme-btn");
  var THEMES = [null, "light", "dark"], THEME_LABEL = { null: "automatic (follows your system)", light: "light", dark: "dark" };
  function setTheme(t) {
    if (t) root.setAttribute("data-theme", t); else root.removeAttribute("data-theme");
    save("theme", t);
    if (themeBtn) {
      themeBtn.setAttribute("aria-label", "Theme: " + THEME_LABEL[t] + ". Click to change");
      themeBtn.setAttribute("data-tip", "Theme: " + THEME_LABEL[t]);
    }
  }
  // The state lives here, not in the DOM: a view transition applies the change a moment later.
  var theme = root.getAttribute("data-theme");
  setTheme(theme);
  if (themeBtn) themeBtn.addEventListener("click", function (e) {
    var next = theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
    reveal(e, function () { setTheme(next); });
  });

  var palBtn = $("#palette-btn");
  var PALETTES = ["aurora", "sunset", "ocean"], PAL_LABEL = { aurora: "Aurora", sunset: "Sunset", ocean: "Ocean" };
  function setPalette(p) {
    if (p === "aurora") root.removeAttribute("data-palette"); else root.setAttribute("data-palette", p);
    save("palette", p === "aurora" ? null : p);
    if (palBtn) {
      palBtn.setAttribute("aria-label", "Colour theme: " + PAL_LABEL[p] + ". Click to change");
      palBtn.setAttribute("data-tip", "Colours: " + PAL_LABEL[p]);
    }
    sky.recolor();
  }
  var palette = root.getAttribute("data-palette") || "aurora";
  if (palBtn) palBtn.addEventListener("click", function (e) {
    var next = palette = PALETTES[(PALETTES.indexOf(palette) + 1) % PALETTES.length];
    reveal(e, function () { setPalette(next); });
  });

  // ------------------------------------------------------------ hero starfield
  var sky = (function () {
    var c = $(".sky"), hero = $(".hero");
    if (!c || !c.getContext || !hero) return { start: function () {}, stop: function () {}, recolor: function () {}, pointer: function () {} };
    var ctx = c.getContext("2d"), pts = [], raf = 0, w = 0, h = 0, running = false, visible = true;
    var mouse = { x: -1e4, y: -1e4 }, line = "#ffffff";
    function size() {
      var dpr = Math.min(2, window.devicePixelRatio || 1);
      w = hero.clientWidth; h = hero.clientHeight;
      c.width = w * dpr; c.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var n = Math.round(Math.min(90, (w * h) / 13000));
      pts = [];
      for (var i = 0; i < n; i++) {
        pts.push({ x: Math.random() * w, y: Math.random() * h, vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
                   r: Math.random() * 1.6 + 0.5, tw: Math.random() * 6.28 });
      }
    }
    function frame(t) {
      raf = 0;
      if (!running || !visible || document.hidden) return;
      ctx.clearRect(0, 0, w, h);
      var i, j, p, q, dx, dy, d;
      for (i = 0; i < pts.length; i++) {
        p = pts[i];
        p.x += p.vx; p.y += p.vy;
        if (p.x < -10) p.x = w + 10; else if (p.x > w + 10) p.x = -10;
        if (p.y < -10) p.y = h + 10; else if (p.y > h + 10) p.y = -10;
        dx = p.x - mouse.x; dy = p.y - mouse.y; d = Math.sqrt(dx * dx + dy * dy);
        if (d < 130 && d > 0.1) { p.x += (dx / d) * (1 - d / 130) * 1.6; p.y += (dy / d) * (1 - d / 130) * 1.6; }
      }
      ctx.strokeStyle = line;
      ctx.lineWidth = 1;
      for (i = 0; i < pts.length; i++) {
        p = pts[i];
        for (j = i + 1; j < pts.length; j++) {
          q = pts[j]; dx = p.x - q.x; dy = p.y - q.y; d = dx * dx + dy * dy;
          if (d < 12100) {
            ctx.globalAlpha = (1 - Math.sqrt(d) / 110) * 0.28;
            ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); ctx.stroke();
          }
        }
      }
      ctx.fillStyle = "#ffffff";
      for (i = 0; i < pts.length; i++) {
        p = pts[i];
        ctx.globalAlpha = 0.45 + 0.45 * Math.sin(t / 700 + p.tw);
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.2832); ctx.fill();
      }
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(frame);
    }
    function kick() { if (!raf && running) raf = requestAnimationFrame(frame); }
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) { visible = es[0].isIntersecting; kick(); }).observe(hero);
    }
    document.addEventListener("visibilitychange", kick);
    var rt;
    window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if (running) size(); }, 200); });
    return {
      start: function () { if (running) return; running = true; this.recolor(); size(); c.classList.add("on"); kick(); },
      stop: function () { running = false; c.classList.remove("on"); ctx.clearRect(0, 0, w, h); },
      recolor: function () { line = css("--glow") || "#ffffff"; },
      pointer: function (x, y) { mouse.x = x; mouse.y = y; },
    };
  })();
  setPalette(palette);

  // hero parallax + starfield repel
  var hero = $(".hero");
  if (hero && canHover) {
    hero.addEventListener("pointermove", function (e) {
      var r = hero.getBoundingClientRect();
      sky.pointer(e.clientX - r.left, e.clientY - r.top);
      if (!motionOn()) return;
      hero.style.setProperty("--px", ((e.clientX - r.left) / r.width - 0.5) * 2);
      hero.style.setProperty("--py", ((e.clientY - r.top) / r.height - 0.5) * 2);
    });
    hero.addEventListener("pointerleave", function () {
      sky.pointer(-1e4, -1e4);
      hero.style.setProperty("--px", 0); hero.style.setProperty("--py", 0);
    });
  }

  // ------------------------------------------------------------ card spotlight + project card tilt
  if (canHover) {
    document.addEventListener("pointermove", function (e) {
      var el = e.target.closest && e.target.closest(".spot");
      if (!el) return;
      var r = el.getBoundingClientRect();
      el.style.setProperty("--mx", e.clientX - r.left + "px");
      el.style.setProperty("--my", e.clientY - r.top + "px");
      if (el.classList.contains("pcard") && motionOn()) {
        var x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        el.style.setProperty("--rx", ((0.5 - y) * 8).toFixed(2) + "deg");
        el.style.setProperty("--ry", ((x - 0.5) * 10).toFixed(2) + "deg");
      }
    }, { passive: true });
    $$(".pcard").forEach(function (el) {
      el.addEventListener("pointerleave", function () { el.style.setProperty("--rx", "0deg"); el.style.setProperty("--ry", "0deg"); });
    });
  }

  // ------------------------------------------------------------ flip cards (hover flips with CSS; taps toggle here)
  $$(".tile").forEach(function (t) {
    t.addEventListener("click", function () {
      if (canHover) return;
      if (t.classList.toggle("flipped")) return;
      t.blur();
    });
    t.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); t.classList.toggle("flipped"); }
    });
  });

  // ------------------------------------------------------------ module details: cascade topics when opened
  $$("details.module").forEach(function (d) {
    d.addEventListener("toggle", function () {
      if (!d.open || !motionOn()) return;
      d.classList.add("opening");
      setTimeout(function () { d.classList.remove("opening"); }, 1200);
    });
  });

  // ------------------------------------------------------------ confetti
  function confetti(x, y, n) {
    if (!motionOn()) return;
    var c = document.createElement("canvas");
    c.className = "confetti"; c.setAttribute("aria-hidden", "true");
    document.body.appendChild(c);
    var dpr = Math.min(2, window.devicePixelRatio || 1), W = window.innerWidth, H = window.innerHeight;
    c.width = W * dpr; c.height = H * dpr;
    var ctx = c.getContext("2d"); ctx.scale(dpr, dpr);
    var colors = [css("--g1"), css("--g2"), css("--g3"), css("--good"), css("--warn"), css("--glow")];
    var ps = [];
    for (var i = 0; i < (n || 140); i++) {
      var a = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.1, v = 6 + Math.random() * 9;
      ps.push({ x: x, y: y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, s: 5 + Math.random() * 6, rot: Math.random() * 6,
                vr: (Math.random() - 0.5) * 0.4, c: colors[i % colors.length], round: Math.random() < 0.3 });
    }
    var start = performance.now();
    (function tick(t) {
      var el = t - start;
      ctx.clearRect(0, 0, W, H);
      ps.forEach(function (p) {
        p.vy += 0.28; p.vx *= 0.985; p.vy *= 0.985; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
        ctx.globalAlpha = Math.max(0, 1 - el / 3200);
        ctx.fillStyle = p.c;
        if (p.round) { ctx.beginPath(); ctx.arc(0, 0, p.s / 2, 0, 6.2832); ctx.fill(); }
        else ctx.fillRect(-p.s / 2, -p.s / 4, p.s, p.s / 2);
        ctx.restore();
      });
      if (el < 3200) requestAnimationFrame(tick); else c.remove();
    })(start);
  }
  var ring = $(".ring");
  if (ring) ring.addEventListener("click", function () {
    var r = ring.getBoundingClientRect();
    confetti(r.left + r.width / 2, r.top + r.height / 2, 160);
  });

  // ------------------------------------------------------------ module pop-up
  var modal = $("#modal"), mcontent = modal && $(".mcontent", modal);
  var mods = $$("details.module");
  var order = mods.map(function (d) { return d.getAttribute("data-id"); });
  var shortName = {};
  $$(".stepbtn").forEach(function (b) { shortName[b.getAttribute("data-module")] = $(".slabel", b).textContent; });
  var current = -1;
  function fill(i) {
    var d = mods[i], id = order[i];
    var titleEl = $(".mtitle", d), sched = $(".sched", d).textContent;
    var title = titleEl.firstChild.textContent.trim();
    var pct = parseInt(d.getAttribute("data-pct"), 10) || 0, count = $(".count", d).textContent;
    var circ = 2 * Math.PI * 40;
    var prev = i > 0 ? "← " + order[i - 1] + " · " + shortName[order[i - 1]] : "";
    var next = i < order.length - 1 ? order[i + 1] + " · " + shortName[order[i + 1]] + " →" : "";
    mcontent.innerHTML =
      '<button type="button" class="mclose" aria-label="Close">×</button>' +
      '<header class="mhead"><div><p class="mk">' + (id === "CAP" ? "Capstone" : "Module " + id) + '</p><h3 id="modal-title"></h3>' +
      '<p class="msched"></p></div>' +
      '<svg class="mring" viewBox="0 0 100 100" role="img" aria-label="' + pct + '% of topics covered">' +
      '<circle class="t" cx="50" cy="50" r="40"/><circle class="f" cx="50" cy="50" r="40" stroke-dasharray="0 ' + circ.toFixed(1) +
      '" transform="rotate(-90 50 50)"/><text x="50" y="57">' + pct + '%</text></svg></header>' +
      '<div class="mbody"></div>' +
      '<nav class="mnav"><button type="button" data-go="-1"' + (prev ? "" : " disabled") + '></button>' +
      '<button type="button" data-go="1"' + (next ? "" : " disabled") + '></button></nav>';
    $("#modal-title", mcontent).textContent = title;
    $(".msched", mcontent).textContent = sched + " · " + count;
    $(".mhead > div", mcontent).appendChild($(".status", d).cloneNode(true));
    var body = $(".mbody", mcontent);
    var topics = $(".topics", d), proj = $(".proj", d);
    if (topics) body.appendChild(topics.cloneNode(true));
    if (proj) body.appendChild(proj.cloneNode(true));
    var navs = $$(".mnav button", mcontent);
    navs[0].textContent = prev; navs[1].textContent = next;
    var f = $(".mring .f", mcontent), final = (circ * pct / 100).toFixed(1) + " " + circ.toFixed(1);
    if (motionOn()) {
      requestAnimationFrame(function () { requestAnimationFrame(function () { f.setAttribute("stroke-dasharray", final); }); });
      setTimeout(function () { f.setAttribute("stroke-dasharray", final); }, 400);
    } else {
      f.setAttribute("stroke-dasharray", final);
    }
    current = i;
    if (d.classList.contains("completed") && motionOn()) {
      setTimeout(function () {
        var r = $(".mhead", mcontent).getBoundingClientRect();
        confetti(r.left + r.width / 2, r.top + 30, 120);
      }, 350);
    }
  }
  function openModule(id) {
    if (!modal || !modal.showModal) {
      var d = mods[order.indexOf(id)];
      if (d) { d.open = true; d.scrollIntoView({ behavior: motionOn() ? "smooth" : "auto", block: "start" }); }
      return;
    }
    fill(order.indexOf(id));
    modal.classList.remove("closing", "swap");
    if (!modal.open) modal.showModal();
  }
  function closeModal() {
    if (!modal.open) return;
    if (!motionOn()) { modal.close(); return; }
    modal.classList.add("closing");
    setTimeout(function () { modal.classList.remove("closing"); modal.close(); }, 220);
  }
  if (modal) {
    $$("[data-module]").forEach(function (b) {
      b.addEventListener("click", function () { tip && (tip.hidden = true); openModule(b.getAttribute("data-module")); });
    });
    modal.addEventListener("click", function (e) {
      if (e.target === modal) { closeModal(); return; }
      if (e.target.closest(".mclose")) { closeModal(); return; }
      var go = e.target.closest("[data-go]");
      if (go && !go.disabled) {
        var step = parseInt(go.getAttribute("data-go"), 10);
        modal.style.setProperty("--dir", step > 0 ? "40px" : "-40px");
        modal.classList.remove("swap"); void modal.offsetWidth; modal.classList.add("swap");
        fill(current + step);
        var again = $('[data-go="' + step + '"]', modal);
        if (again && !again.disabled) again.focus(); else $(".mclose", modal).focus();
      }
    });
    modal.addEventListener("cancel", function (e) { e.preventDefault(); closeModal(); });
    modal.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight" && current < order.length - 1) $('[data-go="1"]', modal).click();
      if (e.key === "ArrowLeft" && current > 0) $('[data-go="-1"]', modal).click();
    });
  }

  // ------------------------------------------------------------ latest-push toast
  var toast = $("#toast");
  function ago(iso) {
    var s = (Date.now() - Date.parse(iso)) / 1000;
    if (!isFinite(s) || !window.Intl || !Intl.RelativeTimeFormat) return "";
    var rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
    var units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
    for (var i = 0; i < units.length; i++) if (s >= units[i][1]) return rtf.format(-Math.floor(s / units[i][1]), units[i][0]);
    return "just now";
  }
  if (toast) {
    var a = ago(toast.getAttribute("data-when"));
    if (a) $(".ago", toast).textContent = "· " + a;
    var hideTimer, TOAST_MS = 9000;
    var dismiss = function () {
      clearTimeout(hideTimer);
      if (!motionOn()) { toast.hidden = true; return; }
      toast.classList.add("out");
      setTimeout(function () { toast.hidden = true; toast.classList.remove("in", "out"); }, 350);
    };
    toast.style.setProperty("--toast-ms", TOAST_MS + "ms");
    $(".tclose", toast).addEventListener("click", dismiss);
    toast.addEventListener("pointerenter", function () { clearTimeout(hideTimer); });
    toast.addEventListener("pointerleave", function () { hideTimer = setTimeout(dismiss, 3000); });
    setTimeout(function () {
      toast.hidden = false;
      toast.classList.add("in");
      hideTimer = setTimeout(dismiss, TOAST_MS);
    }, 1600);
  }

  // ------------------------------------------------------------ motion: opt-in, proven, switchable
  var motionBtn = $("#motion-btn");
  var pref = load("motion");
  var want = pref ? pref === "on" : !reduce;
  var probed = false, entered = false;
  function label() {
    if (!motionBtn) return;
    motionBtn.setAttribute("aria-pressed", want ? "true" : "false");
    motionBtn.setAttribute("aria-label", "Animations " + (want ? "on" : "off") + ". Click to turn " + (want ? "off" : "on"));
    motionBtn.setAttribute("data-tip", "Animations " + (want ? "on" : "off"));
  }
  // Only switch motion on once the browser proves it runs CSS animations: a 1 ms probe animation must finish.
  // Where animations never run (some bots, screenshot tools, throttled tabs) the page stays fully visible and static.
  function probe(cb) {
    if (probed) { cb(); return; }
    var el = document.createElement("div");
    el.className = "motion-probe"; el.setAttribute("aria-hidden", "true");
    el.addEventListener("animationend", function () { el.remove(); probed = true; cb(); }, { once: true });
    document.body.appendChild(el);
  }
  function enable(initial) {
    probe(function () {
      if (!want) return;
      root.classList.add("motion");
      sky.start();
      if (initial && !entered) { entered = true; entrances(); }
    });
  }
  function disable() {
    root.classList.remove("motion");
    sky.stop();
    $$(".block.pending").forEach(function (b) { b.classList.remove("pending"); });
    $$(".tile.peek").forEach(function (t) { t.classList.remove("peek"); });
  }
  label();
  if (motionBtn) motionBtn.addEventListener("click", function () {
    want = !want;
    save("motion", want ? "on" : "off");
    label();
    if (want) enable(false); else disable();
  });
  if (want) enable(true);

  function entrances() {
    // Safety net: if content that should have animated in is still invisible, switch motion off so it all shows.
    // (Some text is translucent by design, e.g. the hero eyebrow at .8, so "visible" means clearly above zero.)
    function opaque(el) { return parseFloat(getComputedStyle(el).opacity) > 0.5; }
    function verify(els, wait) {
      setTimeout(function () { if (motionOn() && !els.every(opaque)) disable(); }, wait);
    }
    verify($$(".tile, .hero-text > *, .ring"), 2800);

    // progress ring sweeps from 0 to its value
    var fillEl = $(".ring-fill");
    if (fillEl) {
      var final = fillEl.getAttribute("stroke-dasharray"), full = final.split(" ")[1];
      fillEl.setAttribute("stroke-dasharray", "0 " + full);
      requestAnimationFrame(function () { requestAnimationFrame(function () { fillEl.setAttribute("stroke-dasharray", final); }); });
      setTimeout(function () { fillEl.setAttribute("stroke-dasharray", final); }, 500);
      if (once("ring-burst")) {
        setTimeout(function () {
          var r = ring.getBoundingClientRect();
          if (r.bottom > 0) confetti(r.left + r.width / 2, r.top + r.height / 2, 70);
        }, 2100);
      }
    }

    // sections fade up when scrolled to; everything is revealed after 6 s regardless
    var blocks = $$(".block");
    function revealBlock(el) {
      if (!el.classList.contains("pending")) return;
      el.classList.remove("pending");
      verify([el], 1600);
    }
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting) { revealBlock(e.target); io.unobserve(e.target); } });
      }, { rootMargin: "0px 0px -8% 0px" });
      blocks.forEach(function (el) { el.classList.add("pending"); io.observe(el); });
    }
    setTimeout(function () { blocks.forEach(revealBlock); }, 6000);

    // stat numbers count up, then pop
    $$(".tile .num[data-count]").forEach(function (el, k) {
      var target = parseInt(el.getAttribute("data-count"), 10);
      if (!target) return;
      var start = null, dur = 1100, done = false;
      el.textContent = "0";
      function finish() {
        if (done) return;
        done = true;
        el.textContent = target.toLocaleString("en-US");
        el.classList.add("pop");
      }
      function step(ts) {
        if (done) return;
        if (start === null) start = ts;
        var p = Math.min(1, (ts - start) / dur);
        el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))).toLocaleString("en-US");
        if (p < 1) requestAnimationFrame(step); else finish();
      }
      setTimeout(function () { requestAnimationFrame(step); }, 350 + k * 90);
      // always land on the real value, even where animation frames don't run (background tabs)
      setTimeout(finish, 350 + k * 90 + dur + 300);
    });

    // once per visit, the stat cards flip over in a wave to show there's something on the back
    if (once("tile-wave")) {
      $$(".tile").forEach(function (t, k) {
        setTimeout(function () {
          if (!motionOn() || t.matches(":hover")) return;
          t.classList.add("peek");
          setTimeout(function () { t.classList.remove("peek"); }, 1300);
        }, 3200 + k * 170);
      });
    }
  }
})();
