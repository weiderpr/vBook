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
    
    reservations = Reservation.objects.filter(
        property=prop,
        start_date__gte=first_day_last_month
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
