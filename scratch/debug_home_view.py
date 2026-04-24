import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from properties.models import ServiceProvider
from reservations.models import ReservationCost

token = '78cdca7d-5394-4f60-8294-d1ed885aa59c'
provider = ServiceProvider.objects.get(access_token=token)

print(f"Provider: {provider.name}")

active_costs = provider.reservation_costs.filter(is_completed=False).select_related('reservation', 'reservation__property').order_by('reservation__start_date')
print(f"Total Active Costs: {active_costs.count()}")

next_services = []
seen_properties = set()
for cost in active_costs:
    print(f"Checking cost {cost.id} for property {cost.reservation.property.name} (ID: {cost.reservation.property_id})")
    if cost.reservation.property_id not in seen_properties:
        next_services.append(cost)
        seen_properties.add(cost.reservation.property_id)
        print(f"  -> Added as next service")

print(f"Next Services Count: {len(next_services)}")
for s in next_services:
    print(f"- {s.reservation.property.name}: {s.description} ({s.reservation.start_date})")
