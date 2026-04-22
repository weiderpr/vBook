from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import translation
from django.utils.translation import gettext_lazy as _
import json
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm
from reservations.services.evolution_api import EvolutionService

def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def profile_view(request):
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
    
    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form
    })

def login_view(request):
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserLoginForm()
    return render(request, 'accounts/login.html', {'form': form})

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
    
    status = service.get_connection_status()
    
    # Se não tiver instância ainda ou se ela foi deletada do servidor (not_found), tenta criar/vincular
    if not user.whatsapp_instance_name or status == 'not_found':
        instance_name = f"vbook_{user.id}"
        result = service.create_instance(instance_name)
        if result:
            # Na v2, a apikey da instância é retornada no campo 'hash' como uma string
            hash_data = result.get('hash')
            if isinstance(hash_data, str):
                apikey = hash_data
            else:
                instance_data = result.get('instance', {})
                apikey = instance_data.get('apikey') if isinstance(instance_data, dict) else None
                
            user.whatsapp_instance_name = instance_name
            user.whatsapp_instance_key = apikey
            user.save(update_fields=['whatsapp_instance_name', 'whatsapp_instance_key'])
            service = EvolutionService(user=user) # Re-init com os dados
            status = service.get_connection_status() # Atualiza o status após criar
    
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
