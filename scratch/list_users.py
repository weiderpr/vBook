import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()
for u in User.objects.all():
    print(f"Name: {u.full_name}, Email: {u.email}, is_admin: {u.is_admin}, is_staff: {u.is_staff}, is_superuser: {u.is_superuser}")
