import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from subscriptions.models import Subscription
from django.utils import timezone

# Fix active subscriptions without start/end dates
subs = Subscription.objects.filter(status='active', end_date__isnull=True)
count = 0
for sub in subs:
    # Trigger the new save() method logic
    sub.save()
    print(f"Fixed: {sub.user.email} - New End Date: {sub.end_date}")
    count += 1

print(f"\nTotal fixed: {count}")
