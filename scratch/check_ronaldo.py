import os
import django
import datetime
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from reservations.models import Reservation

name = "Ronaldo Maraes"
res = Reservation.objects.filter(client_name__icontains=name).first()

if res:
    print(f"Reservation ID: {res.pk}")
    print(f"Client Name: {res.client_name}")
    print(f"Check-in Completed: {res.checkin_completed}")
    print(f"Is Cancelled: {res.is_cancelled}")
    print(f"Start Date: {res.start_date}")
    print(f"End Date: {res.end_date}")
    print(f"Property: {res.property.name}")
    print(f"Condo: {res.property.condo.name if res.property.condo else 'None'}")
    
    today = timezone.now().date()
    print(f"Today: {today}")
    print(f"End Date >= Today: {res.end_date >= today}")
else:
    print(f"No reservation found for name: {name}")

# Also check for current user's condo
from accounts.models import CustomUser
# I don't know the current user's email, but I can check if there are users with condo assigned
staff = CustomUser.objects.filter(user_type='staff').first()
if staff:
    print(f"\nExample Staff User: {staff.email}")
    print(f"Staff Condo: {staff.condo.name if staff.condo else 'None'}")
