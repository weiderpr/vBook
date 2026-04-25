from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from administration.models import Plan

def landing_view(request):
    plans = Plan.objects.filter(is_active=True).order_by('base_value')
    return render(request, 'core/landing.html', {'plans': plans})

@login_required
def dashboard_view(request):
    return render(request, 'core/dashboard.html')
