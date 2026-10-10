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

  // Count-up for the stat tiles (final values are already in the HTML).
  document.querySelectorAll(".tile .num[data-count]").forEach(function (el) {
    var target = parseInt(el.getAttribute("data-count"), 10);
    if (!target) return;
    var start = null, dur = 900;
    el.textContent = "0";
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased).toLocaleString("en-US");
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
    // Always land on the real value, even where animation frames don't run (previews, background tabs).
    setTimeout(function () { el.textContent = target.toLocaleString("en-US"); }, dur + 300);
  });

})();
