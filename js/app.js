(() => {
  const byId = id => document.getElementById(id);
  const input = byId('files');
  const stationPanel = byId('selected-stations');
  const stationList = byId('selected-station-list');
  const returnLink = byId('return-to-start');
  const selectedStops = new Map();
  const completed = new Set();
  const completionKey = 'quest-map-completed';
  let completionDay = '';
  let position = null;
  let tripOrigin = null;
  let legStart = null;
  let syncPopup = null;
  const report = message => { byId('map-status').textContent = message; };
  const map = createQuestMap(byId('map'), byId('locate'), report, (coords, first) => {
    center = coords;
    position = { lat: coords.latitude, lng: coords.longitude };
    refresh(first);
  }, addActions);
  let records = [];
  let matching = [];
  let center = null;

  function syncCompletionDay() {
    const day = QuestParser.parseDate(Math.floor(Date.now() / 1000)).slice(0, 10);
    if (completionDay === day) return;
    completionDay = day;
    completed.clear();
    try {
      const saved = JSON.parse(localStorage.getItem(completionKey));
      if (saved?.day === day && Array.isArray(saved.keys)) saved.keys.forEach(key => completed.add(key));
    } catch { /* Storage can be unavailable in some browsing modes. */ }
    return true;
  }

  function refresh(fit = false) {
    if (syncCompletionDay()) refreshTrip();
    const visible = center ? QuestFilters.nearby(matching, center, 5) : matching;
    byId('count').textContent = visible.length.toLocaleString('zh-TW');
    byId('range').textContent = center ? '附近 5 公里' : '全部範圍';
    map?.render(visible, fit, center, completed);
    byId('empty').hidden = visible.length > 0;
    byId('empty').textContent = center ? '附近 5 公里沒有符合的任務' :
      records.length ? '資料中沒有符合指定任務與獎勵的補給站' : '匯入任務 JSON 以顯示補給站';
  }

  function refreshTrip(focusKey) {
    const stops = [...selectedStops.values()];
    const pending = stops.filter(stop => !completed.has(stop.key));
    const finished = stops.filter(stop => completed.has(stop.key));
    const route = QuestRoute.order(pending, legStart, tripOrigin);
    byId('selected-station-count').textContent = stops.length.toLocaleString('zh-TW');
    let focused;
    const items = [...route, ...finished].map(stop => {
      const item = document.createElement('li');
      item.classList.toggle('selected-station-completed', completed.has(stop.key));
      const row = document.createElement('div');
      row.className = 'selected-station-row';
      const link = document.createElement('a');
      link.href = QuestRoute.navigationUrl(stop);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = stop.name;
      const label = document.createElement('label');
      label.className = 'station-completion';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = completed.has(stop.key);
      checkbox.setAttribute('aria-label', stop.name + '已完成');
      checkbox.addEventListener('change', () => toggleComplete(stop, true));
      if (stop.key === focusKey) focused = checkbox;
      label.append(checkbox, document.createTextNode('完成'));
      row.append(link, label);
      item.append(row);
      return item;
    });
    stationList.replaceChildren(...items);
    stationList.hidden = !items.length;
    if (tripOrigin) returnLink.href = QuestRoute.navigationUrl(tripOrigin);
    else returnLink.removeAttribute('href');
    stationPanel.hidden = !tripOrigin;
    if (stationPanel.hidden) stationPanel.open = false;
    focused?.focus({ preventScroll: true });
    syncPopup?.();
    map?.showRoute(route, legStart, tripOrigin);
  }

  function toggleComplete(record, fromList = false) {
    syncCompletionDay();
    if (completed.has(record.key)) {
      completed.delete(record.key);
    } else {
      completed.add(record.key);
      if (selectedStops.has(record.key)) legStart = { lat: record.lat, lng: record.lng };
    }
    try {
      localStorage.setItem(completionKey, JSON.stringify({ day: completionDay, keys: [...completed] }));
    } catch { /* Keep completion in memory if storage is unavailable. */ }
    refreshTrip(fromList ? record.key : undefined);
    refresh();
  }

  function addActions(popup, record) {
    syncCompletionDay();
    const label = document.createElement('label');
    label.className = 'finished-toggle';
    const check = document.createElement('input');
    check.type = 'checkbox';
    check.addEventListener('change', () => {
      if (check.checked) {
        if (selectedStops.size >= QuestRoute.MAX_STOPS) {
          check.checked = false;
          report('每條路線最多 ' + QuestRoute.MAX_STOPS + ' 站');
          return;
        }
        if (!selectedStops.size) {
          tripOrigin = position || { lat: record.lat, lng: record.lng };
          legStart = tripOrigin;
        }
        selectedStops.set(record.key, record);
      } else {
        selectedStops.delete(record.key);
        if (!selectedStops.size) {
          tripOrigin = null;
          legStart = null;
        }
      }
      refreshTrip();
    });
    label.append(check, document.createTextNode('加入路線'));
    const done = document.createElement('button');
    done.type = 'button';
    done.className = 'mark-complete';
    const updateLabel = () => {
      check.checked = selectedStops.has(record.key);
      const isComplete = completed.has(record.key);
      check.disabled = isComplete && !check.checked;
      done.textContent = isComplete ? '取消完成' : '標記完成';
    };
    done.addEventListener('click', () => toggleComplete(record));
    syncPopup = updateLabel;
    updateLabel();
    popup.append(label, done);
  }

  function refreshData(fit) {
    matching = QuestFilters.matchingQuest(records);
    refresh(fit);
  }

  byId('fit').addEventListener('click', () => {
    map?.stopFollowing();
    center = null;
    report('');
    refresh(true);
  });
  window.addEventListener('pageshow', () => refresh());
  byId('import').addEventListener('click', () => input.click());

  input.addEventListener('change', async () => {
    const files = Array.from(input.files);
    input.value = '';
    if (!files.length) return;
    byId('import').disabled = true;
    byId('import-status').textContent = '正在匯入…';
    let invalid = 0;
    let duplicates = 0;
    let successes = 0;
    const failures = [];
    for (const file of files) {
      try {
        const parsed = QuestParser.parse(JSON.parse((await file.text()).replace(/^\uFEFF/, '')));
        const merged = QuestParser.merge(records, parsed.records);
        records = merged.records;
        invalid += parsed.invalid;
        duplicates += merged.duplicates;
        successes++;
      } catch (error) {
        failures.push(file.name + '（' + error.message + '）');
      }
    }
    refreshData(successes > 0);
    const message = ['匯入 ' + successes + '/' + files.length + ' 個檔案'];
    if (invalid) message.push('略過 ' + invalid + ' 筆無效座標');
    if (duplicates) message.push('合併 ' + duplicates + ' 筆重複資料');
    if (failures.length) message.push('讀取失敗 ' + failures.join('、'));
    byId('import-status').textContent = message.join('，');
    byId('import').disabled = false;
  });

  refresh();
  function showSnapshotTime(value) {
    const time = typeof value === 'string' ? Date.parse(value) : NaN;
    const status = byId('snapshot-status');
    if (!Number.isFinite(time) || time < 0) {
      status.textContent = '這份快照未記錄最後更新時間';
      return;
    }
    const stale = Date.now() - time > 48 * 60 * 60 * 1000;
    status.textContent = '最後更新 ' + QuestParser.parseDate(Math.floor(time / 1000)) +
      '（台灣時間）' + (stale ? ' · 資料已超過 48 小時' : '');
    status.classList.toggle('stale', stale);
  }

  async function loadSnapshot() {
    try {
      const inline = byId('quest-snapshot');
      let raw;
      if (inline) {
        raw = JSON.parse(inline.textContent);
      } else {
        if (!['https:', 'http:'].includes(location.protocol)) return;
        const options = { cache: 'no-store', redirect: 'error' };
        let response = await fetch('./data/quests.json', options);
        if (response.status === 404) response = await fetch('./quests.json', options);
        if (!response.ok) return;
        raw = await response.json();
      }
      const parsed = QuestParser.parse(raw);
      const bundled = QuestParser.merge([], parsed.records).records;
      records = QuestParser.merge(bundled, records).records;
      refreshData(true);
      showSnapshotTime(raw.updated_at);
      byId('import-status').textContent = '已載入任務快照';
    } catch {
      byId('import-status').textContent = '任務快照無法載入，可手動匯入';
    }
  }
  loadSnapshot();
})();

