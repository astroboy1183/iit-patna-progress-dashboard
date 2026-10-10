(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Heatmap tooltips (each cell's <title> is the no-JS fallback).
  var tip = document.getElementById("tip");
  if (tip) {
    document.querySelectorAll("svg.heat rect[data-tip]").forEach(function (el) {
      var t = el.querySelector("title");
      if (t) { el.setAttribute("aria-label", t.textContent); t.remove(); }
      el.addEventListener("mouseenter", function () {
        var r = el.getBoundingClientRect();
        tip.textContent = el.getAttribute("data-tip");
        tip.style.left = r.left + r.width / 2 + "px";
        tip.style.top = r.top + "px";
        tip.hidden = false;
      });
      el.addEventListener("mouseleave", function () { tip.hidden = true; });
    });
    window.addEventListener("scroll", function () { tip.hidden = true; }, { passive: true });
  }

  if (reduce) return;

  // Only switch motion on once the browser proves it runs CSS animations: a 1 ms probe animation
  // must actually finish. Where animations never run (some bots, screenshot tools, throttled tabs)
  // the probe never ends, motion is never enabled, and the page stays fully visible and static.
  var probe = document.createElement("div");
  probe.className = "motion-probe";
  probe.setAttribute("aria-hidden", "true");
  probe.addEventListener("animationend", function () { probe.remove(); startMotion(); }, { once: true });
  document.body.appendChild(probe);

  function startMotion() {
    var root = document.documentElement;
    root.classList.add("motion");

    // Safety net: some environments (link-preview bots, screenshot tools, throttled tabs) never run
    // CSS animations, which would leave content stuck invisible. After animations should have finished,
    // check that the elements really are visible; if not, switch motion off so everything shows at once.
    function opaque(el) { return parseFloat(getComputedStyle(el).opacity) > 0.95; }
    function verify(els, wait) {
      setTimeout(function () {
        if (!els.every(opaque)) root.classList.remove("motion");
      }, wait);
    }
    verify(Array.prototype.slice.call(document.querySelectorAll(".tile, .hero-text > *, .ring")), 2600);

    // Progress ring sweeps from 0 to its value.
    var ring = document.querySelector(".ring-fill");
    if (ring) {
      var final = ring.getAttribute("stroke-dasharray");
      var full = final.split(" ")[1];
      ring.setAttribute("stroke-dasharray", "0 " + full);
      requestAnimationFrame(function () { requestAnimationFrame(function () { ring.setAttribute("stroke-dasharray", final); }); });
      setTimeout(function () { ring.setAttribute("stroke-dasharray", final); }, 400);
    }

    // Sections below the fold fade in when scrolled to; everything is revealed after 4s regardless.
    var blocks = Array.prototype.slice.call(document.querySelectorAll(".block"));
    function reveal(el) {
      if (!el.classList.contains("pending")) return;
      el.classList.remove("pending");
      verify([el], 1500);
    }
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting) { reveal(e.target); io.unobserve(e.target); } });
      }, { rootMargin: "0px 0px -10% 0px" });
      blocks.forEach(function (el) {
        el.classList.add("pending");
        io.observe(el);
      });
    }
    // If the page is never scrolled (e.g. a tall viewport), still reveal everything eventually.
    setTimeout(function () { blocks.forEach(reveal); }, 6000);

    // Count-up for the stat tiles (final values are already in the HTML).
    document.querySelectorAll(".tile .num[data-count]").forEach(function (el) {
      var target = parseInt(el.getAttribute("data-count"), 10);
      if (!target) return;
      var start = null, dur = 900, done = false;
      el.textContent = "0";
      function step(ts) {
        if (done) return;
        if (start === null) start = ts;
        var p = Math.min(1, (ts - start) / dur);
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(target * eased).toLocaleString("en-US");
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
      // Always land on the real value, even where animation frames don't run (previews, background tabs).
      setTimeout(function () { done = true; el.textContent = target.toLocaleString("en-US"); }, dur + 300);
    });

  }
})();
