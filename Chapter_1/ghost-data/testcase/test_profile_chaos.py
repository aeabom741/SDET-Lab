"""
SDET System Design Lab — 自動化測試
====================================
這組測試驗證「更新 Profile」流程在各種故障場景下的系統行為。

使用方式:
  1. 先啟動服務:docker-compose up -d
  2. 等待幾秒讓 DB 初始化
  3. 執行測試:pytest tests/ -v

測試場景對照 System Design 觀念:
  - test_happy_path            → 正常流程，驗證 DB + Cache 一致性
  - test_ghost_data            → 幽靈數據:DB 寫了但 Cache 沒更新
  - test_cache_aside_pattern   → Cache-Aside 讀取模式驗證
  - test_cache_ttl_safety_net  → TTL 安全網:Cache 過期後自動修復
  - test_idempotency           → 冪等性:重複更新不應產生異常
"""

import time

import pytest
import requests

BASE_URL = "http://localhost:5000"
TEST_USER = "user_001"


@pytest.fixture(autouse=True)
def reset_state():
    """每個測試前重置用戶資料到初始狀態"""
    requests.post(f"{BASE_URL}/debug/reset/{TEST_USER}")
    yield


# ============================================================
# 場景 1:Happy Path — 正常更新，驗證 DB + Cache 一致
# ============================================================

class TestHappyPath:
    """
    對應 System Design 觀念:Write-Through Cache
    正常情況下，DB 和 Cache 應該同時被更新，資料一致。
    """

    def test_update_profile_success(self):
        """PUT /profile 應回傳 200 且資料正確"""
        resp = requests.put(
            f"{BASE_URL}/profile/{TEST_USER}",
            json={"bio": "新的自我介紹", "avatar_url": "https://new-avatar.jpg"},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["bio"] == "新的自我介紹"
        assert data["avatar_url"] == "https://new-avatar.jpg"

    def test_db_and_cache_consistent_after_update(self):
        """更新後，DB 和 Cache 的資料應該完全一致"""
        # 執行更新
        requests.put(
            f"{BASE_URL}/profile/{TEST_USER}",
            json={"bio": "一致性測試", "avatar_url": "https://consistent.jpg"},
        )

        # 用 debug API 檢查一致性
        state = requests.get(f"{BASE_URL}/debug/state/{TEST_USER}").json()

        assert state["is_consistent"] is True
        assert len(state["inconsistencies"]) == 0
        assert state["database"]["bio"] == "一致性測試"
        assert state["cache"]["bio"] == "一致性測試"

    def test_get_profile_returns_from_cache(self):
        """更新後，GET 應該從 Cache 讀取（驗證 _source 欄位）"""
        # 先更新，讓 Cache 有資料
        requests.put(
            f"{BASE_URL}/profile/{TEST_USER}",
            json={"bio": "快取測試"},
        )

        # 讀取 — 應該 hit Cache
        resp = requests.get(f"{BASE_URL}/profile/{TEST_USER}")
        assert resp.json()["_source"] == "cache"


# ============================================================
# 場景 2:幽靈數據 — DB 寫了但 Cache 沒更新
# ============================================================

class TestGhostData:
    """
    對應 System Design 觀念:Cache Inconsistency
    當 Server 在寫完 DB 後、更新 Cache 前崩潰，
    就會產生「幽靈數據」— DB 是新的，Cache 是舊的。
    """

    def test_crash_after_db_creates_inconsistency(self):
        """
        注入故障:Server 在 DB 寫入後崩潰
        預期:DB 有新資料，Cache 還是舊資料
        """
        # 先做一次正常更新，讓 Cache 有「舊資料」
        requests.put(
            f"{BASE_URL}/profile/{TEST_USER}",
            json={"bio": "舊的 Bio"},
        )

        # 注入故障:在 DB 寫入後崩潰
        resp = requests.put(
            f"{BASE_URL}/profile/{TEST_USER}",
            json={"bio": "新的 Bio（幽靈）"},
            headers={"X-Fail-At": "after_db"},
        )

        # Server 回傳 500
        assert resp.status_code == 500

        # 驗證幽靈數據:DB 和 Cache 不一致！
        state = requests.get(f"{BASE_URL}/debug/state/{TEST_USER}").json()

        assert state["is_consistent"] is False
        assert state["database"]["bio"] == "新的 Bio（幽靈）"  # DB 是新的
        assert state["cache"]["bio"] == "舊的 Bio"  # Cache 還是舊的！

    def test_user_reads_stale_data_after_crash(self):
        """
        幽靈數據的用戶影響:
        用戶重新整理頁面，會讀到 Cache 裡的舊資料
        """
        # 建立舊的 Cache
        requests.put(
            f"{BASE_URL}/profile/{TEST_USER}",
            json={"bio": "舊資料"},
        )

        # 注入故障
        requests.put(
            f"{BASE_URL}/profile/{TEST_USER}",
            json={"bio": "用戶看不到的新資料"},
            headers={"X-Fail-At": "after_db"},
        )

        # 用戶讀取 — 會拿到舊的 Cache 資料
        profile = requests.get(f"{BASE_URL}/profile/{TEST_USER}").json()
        assert profile["_source"] == "cache"
        assert profile["bio"] == "舊資料"  # 用戶看到的是舊的！


# ============================================================
# 場景 3:Cache-Aside Pattern — Cache Miss 時自動從 DB 載入
# ============================================================

class TestCacheAsidePattern:
    """
    對應 System Design 觀念:Cache-Aside (Lazy Loading)
    當 Cache 中沒有資料時，系統應該從 DB 讀取並回填 Cache。
    """

    def test_cache_miss_falls_back_to_db(self):
        """Cache 沒資料時，應從 DB 讀取"""
        # 確保 Cache 是空的（reset 已清除）
        # 直接讀取 — 應該 Cache Miss，從 DB 拿
        resp = requests.get(f"{BASE_URL}/profile/{TEST_USER}")
        data = resp.json()

        assert data["_source"] == "database"
        assert data["bio"] == "原始的 Bio"

    def test_cache_miss_backfills_cache(self):
        """Cache Miss 後，資料應該被回填到 Cache"""
        # 第一次讀:Cache Miss
        resp1 = requests.get(f"{BASE_URL}/profile/{TEST_USER}")
        assert resp1.json()["_source"] == "database"

        # 第二次讀:應該 hit Cache 了
        resp2 = requests.get(f"{BASE_URL}/profile/{TEST_USER}")
        assert resp2.json()["_source"] == "cache"


# ============================================================
# 場景 4:TTL 安全網 — Cache 過期後自動修復不一致
# ============================================================

class TestTTLSafetyNet:
    """
    對應 System Design 觀念:TTL as Safety Net
    即使發生了 Cache 不一致，TTL 過期後 Cache 會失效，
    下次讀取就會從 DB 拿到正確的資料。

    注意:這個測試需要等待 TTL 過期，實務上 TTL 設 60 秒，
    但為了測試速度，你可以把 app.py 裡的 TTL 改成 3 秒來跑這個測試。
    """

    @pytest.mark.skip(reason="TTL 設 60 秒太久，改成 3 秒後移除 skip")
    def test_stale_cache_auto_heals_after_ttl(self):
        """幽靈數據在 TTL 過期後自動修復"""
        # 建立幽靈數據
        requests.put(
            f"{BASE_URL}/profile/{TEST_USER}",
            json={"bio": "舊的"},
        )
        requests.put(
            f"{BASE_URL}/profile/{TEST_USER}",
            json={"bio": "新的（幽靈）"},
            headers={"X-Fail-At": "after_db"},
        )

        # 確認不一致
        state = requests.get(f"{BASE_URL}/debug/state/{TEST_USER}").json()
        assert state["is_consistent"] is False

        # 等待 TTL 過期（需要把 app.py 的 TTL 改成 3 秒）
        time.sleep(4)

        # 讀取 — Cache 已過期，會從 DB 拿到新資料
        profile = requests.get(f"{BASE_URL}/profile/{TEST_USER}").json()
        assert profile["_source"] == "database"
        assert profile["bio"] == "新的（幽靈）"  # 終於拿到正確的了！

        # 一致性也修復了
        state = requests.get(f"{BASE_URL}/debug/state/{TEST_USER}").json()
        assert state["is_consistent"] is True


# ============================================================
# 場景 5:冪等性 — 重複更新不應產生異常
# ============================================================

class TestIdempotency:
    """
    對應 System Design 觀念:Idempotency
    同樣的更新請求發送多次，結果應該跟發一次一樣。
    """

    def test_duplicate_updates_produce_same_result(self):
        """同一個更新發兩次，最終狀態應該一樣"""
        payload = {"bio": "冪等性測試", "avatar_url": "https://idempotent.jpg"}

        # 發兩次
        resp1 = requests.put(f"{BASE_URL}/profile/{TEST_USER}", json=payload)
        resp2 = requests.put(f"{BASE_URL}/profile/{TEST_USER}", json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        # 最終狀態應該一致
        state = requests.get(f"{BASE_URL}/debug/state/{TEST_USER}").json()
        assert state["is_consistent"] is True
        assert state["database"]["bio"] == "冪等性測試"

    def test_rapid_fire_updates_no_corruption(self):
        """快速連發 10 次更新，資料不應損壞"""
        for i in range(10):
            requests.put(
                f"{BASE_URL}/profile/{TEST_USER}",
                json={"bio": f"第 {i + 1} 次更新"},
            )

        # 最終狀態應該一致，且是最後一次的值
        state = requests.get(f"{BASE_URL}/debug/state/{TEST_USER}").json()
        assert state["is_consistent"] is True
        assert state["database"]["bio"] == "第 10 次更新"
        assert state["cache"]["bio"] == "第 10 次更新"
