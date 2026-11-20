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
  let route = [];
  let syncPopup = null;
  const report = message => { byId('map-status').textContent = message; };
  const map = createQuestMap(byId('map'), byId('locate'), report, coords => {
    position = { lat: coords.latitude, lng: coords.longitude };
  }, addActions);
  let records = [];
  let matching = [];

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
    byId('count').textContent = matching.length.toLocaleString('zh-TW');
    map?.render(matching, fit, completed);
    byId('empty').hidden = matching.length > 0;
    byId('empty').textContent = records.length ?
      '資料中沒有符合指定任務與獎勵的補給站' : '匯入任務 JSON 以顯示補給站';
  }

  function refreshTrip(focusKey) {
    byId('selected-station-count').textContent = route.length.toLocaleString('zh-TW');
    let focused;
    const items = route.map(stop => {
      const isComplete = completed.has(stop.key);
      const item = document.createElement('li');
      item.classList.toggle('selected-station-completed', isComplete);
      const row = document.createElement('div');
      row.className = 'selected-station-row';
      const name = document.createElement(isComplete ? 'span' : 'a');
      name.className = 'selected-station-name';
      name.textContent = stop.name;
      if (!isComplete) {
        name.href = QuestRoute.navigationUrl(stop);
        name.target = '_blank';
        name.rel = 'noopener noreferrer';
      }
      const label = document.createElement('label');
      label.className = 'station-completion';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = isComplete;
      checkbox.setAttribute('aria-label', stop.name + '已完成');
      checkbox.addEventListener('change', () => toggleComplete(stop, true));
      if (stop.key === focusKey) focused = checkbox;
      label.append(checkbox, document.createTextNode('完成'));
      row.append(name, label);
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
    map?.showRoute(route, tripOrigin, completed);
  }

  function toggleComplete(record, fromList = false) {
    syncCompletionDay();
    if (completed.has(record.key)) {
      completed.delete(record.key);
    } else {
      completed.add(record.key);
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
        }
        selectedStops.set(record.key, record);
      } else {
        selectedStops.delete(record.key);
        if (!selectedStops.size) {
          tripOrigin = null;
        }
      }
      route = QuestRoute.order(selectedStops.values(), tripOrigin);
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
    refreshData(successes > 0 && !position);
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
      refreshData(!position);
      showSnapshotTime(raw.updated_at);
      byId('import-status').textContent = '已載入任務快照';
    } catch {
      byId('import-status').textContent = '任務快照無法載入，可手動匯入';
    }
  }
  map?.recenter();
  loadSnapshot();
})();

