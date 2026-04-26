from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from administration.models import Plan, SystemSetting
from .models import Subscription, Payment
from .services import MercadoPagoService, StripeService
from django.utils import timezone
from django.urls import reverse
import json
import os
import logging
import uuid
import sys

import sys
from datetime import datetime

logger = logging.getLogger(__name__)

def log_mp(message):
    with open('/root/verticebook/mercado_pago.log', 'a') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] {message}\n")

def log_stripe(message):
    with open('/root/verticebook/stripe.log', 'a') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] {message}\n")

@login_required
def checkout_view(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)
    settings = SystemSetting.get_settings()
    
    context = {
        'plan': plan,
        'active_gateway': settings.active_gateway
    }
    
    if settings.active_gateway == 'mercadopago':
        context['public_key'] = settings.mercadopago_public_key or os.getenv('MERCADOPAGO_PUBLIC_KEY')
    elif settings.active_gateway == 'stripe':
        context['public_key'] = settings.stripe_public_key or os.getenv('STRIPE_PUBLIC_KEY')
        
    return render(request, 'subscriptions/checkout.html', context)

@csrf_exempt
def create_stripe_intent_view(request):
    """
    Cria um PaymentIntent para o Stripe e retorna o client_secret
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Acesso negado: Usuário não autenticado'}, status=401)
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plan_id = data.get('plan_id')
            plan = get_object_or_404(Plan, id=plan_id)
            
            log_stripe(f"CRIANDO INTENT PARA PLANO {plan_id} (Usuário {request.user.id})")
            stripe_service = StripeService()
            intent = stripe_service.create_payment_intent(
                amount=float(plan.base_value),
                description=f"Assinatura VerticeBook - {plan.description}",
                metadata={
                    'plan_id': plan.id,
                    'user_id': request.user.id
                }
            )
            
            if intent:
                log_stripe(f"INTENT CRIADO: {intent.id}")
                return JsonResponse({
                    'client_secret': intent.client_secret,
                    'id': intent.id
                })
            log_stripe("ERRO: Falha ao criar intent (retornou None)")
            return JsonResponse({'error': 'Falha ao criar intent'}, status=400)
        except Exception as e:
            log_stripe(f"EXCEÇÃO NO VIEW STRIPE: {str(e)}")
            logger.error(f"Erro Stripe Intent: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Método não permitido'}, status=405)

@login_required
@csrf_exempt
def process_payment_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plan_id = data.get('plan_id')
            plan = get_object_or_404(Plan, id=plan_id)
            
            mp_service = MercadoPagoService()
            
            payment_method_id = data.get("payment_method_id", "")
            is_pix = payment_method_id == "pix"

            # Gerar Idempotency Key única para esta tentativa
            idempotency_key = uuid.uuid4()

            # Montar e-mail e nome do pagador (priorizando usuário logado)
            payer_data = data.get("payer", {})
            if not payer_data.get("email"):
                payer_data["email"] = request.user.email
            
            # PIX exige nome e sobrenome. Vamos tentar extrair do full_name
            if not payer_data.get("first_name"):
                full_name = getattr(request.user, 'full_name', '')
                if full_name:
                    parts = full_name.split(' ', 1)
                    payer_data["first_name"] = parts[0]
                    # Se não houver sobrenome na partição, garante que last_name tenha algo
                    if len(parts) > 1:
                        payer_data["last_name"] = parts[1]
                    else:
                        payer_data["last_name"] = request.user.last_name or "VBook"
                else:
                    payer_data["first_name"] = request.user.first_name or "Usuario"

            if not payer_data.get("last_name"):
                payer_data["last_name"] = request.user.last_name or "VBook"

            # Construir notification_url dinamicamente baseada no host da requisição (Django Way)
            notification_url = request.build_absolute_uri(reverse('subscriptions:mp_webhook'))

            # Montar payload base para o Mercado Pago
            payment_data = {
                "transaction_amount": float(plan.base_value),
                "description": f"Assinatura VerticeBook - {plan.description}",
                "payment_method_id": payment_method_id,
                "payer": payer_data,
                "notification_url": notification_url,
                "external_reference": f"SUB-{request.user.id}-{int(timezone.now().timestamp())}"
            }

            # Campos exclusivos de pagamento com cartão
            if not is_pix:
                payment_data["token"] = data.get("token")
                payment_data["installments"] = int(data.get("installments") or 1)
                payment_data["issuer_id"] = data.get("issuer_id")

            # Criar pagamento no Mercado Pago
            log_mp(f"ENVIANDO PAYLOAD: {json.dumps(payment_data, indent=2)}")
            response = mp_service.create_payment(payment_data, idempotency_key=idempotency_key)
            log_mp(f"RESPOSTA RECEBIDA: {json.dumps(response, indent=2) if response else 'None'}")

            if response and response.get('status') in ['approved', 'pending']:
                # Criar ou atualizar assinatura
                subscription, created = Subscription.objects.get_or_create(
                    user=request.user,
                    defaults={'plan': plan, 'status': 'active' if response.get('status') == 'approved' else 'pending'}
                )
                
                if not created:
                    subscription.plan = plan
                    subscription.status = 'active' if response.get('status') == 'approved' else 'pending'
                    subscription.save()

                # Registrar o pagamento
                Payment.objects.create(
                    subscription=subscription,
                    amount=plan.base_value,
                    payment_method=payment_method_id,
                    mp_payment_id=str(response.get('id')),
                    status=response.get('status'),
                    raw_data=response
                )

                # Se for PIX, retornar dados do QR Code
                if is_pix:
                    qr_code = response.get('point_of_interaction', {}).get('transaction_data', {}).get('qr_code')
                    qr_code_base64 = response.get('point_of_interaction', {}).get('transaction_data', {}).get('qr_code_base64')
                    return JsonResponse({
                        'status': 'pending',
                        'id': response.get('id'),
                        'qr_code': qr_code,
                        'qr_code_base64': qr_code_base64
                    })

                return JsonResponse({'status': response.get('status'), 'id': response.get('id')})
            else:
                # LOG CRÍTICO PARA DEBUG IMEDIATO
                error_detail = response.get('message') if response else "Erro desconhecido ou resposta vazia"
                log_mp(f"ERRO NO PAGAMENTO: {error_detail}")
                logger.error(f"Erro Mercado Pago: {error_detail}")
                return JsonResponse({'status': 'error', 'message': error_detail}, status=400)

        except Exception as e:
            import traceback
            log_mp(f"EXCEÇÃO NO VIEW: {str(e)}\n{traceback.format_exc()}")
            logger.exception("Erro interno ao processar pagamento")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Método não permitido'}, status=405)

@login_required
def payment_success_view(request):
    return render(request, 'subscriptions/success.html')

@login_required
def payment_status_view(request, mp_payment_id):
    """
    Endpoint para polling do status do pagamento
    """
    payment = get_object_or_404(Payment, mp_payment_id=mp_payment_id)
    
    # Se o pagamento ainda estiver pendente no banco, tenta atualizar via API
    if payment.status == 'pending':
        mp_service = MercadoPagoService()
        mp_data = mp_service.get_payment(mp_payment_id)
        if mp_data and mp_data.get('status') != payment.status:
            payment.status = mp_data.get('status')
            payment.save()
            
            # Se aprovou, ativa a assinatura
            if payment.status == 'approved':
                payment.subscription.status = 'active'
                payment.subscription.save()
                
    return JsonResponse({'status': payment.status})

@login_required
def simulate_approval_view(request, payment_id):
    """
    Função de conveniência para testar o fluxo de redirecionamento
    """
    try:
        payment = Payment.objects.get(mp_payment_id=payment_id)
        payment.status = 'approved'
        payment.save()
        
        # Ativar a assinatura
        payment.subscription.status = 'active'
        payment.subscription.save()
        
        return JsonResponse({'status': 'success', 'message': 'Pagamento simulado como aprovado!'})
    except Payment.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Pagamento não encontrado'}, status=404)

@csrf_exempt
def webhook_view(request):
    """
    Recebe notificações do Mercado Pago (IPN)
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mp_service = MercadoPagoService()
            payment_data = mp_service.process_webhook(data)
            
            if payment_data:
                payment_id = payment_data.get('id')
                status = payment_data.get('status')
                
                try:
                    payment = Payment.objects.get(mp_payment_id=payment_id)
                    if payment.status != status:
                        payment.status = status
                        payment.save()
                        
                        if status == 'approved':
                            payment.subscription.status = 'active'
                            payment.subscription.save()
                except Payment.DoesNotExist:
                    pass # Pagamento não encontrado localmente
                    
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            logger.error(f"Erro no Webhook: {str(e)}")
            return JsonResponse({'status': 'error'}, status=400)
            
@csrf_exempt
def stripe_webhook_view(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    stripe_service = StripeService()
    event = stripe_service.process_webhook(payload, sig_header)
    
    if event:
        event_type = event.get('type')
        data_object = event.get('data', {}).get('object', {})
        
        if event_type == 'payment_intent.succeeded':
            intent_id = data_object.get('id')
            user_id = data_object.get('metadata', {}).get('user_id')
            plan_id = data_object.get('metadata', {}).get('plan_id')
            
            if user_id and plan_id:
                from accounts.models import CustomUser
                user = CustomUser.objects.get(id=user_id)
                plan = Plan.objects.get(id=plan_id)
                
                subscription, created = Subscription.objects.get_or_create(
                    user=user,
                    defaults={'plan': plan, 'status': 'active'}
                )
                if not created:
                    subscription.plan = plan
                    subscription.status = 'active'
                    subscription.save()
                
                Payment.objects.get_or_create(
                    mp_payment_id=intent_id, # Usando o mesmo campo para simplificar ou poderíamos renomear para gateway_id
                    defaults={
                        'subscription': subscription,
                        'amount': data_object.get('amount') / 100,
                        'status': 'approved',
                        'payment_method': 'stripe_card',
                        'raw_data': data_object
                    }
                )
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)
