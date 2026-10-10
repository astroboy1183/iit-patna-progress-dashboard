(function () {
  "use strict";
  // Hover / focus tooltip for heatmap cells (the <title> inside each cell is the no-JS fallback).
  var tip = document.getElementById("tip");
  if (!tip) return;
  function show(el) {
    var text = el.getAttribute("data-tip");
    if (!text) return;
    var r = el.getBoundingClientRect();
    tip.textContent = text;
    tip.style.left = r.left + r.width / 2 + "px";
    tip.style.top = r.top + "px";
    tip.hidden = false;
  }
  function hide() { tip.hidden = true; }
  document.querySelectorAll("svg.heat rect[data-tip]").forEach(function (el) {
    var t = el.querySelector("title");
    if (t) { el.setAttribute("aria-label", t.textContent); t.remove(); }
    el.addEventListener("mouseenter", function () { show(el); });
    el.addEventListener("mouseleave", hide);
  });
  window.addEventListener("scroll", hide, { passive: true });
})();
