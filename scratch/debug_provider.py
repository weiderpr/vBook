import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from properties.models import ServiceProvider
from reservations.models import ReservationCost
from maintenance.models import Maintenance

provider_name = "Andreia Pereira" # Partial match
providers = ServiceProvider.objects.filter(name__icontains=provider_name)

for p in providers:
    print(f"Provider: {p.name} (ID: {p.id})")
    print(f"  Balance: {p.financial_balance}")
    
    res_costs = ReservationCost.objects.filter(provider=p)
    print(f"  ReservationCosts found: {res_costs.count()}")
    for rc in res_costs:
        print(f"    - {rc.description}: {rc.value} (is_completed: {rc.is_completed})")
        
    maintenances = Maintenance.objects.filter(provider=p)
    print(f"  Maintenances found: {maintenances.count()}")
    for m in maintenances:
        print(f"    - {m.title}: {m.execution_value} (status: {m.status})")
    
    prop_costs = p.property_costs.all()
    print(f"  PropertyCosts found: {prop_costs.count()}")
    for pc in prop_costs:
        print(f"    - {pc.name}: {pc.amount} (frequency: {pc.frequency})")
