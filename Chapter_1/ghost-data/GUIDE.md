# Chapter 1 學習指南：從黑箱到白箱

> 給沒有後端背景的 SDET，一步一步拆開這個系統

## 你的起點

你會 API 測試（打 endpoint、驗 response），但不知道 Server 背後在幹嘛。
這份指南會帶你從「看懂 app.py 每一行」開始，最後能自己寫故障測試。

預計時間：2-3 個週末，每次 2-3 小時

---

## Week 1：看懂這個系統（理解架構）

### Step 1：先不看 code，用 curl 把系統當黑箱打

你已經會 API 測試了，先用你熟悉的方式跟這個系統互動。

```bash
# 啟動系統
cd Chapter_1/ghost-data
docker-compose up -d --build
sleep 5

# 1. 讀取用戶資料（你平常做的 API 測試）
curl http://localhost:5000/profile/user_001 | python -m json.tool

# 2. 更新用戶資料
curl -X PUT http://localhost:5000/profile/user_001 \
  -H "Content-Type: application/json" \
  -d '{"bio": "我的第一次更新"}' | python -m json.tool

# 3. 再讀一次，確認更新成功
curl http://localhost:5000/profile/user_001 | python -m json.tool
```

做完之後問自己：
- response 裡的 `_source` 欄位，第一次是什麼？第二次是什麼？為什麼不同？
- 把答案寫在筆記裡

### Step 2：用 debug API 偷看系統內部

```bash
# 這個 API 會同時顯示 DB 和 Redis 裡的資料
curl http://localhost:5000/debug/state/user_001 | python -m json.tool
```

你會看到類似這樣的東西：
```json
{
  "database": { "bio": "我的第一次更新", ... },
  "cache": { "bio": "我的第一次更新", ... },
  "is_consistent": true,
  "inconsistencies": []
}
```

這就是從黑箱變白箱的第一步——你現在能同時看到 DB 和 Cache 的內容了。

### Step 3：製造第一個 Bug

```bash
# 重置到初始狀態
curl -X POST http://localhost:5000/debug/reset/user_001

# 先正常更新一次，讓 Cache 有「舊資料」
curl -X PUT http://localhost:5000/profile/user_001 \
  -H "Content-Type: application/json" \
  -d '{"bio": "舊的 Bio"}'

# 注入故障：Server 在寫完 DB 後崩潰！
curl -X PUT http://localhost:5000/profile/user_001 \
  -H "Content-Type: application/json" \
  -H "X-Fail-At: after_db" \
  -d '{"bio": "新的 Bio（但 Cache 不知道）"}'

# 看看系統現在的狀態
curl http://localhost:5000/debug/state/user_001 | python -m json.tool
```

你會看到：
```json
{
  "database": { "bio": "新的 Bio（但 Cache 不知道）" },
  "cache": { "bio": "舊的 Bio" },
  "is_consistent": false,
  "inconsistencies": [
    { "field": "bio", "db_value": "新的 Bio（但 Cache 不知道）", "cache_value": "舊的 Bio" }
  ]
}
```

恭喜，你親手製造了「幽靈數據」。DB 已經更新了，但 Cache 還是舊的。

現在試試：
```bash
# 模擬用戶重新整理頁面
curl http://localhost:5000/profile/user_001 | python -m json.tool
```

用戶拿到的是 Cache 裡的「舊的 Bio」，看不到已經更新的內容。
這就是分散式系統最經典的 Bug 之一。

### Step 4：讀懂 app.py（把黑箱打開）

現在你已經親手操作過了，回去讀 code 會容易很多。
打開 `app.py`，你只需要看懂四個部分：

**Part A：資料庫連線（第 26-35 行）**
```python
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://...")
REDIS_URL = os.environ.get("REDIS_URL", "redis://...")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
```
就是告訴 Python 要連到哪個 DB 和哪個 Redis，跟你在 Postman 裡設定 base URL 一樣。

**Part B：GET /profile（第 68-96 行）**
```
用戶發 GET → 先查 Redis 有沒有 → 有就直接回 → 沒有就查 DB → 查到後寫回 Redis → 回給用戶
```
這就是 Cache-Aside Pattern，你不需要背這個名詞，只需要理解「先查快的（Redis），沒有再查慢的（DB）」。

**Part C：PUT /profile（第 99-155 行）**
```
用戶發 PUT → 寫入 DB → [故障注入點] → 更新 Redis → 回給用戶
```
中間的 `if fail_at == "after_db"` 就是故障注入的開關。
你剛才用 `X-Fail-At: after_db` Header 就是觸發了這個 if 條件。

**Part D：debug/state（第 158-189 行）**
```
同時讀 DB 和 Redis → 比對兩邊的值 → 回報一不一致
```
這就是你剛才用來「偷看」系統內部的透視鏡。

讀完之後，你應該能回答：
- 為什麼第一次 GET 的 `_source` 是 `database`？
- 為什麼第二次 GET 的 `_source` 是 `cache`？
- `X-Fail-At: after_db` 到底做了什麼？

---

## Week 2：把手動測試轉成自動化（寫測試）

### Step 5：先用自然語言寫 Test Case

在寫 code 之前，先用 Given-When-Then 把你 Week 1 做的事情寫下來。
你已經很會這個了，就是你在 XMind 裡做的事。

```
Test Case 1: 正常更新後 DB 和 Cache 一致
  Given 用戶 user_001 已重置到初始狀態
  When  發送 PUT /profile/user_001 {"bio": "新的 Bio"}
  Then  GET /debug/state/user_001 的 is_consistent 應為 true
  And   database.bio 和 cache.bio 都應為 "新的 Bio"

Test Case 2: 幽靈數據 — DB 寫了但 Cache 沒更新
  Given 用戶 user_001 已重置到初始狀態
  And   已正常更新 bio 為 "舊的"
  When  發送 PUT /profile/user_001 {"bio": "新的"}，Header X-Fail-At: after_db
  Then  response status 應為 500
  And   GET /debug/state/user_001 的 is_consistent 應為 false
  And   database.bio 應為 "新的"
  And   cache.bio 應為 "舊的"

Test Case 3: 幽靈數據下用戶讀到舊資料
  Given 已製造幽靈數據（同 Test Case 2）
  When  發送 GET /profile/user_001
  Then  response 的 _source 應為 "cache"
  And   bio 應為 "舊的"（不是 DB 裡的 "新的"）
```

### Step 6：把 Given-When-Then 翻譯成 pytest

每一行 Given-When-Then 都直接對應一行 Python。
你已經會用 requests 打 API 了，這跟你寫 Playwright 測試的邏輯完全一樣。

```python
import requests

BASE_URL = "http://localhost:5000"

def test_ghost_data():
    # Given: 重置用戶
    requests.post(f"{BASE_URL}/debug/reset/user_001")

    # Given: 先正常更新，讓 Cache 有「舊資料」
    requests.put(
        f"{BASE_URL}/profile/user_001",
        json={"bio": "舊的"}
    )

    # When: 注入故障
    resp = requests.put(
        f"{BASE_URL}/profile/user_001",
        json={"bio": "新的"},
        headers={"X-Fail-At": "after_db"}
    )

    # Then: Server 回 500
    assert resp.status_code == 500

    # Then: 驗證不一致
    state = requests.get(f"{BASE_URL}/debug/state/user_001").json()
    assert state["is_consistent"] == False
    assert state["database"]["bio"] == "新的"
    assert state["cache"]["bio"] == "舊的"
```

看到了嗎？每一個 assert 都對應你 Given-When-Then 裡的一行 Then。
跟你寫 Playwright 的 `expect(page.locator(...)).toHaveText(...)` 是完全同樣的概念，
只是從驗證 UI 元素變成驗證系統狀態。

### Step 7：自己寫一個新的 Test Case

試著自己寫這個場景（不要看現有的測試檔）：

```
Test Case: 重置後 Cache 應該被清空
  Given 用戶 user_001 有 Cache 資料
  When  發送 POST /debug/reset/user_001
  And   發送 GET /profile/user_001
  Then  response 的 _source 應為 "database"（因為 Cache 被清了）
```

把它翻譯成 pytest，加到 `tests/` 資料夾裡，跑 `pytest tests/ -v` 確認通過。
如果你能自己完成這個，代表你已經掌握了「手動驗證 → 自動化測試」的轉換能力。

---

## Week 3：深入理解 + 挑戰自己（模擬更多錯誤）

### Step 8：直接操作 Redis，建立底層理解

```bash
# 進入 Redis 容器
docker exec -it ghost-data-redis-1 redis-cli

# 查看所有 key
KEYS *

# 讀取用戶的 Cache 資料
GET profile:user_001

# 手動刪除 Cache（模擬 Cache 過期）
DEL profile:user_001

# 查看某個 key 的 TTL（剩餘存活時間）
TTL profile:user_001
```

做完之後，回到瀏覽器或 curl 打 `GET /profile/user_001`，
你會發現 `_source` 變成 `database` 了，因為 Cache 被你清掉了。
這就是 Cache-Aside Pattern 的自癒機制。

### Step 9：直接操作 PostgreSQL，理解 DB 層

```bash
# 進入 DB 容器
docker exec -it ghost-data-db-1 psql -U sdet -d sdet_lab

# 查看所有用戶資料
SELECT * FROM users;

# 手動修改 DB（模擬「有人直接改 DB」的情境）
UPDATE users SET bio = '被直接改的 Bio' WHERE user_id = 'user_001';

# 退出
\q
```

改完 DB 之後，打 `GET /profile/user_001`，
你會發現拿到的還是 Cache 裡的舊資料（如果 Cache 還沒過期）。
再打 `GET /debug/state/user_001`，你會看到不一致。

這就是為什麼「直接改 DB 而不清 Cache」是危險的——
你在工作中可能也遇過開發者直接進 DB 改資料然後前端沒更新的狀況，原因就在這裡。

### Step 10：自己設計一個故障場景

你已經學會了基本套路：
1. 搞清楚系統的正常流程
2. 在某個步驟製造故障
3. 觀察故障後的系統狀態
4. 寫測試驗證

試著自己設計一個新場景。例如：

- 如果兩個用戶同時更新同一筆 Profile，會發生什麼？
- 如果 Redis 容器直接被 kill 掉，API 會回什麼？
- 如果在 PUT 的過程中 DB 容器掛了，會怎樣？

```bash
# 殺掉 Redis（模擬 Cache 層整個掛掉）
docker stop ghost-data-redis-1

# 試試看 GET /profile/user_001 會怎樣
curl http://localhost:5000/profile/user_001

# 試試看 PUT 會怎樣
curl -X PUT http://localhost:5000/profile/user_001 \
  -H "Content-Type: application/json" \
  -d '{"bio": "Redis 掛了的時候更新"}'

# 把 Redis 救回來
docker start ghost-data-redis-1
```

觀察到什麼行為？API 是直接 500 還是 graceful degradation？
把你的觀察寫成 test case，加到測試裡。

---

## 你的檢查清單

完成 Week 1 後你應該能回答：
- [ ] Cache-Aside Pattern 的讀取流程是什麼？
- [ ] 什麼是幽靈數據？怎麼產生的？
- [ ] `X-Fail-At: after_db` 在 code 裡做了什麼？

完成 Week 2 後你應該能回答：
- [ ] 怎麼用 requests + pytest 測試 API 的行為？
- [ ] 怎麼用 /debug/state 驗證 DB 和 Cache 的一致性？
- [ ] 我能自己把 Given-When-Then 翻譯成 pytest code

完成 Week 3 後你應該能回答：
- [ ] 怎麼直接操作 Redis 和 PostgreSQL？
- [ ] Cache 被清除後系統怎麼自癒？
- [ ] 我能自己設計新的故障場景並寫出對應的測試

---

## 做完這章之後

回到 Chapter_1/README.md，填寫「我從這章學到什麼」和「延伸思考」。
然後帶著你的問題去找 Claude，開始 Chapter_2。
