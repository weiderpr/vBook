import os
import sys
from django.utils import timezone
from django.db.models import Sum

# Add the project root to sys.path
sys.path.append('/root/verticebook')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
import django
django.setup()

from core.utils import is_mobile
from properties.models import Property, PropertyCost
from reservations.models import Reservation, ReservationCost
from accounts.models import CustomUser

# Let's test for a specific user or just see if there are any reservations at all
now = timezone.now()
month = now.month
year = now.year

print(f"Current Month: {month}, Year: {year}")

# Check first user
user = CustomUser.objects.first()
if user:
    print(f"Testing for user: {user.email}")
    
    res = Reservation.objects.filter(
        property__user=user,
        start_date__month=month,
        start_date__year=year,
        is_cancelled=False
    )
    print(f"Found {res.count()} reservations for this month")
    for r in res:
        print(f"  - {r.client_name}: {r.total_value} (Start: {r.start_date})")
    
    gross = res.aggregate(total=Sum('total_value'))['total'] or 0
    print(f"Gross Revenue: {gross}")
    
    res_costs = ReservationCost.objects.filter(
        reservation__property__user=user,
        reservation__start_date__month=month,
        reservation__start_date__year=year,
        reservation__is_cancelled=False
    ).aggregate(total=Sum('value'))['total'] or 0
    print(f"Res Costs: {res_costs}")
    
    fixed_costs = PropertyCost.objects.filter(
        property__user=user,
        frequency='monthly'
    ).aggregate(total=Sum('amount'))['total'] or 0
    print(f"Fixed Costs: {fixed_costs}")
else:
    print("No users found")
