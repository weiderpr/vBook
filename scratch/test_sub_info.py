import os
import django
from django.utils import timezone
from django.test import RequestFactory

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from subscriptions.context_processors import subscription_info
from django.contrib.auth import get_user_model
from subscriptions.models import Subscription, Plan

User = get_user_model()
user = User.objects.first()

if not user:
    print("No user found")
else:
    print(f"Testing for user: {user.email}")
    
    # Mock request
    rf = RequestFactory()
    request = rf.get('/')
    request.user = user
    
    # Get info
    info = subscription_info(request)
    print(f"Result: {info}")
    
    if not info:
        print("No subscription info found for this user. Creating a temporary one for testing...")
        plan = Plan.objects.first()
        if not plan:
            print("No plans found")
        else:
            sub, created = Subscription.objects.get_or_create(
                user=user,
                defaults={'plan': plan, 'status': 'active', 'end_date': timezone.now() + timezone.timedelta(days=10)}
            )
            if not created:
                sub.end_date = timezone.now() + timezone.timedelta(days=10)
                sub.status = 'active'
                sub.save()
            
            info = subscription_info(request)
            print(f"Result after creating sub: {info}")
            
            # Test expiring soon
            sub.end_date = timezone.now() + timezone.timedelta(days=3)
            sub.save()
            info = subscription_info(request)
            print(f"Result for expiring soon (3 days): {info}")
