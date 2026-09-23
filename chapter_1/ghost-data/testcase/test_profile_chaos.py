import allure

from api.api_validator import APIValidator


@allure.feature("Profile API")
@allure.story("Positive")
class TestProfilePositive:

    @allure.title("GET /profile/<user_id>")
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

    @allure.title("GET /profile/<user_id>")
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


@allure.feature("Profile API")
@allure.story("Scenario")
class TestProfileScenario:
    """有狀態的多步流程：驗證 reset 會清掉 Cache（Cache-Aside 的自癒機制）。"""

    @allure.title("GET /profile/<user_id>")
    def test_reset_clears_cache(self, api):
        # Given: 用戶已重置到初始狀態（autouse fixture）
        # When:  第一次 GET → Cache Miss，從 DB 讀
        # Then:  _source = database
        APIValidator(response=api.get_profile(), name="GET /profile (冷讀)") \
            .status_should_be(200) \
            .field_should_be("_source", "database")

        # When:  第二次 GET → Cache Hit
        # Then:  _source = cache（★ 這步證明 Cache 確實被回填了，是整個因果鏈的關鍵）
        APIValidator(response=api.get_profile(), name="GET /profile (熱讀)") \
            .status_should_be(200) \
            .field_should_be("_source", "cache")

        # When:  重置用戶
        api.reset_user()

        # Then:  再次 GET 又變回 Cache Miss → 證明 reset 把「本來有的」Cache 清掉了
        APIValidator(response=api.get_profile(), name="GET /profile (reset 後)") \
            .status_should_be(200) \
            .field_should_be("_source", "database")


@allure.feature("Profile API")
@allure.story("Negative")
class TestProfileNegative:
    """錯誤路徑：該失敗時，有沒有回正確的狀態碼與錯誤訊息。"""

    @allure.title("GET /profile/<user_id>")
    def test_get_profile_user_not_found(self, api):
        # Given: 一個不存在的 user_id
        # When:  GET /profile/<不存在>
        # Then:  404，且 error 訊息明確
        APIValidator(response=api.get_profile(user_id="no_such_user"),
                     name="GET /profile (查無此人)") \
            .status_should_be(404) \
            .field_should_be("error", "User not found")
