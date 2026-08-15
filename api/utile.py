
class DataExtractor:

    @staticmethod
    def get_value_by_path(response_json, path: str):
        """
        支援用 'data.user.id' 這種方式拿資料
        """
        keys = path.split(".")
        value = response_json
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        return value