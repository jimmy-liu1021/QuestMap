const QuestFilters = (() => {
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

  return { matchingQuest, nearby };
})();

