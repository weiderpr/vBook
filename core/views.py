from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from administration.models import Plan
from core.utils import is_mobile

def landing_view(request):
    # Se já estiver logado, redireciona para o dashboard apropriado
    if request.user.is_authenticated:
        if is_mobile(request):
            return redirect('mobile:home')
        return redirect('dashboard')

    if is_mobile(request):
        return redirect('login')
    
    plans = Plan.objects.filter(is_active=True).order_by('-base_value')
    return render(request, 'core/landing.html', {'plans': plans})

@login_required
def dashboard_view(request):
    if is_mobile(request):
        return redirect('mobile:home')
    return render(request, 'core/dashboard.html')

