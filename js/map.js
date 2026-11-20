function createQuestMap(element, locate, report, onPosition) {
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
    return content;
  }

  let position;
  function locateUser() {
    if (locate.disabled) return;
    if (!navigator.geolocation) {
      report('瀏覽器無法使用定位');
      return;
    }
    locate.disabled = true;
    report('正在定位…');
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      locate.disabled = false;
      const point = [coords.latitude, coords.longitude];
      position?.remove();
      position = L.circleMarker(point, { radius: 8 }).addTo(map).bindTooltip('目前位置');
      report('顯示目前位置 5 公里內的任務');
      onPosition(coords);
    }, error => {
      locate.disabled = false;
      report(error.code === 1 ? '定位權限未開啟，請確認 Safari 設定與 HTTPS' : '目前無法取得位置');
    }, { timeout: 12000 });
  }
  locate.addEventListener('click', locateUser);

  let renderId = 0;
  function render(records, fit, center) {
    const id = ++renderId;
    cluster.clearLayers();
    if (fit && (records.length || center)) {
      const bounds = L.latLngBounds(records.map(record => [record.lat, record.lng]));
      if (center) bounds.extend([center.latitude, center.longitude]);
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16, animate: false });
    }

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

  return { render, locateUser };
}

