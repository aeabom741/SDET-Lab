import pytest

from conf.log import HandlLog
from api.collections.profile import Profile
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def api():
    with sync_playwright() as p:
        request = p.request.new_context()
        yield Profile(request)
        request.dispose()

@pytest.fixture(autouse=True)
def reset(api):
    HandlLog.reset_first_log()
    api.reset_user()
    yield
