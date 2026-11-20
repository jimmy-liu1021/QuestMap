const QuestRoute = (() => {
  const MAX_STOPS = 16;

  function distance(from, to) {
    const rad = Math.PI / 180;
    const h = Math.sin((to.lat - from.lat) * rad / 2) ** 2 +
      Math.cos(from.lat * rad) * Math.cos(to.lat * rad) *
      Math.sin((to.lng - from.lng) * rad / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(Math.min(1, h)));
  }

  function order(stops, start, finish = start) {
    const nodes = [...stops];
    const count = nodes.length;
    if (!count) return [];
    if (count > MAX_STOPS) throw new RangeError('Too many route stops');
    start ??= nodes[0];
    finish ??= start;
    const edge = nodes.map(from => nodes.map(to => distance(from, to)));
    const endCost = nodes.map(from => distance(from, finish));
    const masks = 1 << count;
    const cost = new Float64Array(masks * count);
    const next = new Int8Array(masks * count);

    // Each state is the cheapest path from one stop through the rest of the mask, then back to finish.
    for (let mask = 1; mask < masks; mask++) {
      for (let bits = mask; bits; bits &= bits - 1) {
        const bit = bits & -bits;
        const stop = 31 - Math.clz32(bit);
        const rest = mask ^ bit;
        const state = mask * count + stop;
        let best = endCost[stop];
        let choice = -1;
        if (rest) {
          best = Infinity;
          for (let remaining = rest; remaining; remaining &= remaining - 1) {
            const candidate = 31 - Math.clz32(remaining & -remaining);
            const km = edge[stop][candidate] + cost[rest * count + candidate];
            if (km < best) {
              best = km;
              choice = candidate;
            }
          }
        }
        cost[state] = best;
        next[state] = choice;
      }
    }
    let mask = masks - 1;
    let current = 0;
    let best = Infinity;
    nodes.forEach((stop, index) => {
      const km = distance(start, stop) + cost[mask * count + index];
      if (km < best) {
        best = km;
        current = index;
      }
    });
    const ordered = [];
    while (current >= 0) {
      ordered.push(nodes[current]);
      const following = next[mask * count + current];
      mask ^= 1 << current;
      current = following;
    }
    return ordered;
  }

  function directions(stops, start, finish) {
    const point = stop => stop.lat + ',' + stop.lng;
    const destinations = [...stops];
    if (finish) destinations.push(finish);
    if (start && destinations.length && point(start) === point(destinations[0])) destinations.shift();
    const links = [];
    for (let offset = 0; offset < destinations.length; offset += 4) {
      const segment = destinations.slice(offset, offset + 4);
      const params = new URLSearchParams({
        api: '1', travelmode: 'walking', destination: point(segment.at(-1))
      });
      const origin = offset ? destinations[offset - 1] : start;
      if (origin) params.set('origin', point(origin));
      if (segment.length > 1) params.set('waypoints', segment.slice(0, -1).map(point).join('|'));
      links.push('https://www.google.com/maps/dir/?' + params);
    }
    return links;
  }
  return { order, directions, MAX_STOPS };
})();
