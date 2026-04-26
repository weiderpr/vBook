import os
import sys
import calendar
from django.utils import timezone
from django.db.models import Sum
from datetime import date

# Add the project root to sys.path
sys.path.append('/root/verticebook')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
import django
django.setup()

from properties.models import Property
from reservations.models import Reservation
from accounts.models import CustomUser

now = timezone.now()
month = now.month
year = now.year
days_in_month = calendar.monthrange(year, month)[1]
month_start = date(year, month, 1)
month_end = date(year, month, days_in_month)

print(f"Target Month: {month}/{year} ({days_in_month} days)")

user = CustomUser.objects.first()
if user:
    print(f"User: {user.email}")
    user_properties = Property.objects.filter(user=user)
    print(f"Found {user_properties.count()} properties")
    
    for prop in user_properties:
        prop_res_overlap = Reservation.objects.filter(
            property=prop,
            is_cancelled=False,
            start_date__lte=month_end,
            end_date__gte=month_start
        )
        
        reserved_days = 0
        for res in prop_res_overlap:
            actual_start = max(res.start_date, month_start)
            actual_end = min(res.end_date, month_end)
            overlap_days = (actual_end - actual_start).days
            reserved_days += max(0, overlap_days)
            print(f"  - Reservation: {res.client_name} ({res.start_date} to {res.end_date}) -> Overlap: {overlap_days} days")
            
        occupancy_rate = (reserved_days / days_in_month) * 100
        print(f"Property: {prop.name} -> Reserved Days: {reserved_days}, Occupancy: {occupancy_rate:.1f}%")
else:
    print("No user found")
