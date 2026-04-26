from django.contrib.auth import get_user_model
from subscriptions.models import Subscription, Payment
User = get_user_model()
try:
    user = User.objects.get(email='teste1@teste.com')
    print(f'User: {user.username}')
    subs = Subscription.objects.filter(user=user)
    print(f'Subscriptions: {subs.count()}')
    for s in subs:
        print(f'  Plan: {s.plan.description}, Status: {s.status}')
    payments = Payment.objects.filter(subscription__user=user).order_by('-created_at')
    print(f'Payments: {payments.count()}')
    for p in payments:
        print(f'  ID: {p.mp_payment_id}, Status: {p.status}, Amount: {p.amount}, Created: {p.created_at}')
except User.DoesNotExist:
    print('User teste1@teste.com not found')
except Exception as e:
    print(f'Error: {str(e)}')
