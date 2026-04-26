import mercadopago
import stripe
from django.conf import settings
import logging
import os

logger = logging.getLogger(__name__)

class MercadoPagoService:
    def __init__(self):
        from administration.models import SystemSetting
        settings = SystemSetting.get_settings()
        
        # Try database settings first, then fallback to .env
        self.access_token = settings.mercadopago_access_token or os.getenv('MERCADOPAGO_ACCESS_TOKEN')
        self.webhook_secret = settings.mercadopago_webhook_secret or os.getenv('MERCADOPAGO_WEBHOOK_SECRET')
        
        if not self.access_token or self.access_token == 'your_access_token_here':
            logger.error("Mercado Pago Access Token not configured.")
        
        self.sdk = mercadopago.SDK(self.access_token)


    def create_payment(self, payment_data, idempotency_key=None):
        """
        Cria um pagamento transparente usando o token do cartão gerado no frontend.
        Envia a X-Idempotency-Key para garantir segurança em produção.
        """
        try:
            request_options = mercadopago.config.RequestOptions()
            if idempotency_key:
                request_options.custom_headers = {
                    'x-idempotency-key': str(idempotency_key)
                }
            
            result = self.sdk.payment().create(payment_data, request_options)
            return result["response"]
        except Exception as e:
            with open('/root/verticebook/mercado_pago.log', 'a') as f:
                from datetime import datetime
                import traceback
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] EXCEÇÃO NO SERVICE: {str(e)}\n{traceback.format_exc()}\n")
            logger.error(f"Erro ao criar pagamento no Mercado Pago: {str(e)}")
            return None

    def get_payment(self, payment_id):
        """
        Busca informações de um pagamento específico.
        """
        try:
            result = self.sdk.payment().get(payment_id)
            return result["response"]
        except Exception as e:
            logger.error(f"Erro ao buscar pagamento {payment_id} no Mercado Pago: {str(e)}")
            return None

    def process_webhook(self, data):
        """
        Processa notificações de webhook (IPN).
        """
        # O Mercado Pago envia o ID da transação e o tipo
        resource_id = data.get('data', {}).get('id')
        topic = data.get('type') or data.get('topic')

        if topic == 'payment' and resource_id:
            return self.get_payment(resource_id)
        
        return None

class StripeService:
    def __init__(self):
        from administration.models import SystemSetting
        settings = SystemSetting.get_settings()
        
        self.secret_key = settings.stripe_secret_key or os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = settings.stripe_webhook_secret or os.getenv('STRIPE_WEBHOOK_SECRET')
        
        if self.secret_key:
            stripe.api_key = self.secret_key

    def create_payment_intent(self, amount, currency='brl', description=None, metadata=None):
        """
        Cria um PaymentIntent no Stripe.
        """
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100), # Stripe usa centavos
                currency=currency,
                description=description,
                metadata=metadata or {}
            )
            return intent
        except Exception as e:
            with open('/root/verticebook/stripe.log', 'a') as f:
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] ERRO NO SERVICE STRIPE: {str(e)}\n")
            logger.error(f"Erro ao criar PaymentIntent no Stripe: {str(e)}")
            return None

    def get_payment_intent(self, intent_id):
        try:
            return stripe.PaymentIntent.retrieve(intent_id)
        except Exception as e:
            logger.error(f"Erro ao buscar PaymentIntent {intent_id}: {str(e)}")
            return None

    def process_webhook(self, payload, sig_header):
        """
        Verifica e processa eventos de webhook do Stripe.
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return event
        except Exception as e:
            logger.error(f"Erro ao processar Webhook do Stripe: {str(e)}")
            return None
