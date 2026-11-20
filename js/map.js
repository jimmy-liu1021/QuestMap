function createQuestMap(element, locate, report, onPosition, addActions) {
  if (!window.L?.map) {
    element.textContent = '地圖套件載入失敗。連上網路後請重新開啟頁面。';
    locate.disabled = true;
    return null;
  }

  const map = L.map(element, { zoomControl: false }).setView([23.7, 120.95], 7);
  if (window.ResizeObserver) {
    new ResizeObserver(() => map.invalidateSize({ debounceMoveend: true })).observe(element);
  }
  L.control.zoom({ position: 'bottomright' }).addTo(map);
  const tiles = L.tileLayer('https://wmts.nlsc.gov.tw/wmts/EMAP/default/GoogleMapsCompatible/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: '底圖 © <a href="https://maps.nlsc.gov.tw/">內政部國土測繪中心</a>'
  }).addTo(map);
  tiles.on('tileerror', () => report('部分底圖圖磚無法載入'));

  const markerLayer = L.layerGroup().addTo(map);
  const routeLine = L.polyline([], { color: '#2355b5', weight: 4, dashArray: '7 8', interactive: false }).addTo(map);
  const routeNumbers = L.layerGroup().addTo(map);
  const icon = L.divIcon({ className: 'quest-pin', iconSize: [24, 24], iconAnchor: [12, 12] });
  const doneIcon = L.divIcon({ className: 'quest-pin quest-pin-completed', iconSize: [24, 24], iconAnchor: [12, 12] });

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
    link.href = QuestRoute.navigationUrl(record);
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
  let centerNextFix = false;
  function stopFollowing() {
    watchGeneration++;
    if (watch !== null) navigator.geolocation.clearWatch(watch);
    watch = null;
    started = false;
    centerNextFix = false;
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
    watch = navigator.geolocation.watchPosition(({ coords }) => {
      if (!started || generation !== watchGeneration) return;
      const point = [coords.latitude, coords.longitude];
      if (position) position.setLatLng(point);
      else position = L.circleMarker(point, { radius: 8, className: 'current-location' }).addTo(map).bindTooltip('目前位置');
      onPosition(coords);
      if (centerNextFix) {
        centerNextFix = false;
        map.setView(point, Math.max(map.getZoom(), 15), { animate: false });
      } else if (!popupOpen) {
        map.panTo(point, { animate: false });
      }
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
  function recenter() {
    if (started && position) {
      map.setView(position.getLatLng(), Math.max(map.getZoom(), 15), { animate: false });
    } else {
      centerNextFix = true;
      locateUser();
    }
  }
  const currentLocation = L.control({ position: 'bottomright' });
  currentLocation.onAdd = () => {
    const control = L.DomUtil.create('div', 'leaflet-bar leaflet-location-control');
    const button = L.DomUtil.create('button', 'map-recenter', control);
    button.type = 'button';
    button.title = '回到目前位置';
    button.setAttribute('aria-label', '回到目前位置');
    const icon = L.DomUtil.create('span', 'map-recenter-icon', button);
    icon.setAttribute('aria-hidden', 'true');
    L.DomEvent.disableClickPropagation(control);
    button.addEventListener('click', recenter);
    return control;
  };
  currentLocation.addTo(map);
  window.addEventListener('pagehide', () => {
    resumeFollowing = started;
    stopFollowing();
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted && resumeFollowing) locateUser();
  });

  let renderId = 0;
  let rendered = [];
  const markers = new Map();
  function render(records, fit, completed) {
    if (fit && records.length) {
      const bounds = L.latLngBounds(records.map(record => [record.lat, record.lng]));
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16, animate: false });
    }
    if (rendered.length === records.length && rendered.every((record, index) => record === records[index])) {
      for (const [key, marker] of markers) {
        const newIcon = completed.has(key) ? doneIcon : icon;
        if (marker.options.icon !== newIcon) marker.setIcon(newIcon);
      }
      return;
    }
    rendered = records;
    const id = ++renderId;
    markerLayer.clearLayers();
    markers.clear();

    let offset = 0;
    function addBatch() {
      if (id !== renderId) return;
      const batch = records.slice(offset, offset + 300);
      for (const record of batch) {
        const marker = L.marker([record.lat, record.lng], {
          icon: completed.has(record.key) ? doneIcon : icon,
          title: record.name
        }).bindPopup(() => popup(record));
        markers.set(record.key, marker);
        marker.addTo(markerLayer);
      }
      offset += batch.length;
      if (offset < records.length) requestAnimationFrame(addBatch);
    }
    if (records.length) requestAnimationFrame(addBatch);
  }

  function showRoute(stops, origin, completed) {
    const points = stops.map(stop => [stop.lat, stop.lng]);
    if (origin) {
      const start = [origin.lat, origin.lng];
      points.unshift(start);
      points.push(start);
    }
    routeLine.setLatLngs(points);
    routeNumbers.clearLayers();
    stops.forEach((stop, index) => {
      const label = L.divIcon({
        className: completed.has(stop.key) ? 'route-stop-number route-stop-completed' : 'route-stop-number',
        html: String(index + 1),
        iconSize: [26, 26], iconAnchor: [4, 32]
      });
      L.marker([stop.lat, stop.lng], {
        icon: label, interactive: false, keyboard: false, zIndexOffset: 1000
      }).addTo(routeNumbers);
    });
    if (origin) {
      const label = L.divIcon({ className: 'route-start-label', html: '起點',
        iconSize: [35, 25], iconAnchor: [40, 32] });
      L.marker([origin.lat, origin.lng], {
        icon: label, interactive: false, keyboard: false, zIndexOffset: 1000
      }).addTo(routeNumbers);
    }
  }
  return { render, recenter, showRoute };
}

