from django.shortcuts import redirect
from django.urls import reverse, resolve
from .models import Subscription
from core.utils import is_mobile

class SubscriptionMiddleware:
    """
    Middleware para garantir que usuários com planos pagos tenham uma assinatura ativa
    para acessar as áreas restritas do sistema.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Se não autenticado, segue fluxo normal (login vai tratar)
        if not request.user.is_authenticated:
            return self.get_response(request)

        # 2. Bypass CRÍTICO: Admins e Staff de Condomínio não precisam de plano pessoal
        user = request.user
        is_admin = getattr(user, 'is_admin', False)
        user_type = getattr(user, 'user_type', '')
        
        if is_admin or user_type == 'staff':
            return self.get_response(request)

        # 3. Identificação da View
        try:
            match = resolve(request.path_info)
            view_name = match.view_name
        except:
            view_name = None

        # URLs que sempre devem ser acessíveis
        allowed_view_names = [
            'subscriptions:checkout',
            'subscriptions:process_payment',
            'subscriptions:create_stripe_intent',
            'subscriptions:stripe_webhook',
            'subscriptions:payment_status',
            'subscriptions:payment_success',
            'subscriptions:mp_webhook',
            'subscriptions:simulate_approval',
            'profile',  # Permitimos o perfil web (será tratado abaixo para mobile)
            'mobile:plans', # Permitimos os planos mobile
            'mobile:profile', # Permitimos o perfil mobile
            'logout',
            'landing',
        ]
        
        # Permitimos caminhos de admin e estáticos (com e sem o prefixo /book)
        current_path = request.path
        if any(current_path.startswith(p) for p in ['/admin/', '/static/', '/media/', '/book/admin/', '/book/static/', '/book/media/']):
            return self.get_response(request)

        # Se a view não for uma das permitidas OU se for o perfil desktop acessado por mobile
        is_desktop_profile = (view_name == 'profile')
        
        if view_name not in allowed_view_names or (is_desktop_profile and is_mobile(request)):
            try:
                subscription = request.user.subscription
                # Se o plano exige pagamento e a assinatura não é válida (não ativa ou expirada)
                if subscription.plan.requires_payment and not subscription.is_valid:
                    if is_mobile(request):
                        return redirect('mobile:plans')
                    return redirect('profile')
            except Subscription.DoesNotExist:
                # Se não tem registro de assinatura e o sistema exige, redireciona para o perfil
                if is_mobile(request):
                    return redirect('mobile:plans')
                return redirect('profile')

        return self.get_response(request)
