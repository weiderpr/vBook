from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from administration.models import Plan
from core.utils import is_mobile
from properties.utils import get_yearly_stats
import json

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
    from properties.utils import get_yearly_stats, get_operational_stats
    import json
    
    yearly_stats = get_yearly_stats(request.user)
    operational_stats = get_operational_stats(request.user)
    
    # Pre-calculate current year revenue distribution for Area 3
    from django.utils import timezone
    current_year = timezone.localtime(timezone.now()).year
    revenue_distribution = []
    
    for prop in yearly_stats['properties']:
        # Try both int and string for the year key to be safe
        year_data = prop['data_by_year'].get(current_year) or prop['data_by_year'].get(str(current_year))
        val = year_data.get('gross', 0) if year_data else 0
        
        if val > 0:
            revenue_distribution.append({
                'name': prop['name'],
                'value': val,
                'color': prop['color']
            })
    
    context = {
        'yearly_stats_json': json.dumps(yearly_stats),
        'revenue_distribution_json': json.dumps(revenue_distribution),
        'operational_stats': operational_stats,
        'current_year': current_year,
    }
    return render(request, 'core/dashboard.html', context)

@cache_control(max_age=86400, public=True)
def service_worker(request):
    import os
    from django.conf import settings
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    with open(sw_path, 'rb') as f:
        content = f.read()
    return HttpResponse(content, content_type='application/javascript')
