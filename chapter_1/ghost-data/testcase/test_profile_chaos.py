from api.api_validator import APIValidator

class TestPositiveCase:

    def test_get_profile_source_database(self, api):
        # Given: 用戶 user_001 已重置到初始狀態
        # When:  第一次 GET /profile/user_001（Cache 為空）
        # Then:  狀態碼 200
        #        _source 為 database（Cache Miss，從 DB 讀取）
        #        所有欄位應為初始值
        self.resp = api.get_profile()

        APIValidator(response=self.resp, name="GET /profile/<user-id>") \
            .status_should_be(200) \
            .field_should_be(path="_source", expected_value="database") \
            .field_should_be(path="avatar_url", expected_value="https://old-avatar.jpg") \
            .field_should_be(path="bio", expected_value="原始的 Bio") \
            .field_should_be(path="nickname", expected_value="Leo") \
            .field_should_be(path="user_id", expected_value="user_001")

    def test_get_profile_source_cache(self, api):
        # Given: 用戶 user_001 已重置到初始狀態
        # And:   已 GET 一次，觸發 Cache-Aside 回填
        # When:  第二次 GET /profile/user_001
        # Then:  狀態碼 200
        #        _source 為 cache（Cache Hit，從 Redis 讀取）
        #        所有欄位與第一次相同
        api.get_profile()
        self.resp = api.get_profile()

        APIValidator(response=self.resp, name="GET /profile/<user-id>") \
            .status_should_be(200) \
            .field_should_be(path="_source", expected_value="cache") \
            .field_should_be(path="avatar_url", expected_value="https://old-avatar.jpg") \
            .field_should_be(path="bio", expected_value="原始的 Bio") \
            .field_should_be(path="nickname", expected_value="Leo") \
            .field_should_be(path="user_id", expected_value="user_001")

    def test_get_profile_debug_state(self, api):
        # Given: 用戶 user_001 已重置到初始狀態
        # And:   尚未執行任何 GET 或 PUT（Cache 應為空）
        # When:  GET /debug/state/user_001
        # Then:  狀態碼 200
        #        cache 為 None（尚未被回填）
        #        database 有初始資料
        #        is_consistent 為 True（Cache 不存在不算不一致）
        #        inconsistencies 為空陣列
        self.resp = api.get_debug_state()

        APIValidator(response=self.resp, name="GET /debug/state/<user-id>") \
            .status_should_be(200) \
            .field_should_be("cache", None) \
            .field_should_be("database.avatar_url", "https://old-avatar.jpg") \
            .field_should_be("database.bio", "原始的 Bio") \
            .field_should_be("database.nickname", "Leo") \
            .field_should_be("database.user_id", "user_001") \
            .field_should_be("inconsistencies", []) \
            .field_should_be("is_consistent", True)

    def test_get_profile_debug_state_cache(self, api):
        # Given: 用戶 user_001 已重置到初始狀態
        # And:   已 GET 一次，觸發 Cache-Aside 回填 Redis
        # When:  GET /debug/state/user_001
        # Then:  狀態碼 200
        #        cache 和 database 的所有欄位應完全一致
        #        is_consistent 為 True
        #        inconsistencies 為空陣列
        api.get_profile()
        self.resp = api.get_debug_state()

        APIValidator(response=self.resp, name="GET /debug/state/<user-id>") \
            .status_should_be(200) \
            .field_should_be("cache.avatar_url", "https://old-avatar.jpg") \
            .field_should_be("cache.bio", "原始的 Bio") \
            .field_should_be("cache.nickname", "Leo") \
            .field_should_be("cache.user_id", "user_001") \
            .field_should_be("database.avatar_url", "https://old-avatar.jpg") \
            .field_should_be("database.bio", "原始的 Bio") \
            .field_should_be("database.nickname", "Leo") \
            .field_should_be("database.user_id", "user_001") \
            .field_should_be("inconsistencies", []) \
            .field_should_be("is_consistent", True)

    def test_put_profile(self, api):
        # Given: 用戶 user_001 已重置到初始狀態（autouse fixture）
        # When:  PUT /profile/user_001 更新 bio 和 avatar_url
        # Then:  狀態碼 200
        #        message 為 "Profile updated successfully"
        #        data 中 bio 和 avatar_url 為新值
        #        nickname 維持原值（PUT 不應更新 nickname）
        self.resp = api.update_profile(data={
            "avatar_url": "https://test_update.jpg",
            "bio": "test update"
        })

        APIValidator(response=self.resp, name="PUT /profile/<user-id>") \
            .status_should_be(200) \
            .field_should_be("message", "Profile updated successfully") \
            .field_should_be("data.avatar_url", "https://test_update.jpg") \
            .field_should_be("data.bio", "test update") \
            .field_should_be("data.nickname", "Leo") \
            .field_should_be("data.user_id", "user_001")


class TestGhostData:
    """幽靈數據：DB 寫入成功但 Cache 沒更新 → DB 與 Cache 不一致。

    對應 System Design 觀念：Cache-Aside 的寫入路徑若在「寫 DB」與
    「更新 Cache」之間崩潰，Cache 會殘留舊值，用戶讀到的是過期資料。
    """

    def test_ghost_data_inconsistency(self, api):
        # Given: 用戶已重置（autouse），先正常更新一次讓 Cache 有「舊的 Bio」
        api.update_profile(data={"bio": "舊的 Bio"})

        # When:  再次更新，但用 X-Fail-At: after_db 讓 Server 在寫完 DB 後崩潰
        self.resp = api.update_profile(
            data={"bio": "新的 Bio"},
            headers={"X-Fail-At": "after_db"},
        )

        # Then:  回傳 500，且 error body 說明是 DB 寫入後崩潰
        APIValidator(response=self.resp, name="PUT /profile (after_db crash)") \
            .status_should_be(500) \
            .field_should_be("error", "💥 Server crashed after DB write!")

        # And:   DB 已是新值、Cache 還是舊值 → 系統偵測到不一致
        APIValidator(response=api.get_debug_state(), name="GET /debug/state (ghost)") \
            .status_should_be(200) \
            .field_should_be("is_consistent", False) \
            .field_should_be("database.bio", "新的 Bio") \
            .field_should_be("cache.bio", "舊的 Bio")

    def test_user_reads_stale_cache(self, api):
        # Given: 製造幽靈數據（同上）
        api.update_profile(data={"bio": "舊的 Bio"})
        api.update_profile(
            data={"bio": "新的 Bio"},
            headers={"X-Fail-At": "after_db"},
        )

        # When:  用戶重新整理頁面 → GET /profile
        # Then:  拿到的是 Cache 裡的「舊的 Bio」，看不到 DB 已更新的「新的 Bio」
        APIValidator(response=api.get_profile(), name="GET /profile (stale read)") \
            .status_should_be(200) \
            .field_should_be("_source", "cache") \
            .field_should_be("bio", "舊的 Bio")
