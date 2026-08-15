import allure
from playwright.sync_api import APIRequestContext

class BaseAPI:
    def __init__(self, request: APIRequestContext):
        self.request = request
        self.base_url = "http://localhost:5050"

    def get(self, endpoint, **kwargs):
        with allure.step(f"[GET] Endpoint:{endpoint}"):
            return self.request.get(url=f"{self.base_url}{endpoint}", **kwargs)

    def post(self, endpoint, **kwargs):
        with allure.step(f"[POST] Endpoint:{endpoint}"):
            return self.request.post(url=f"{self.base_url}{endpoint}", **kwargs)

    def put(self, endpoint, **kwargs):
        with allure.step(f"[PUT] Endpoint:{endpoint}"):
            return self.request.put(url=f"{self.base_url}{endpoint}", **kwargs)
