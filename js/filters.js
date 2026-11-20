const QuestFilters = (() => {
  function matchingQuest(records) {
    return records.filter(record =>
      record.task.raw === featuredQuest.task && record.reward.raw === featuredQuest.reward
    );
  }

  return { matchingQuest };
})();

