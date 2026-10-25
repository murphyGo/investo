/* u182: local DOM filters only. No fetch, clock guessing or external dependency. */
(() => {
  function initialize() {
    document.querySelectorAll('[data-calendar]').forEach(root => {
      if (root.dataset.ready === 'true') return;
      root.dataset.ready = 'true';
      const controls = root.querySelector('[data-calendar-filters]');
      const status = root.querySelector('[data-calendar-status]');
      const empty = root.querySelector('[data-calendar-empty]');
      const rows = [...root.querySelectorAll('[data-event]')];
      if (!controls || !status || !empty) return;
      let days = '7', category = 'all';
      const update = () => {
        let count = 0;
        rows.forEach(row => {
          row.hidden = !((days === '30' || row.dataset.withinSeven === 'true') &&
                         (category === 'all' || row.dataset.category === category));
          if (!row.hidden) count++;
        });
        controls.querySelectorAll('[data-days]').forEach(button => {
          button.setAttribute('aria-pressed', String(button.dataset.days === days));
        });
        controls.querySelectorAll('[data-category-filter]').forEach(button => {
          button.setAttribute('aria-pressed', String(button.dataset.categoryFilter === category));
        });
        empty.hidden = count !== 0;
        status.textContent = `${days}일 · 표시 ${count}건 · 날짜 기준은 각 일정에 표시됩니다.`;
      };
      controls.addEventListener('click', event => {
        const button = event.target.closest('button');
        if (!button || !controls.contains(button)) return;
        if (button.dataset.days) days = button.dataset.days;
        if (button.dataset.categoryFilter) category = button.dataset.categoryFilter;
        update();
      });
      root.querySelector('[data-testid="calendar-thirty-anchor"]')?.addEventListener('click', () => {
        days = '30'; update();
      });
      controls.hidden = false;
      update();
    });
  }
  initialize();
  if (typeof document$ !== 'undefined') document$.subscribe(initialize);
})();
