from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from properties.models import Property, PropertyCost
from properties.utils import get_property_stats
from reservations.models import Reservation, ReservationCost
from django.utils.translation import gettext_lazy as _
from reservations.forms import ReservationForm

@login_required
def mobile_home(request):
    now = timezone.localtime(timezone.now())
    month = now.month
    year = now.year
    
    property_count = Property.objects.filter(user=request.user).count()
    reservation_count = Reservation.objects.filter(property__user=request.user).count()
    
    # Financial Stats for current month
    # Accounting reference: end_date (checkout)
    gross_revenue = Reservation.objects.filter(
        property__user=request.user,
        end_date__month=month,
        end_date__year=year,
        is_cancelled=False
    ).aggregate(total=Sum('total_value'))['total'] or 0
    
    # Reservation Costs
    res_costs = ReservationCost.objects.filter(
        reservation__property__user=request.user,
        reservation__end_date__month=month,
        reservation__end_date__year=year,
        reservation__is_cancelled=False
    ).aggregate(total=Sum('value'))['total'] or 0
    
    # Fixed and Other Property Costs (filtering by month/year)
    from django.db.models import Q
    fixed_costs = PropertyCost.objects.filter(
        Q(property__user=request.user) &
        (
            Q(payment_date__month=month, payment_date__year=year) |
            Q(month=month, year=year)
        )
    ).exclude(frequency='per_booking').aggregate(total=Sum('amount'))['total'] or 0
    
    total_costs = res_costs + fixed_costs
    net_value = gross_revenue - total_costs
    
    # Check-ins and Check-outs for today
    today = now.date()
    today_checkins = Reservation.objects.filter(
        property__user=request.user,
        start_date=today,
        is_cancelled=False
    ).count()
    
    today_checkouts = Reservation.objects.filter(
        property__user=request.user,
        end_date=today,
        is_cancelled=False
    ).count()
    
    # Per Property Stats
    properties_data = []
    user_properties = Property.objects.filter(user=request.user)
    
    import calendar
    from datetime import date
    days_in_month = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)
    
    for prop in user_properties:
        stats = get_property_stats(prop, month, year)
        
        properties_data.append({
            'obj': prop,
            'res_count': stats['res_count'],
            'occupancy': stats['occupancy'],
            'vacancy_loss': stats['vacancy_loss'],
            'gross': stats['gross'],
            'costs': stats['costs'],
            'net': stats['net'],
            'ytd_growth': stats['ytd_growth'],
            'has_last_year': stats['has_last_year'],
            'is_currently_occupied': stats['is_currently_occupied']
        })
    
    context = {
        'property_count': property_count,
        'reservation_count': reservation_count,
        'gross_revenue': gross_revenue,
        'total_costs': total_costs,
        'net_value': net_value,
        'today_checkins': today_checkins,
        'today_checkouts': today_checkouts,
        'properties_data': properties_data,
        'current_month_name': now.strftime('%B'),
    }
    return render(request, 'mobile/mobile_home.html', context)

@login_required
def mobile_reservations_today(request):
    # ... (rest of the view remains the same)
    res_type = request.GET.get('type', 'checkin')
    now = timezone.localtime(timezone.now())
    today = now.date()
    
    if res_type == 'checkout':
        reservations = Reservation.objects.filter(
            property__user=request.user,
            end_date=today,
            is_cancelled=False
        )
        title = "Check-outs de Hoje"
    else:
        reservations = Reservation.objects.filter(
            property__user=request.user,
            start_date=today,
            is_cancelled=False
        )
        title = "Check-ins de Hoje"
        
    return render(request, 'mobile/reservations_today.html', {
        'reservations': reservations,
        'title': title,
        'res_type': res_type
    })

@login_required
def mobile_property_detail(request, pk):
    from django.shortcuts import get_object_or_404
    from datetime import timedelta, date
    
    prop = get_object_or_404(Property, pk=pk, user=request.user)
    
    # Calculate first day of last month
    now = timezone.localtime(timezone.now())
    first_day_this_month = now.replace(day=1)
    last_month_end = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_month_end.replace(day=1).date()
    
    from django.db.models import Q
    reservations = Reservation.objects.filter(
        Q(property=prop) &
        (Q(start_date__gte=first_day_last_month) | Q(end_date__gte=first_day_last_month))
    ).prefetch_related('costs', 'costs__provider', 'payments').order_by('-start_date')
    
    # Annotate with totals for display
    from django.db.models import Sum
    for res in reservations:
        res.total_costs = res.costs.aggregate(total=Sum('value'))['total'] or 0
        res.total_received = res.payments.aggregate(total=Sum('value'))['total'] or 0
    
    return render(request, 'mobile/property_detail.html', {
        'property': prop,
        'reservations': reservations
    })

@login_required
def mobile_reservation_create(request, property_pk):
    prop = get_object_or_404(Property, pk=property_pk, user=request.user)
    
    if request.method == 'POST':
        form = ReservationForm(request.POST, property_obj=prop)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.property = prop
            reservation.save()
            return redirect('mobile:property_detail', pk=prop.pk)
    else:
        form = ReservationForm(property_obj=prop)
    
    return render(request, 'mobile/reservation_form.html', {
        'form': form,
        'property': prop,
        'title': _("Nova Reserva")
    })

@login_required
def mobile_reservation_edit(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk, property__user=request.user)
    prop = reservation.property
    
    if request.method == 'POST':
        form = ReservationForm(request.POST, instance=reservation, property_obj=prop)
        if form.is_valid():
            form.save()
            return redirect('mobile:property_detail', pk=prop.pk)
    else:
        form = ReservationForm(instance=reservation, property_obj=prop)
    
    return render(request, 'mobile/reservation_form.html', {
        'form': form,
        'property': prop,
        'title': _("Editar Reserva")
    })
@login_required
def mobile_reservation_detail(request, pk):
    reservation = get_object_or_404(
        Reservation.objects.select_related('property').prefetch_related('costs', 'costs__provider', 'payments'),
        pk=pk,
        property__user=request.user
    )
    
    # Financial calculations
    total_paid = sum(p.value for p in reservation.payments.all())
    remaining = reservation.total_value - total_paid
    
    # For modals
    from properties.models import ServiceProvider
    providers = ServiceProvider.objects.filter(user=request.user)
    
    return render(request, 'mobile/reservation_detail.html', {
        'reservation': reservation,
        'property': reservation.property,
        'total_paid': total_paid,
        'remaining': remaining,
        'providers': providers,
        'title': _("Detalhes da Reserva"),
        'confirm_msg': _("Esta mensagem de boas-vindas já foi enviada. Deseja reenviar?")
    })

@login_required
def mobile_add_reservation_cost(request, pk):
    if request.method == 'POST':
        reservation = get_object_or_404(Reservation, pk=pk, property__user=request.user)
        description = request.POST.get('description')
        value = Decimal(request.POST.get('value', '0').replace(',', '.'))
        provider_id = request.POST.get('provider')
        is_completed = request.POST.get('is_completed') == 'on'
        
        cost = ReservationCost.objects.create(
            reservation=reservation,
            description=description,
            value=value,
            provider_id=provider_id if provider_id else None,
            is_completed=is_completed
        )
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def mobile_add_reservation_payment(request, pk):
    if request.method == 'POST':
        reservation = get_object_or_404(Reservation, pk=pk, property__user=request.user)
        description = request.POST.get('description')
        value = Decimal(request.POST.get('value', '0').replace(',', '.'))
        payment_date = request.POST.get('payment_date')
        
        from reservations.models import ReservationPayment
        ReservationPayment.objects.create(
            reservation=reservation,
            description=description,
            value=value,
            payment_date=payment_date
        )
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)
@login_required
def mobile_delete_reservation_cost(request, pk, cost_id):
    reservation = get_object_or_404(Reservation, pk=pk, property__user=request.user)
    cost = get_object_or_404(ReservationCost, id=cost_id, reservation=reservation)
    cost.delete()
    return JsonResponse({'status': 'success'})

@login_required
def mobile_delete_reservation_payment(request, pk, payment_id):
    reservation = get_object_or_404(Reservation, pk=pk, property__user=request.user)
    from reservations.models import ReservationPayment
    payment = get_object_or_404(ReservationPayment, id=payment_id, reservation=reservation)
    payment.delete()
    return JsonResponse({'status': 'success'})

@login_required
def mobile_send_whatsapp_reservation(request, property_pk, pk):
    from reservations.models import Reservation
    from reservations.services.evolution_api import EvolutionService
    from django.contrib import messages
    
    reservation = get_object_or_404(Reservation, pk=pk, property__pk=property_pk, property__user=request.user)
    service = EvolutionService(user=reservation.property.user)
    success, message = service.enviar_link_checkin(reservation.id)
    
    if success:
        reservation.welcome_message_sent = True
        reservation.save(update_fields=['welcome_message_sent'])
        messages.success(request, message)
    else:
        messages.error(request, message)
    
    return redirect('mobile:reservation_detail', pk=pk)
@login_required
def mobile_send_authorization_whatsapp(request, property_pk, pk):
    from reservations.views_checkin import ReservationSendAuthorizationWhatsAppView
    view = ReservationSendAuthorizationWhatsAppView.as_view()
    return view(request, property_pk=property_pk, pk=pk)

@login_required
def mobile_reservation_cancel(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk, property__user=request.user)
    
    if not reservation.is_cancelled:
        reservation.is_cancelled = True
        reservation.save(update_fields=['is_cancelled'])
        from django.contrib import messages
        messages.success(request, _("Reserva cancelada com sucesso."))
        
    return redirect('mobile:reservation_detail', pk=pk)

@login_required
def mobile_reservation_delete(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk, property__user=request.user)
    property_pk = reservation.property.pk
    
    reservation.delete()
    from django.contrib import messages
    messages.success(request, _("Reserva excluída com sucesso."))
    
    return redirect('mobile:property_detail', pk=property_pk)

@login_required
def mobile_reservation_reactivate(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk, property__user=request.user)
    
    if reservation.is_cancelled:
        reservation.is_cancelled = False
        reservation.save(update_fields=['is_cancelled'])
        from django.contrib import messages
        messages.success(request, _("Reserva reativada com sucesso."))
        
    return redirect('mobile:reservation_detail', pk=pk)

@login_required
def mobile_profile(request):
    return render(request, 'mobile/mobile_profile.html', {
        'user': request.user,
        'title': _("Meu Perfil")
    })

@login_required
def mobile_update_theme(request):
    if request.method == 'POST':
        theme = request.POST.get('theme')
        if theme in ['light', 'dark']:
            request.user.mobile_theme_preference = theme
            request.user.save(update_fields=['mobile_theme_preference'])
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)
@login_required
def mobile_password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, _('Sua senha foi alterada com sucesso!'))
            return redirect('mobile:profile')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'mobile/password_change.html', {
        'form': form,
        'title': _("Alterar Senha")
    })

@login_required
def mobile_plans(request):
    from administration.models import Plan
    from subscriptions.models import Subscription
    
    available_plans = Plan.objects.filter(is_active=True, requires_payment=True).order_by('base_value')
    subscription = Subscription.objects.filter(user=request.user).first()
    
    # Calculate current balance in days
    subscription_days_remaining = 0
    if subscription:
        if subscription.end_date and subscription.status == 'active':
            now = timezone.now()
            if subscription.end_date > now:
                delta = subscription.end_date - now
                subscription_days_remaining = delta.days

    return render(request, 'mobile/subscription_plans.html', {
        'available_plans': available_plans,
        'subscription': subscription,
        'subscription_days_remaining': subscription_days_remaining,
        'title': _("Planos e Assinatura")
    })
@login_required
def mobile_financeiro(request):
    from reservations.models import Reservation, ReservationCost, ReservationPayment
    from maintenance.models import Maintenance
    from django.db.models import Q
    
    now = timezone.localtime(timezone.now())
    selected_month = int(request.GET.get('month', now.month))
    
    # Handle localized year (e.g. '2.026')
    year_val = request.GET.get('year')
    if year_val:
        try:
            selected_year = int(str(year_val).replace('.', '').replace(',', ''))
        except ValueError:
            selected_year = now.year
    else:
        selected_year = now.year
    active_tab = request.GET.get('tab', 'receber')
    
    user_properties = Property.objects.filter(user=request.user)
    
    # Months for selector
    months = [
        (1, _('Janeiro')), (2, _('Fevereiro')), (3, _('Março')), (4, _('Abril')),
        (5, _('Maio')), (6, _('Junho')), (7, _('Julho')), (8, _('Agosto')),
        (9, _('Setembro')), (10, _('Outubro')), (11, _('Novembro')), (12, _('Dezembro'))
    ]
    
    context = {
        'selected_month': selected_month,
        'selected_year': selected_year,
        'active_tab': active_tab,
        'months': months,
        'title': _("Financeiro")
    }

    if active_tab == 'receber':
        report_data = []
        for prop in user_properties:
            reservations = prop.reservations.filter(
                end_date__month=selected_month,
                end_date__year=selected_year,
                is_cancelled=False
            )
            res_ids = reservations.values_list('id', flat=True)
            total_val = reservations.aggregate(total=Sum('total_value'))['total'] or Decimal(0)
            comissao = ReservationCost.objects.filter(
                reservation_id__in=res_ids,
                property_cost__recipient='platform'
            ).aggregate(total=Sum('value'))['total'] or Decimal(0)
            received = ReservationPayment.objects.filter(reservation_id__in=res_ids).aggregate(total=Sum('value'))['total'] or Decimal(0)
            balance = (total_val - comissao) - received
            
            if total_val > 0 or comissao > 0 or received > 0:
                report_data.append({
                    'property': prop,
                    'comissao': comissao,
                    'received': received,
                    'balance': balance,
                    'total_value': total_val
                })
        
        context['report_data'] = report_data
        context['totals'] = {
            'comissao': sum(item['comissao'] for item in report_data),
            'received': sum(item['received'] for item in report_data),
            'balance': sum(item['balance'] for item in report_data),
            'total_value': sum(item['total_value'] for item in report_data)
        }

    elif active_tab == 'consolidado':
        consolidated_data = []
        global_totals = {'gross': Decimal(0), 'costs': Decimal(0), 'net': Decimal(0)}
        
        for prop in user_properties:
            # Monthly metrics for selected month
            # 1. Reservations
            res_m = prop.reservations.filter(end_date__month=selected_month, end_date__year=selected_year, is_cancelled=False)
            gross_m = res_m.aggregate(total=Sum('total_value'))['total'] or Decimal(0)
            res_costs_m = ReservationCost.objects.filter(reservation__in=res_m).aggregate(total=Sum('value'))['total'] or Decimal(0)
            
            # 2. Fixed/Property Costs
            prop_costs_m = prop.costs.filter(
                (Q(frequency='monthly') & (Q(year=selected_year) | Q(year__isnull=True)) & (Q(month=selected_month) | Q(month__isnull=True))) | 
                Q(payment_date__year=selected_year, payment_date__month=selected_month) |
                (Q(year=selected_year, month=selected_month))
            ).aggregate(total=Sum('amount'))['total'] or Decimal(0)
            
            # 3. Maintenances
            maint_m = Maintenance.objects.filter(property=prop, status='finished').filter(
                Q(execution_end_date__year=selected_year, execution_end_date__month=selected_month) | 
                Q(execution_end_date__isnull=True, updated_at__year=selected_year, updated_at__month=selected_month)
            ).aggregate(total=Sum('execution_value'))['total'] or Decimal(0)
            
            # 4. Financial History
            hist_m = prop.financial_histories.filter(year=selected_year, month=selected_month).aggregate(
                g=Sum('gross_value'), c=Sum('costs')
            )
            gross_m += (hist_m['g'] or Decimal(0))
            costs_m = res_costs_m + prop_costs_m + maint_m + (hist_m['c'] or Decimal(0))
            
            net_m = gross_m - costs_m
            
            # Add to global
            global_totals['gross'] += gross_m
            global_totals['costs'] += costs_m
            global_totals['net'] += net_m
            
            consolidated_data.append({
                'property': prop,
                'gross': gross_m,
                'costs': costs_m,
                'net': net_m
            })
            
        context['consolidated_data'] = consolidated_data
        context['global_totals'] = global_totals

    return render(request, 'mobile/financeiro.html', context)

@login_required
def mobile_operacional(request):
    from reservations.models import ReservationCost
    from django.utils import timezone
    from collections import defaultdict
    import datetime

    # Filtro de data: do início do mês ANTERIOR em diante
    now = timezone.now().date()
    # Calcula o primeiro dia do mês anterior
    if now.month == 1:
        start_of_range = now.replace(year=now.year - 1, month=12, day=1)
    else:
        start_of_range = now.replace(month=now.month - 1, day=1)

    # Buscar custos de reserva (diárias/serviços) com prestador
    # Usamos end_date (checkout) para garantir que serviços de saída apareçam
    services = ReservationCost.objects.filter(
        reservation__property__user=request.user,
        provider__isnull=False,
        reservation__end_date__gte=start_of_range
    ).select_related('provider', 'reservation', 'reservation__property').order_by('-reservation__end_date')

    # Agrupar por prestador
    # Usamos o nome do prestador como chave para facilitar o agrupamento no template
    providers_dict = defaultdict(list)
    for service in services:
        providers_dict[service.provider].append(service)

    # Converter para lista de tuplas (provider, services) para manter a ordem se necessário, 
    # ou apenas passar o dicionário
    context = {
        'grouped_services': dict(providers_dict),
        'active_tab': request.GET.get('tab', 'servicos'),
    }
    return render(request, 'mobile/operacional.html', context)
