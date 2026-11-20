const QuestFilters = (() => {
  function categories(records, kind) {
    const options = new Map(records.map(record => [record[kind].key, record[kind].category]));
    return [...options].sort((left, right) => left[1].localeCompare(right[1], 'zh-TW', { numeric: true }));
  }

  function apply(records, search, tasks, rewards) {
    const query = search.trim().normalize('NFKC').toLowerCase();
    return records.filter(record =>
      (!query || record.name.normalize('NFKC').toLowerCase().includes(query)) &&
      (!tasks.size || tasks.has(record.task.key)) &&
      (!rewards.size || rewards.has(record.reward.key))
    );
  }

  function matchingQuest(records) {
    return records.filter(record =>
      record.task.raw === featuredQuest.task && record.reward.raw === featuredQuest.reward
    );
  }

  function nearby(records, { latitude, longitude }, radiusKm) {
    const radians = Math.PI / 180;
    const limit = Math.sin(radiusKm / (2 * 6371)) ** 2;
    return records.filter(({ lat, lng }) =>
      Math.sin((lat - latitude) * radians / 2) ** 2 +
      Math.cos(latitude * radians) * Math.cos(lat * radians) *
      Math.sin((lng - longitude) * radians / 2) ** 2 <= limit
    );
  }

  return { categories, apply, matchingQuest, nearby };
})();

