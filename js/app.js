(() => {
  const byId = id => document.getElementById(id);
  const input = byId('files');
  const search = byId('search');
  const tasks = new Set();
  const rewards = new Set();
  const selectedStops = new Map();
  const completedToggle = byId('show-completed');
  const completed = new Set();
  const completionKey = 'quest-map-completed';
  let completionDay = '';
  let route = [];
  let position = null;
  let tripOrigin = null;
  let legStart = null;
  const report = message => { byId('map-status').textContent = message; };
  const map = createQuestMap(byId('map'), byId('locate'), report, (coords, first) => {
    center = coords;
    position = { lat: coords.latitude, lng: coords.longitude };
    refresh(first);
  }, addActions);
  let records = [];
  let matching = [];
  let filterTimer;
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
  }

  function refresh(fit = false) {
    syncCompletionDay();
    const inRange = center ? QuestFilters.nearby(matching, center, 5) : matching;
    const active = completedToggle.checked ? inRange : inRange.filter(record => !completed.has(record.key));
    const visible = QuestFilters.apply(active, search.value, tasks, rewards);
    byId('completed-count').textContent = completed.size ? '（' + completed.size + '）' : '';
    byId('count').textContent = visible.length.toLocaleString('zh-TW');
    byId('range').textContent = center ? '附近 5 公里' : '全部範圍';
    map?.render(visible, fit, center);
    byId('empty').hidden = visible.length > 0;
    byId('empty').textContent = center && !inRange.length ? '附近 5 公里沒有符合的任務' :
      matching.length ? '沒有符合條件的補給站' :
      records.length ? '資料中沒有符合指定任務與獎勵的補給站' : '匯入任務 JSON 以顯示補給站';
  }

  function refreshTrip() {
    route = QuestRoute.order(selectedStops.values(), legStart, tripOrigin);
    byId('trip-count').textContent = route.length ? '（' + route.length + ' 站）' : '';
    byId('trip-hint').textContent = route.length ? '依直線總距離最佳化，最後回到起點。' :
      tripOrigin ? '可導航返回起點。' : '點選地圖站點加入路線，最多 ' + QuestRoute.MAX_STOPS + ' 站。';
    byId('end-trip').hidden = !tripOrigin;
    const list = route.map(record => {
      const item = document.createElement('li');
      item.textContent = record.name;
      const done = document.createElement('button');
      done.type = 'button';
      done.textContent = '完成';
      done.setAttribute('aria-label', record.name + '標記完成');
      done.addEventListener('click', () => toggleComplete(record));
      item.append(done);
      return item;
    });
    byId('trip-stops').replaceChildren(...list);
    const urls = QuestRoute.directions(route, legStart, tripOrigin);
    byId('trip-links').replaceChildren(...urls.map((url, index) => {
      const link = document.createElement('a');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.className = 'directions';
      link.textContent = !route.length ? 'Google Maps 返回起點' :
        urls.length === 1 ? 'Google Maps 步行導航' : '步行導航 第 ' + (index + 1) + ' 段';
      return link;
    }));
    map?.showRoute(route, legStart, tripOrigin);
  }

  function toggleComplete(record) {
    syncCompletionDay();
    if (completed.has(record.key)) {
      completed.delete(record.key);
    } else {
      completed.add(record.key);
      if (selectedStops.delete(record.key)) legStart = { lat: record.lat, lng: record.lng };
    }
    try {
      localStorage.setItem(completionKey, JSON.stringify({ day: completionDay, keys: [...completed] }));
    } catch { /* Keep completion in memory if storage is unavailable. */ }
    refreshTrip();
    refresh();
  }

  function addActions(popup, record) {
    syncCompletionDay();
    const label = document.createElement('label');
    label.className = 'finished-toggle';
    const check = document.createElement('input');
    check.type = 'checkbox';
    check.checked = selectedStops.has(record.key);
    check.disabled = completed.has(record.key);
    check.addEventListener('change', () => {
      if (check.checked) {
        if (selectedStops.size >= QuestRoute.MAX_STOPS) {
          check.checked = false;
          report('每條路線最多 ' + QuestRoute.MAX_STOPS + ' 站');
          return;
        }
        if (!tripOrigin) {
          tripOrigin = position || { lat: record.lat, lng: record.lng };
          legStart = tripOrigin;
        }
        selectedStops.set(record.key, record);
      } else {
        selectedStops.delete(record.key);
      }
      refreshTrip();
    });
    label.append(check, document.createTextNode('加入路線'));
    const done = document.createElement('button');
    done.type = 'button';
    const updateLabel = () => {
      check.checked = selectedStops.has(record.key);
      check.disabled = completed.has(record.key);
      done.textContent = check.disabled ? '取消完成' : '標記完成';
    };
    done.addEventListener('click', () => {
      toggleComplete(record);
      updateLabel();
    });
    updateLabel();
    popup.append(label, done);
  }

  function options(kind, target, selected) {
    const choices = QuestFilters.categories(matching, kind);
    const keys = new Set(choices.map(([key]) => key));
    for (const key of selected) if (!keys.has(key)) selected.delete(key);
    const nodes = choices.map(([key, caption]) => {
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = selected.has(key);
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) selected.add(key);
        else selected.delete(key);
        refresh();
      });
      label.append(checkbox, document.createTextNode(caption));
      return label;
    });
    target.replaceChildren(...nodes);
  }

  function refreshData(fit) {
    matching = QuestFilters.matchingQuest(records);
    options('task', byId('tasks'), tasks);
    options('reward', byId('rewards'), rewards);
    refresh(fit);
  }

  search.addEventListener('input', () => {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(refresh, 150);
  });
  byId('clear').addEventListener('click', () => {
    search.value = '';
    tasks.clear();
    rewards.clear();
    document.querySelectorAll('#filters input[type=checkbox]').forEach(box => { box.checked = false; });
    refresh();
  });
  byId('fit').addEventListener('click', () => {
    map?.stopFollowing();
    center = null;
    report('');
    refresh(true);
  });
  completedToggle.addEventListener('change', () => refresh());
  byId('end-trip').addEventListener('click', () => {
    selectedStops.clear();
    tripOrigin = null;
    legStart = null;
    map?.closePopup();
    refreshTrip();
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
      map?.locateUser();
    } catch {
      byId('import-status').textContent = '任務快照無法載入，可手動匯入';
    }
  }
  loadSnapshot();
})();

