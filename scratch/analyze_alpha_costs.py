import os
import sys
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum

# Add the project root to sys.path
sys.path.append('/root/verticebook')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
import django
django.setup()

from properties.models import Property, PropertyCost
from reservations.models import Reservation, ReservationCost

month = 4
year = 2026

prop = Property.objects.filter(name__icontains="Alpha Concept").first()
if not prop:
    print("Property not found")
    sys.exit(1)

print(f"Property: {prop.name} (ID: {prop.id})")

# 1. Gross Revenue (based on end_date)
prop_res = Reservation.objects.filter(
    property=prop,
    end_date__month=month,
    end_date__year=year,
    is_cancelled=False
)
gross = prop_res.aggregate(total=Sum('total_value'))['total'] or Decimal(0)
print(f"Gross (April 2026): {gross}")

# 2. Reservation Costs (based on end_date)
res_costs = ReservationCost.objects.filter(
    reservation__property=prop,
    reservation__end_date__month=month,
    reservation__end_date__year=year,
    reservation__is_cancelled=False
).aggregate(total=Sum('value'))['total'] or Decimal(0)
print(f"Reservation Costs: {res_costs}")

# 3. Property Costs (Fixed/Monthly)
prop_costs_sum = Decimal(0)
# Following PropertySettingsView logic
other_costs = prop.costs.exclude(frequency='per_booking')
for pc in other_costs:
    m, y = None, None
    if pc.payment_date:
        m, y = pc.payment_date.month, pc.payment_date.year
    elif pc.month and pc.year:
        m, y = pc.month, pc.year
        
    if m == month and y == year:
        print(f"  - Property Cost: {pc.name} = {pc.amount} (Source: {'payment_date' if pc.payment_date else 'month/year'})")
        prop_costs_sum += pc.amount

# 4. Property Costs (following PropertyReportsView logic - ONLY frequency='monthly' and month/year)
prop_costs_reports_sum = Decimal(0)
prop_costs_reports = prop.costs.filter(frequency='monthly', month=month, year=year)
for pc in prop_costs_reports:
    prop_costs_reports_sum += pc.amount
print(f"Property Costs (Reports logic): {prop_costs_reports_sum}")

print(f"Total Costs (Settings logic): {res_costs + prop_costs_sum}")
print(f"Total Costs (Reports logic): {res_costs + prop_costs_reports_sum}")
