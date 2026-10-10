/* u178: optional presentation hint, based only on the actual table viewport. */
(function () {
  "use strict";
  function init() {
    var tables = document.querySelectorAll(".investo-data-table");
    function measure(element) {
      element.dataset.overflow = String(element.scrollWidth > element.clientWidth);
    }
    if (typeof ResizeObserver === "function") {
      var observer = new ResizeObserver(function (entries) {
        entries.forEach(function (entry) { measure(entry.target); });
      });
      tables.forEach(function (element) { observer.observe(element); });
    }
    tables.forEach(measure);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
