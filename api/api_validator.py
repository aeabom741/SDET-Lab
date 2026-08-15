from conf.log import HandlLog
from playwright.sync_api import APIResponse

class APIValidator:
    
    def __init__(self, response: APIResponse, name: str = "API"):
        self.hand_log = HandlLog()
        self.response = response
        self.name = name
        self.json_data = None

        # 不論 2xx 或 4xx/5xx 都嘗試解析 body。
        # 混沌測試常常要對「錯誤回應」的 body 做斷言（例如 error 訊息），
        # 若只在 response.ok 時解析，500 的 error body 會永遠拿不到。
        try:
            self.json_data = response.json()
        except Exception:
            self.json_data = {}

    def status_should_be(self, code: int = 200):
        actual = self.response.status
        self.hand_log.handle_log(f"[{self.name}] 驗證狀態碼: 預期 {code}, 實際 {actual}")
        assert actual == code, f"[{self.name}] 狀態碼不符！預期 {code}，實際 {actual}"
        return self 

    def field_should_be(self, path: str, expected_value):
        keys = path.split(".")
        actual_value = self.json_data
        for k in keys:
            if actual_value is None:
                break
            actual_value = actual_value.get(k)
        self.hand_log.handle_log(f"[{self.name}] 驗證欄位 {path}: 預期 {expected_value}, 實際 {actual_value}")
        assert actual_value == expected_value, f"[{self.name}] 欄位 {path} 驗證失敗！預期 {expected_value}，實際 {actual_value}"
        return self

