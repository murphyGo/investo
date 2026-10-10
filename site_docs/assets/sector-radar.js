/* The radar reads only its generated DOM; filters never fetch or recalculate data. */
(() => {
  "use strict";

  function initializeRadar() {
    const dashboard = document.querySelector(".sector-dashboard");
    if (!dashboard || dashboard.dataset.radarInitialized === "true") return;
    const groupView = dashboard.querySelector("#sector-view-groups");
    const overviewView = dashboard.querySelector("#sector-view-overview");
    if (!groupView || !overviewView) return;

    dashboard.dataset.radarInitialized = "true";
    dashboard.classList.add("sector-dashboard--interactive");
    const tabs = [...dashboard.querySelectorAll("[data-sector-view]")];
    const filters = [...groupView.querySelectorAll("[data-group-filter]")];
    const rows = [...groupView.querySelectorAll(".sector-group-row, .sector-group-chip")];
    const tableRows = [...groupView.querySelectorAll("tr.sector-group-row")];
    const announcement = groupView.querySelector(".sector-filter-announcement");

    function selectView(name, focus = false) {
      groupView.hidden = name !== "groups";
      overviewView.hidden = name !== "overview";
      tabs.forEach((tab) => {
        const selected = tab.dataset.sectorView === name;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        if (selected && focus) tab.focus();
      });
    }

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => selectView(tab.dataset.sectorView));
      tab.addEventListener("keydown", (event) => {
        const destination = {
          ArrowRight: (index + 1) % tabs.length,
          ArrowLeft: (index + tabs.length - 1) % tabs.length,
          Home: 0,
          End: tabs.length - 1,
        }[event.key];
        if (!Number.isInteger(destination)) return;
        event.preventDefault();
        selectView(tabs[destination].dataset.sectorView, true);
      });
    });

    filters.forEach((button) => {
      button.addEventListener("click", () => {
        const category = button.dataset.groupFilter;
        filters.forEach((filter) => {
          filter.setAttribute("aria-pressed", String(filter === button));
        });
        rows.forEach((row) => {
          row.hidden = category !== "all" && row.dataset.groupCategory !== category;
        });
        groupView.querySelectorAll(".sector-regime").forEach((cell) => {
          const count = [...cell.querySelectorAll(".sector-group-chip")].filter(
            (chip) => !chip.hidden
          ).length;
          cell.querySelector("[data-group-regime-count]").textContent = String(count);
          cell.querySelector("[data-group-regime-empty]").hidden = count !== 0;
        });
        const count = tableRows.filter((row) => !row.hidden).length;
        announcement.textContent = `${button.textContent}: ${count}개 그룹 표시`;
      });
    });

    // A table-of-contents link into a hidden view must reveal that view first.
    dashboard.revealRadarAnchor = () => {
      let id;
      try { id = decodeURIComponent(location.hash.slice(1)); }
      catch { return; }
      const target = id ? document.getElementById(id) : null;
      const view = target?.closest(".sector-view");
      if (!view || !dashboard.contains(view)) return;
      if (view.hidden) {
        selectView(view === overviewView ? "overview" : "groups");
        target.scrollIntoView();
      }
    };
    selectView("groups");
    dashboard.revealRadarAnchor();
  }

  window.addEventListener("hashchange", () => {
    document.querySelector(".sector-dashboard")?.revealRadarAnchor?.();
  });
  if (typeof document$ !== "undefined") {
    document$.subscribe(initializeRadar);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeRadar, { once: true });
  } else {
    initializeRadar();
  }
})();
