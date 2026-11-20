function createQuestMap(element, locate, report, onPosition, addActions) {
  if (!window.L?.markerClusterGroup) {
    element.textContent = '地圖套件載入失敗。連上網路後請重新開啟頁面。';
    locate.disabled = true;
    return null;
  }

  const map = L.map(element, { zoomControl: false }).setView([23.7, 120.95], 7);
  if (window.ResizeObserver) {
    new ResizeObserver(() => map.invalidateSize({ pan: false })).observe(element);
  }
  L.control.zoom({ position: 'bottomright' }).addTo(map);
  const tiles = L.tileLayer('https://wmts.nlsc.gov.tw/wmts/EMAP/default/GoogleMapsCompatible/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: '底圖 © <a href="https://maps.nlsc.gov.tw/">內政部國土測繪中心</a>'
  }).addTo(map);
  tiles.on('tileerror', () => report('部分底圖圖磚無法載入'));

  const cluster = L.markerClusterGroup({ removeOutsideVisibleBounds: true });
  cluster.addTo(map);
  const routeLine = L.polyline([], { color: '#2355b5', weight: 4, dashArray: '7 8', interactive: false }).addTo(map);
  const icon = L.divIcon({ className: 'quest-pin', iconSize: [24, 24], iconAnchor: [12, 12] });

  function popup(record) {
    const content = document.createElement('section');
    const title = document.createElement('h2');
    title.textContent = record.name;
    content.append(title);
    for (const [caption, value] of [
      ['任務', record.task.label],
      ['獎勵', record.reward.label],
      ['更新時間（台灣）', record.timestamp === null ? '未提供' : QuestParser.parseDate(record.timestamp)],
    ]) {
      const row = document.createElement('p');
      const label = document.createElement('strong');
      label.textContent = caption;
      row.append(label, document.createTextNode(value));
      content.append(row);
    }
    const link = document.createElement('a');
    link.className = 'directions';
    link.href = 'https://www.google.com/maps/dir/?api=1&destination=' + record.lat + ',' + record.lng;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = 'Google Maps 導航';
    content.append(link);
    addActions(content, record);
    return content;
  }

  let position;
  let popupOpen = false;
  map.on('popupopen', () => { popupOpen = true; });
  map.on('popupclose', () => { popupOpen = false; });
  let watch = null;
  let started = false;
  let watchGeneration = 0;
  let resumeFollowing = false;
  function stopFollowing() {
    watchGeneration++;
    if (watch !== null) navigator.geolocation.clearWatch(watch);
    watch = null;
    started = false;
    locate.textContent = '跟隨定位';
    locate.setAttribute('aria-pressed', 'false');
  }
  function locateUser() {
    if (started) return;
    if (!navigator.geolocation) {
      report('瀏覽器無法使用定位');
      return;
    }
    started = true;
    const generation = ++watchGeneration;
    locate.textContent = '停止跟隨';
    locate.setAttribute('aria-pressed', 'true');
    report('正在定位…');
    let first = true;
    watch = navigator.geolocation.watchPosition(({ coords }) => {
      if (!started || generation !== watchGeneration) return;
      const point = [coords.latitude, coords.longitude];
      if (position) position.setLatLng(point);
      else position = L.circleMarker(point, { radius: 8, className: 'current-location' }).addTo(map).bindTooltip('目前位置');
      onPosition(coords, first);
      if (!first && !popupOpen) map.panTo(point, { animate: false });
      first = false;
      report('');
    }, error => {
      if (!started || generation !== watchGeneration) return;
      if (error.code === 1) stopFollowing();
      report(error.code === 1 ? '定位權限未開啟，請確認 Safari 設定與 HTTPS' : '目前無法取得位置');
    }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 12000 });
  }
  locate.addEventListener('click', () => {
    if (started) stopFollowing();
    else locateUser();
  });
  window.addEventListener('pagehide', () => {
    resumeFollowing = started;
    stopFollowing();
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted && resumeFollowing) locateUser();
  });

  let renderId = 0;
  let rendered = [];
  function render(records, fit, center) {
    if (fit && (records.length || center)) {
      const bounds = L.latLngBounds(records.map(record => [record.lat, record.lng]));
      if (center) bounds.extend([center.latitude, center.longitude]);
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16, animate: false });
    }
    if (rendered.length === records.length && rendered.every((record, index) => record === records[index])) return;
    rendered = records;
    const id = ++renderId;
    cluster.clearLayers();

    let offset = 0;
    function addBatch() {
      if (id !== renderId) return;
      const batch = records.slice(offset, offset + 300).map(record =>
        L.marker([record.lat, record.lng], { icon, title: record.name })
          .bindPopup(() => popup(record))
      );
      cluster.addLayers(batch);
      offset += batch.length;
      if (offset < records.length) requestAnimationFrame(addBatch);
    }
    if (records.length) requestAnimationFrame(addBatch);
  }

  function showRoute(stops, origin) {
    const points = stops.map(stop => [stop.lat, stop.lng]);
    if (points.length && origin) points.unshift([origin.lat, origin.lng]);
    routeLine.setLatLngs(points);
  }
  return { render, locateUser, stopFollowing, showRoute };
}

