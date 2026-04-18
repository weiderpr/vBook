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
