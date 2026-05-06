import json
import logging
from pywebpush import webpush, WebPushException
from django.conf import settings
from .models import Notification, PushSubscription

logger = logging.getLogger(__name__)

def is_mobile(request):
    """
    Detects if the request comes from a mobile device based on the User-Agent header
    or if the request is targeting a mobile-specific path.
    """
    # Check if it's a mobile-specific path (including with the /book/ prefix)
    current_path = request.path
    if '/mobile/' in current_path:
        return True

    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    mobile_patterns = [
        'iphone', 'android', 'phone', 'mobile', 'mobi', 'webos', 'ipod', 'blackberry',
        'windows phone', 'iemobile', 'opera mini', 'standalone'
    ]
    return any(pattern in user_agent for pattern in mobile_patterns)

from django.utils.encoding import force_str

def send_notification(user, title, message, link=None):
    """
    Cria uma notificação no banco de dados e tenta disparar um Web Push 
    para todos os dispositivos registrados do usuário.
    """
    # Converter strings traduzidas para strings normais (evitar erro de serialização JSON)
    title = force_str(title)
    message = force_str(message)

    # 1. Criar Notificação Interna
    try:
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            link=link
        )
    except Exception as e:
        logger.error(f"Erro ao criar notificação no banco: {e}")

    # 2. Enviar Web Push
    subscriptions = PushSubscription.objects.filter(user=user)
    
    # Payload para o Service Worker
    payload = {
        "title": title,
        "body": message,
        "icon": "/book/static/images/hero.png",
        "badge": "/book/static/images/hero.png",
        "data": {
            "url": link or "/book/mobile/home/"
        }
    }
    
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth
                    }
                },
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY_PATH,
                vapid_claims={
                    "sub": f"mailto:{settings.VAPID_ADMIN_EMAIL}"
                }
            )
        except WebPushException as ex:
            # Se a assinatura expirou ou o usuário desinstalou/bloqueou
            if ex.response is not None and ex.response.status_code in [404, 410]:
                sub.delete()
            logger.warning(f"Erro Web Push (esperado se expirar): {ex}")
        except Exception as e:
            logger.error(f"Erro genérico no Web Push: {e}")
