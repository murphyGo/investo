/* u182/u184: bounded month/date navigation over the published DOM; no fetch. */
(() => {
  'use strict';
  const DAY = 86400000;
  const categories = {economic_release: '경제지표', central_bank: '중앙은행', treasury_auction: '국채 입찰'};
  const addDays = (iso, count) => new Date(Date.parse(iso + 'T00:00:00Z') + count * DAY).toISOString().slice(0, 10);
  function interval(item, days) {
    return [item.start > item.windowStart ? item.start : item.windowStart,
      item.end < addDays(item.windowStart, days - 1) ? item.end : addDays(item.windowStart, days - 1)];
  }
  function includesDay(item, day, days) {
    const [start, end] = interval(item, days);
    return start <= day && day <= end;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {addDays, interval, includesDay};
  if (typeof document === 'undefined') return;
  function initialize() {
    document.querySelectorAll('[data-calendar]').forEach(root => {
      if (root.dataset.ready === 'true') return;
      root.dataset.ready = 'true';
      const controls = root.querySelector('[data-calendar-filters]');
      const status = root.querySelector('[data-calendar-status]');
      const empty = root.querySelector('[data-calendar-empty]');
      if (!controls || !status || !empty) return;
      const board = root.querySelector('[data-calendar-initial-month]');
      const months = [...root.querySelectorAll('[data-calendar-month]')];
      const monthTitle = root.querySelector('[data-calendar-month-title]');
      const agendaTitle = root.querySelector('[data-calendar-agenda-title]');
      const previous = root.querySelector('[data-calendar-previous]');
      const next = root.querySelector('[data-calendar-next]');
      const reset = root.querySelector('[data-calendar-reset]');
      const daysInGrid = [...root.querySelectorAll('[data-calendar-day]')];
      const items = [...root.querySelectorAll('[data-event]')].map(row => ({
        row, category: row.dataset.category, withinSeven: row.dataset.withinSeven === 'true',
        start: row.dataset.start, end: row.dataset.end, windowStart: row.dataset.windowStart,
        title: row.querySelector('h3')?.textContent || '', clock: row.dataset.clock ? `${row.dataset.clock} KST` : '미 동부 · 시간 미정',
        basis: row.dataset.clockBasis,
      }));
      let monthIndex = Math.max(0, months.findIndex(m => m.dataset.calendarMonth === board?.dataset.calendarInitialMonth));
      const initialMonth = monthIndex;
      let days = 30, category = 'all', selected = null, allMonths = !board;
      const eligible = item => (days === 30 || item.withinSeven) && (category === 'all' || item.category === category);
      const node = (className, value) => {
        const span = document.createElement('span'); span.className = className; span.textContent = value; return span;
      };
      function update() {
        const month = months[monthIndex];
        const monthKey = month?.dataset.calendarMonth;
        const monthLabel = month?.dataset.monthLabel || '';
        months.forEach((element, index) => { element.hidden = index !== monthIndex; });
        if (monthTitle) monthTitle.textContent = monthLabel;
        if (previous) previous.disabled = monthIndex === 0;
        if (next) next.disabled = monthIndex === months.length - 1;
        let count = 0;
        items.forEach(item => {
          let visible = eligible(item);
          if (visible && item.start && selected) visible = includesDay(item, selected, days);
          else if (visible && item.start && monthKey && !allMonths) {
            const [start, end] = interval(item, days);
            visible = start.slice(0, 7) <= monthKey && end.slice(0, 7) >= monthKey;
          }
          item.row.hidden = !visible;
          if (visible) count++;
        });
        controls.querySelectorAll('[data-days]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.days) === days)));
        controls.querySelectorAll('[data-category-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.categoryFilter === category)));
        for (const link of daysInGrid) {
          const day = link.dataset.calendarDay;
          const matches = items.filter(item => eligible(item) && includesDay(item, day, days));
          const kst = matches.filter(item => item.basis === 'exact').length;
          link.setAttribute('role', 'button');
          link.setAttribute('aria-pressed', String(day === selected));
          link.setAttribute('aria-label', `${day} · 표시 ${matches.length}건 · KST ${kst}건 · 미 동부 날짜 ${matches.length - kst}건`);
          link.querySelector('.calendar-day-count').textContent = matches.length ? `${matches.length}건` : '—';
          const basis = link.querySelector('.calendar-day-basis');
          basis.replaceChildren(node('', `KST ${kst}`), document.createElement('br'), node('', `동부 ${matches.length - kst}`));
          const previews = matches.slice(0, 2).map(item => {
            const preview = node('calendar-preview', ''); preview.dataset.category = item.category;
            preview.append(node('calendar-preview-title', item.title), node('calendar-preview-clock', item.clock), node('calendar-preview-category', categories[item.category]));
            return preview;
          });
          link.querySelector('.calendar-day-previews').replaceChildren(...previews);
          link.querySelector('.calendar-day-more').textContent = matches.length > 2 ? `+${matches.length - 2}건` : '';
        }
        const scope = selected ? `${selected} 표기 일정` : allMonths ? `${days}일 전체 일정` : `${monthLabel} 일정`;
        if (agendaTitle) agendaTitle.textContent = scope;
        if (reset) reset.hidden = selected === null;
        empty.hidden = count !== 0;
        status.textContent = `${scope} · ${categories[category] || '전체'} · 표시 ${count}건. KST 시각과 미 동부 날짜를 구분해 확인하세요.`;
      }
      root.addEventListener('click', event => {
        if (!(event.target instanceof Element)) return;
        const dayLink = event.target.closest('[data-calendar-day]');
        if (dayLink && root.contains(dayLink)) {
          event.preventDefault(); selected = dayLink.dataset.calendarDay; allMonths = false; update();
          agendaTitle?.focus({preventScroll: true});
          agendaTitle?.scrollIntoView({block: 'start', behavior: 'auto'});
          return;
        }
        const button = event.target.closest('button');
        if (!button || !root.contains(button)) return;
        if (button.hasAttribute('data-calendar-previous') && monthIndex > 0) { monthIndex--; selected = null; allMonths = false; }
        if (button.hasAttribute('data-calendar-next') && monthIndex < months.length - 1) { monthIndex++; selected = null; allMonths = false; }
        if (button.hasAttribute('data-calendar-reset')) { selected = null; allMonths = false; }
        if (button.dataset.days) { days = Number(button.dataset.days); selected = null; monthIndex = initialMonth; allMonths = false; }
        if (button.dataset.categoryFilter) { category = button.dataset.categoryFilter; selected = null; }
        update();
        if (button.hasAttribute('data-calendar-reset')) agendaTitle?.focus({preventScroll: true});
      });
      root.addEventListener('keydown', event => {
        if (!(event.target instanceof Element)) return;
        const link = event.target.closest('[data-calendar-day]');
        if (!link) return;
        if (event.key === ' ') { event.preventDefault(); link.click(); return; }
        const delta = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7}[event.key];
        if (!delta) return;
        event.preventDefault();
        const day = addDays(link.dataset.calendarDay, delta);
        const target = daysInGrid.find(cell => cell.dataset.calendarDay === day);
        if (!target) return;
        monthIndex = months.indexOf(target.closest('[data-calendar-month]'));
        allMonths = false; update(); target.focus();
      });
      root.querySelector('[data-testid="calendar-thirty-anchor"]')?.addEventListener('click', () => {
        days = 30; selected = null; allMonths = true; update();
      });
      const navigation = root.querySelector('[data-calendar-navigation]');
      if (navigation) navigation.hidden = false;
      controls.hidden = false;
      update();
    });
  }
  initialize();
  if (typeof document$ !== 'undefined') document$.subscribe(initialize);
})();
