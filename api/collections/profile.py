from api.base_api import BaseAPI

class Profile(BaseAPI):
    def get_profile(self, user_id="user_001"):
        return self.get(f"/profile/{user_id}")

    def update_profile(self, user_id="user_001", data=None, headers=None):
        return self.put(f"/profile/{user_id}", data=data, headers=headers)

    def get_debug_state(self, user_id="user_001"):
        return self.get(f"/debug/state/{user_id}")

    def reset_user(self, user_id="user_001"):
        return self.post(f"/debug/reset/{user_id}")
