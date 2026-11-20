
import gzip
import json

# 讀取 GZIP 壓縮資料
with gzip.open("response.bin", "rt", encoding="utf-8-sig") as f:
    data = json.load(f)

# 輸出成容易閱讀的 JSON
with open("quests.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("解壓縮成功！")
print("頂層欄位：", list(data.keys()))
print("前 2 筆資料：")
print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])
