import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from subscriptions.models import Subscription
from django.contrib.auth import get_user_model

User = get_user_model()
for sub in Subscription.objects.all():
    print(f"User: {sub.user.email}, Status: {sub.status}, End: {sub.end_date}, is_staff: {sub.user.is_staff}, is_superuser: {sub.user.is_superuser}")
