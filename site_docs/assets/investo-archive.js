/* u179: optional date/month filters; static links remain the source of truth. */
(function () {
  "use strict";
  function init() {
    document.querySelectorAll(".investo-archive").forEach(function (archive) {
      var form = archive.querySelector(".investo-archive-controls");
      if (!form || archive.dataset.filtersReady) return;
      var month = form.elements.namedItem("month");
      var date = form.elements.namedItem("date");
      var groups = Array.from(archive.querySelectorAll(".investo-archive-month"));
      var rows = Array.from(archive.querySelectorAll(".investo-archive-entry"));
      var status = archive.querySelector(".investo-archive-result");
      if (!month || !date || !status) return;
      function update() {
        var query = date.value.trim();
        var count = 0;
        groups.forEach(function (group) {
          var visible = 0;
          group.querySelectorAll(".investo-archive-entry").forEach(function (row) {
            var matches = (!month.value || group.dataset.month === month.value) &&
              row.dataset.date.indexOf(query) !== -1;
            row.hidden = !matches;
            if (matches) visible++;
          });
          group.hidden = visible === 0;
          count += visible;
        });
        status.textContent = count ? "전체 " + rows.length + "건 중 " + count + "건 표시" :
          "조건에 맞는 날짜가 없습니다. 전체 목록으로 돌아가 다시 찾아보세요.";
      }
      form.addEventListener("submit", function (event) { event.preventDefault(); });
      month.addEventListener("change", update);
      date.addEventListener("input", update);
      form.addEventListener("reset", function () { window.setTimeout(update, 0); });
      document.querySelectorAll('a[href^="#month-"]').forEach(function (link) {
        var target = document.getElementById(link.getAttribute("href").slice(1));
        if (!target || !archive.contains(target)) return;
        link.addEventListener("click", function () {
          month.value = "";
          date.value = "";
          update();
        });
      });
      archive.dataset.filtersReady = "true";
      form.hidden = false;
      update();
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
