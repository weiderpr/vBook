import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from properties.models import Property, FinancialHistory
from reservations.models import Reservation
from django.db.models import Sum

for p in Property.objects.all():
    res = Reservation.objects.filter(property=p, end_date__year=2026, is_cancelled=False).aggregate(s=Sum('total_value'))['s'] or Decimal(0)
    hist = FinancialHistory.objects.filter(property=p, year=2026).aggregate(s=Sum('gross_value'))['s'] or Decimal(0)
    print(f"ID {p.id}: {p.name}")
    print(f"  Res: {res}")
    print(f"  Hist: {hist}")
    print(f"  Total: {res + hist}")
