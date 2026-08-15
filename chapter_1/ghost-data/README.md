# Chapter 1: Cache 與 DB 的一致性問題

## 主題
當 Web Server 同時操作 DB 和 Cache，在中間步驟發生故障時，資料會變成什麼狀態？

## 你會學到什麼
- Cache-Aside（Lazy Loading）讀取模式
- Write-Through 與 Write-Behind 的差異
- 幽靈數據（Ghost Data）：DB 和 Cache 不一致的成因
- TTL 作為安全網的原理
- 冪等性（Idempotency）：重複請求不應破壞資料

## 架構

```
Actor → Flask API → PostgreSQL (DB) → Redis (Cache)
```

所有情境共用同一組基礎元件：一個 Flask API Server、一個 PostgreSQL、一個 Redis。
透過 HTTP Header `X-Fail-At` 注入故障，模擬 Server 在不同步驟崩潰。

## 快速啟動

```bash
# 進入任一情境資料夾，例如 ghost-data
cd ghost-data

# 啟動服務
docker-compose up -d --build

# 等待 DB 初始化
sleep 5

# 驗證服務正常
curl http://localhost:5050/profile/user_001

# 執行自動化測試
pip install pytest requests
pytest tests/ -v

# 結束後關閉
docker-compose down
```

## API 清單

| Method | Path | 說明 |
|--------|------|------|
| `GET` | `/profile/<user_id>` | 讀取 Profile（先查 Cache，Miss 再查 DB） |
| `PUT` | `/profile/<user_id>` | 更新 Profile（寫 DB → 更新 Cache） |
| `GET` | `/debug/state/<user_id>` | 同時顯示 DB 和 Cache 的資料，比對一致性 |
| `POST` | `/debug/reset/<user_id>` | 重置用戶到初始狀態（方便反覆測試） |

## 故障注入方式

在 `PUT /profile` 的 Header 加上 `X-Fail-At`：

| Header 值 | 效果 | 產生的問題 |
|-----------|------|-----------|
| `after_db` | DB 寫入成功後、Cache 更新前崩潰 | 幽靈數據：DB 新、Cache 舊 |
| `after_cache` | Cache 更新成功後、回傳前崩潰 | 用戶收到 500 但資料其實已更新 |

## 情境進度

| 情境 | 資料夾 | 核心觀念 | SDET 測試重點 | 狀態 |
|------|--------|----------|---------------|------|
| 幽靈數據 | `ghost-data/` | Cache Inconsistency | DB 寫了但 Cache 沒更新，用戶讀到舊資料 | ⬜ |
| Cache-Aside | `cache-aside/` | Lazy Loading | Cache Miss → 查 DB → 回填 Cache 的流程 | ⬜ |
| 冪等性 | `idempotency/` | Idempotent Write | 同一請求發多次，結果跟一次一樣 | ⬜ |

## 各情境測試清單

### ghost-data（幽靈數據）
- [ ] 正常更新後 DB 和 Cache 一致
- [ ] 注入 `after_db` 故障後，DB 是新資料、Cache 是舊資料
- [ ] 幽靈數據狀態下，用戶 GET 讀到的是 Cache 的舊資料
- [ ] TTL 過期後，Cache 自動失效，下次讀取從 DB 拿到正確資料（自癒）

### cache-aside（Cache-Aside Pattern）
- [ ] Cache 沒資料時，GET 從 DB 讀取（`_source: database`）
- [ ] Cache Miss 後，資料自動回填到 Cache
- [ ] 第二次 GET 從 Cache 讀取（`_source: cache`）
- [ ] Cache 被手動刪除後，下次 GET 會重新從 DB 載入

### idempotency（冪等性）
- [ ] 同一筆 PUT 發兩次，最終狀態跟一次一樣
- [ ] 快速連發 10 次更新，資料不損壞，DB 和 Cache 一致
- [ ] 最終資料是最後一次更新的值

## 我從這章學到什麼
（做完後填寫）

## 延伸思考
（做完後記錄你想到的新問題，下次找 Claude 討論）
