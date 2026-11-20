const featuredQuest = {
  task: '16^1^8^0^^^^^Excellent',
  reward: '4^890^^25^N^^^N',
};

const QuestParser = (() => {
  const mappings = {
    task: new Map([[featuredQuest.task, '投出1次Excellent']]),
    reward: new Map([[featuredQuest.reward, '獲得糖果25顆(無極汰那)']]),
  };
  const taipei = new Intl.DateTimeFormat('zh-TW', {
    timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'
  });

  function parseDate(seconds) {
    if (!Number.isSafeInteger(seconds) || seconds < 0 || seconds > 8640000000000) return '';
    const fields = Object.fromEntries(taipei.formatToParts(seconds * 1000).map(part => [part.type, part.value]));
    return fields.year + '/' + fields.month + '/' + fields.day + ' ' +
      fields.hour + ':' + fields.minute + ':' + fields.second;
  }

  function parseCode(value, kind) {
    const raw = typeof value === 'string' ? value : '';
    const parts = raw.split('^');
    const known = mappings[kind].get(raw);
    return { raw, parts, label: known || raw || '未提供' };
  }

  function coordinate(value, limit) {
    if (typeof value !== 'number' && (typeof value !== 'string' || !value.trim())) return NaN;
    const number = Number(value);
    return Math.abs(number) <= limit ? number : NaN;
  }

  function parse(document) {
    if (!Array.isArray(document?.fp)) throw new Error('JSON 必須包含 fp 陣列');
    const records = [];
    let invalid = 0;
    for (const item of document.fp) {
      const lat = coordinate(item?.c, 90);
      const lng = coordinate(item?.d, 180);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
        invalid++;
        continue;
      }
      const id = typeof item.a === 'string' ? item.a.trim() : '';
      const name = typeof item.b === 'string' ? item.b.trim() : '';
      const seconds = coordinate(item.g, 8640000000000);
      const timestamp = Number.isSafeInteger(seconds) && seconds >= 0 ? seconds : null;
      records.push({
        key: id ? 'id:' + id : JSON.stringify([lat, lng, name]),
        name: name || '未命名補給站', lat, lng, timestamp,
        task: parseCode(item.e, 'task'), reward: parseCode(item.f, 'reward'),
      });
    }
    return { records, invalid };
  }

  function merge(existing, incoming) {
    const records = new Map(existing.map(record => [record.key, record]));
    let duplicates = 0;
    for (const record of incoming) {
      const previous = records.get(record.key);
      if (previous) duplicates++;
      if (!previous || (record.timestamp ?? -1) >= (previous.timestamp ?? -1)) {
        records.set(record.key, record);
      }
    }
    return { records: [...records.values()], duplicates };
  }

  return { parse, merge, parseDate };
})();

