from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import json
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm
from reservations.services.evolution_api import EvolutionService
from administration.models import Plan
from core.utils import is_mobile

def register_view(request):
    plan_id = request.GET.get('plan')
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            
            # Vincular plano e tratar pagamento
            plan_id = request.POST.get('plan_id')
            if plan_id:
                try:
                    plan = Plan.objects.get(id=plan_id)
                    from subscriptions.models import Subscription
                    
                    # Cria a assinatura (Ativa se for grátis, Pendente se for pago)
                    Subscription.objects.get_or_create(
                        user=user,
                        defaults={
                            'plan': plan, 
                            'status': 'active' if not plan.requires_payment else 'pending'
                        }
                    )
                    
                    if plan.requires_payment:
                        return redirect('subscriptions:checkout', plan_id=plan.id)
                except Plan.DoesNotExist:
                    pass
            
            if is_mobile(request):
                return redirect('mobile:home')
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    return render(request, 'accounts/register.html', {
        'form': form,
        'plan_id': plan_id
    })

@login_required
def profile_view(request):
    from subscriptions.models import Subscription
    subscription = Subscription.objects.filter(user=request.user).first()
    
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = UserProfileForm(request.POST, request.FILES, instance=request.user)
            password_form = PasswordChangeForm(request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, _('Perfil atualizado com sucesso!'))
                return redirect('profile')
        elif 'change_password' in request.POST:
            profile_form = UserProfileForm(instance=request.user)
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Keeps the user logged in
                messages.success(request, _('Sua senha foi alterada com sucesso!'))
                return redirect('profile')
    else:
        profile_form = UserProfileForm(instance=request.user)
        password_form = PasswordChangeForm(request.user)
    
    # Fetch available paid plans for the modal
    available_plans = Plan.objects.filter(is_active=True, requires_payment=True).order_by('base_value')
    
    # Calculate current balance in days
    subscription_days_remaining = 0
    payments = []
    if subscription:
        payments = subscription.payments.all() # Ordering is already descending by default in Meta
        if subscription.end_date and subscription.status == 'active':
            now = timezone.now()
            if subscription.end_date > now:
                delta = subscription.end_date - now
                subscription_days_remaining = delta.days

    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'subscription': subscription,
        'available_plans': available_plans,
        'subscription_days_remaining': subscription_days_remaining,
        'payment_history': payments
    })


from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import translation

@ensure_csrf_cookie
def login_view(request):
    next_url = request.GET.get('next')
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Se tivermos um next_url que aponte para mobile, respeitamos ele com prioridade
            if next_url and ('mobile' in next_url or '/book/mobile' in next_url):
                return redirect(next_url)
            
            # Se for super-admin, vai direto para o dashboard
            if getattr(user, 'is_admin', False):
                return redirect('dashboard')
                
            # Verifica se tem assinatura válida
            # Bypass para admins e staff de condomínio
            if not getattr(user, 'is_admin', False) and getattr(user, 'user_type', '') != 'staff':
                from subscriptions.models import Subscription
                subscription = Subscription.objects.filter(user=user).first()
                # Se o plano não for válido (vencido ou pendente), vai para o perfil
                if not subscription or not subscription.is_valid:
                    if is_mobile(request) or (next_url and 'mobile' in next_url):
                        return redirect('mobile:plans')
                    return redirect('profile')
                
            if getattr(user, 'user_type', '') == 'staff':
                return redirect('mobilecondominio:dashboard')
                
            # Se não tiver next_url mas for mobile, vai para home mobile
            if is_mobile(request):
                return redirect('mobile:home')
                
            # Fallback para next_url geral ou dashboard
            if next_url:
                return redirect(next_url)
            return redirect('dashboard')
    else:
        form = UserLoginForm()
    return render(request, 'accounts/login.html', {'form': form, 'next': next_url})

def logout_view(request):
    logout(request)
    return redirect('landing')

@login_required
def update_theme_preference(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            theme = data.get('theme')
            if theme in ['light', 'dark']:
                request.user.theme_preference = theme
                request.user.save()
                return JsonResponse({'status': 'success'})
        except Exception:
            pass
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def update_language_preference(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            language = data.get('language')
            if language in ['pt-br', 'en']:
                request.user.language_preference = language
                request.user.save()
                translation.activate(language)
                return JsonResponse({'status': 'success'})
        except Exception:
            pass
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def whatsapp_settings_view(request):
    """
    View para gerenciar a conexão do usuário com o WhatsApp via Evolution API.
    """
    user = request.user
    service = EvolutionService(user=user)
    
    # Se não tiver instância ainda, não tentamos buscar conexão
    if not user.whatsapp_instance_name:
        status = 'not_created'
    else:
        status = service.get_connection_status()
        
        # Se a instância não for encontrada no servidor (foi deletada manualmante lá)
        if status == 'not_found':
            # Resetamos localmente para permitir recriação
            user.whatsapp_instance_name = None
            user.whatsapp_instance_key = None
            user.save(update_fields=['whatsapp_instance_name', 'whatsapp_instance_key'])
            status = 'not_created'
    
    # Atualiza cache de conexão no banco
    is_connected = (status == 'open')
    if user.whatsapp_connected != is_connected:
        user.whatsapp_connected = is_connected
        user.save(update_fields=['whatsapp_connected'])
    
    qr_code = None
    if status != 'open':
        qr_data = service.get_qrcode()
        if qr_data:
            # Evolution API v2 retorna o base64 em qr_data['qrcode']['base64'] ou similar
            qr_code = qr_data.get('qrcode', {}).get('base64') or qr_data.get('base64')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'logout':
            if service.logout_instance():
                messages.success(request, _("WhatsApp desconectado com sucesso."))
            else:
                messages.error(request, _("Erro ao desconectar WhatsApp."))
            return redirect('whatsapp_settings')
        
    return render(request, 'accounts/whatsapp_settings.html', {
        'status': status,
        'qr_code': qr_code,
        'instance_name': user.whatsapp_instance_name,
        'instance_key': user.whatsapp_instance_key
    })

@login_required
def create_whatsapp_instance_view(request):
    """
    View para criar manualmente a instância na Evolution API.
    """
    if request.method == 'POST':
        user = request.user
        from reservations.services.evolution_api import EvolutionService
        
        instance_name = f"vbook_{user.id}"
        service = EvolutionService(instance_name=instance_name)
        
        result = service.create_instance(instance_name)
        if result:
            hash_data = result.get('hash')
            if isinstance(hash_data, str):
                apikey = hash_data
            else:
                instance_data = result.get('instance', {})
                apikey = instance_data.get('apikey') if isinstance(instance_data, dict) else None
            
            user.whatsapp_instance_name = instance_name
            user.whatsapp_instance_key = apikey
            user.save(update_fields=['whatsapp_instance_name', 'whatsapp_instance_key'])
            messages.success(request, _("Instância criada com sucesso! Agora você pode conectar seu WhatsApp."))
        else:
            messages.error(request, _("Erro ao criar instância na API. Tente novamente mais tarde."))
            
    return redirect('whatsapp_settings')
