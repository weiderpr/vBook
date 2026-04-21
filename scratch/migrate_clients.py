import os
import sys
import django

# Add the project root to sys.path
sys.path.append('/root/verticebook')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from reservations.models import Reservation, Client

def migrate_clients():
    reservations = Reservation.objects.filter(client__isnull=True)
    count = 0
    for res in reservations:
        # Avoid duplicate clients if possible (by phone)
        client, created = Client.objects.get_or_create(
            phone=res.client_phone,
            defaults={'name': res.client_name}
        )
        res.client = client
        res.save(update_fields=['client'])
        count += 1
        print(f"Migrated: {res.client_name} ({res.id})")
    
    print(f"Total migrated: {count}")

if __name__ == '__main__':
    migrate_clients()
