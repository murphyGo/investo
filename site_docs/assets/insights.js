/* u181/u183: optional bounded history on interaction. Current data needs no JS. */
(() => {
  "use strict";
  function init() {
    const root = document.querySelector('[data-insights-module="macro"],[data-insights-module="crypto"]');
    const moduleId = root?.dataset.insightsModule === "crypto" ? "crypto" : "macro";
    const button = root?.querySelector('[data-load-history]');
    if (!button || button.dataset.ready) return;
    button.dataset.ready = "true";
    button.hidden = false;
    const status = root.querySelector('[data-history-status]');
    const content = root.querySelector('[data-history-content]');
    const text = (tag, value) => {
      const element = document.createElement(tag);
      element.textContent = value;
      return element;
    };
    async function read(path, cap) {
      const url = new URL(path, location.href);
      if (url.origin !== location.origin) throw new Error("origin");
      const response = await fetch(url, {cache: "no-store", credentials: "same-origin"});
      if (!response.ok || Number(response.headers.get("content-length")) > cap) throw new Error("read");
      const bytes = await response.arrayBuffer();
      if (bytes.byteLength > cap) throw new Error("cap");
      return bytes;
    }
    button.addEventListener("click", async () => {
      button.disabled = true;
      status.textContent = "검증된 관측 이력을 불러오는 중입니다.";
      try {
        const manifest = JSON.parse(new TextDecoder().decode(await read("../_data/manifest.json", 65536)));
        const entry = manifest.modules?.find(value => value.module === moduleId);
        if (!entry || entry.snapshot_id !== root.dataset.snapshot || entry.current_hash !== root.dataset.currentHash) {
          status.textContent = "새 자료가 게시되었습니다. 화면을 새로고침한 뒤 이력을 확인하세요.";
          return;
        }
        const bytes = await read(`../_data/${moduleId}/history.json`, 4 * 1024 * 1024);
        const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), value => value.toString(16).padStart(2, "0")).join("");
        if (hash !== entry.history_hash) throw new Error("identity");
        const history = JSON.parse(new TextDecoder().decode(bytes));
        if (history.module !== moduleId || !Array.isArray(history.rows) || history.rows.length > 11712 || !Array.isArray(history.definitions)) throw new Error("schema");
        const fragment = document.createDocumentFragment();
        let groups = 0;
        for (const card of root.querySelectorAll('[data-comparison-key]')) {
          const definition = history.definitions.find(value => value.key === card.dataset.comparisonKey);
          if (!definition || definition.metric.cadence !== (moduleId === "macro" ? "daily" : "snapshot") || definition.metric.metric_id !== card.dataset.metric || definition.metric.unit !== card.dataset.unit) continue;
          const rows = history.rows.filter(row => row.definition_key === card.dataset.comparisonKey && row.observation_key <= card.dataset.observation)
            .sort((a, b) => a.observation_key.localeCompare(b.observation_key)).slice(-30);
          if (rows.length < 1) continue;
          if (rows.some(row => typeof row.value !== "string" || !Number.isFinite(Number(row.value)) || !/^\d{4}-\d{2}-\d{2}$/.test(row.observation_key))) throw new Error("value");
          const details = document.createElement("details");
          details.append(text("summary", `${definition.metric.label} · 최근 ${rows.length}개 관측`));
          details.append(text("p", definition.attribution || definition.metric.provider));
          const table = document.createElement("table");
          table.append(text("caption", `${definition.metric.label} · ${{percent:"%",basis_point:"bp",krw_per_usd:"원/USD",index:"지수",usd:"USD",usd_notional:"USD 명목",fraction:"원천 비율(카드 표시는 ×100%)"}[card.dataset.unit]} · 결측일 보간 없음`));
          const head = document.createElement("thead");
          const heading = document.createElement("tr");
          const labels = moduleId === "crypto" ? ["수집 표본 UTC일", "원천값", "표본 변경", "원천 시각·적용 주기"] : ["관측일", "원천값", "수정 여부"];
          for (const label of labels) {
            const cell = text("th", label); cell.scope = "col"; heading.append(cell);
          }
          head.append(heading); table.append(head);
          const body = document.createElement("tbody");
          for (const row of rows) {
            const line = document.createElement("tr");
            const day = text("th", row.observation_key); day.scope = "row";
            line.append(day, text("td", row.value), text("td", row.revised_from ? "같은 시점 수정" : row.superseded_from ? "당일 표본 교체" : "—"));
            if (moduleId === "crypto") {
              const at = row.time?.source_updated_at || row.time?.exact_at;
              const clock = at || `수집 구간 ${row.time?.window_start || "미확인"} ~ ${row.time?.window_end || "미확인"}`;
              const cycle = row.time?.applicable_start && row.time?.applicable_end ? ` · 지시적 적용 주기 ${row.time.applicable_start} ~ ${row.time.applicable_end}` : "";
              line.append(text("td", `${clock}${cycle}`.slice(0,400)));
            }
            body.append(line);
          }
          table.append(body); details.append(table); // Exact table survives optional chart failure.
          try {
            window.InvestoInsightCharts?.history(details, rows, definition, moduleId);
          } catch { /* Preserve the exact table if a chart cannot represent the data. */ }
          fragment.append(details); groups++;
        }
        content.replaceChildren(fragment);
        status.textContent = groups ? "원천의 관측일과 값을 확인하세요." : "비교 가능한 관측 이력이 아직 부족합니다.";
        button.hidden = true;
      } catch {
        status.textContent = "이력을 확인하지 못했습니다. 현재 카드와 원천 링크를 확인하거나 다시 시도하세요.";
        button.disabled = false;
      }
    });
  }
  init();
  if (typeof document$ !== "undefined") document$.subscribe(init);
})();
