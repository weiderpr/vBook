from django.utils import timezone
from .models import Subscription

def subscription_info(request):
    """
    Context processor to provide subscription information and days remaining.
    """
    if request.user.is_authenticated:
        try:
            # Buscamos a assinatura ativa do usuário
            subscription = Subscription.objects.filter(user=request.user, status='active').first()
            
            if subscription and subscription.end_date:
                now = timezone.now()
                delta = subscription.end_date - now
                days_remaining = delta.days
                
                return {
                    'user_subscription': subscription,
                    'subscription_days_remaining': days_remaining
                }
        except Exception:
            pass
    return {}
