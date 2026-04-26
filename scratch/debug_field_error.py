import os
import sys
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Q
from datetime import date

# Add the project root to sys.path
sys.path.append('/root/verticebook')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
import django
django.setup()

from properties.models import Property, PropertyCost
from reservations.models import Reservation, ReservationCost
from accounts.models import CustomUser

user = CustomUser.objects.first()
now = timezone.now()
today = now.date()
month = now.month
year = now.year

prop = Property.objects.filter(user=user).first()
if not prop:
    print("No property found")
    sys.exit(0)

print(f"Testing for property: {prop.name}")

ytd_start_this_year = date(year, 1, 1)
ytd_end_this_year = today

ytd_start_last_year = date(year - 1, 1, 1)
ytd_end_last_year = date(year - 1, today.month, today.day)

def get_period_net(start, end, p):
    print(f"  Calculating for {start} to {end}")
    gross = Reservation.objects.filter(
        property=p, end_date__range=[start, end], is_cancelled=False
    ).aggregate(total=Sum('total_value'))['total'] or Decimal(0)
    
    res_c = ReservationCost.objects.filter(
        reservation__property=p, reservation__end_date__range=[start, end], is_cancelled=False
    ).aggregate(total=Sum('value'))['total'] or Decimal(0)
    
    f_costs = PropertyCost.objects.filter(
        Q(property=p) &
        (
            Q(payment_date__range=[start, end]) |
            (Q(year=start.year) & Q(month__gte=start.month, month__lte=end.month))
        )
    ).exclude(frequency='per_booking').aggregate(total=Sum('amount'))['total'] or Decimal(0)
    
    return gross - (res_c + f_costs)

try:
    net_this_year = get_period_net(ytd_start_this_year, ytd_end_this_year, prop)
    print(f"Net This Year: {net_this_year}")
    net_last_year = get_period_net(ytd_start_last_year, ytd_end_last_year, prop)
    print(f"Net Last Year: {net_last_year}")
except Exception as e:
    import traceback
    traceback.print_exc()
