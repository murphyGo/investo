/* u176: keyboard access to Material's native checkbox/radio label controls. */
(function () {
  "use strict";
  function init() {
    document.querySelectorAll(".md-nav__link--active").forEach(function (link) {
      link.setAttribute("aria-current", "page");
    });
    document.querySelectorAll(".md-header__button[for]").forEach(function (label) {
      var id = label.getAttribute("for");
      var input = document.getElementById(id);
      if (!input || label.dataset.investoKeyboard) return;
      label.dataset.investoKeyboard = "true";
      label.dataset.testid = "investo-header-" + id.replace(/^__/, "");
      label.setAttribute("role", "button");
      label.setAttribute("tabindex", "0");
      var names = { __search: "검색", __drawer: "메뉴 열기", __palette_0: "라이트 모드로 전환", __palette_1: "다크 모드로 전환" };
      label.setAttribute("aria-label", label.getAttribute("aria-label") || label.title || names[id]);
      label.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          event.stopPropagation();
          label.click();
        }
      });
      if (id === "__drawer" || id === "__search") {
        var update = function () { label.setAttribute("aria-expanded", String(input.checked)); };
        input.addEventListener("change", update);
        update();
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      ["__search", "__drawer"].forEach(function (id) {
        var input = document.getElementById(id);
        if (!input || !input.checked) return;
        input.checked = false;
        input.dispatchEvent(new Event("change", { bubbles: true }));
        var label = document.querySelector('.md-header__button[for="' + id + '"]');
        var candidates = [label, document.querySelector(".md-header__button.md-logo"),
          document.querySelector('.md-header__button[for="__drawer"]')];
        var target = candidates.find(function (element) {
          return element && element.getClientRects().length;
        });
        // Material also restores focus while closing. Run after that
        // transition so an offscreen/hidden desktop trigger cannot win.
        if (target) window.requestAnimationFrame(function () { target.focus(); });
      });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
