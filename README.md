# SDET System Design Lab 🧪

> 每一章 Alex Xu 的 System Design，都有一個對應的 Lab 讓你親手把系統弄壞，再親手驗證它怎麼修復。

## 為什麼做這個？

讀 System Design 很容易「覺得自己懂了」，但面試時被追問就卡住。
這個 Lab 讓你在本機跑起真實的分散式元件（DB、Cache、Queue、S3），
用 **故障注入 + 自動化測試** 驗證每個章節的核心觀念。

身為 SDET，我們不只讀架構，我們要能回答：
- 這個系統**最容易壞在哪裡**？
- 壞了之後**資料會變成什麼狀態**？
- 我要怎麼**用測試證明它壞了**？
- 系統靠什麼機制**自我修復**？

## 環境需求

- Docker & Docker Compose（跑被測系統）
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（依賴與虛擬環境管理）

安裝測試依賴：在 repo 根目錄執行 `uv sync`，會依 `uv.lock` 還原一模一樣的環境。

## 目錄結構

```
SDET-LAB/
├── README.md                              ← 你正在看的這份
├── pyproject.toml                         ← 測試框架的依賴宣告
├── uv.lock                                ← 鎖定精確版本，uv sync 一鍵重現
├── pytest.ini                             ← pytest 設定（allure 輸出）
│
├── api/                                   ← ★ 可重用的 API 測試框架（跨章節共用）
│   ├── base_api.py                        ← HTTP 封裝（GET/POST/PUT + allure step）
│   ├── api_validator.py                   ← 鏈式斷言（status/field should_be）
│   └── collections/                       ← 各 endpoint 的封裝（類 Page Object）
│       └── profile.py
├── conf/                                  ← 共用設定
│   └── log.py                             ← allure 整合的 logger
│
├── chapter_1/                             ← 你學的第一個主題
│   ├── README.md                          ← 章節總覽 + 啟動方式 + 情境進度
│   └── ghost-data/                        ← 情境：幽靈數據
│       ├── docker-compose.yml             ← Flask + PostgreSQL + Redis
│       ├── Dockerfile
│       ├── app.py                         ← 被測系統（含 X-Fail-At 故障注入）
│       ├── requirements.txt               ← 被測系統自己的依賴（Docker 內用）
│       └── testcase/
│           ├── conftest.py                ← fixtures（api、reset）
│           └── test_profile_chaos.py      ← 自動化測試
│
├── chapter_2/                             ← （尚未建立）
└── ...
```

> `api/` 和 `conf/` 是**跨章節共用**的測試框架,住在 repo 根目錄;每個 `chapter_N/<scenario>/` 只放被測系統 + 該情境的測試。

## 命名規則

- **Chapter 資料夾**：`chapter_N`（小寫），按你的學習順序編號，不綁定書的章節號
- **情境資料夾**：用簡短的英文描述命名，例如 `ghost-data`、`token-bucket`、`sync-conflict`
- 一看資料夾名稱就知道在練什麼，不用打開檔案才知道

## 每個情境的標準結構

```
chapter_N/<scenario-name>/
├── docker-compose.yml         ← 一鍵啟動所有元件
├── Dockerfile                 ← 被測系統 image（如需要）
├── app.py                     ← 被測系統主程式（含故障注入點）
├── requirements.txt           ← 被測系統的 Python 依賴（Docker 內用）
└── testcase/
    ├── conftest.py            ← 該情境的 fixtures
    └── test_<scenario>.py     ← 自動化測試（用根目錄的 api/ 框架）
```

測試依賴統一由根目錄的 `pyproject.toml` 管理,不寫在各情境裡。

## 學習進度

| Chapter | 主題 | 情境 | 完成 |
|---------|------|------|------|
| 1 | Cache & DB 一致性 | `ghost-data` `cache-aside` `idempotency` | 🚧 |
| 2 | Rate Limiter | `token-bucket` `sliding-window` `distributed-rate-limit` | ⬜ |
| 3 | URL Shortener | `hash-collision` `redirect-301-vs-302` `expired-url-cleanup` | ⬜ |
| 4 | Consistent Hashing | `virtual-nodes` `rebalancing` `hotspot` | ⬜ |
| 5 | Key-Value Store | `replication` `quorum-read-write` `read-repair` | ⬜ |
| 6 | Unique ID Generator | `snowflake` `clock-skew` | ⬜ |
| 7 | Notification System | `queue-retry` `duplicate-delivery` `priority-queue` | ⬜ |
| 8 | News Feed System | `fanout-on-write` `fanout-on-read` | ⬜ |
| 9 | Chat System | `websocket-reconnect` `message-ordering` `presence` | ⬜ |
| 10 | Autocomplete | `trie-search` `top-k` | ⬜ |
| 11 | YouTube | `upload-interrupt` `transcode-failure` `cdn-invalidation` | ⬜ |
| 12 | Google Drive | `sync-conflict` `chunked-upload` `version-control` | ⬜ |

> 情境數量是初估，每章讀完後自行調整

## 快速開始

```bash
# 1. 還原測試環境（依 uv.lock，一模一樣）
uv sync

# 2. 啟動某個情境的被測系統
cd chapter_1/ghost-data
docker-compose up -d --build
cd ../..

# 3. 從 repo 根目錄跑測試（測試會 import 根目錄的 api/ 框架）
uv run pytest -v

# 4. 結束後關閉被測系統
cd chapter_1/ghost-data && docker-compose down
```

> 測試一定要**從 repo 根目錄**跑,因為 `test_*.py` 會 `from api... import`,根目錄要在 import path 上。

## 怎麼用這個 Lab

1. **讀完一章 Alex Xu** → 理解架構和設計決策
2. **做對應的 Chapter Lab** → 親手把系統弄壞，建立肌肉記憶
3. **寫測試** → 用 pytest 自動化驗證故障場景
4. **填寫 Chapter README 的心得** → 練習面試口述
---
Built by a SDET who believes **breaking systems is the best way to understand them**.
