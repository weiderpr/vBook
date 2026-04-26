import os
import sys

# Add the project root to sys.path
sys.path.append('/root/verticebook')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
import django
django.setup()

from core.utils import is_mobile

class MockRequest:
    def __init__(self, user_agent):
        self.META = {'HTTP_USER_AGENT': user_agent}

# Test iPhone User-Agent
iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Mobile/15E148 Safari/604.1"
req = MockRequest(iphone_ua)
print(f"iPhone detected: {is_mobile(req)}")

# Test Desktop User-Agent
desktop_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
req = MockRequest(desktop_ua)
print(f"Desktop detected: {is_mobile(req)}")
