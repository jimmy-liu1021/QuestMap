const QuestRoute = (() => {
  function distance(from, to) {
    const rad = Math.PI / 180;
    const h = Math.sin((to.lat - from.lat) * rad / 2) ** 2 +
      Math.cos(from.lat * rad) * Math.cos(to.lat * rad) *
      Math.sin((to.lng - from.lng) * rad / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(Math.min(1, h)));
  }

  function order(stops, position) {
    const pending = [...stops];
    const ordered = [];
    let last = position || pending.shift();
    if (!position && last) ordered.push(last);
    while (pending.length) {
      let nearest = 0;
      let best = Infinity;
      pending.forEach((stop, index) => {
        const km = distance(last, stop);
        if (km < best) {
          nearest = index;
          best = km;
        }
      });
      [last] = pending.splice(nearest, 1);
      ordered.push(last);
    }
    return ordered;
  }

  function directions(stops) {
    const point = stop => stop.lat + ',' + stop.lng;
    const links = [];
    for (let offset = 0; offset < stops.length; offset += 4) {
      const segment = stops.slice(offset, offset + 4);
      const params = new URLSearchParams({
        api: '1', travelmode: 'walking', destination: point(segment.at(-1))
      });
      if (offset) params.set('origin', point(stops[offset - 1]));
      if (segment.length > 1) params.set('waypoints', segment.slice(0, -1).map(point).join('|'));
      links.push('https://www.google.com/maps/dir/?' + params);
    }
    return links;
  }
  return { order, directions };
})();
