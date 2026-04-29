import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from django.apps import apps

target = Decimal('43973.11')

for model in apps.get_models():
    try:
        # Only check models with decimal fields
        decimal_fields = [f.name for f in model._meta.fields if isinstance(f, django.db.models.DecimalField)]
        if not decimal_fields:
            continue
            
        for field in decimal_fields:
            matches = model.objects.filter(**{field: target})
            if matches.exists():
                print(f"MATCH in {model._meta.label} field {field}:")
                for m in matches:
                    print(f"  ID: {m.pk}, {m}")
    except Exception as e:
        continue
