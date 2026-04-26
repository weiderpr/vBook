from django.shortcuts import redirect
from django.urls import reverse, resolve
from .models import Subscription

class SubscriptionMiddleware:
    """
    Middleware para garantir que usuários com planos pagos tenham uma assinatura ativa
    para acessar as áreas restritas do sistema.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Se o usuário não está logado ou é o super-admin do sistema, permitimos
        if not request.user.is_authenticated or getattr(request.user, 'is_admin', False):
            return self.get_response(request)

        # Tentamos identificar a view atual de forma robusta
        try:
            # path_info ignora o prefixo do script (como /book)
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
            'profile',  # Permitimos o perfil para que ele possa renovar
            'logout',
            'landing',
        ]
        
        # Permitimos caminhos de admin e estáticos (com e sem o prefixo /book)
        current_path = request.path
        if any(current_path.startswith(p) for p in ['/admin/', '/static/', '/media/', '/book/admin/', '/book/static/', '/book/media/']):
            return self.get_response(request)

        # Se a view não for uma das permitidas, verificamos a assinatura
        if view_name not in allowed_view_names:
            try:
                subscription = request.user.subscription
                # Se o plano exige pagamento e a assinatura não é válida (não ativa ou expirada)
                if subscription.plan.requires_payment and not subscription.is_valid:
                    return redirect('profile')
            except Subscription.DoesNotExist:
                # Se não tem registro de assinatura e o sistema exige, redireciona para o perfil
                # (Opcional: você pode permitir usuários sem assinatura se desejar)
                return redirect('profile')

        return self.get_response(request)
