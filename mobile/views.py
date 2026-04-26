from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from properties.models import Property, PropertyCost
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
        prop_res = Reservation.objects.filter(
            property=prop,
            end_date__month=month,
            end_date__year=year,
            is_cancelled=False
        )
        
        # Occupancy Calculation
        prop_res_overlap = Reservation.objects.filter(
            property=prop,
            is_cancelled=False,
            start_date__lte=month_end,
            end_date__gte=month_start
        )
        
        reserved_days = 0
        for res in prop_res_overlap:
            actual_start = max(res.start_date, month_start)
            actual_end = min(res.end_date, month_end)
            overlap_days = (actual_end - actual_start).days
            reserved_days += max(0, overlap_days)
            
        occupancy_rate = (reserved_days / days_in_month) * 100
        
        prop_gross = prop_res.aggregate(total=Sum('total_value'))['total'] or 0
        
        prop_res_costs = ReservationCost.objects.filter(
            reservation__property=prop,
            reservation__end_date__month=month,
            reservation__end_date__year=year,
            reservation__is_cancelled=False
        ).aggregate(total=Sum('value'))['total'] or 0
        
        prop_fixed_costs = PropertyCost.objects.filter(
            Q(property=prop) &
            (
                Q(payment_date__month=month, payment_date__year=year) |
                Q(month=month, year=year)
            )
        ).exclude(frequency='per_booking').aggregate(total=Sum('amount'))['total'] or 0
        
        total_prop_costs = prop_res_costs + prop_fixed_costs
        prop_net = prop_gross - total_prop_costs
        
        # Vacancy Loss Calculation
        if occupancy_rate > 0:
            # Potential gross if 100% occupied, extrapolated from current gross per occupied day
            potential_gross = float(prop_gross) / (occupancy_rate / 100)
            vacancy_loss = potential_gross - float(prop_gross)
        else:
            vacancy_loss = 0
            
        # YTD Performance Comparison
        from datetime import date, timedelta
        ytd_start_this_year = date(year, 1, 1)
        ytd_end_this_year = today # Today (e.g., April 25th, 2026)
        
        ytd_start_last_year = date(year - 1, 1, 1)
        ytd_end_last_year = date(year - 1, today.month, today.day)
        
        # Financial YTD (Robust logic matching PropertySettingsView)
        from properties.models import FinancialHistory
        
        def get_period_net_robust(start, end, p):
            total_net = Decimal(0)
            curr_date = start
            
            # Pre-fetch data for the period to avoid N+1 queries
            reservations = Reservation.objects.filter(
                property=p, end_date__range=[start, end], is_cancelled=False
            )
            res_data = {} # (m, y) -> {'gross': D, 'costs': D}
            for res in reservations:
                key = (res.end_date.month, res.end_date.year)
                if key not in res_data: res_data[key] = {'gross': Decimal(0), 'costs': Decimal(0)}
                res_data[key]['gross'] += res.total_value
            
            res_costs = ReservationCost.objects.filter(
                reservation__in=reservations
            )
            for rc in res_costs:
                key = (rc.reservation.end_date.month, rc.reservation.end_date.year)
                res_data[key]['costs'] += rc.value
                
            prop_costs = PropertyCost.objects.filter(
                Q(property=p) &
                (
                    Q(payment_date__range=[start, end]) |
                    (Q(year__range=[start.year, end.year]) & Q(month__isnull=False))
                )
            ).exclude(frequency='per_booking')
            prop_costs_data = {} # (m, y) -> D
            for pc in prop_costs:
                m, y = (pc.payment_date.month, pc.payment_date.year) if pc.payment_date else (pc.month, pc.year)
                if m and y:
                    prop_costs_data[(m, y)] = prop_costs_data.get((m, y), Decimal(0)) + pc.amount
                    
            histories = FinancialHistory.objects.filter(property=p, year__range=[start.year, end.year])
            history_data = {(h.month, h.year): {'gross': h.gross_value, 'costs': h.costs} for h in histories}
            
            # Iterate month by month
            m, y = start.month, start.year
            end_m, end_y = end.month, end.year
            
            while y < end_y or (y == end_y and m <= end_m):
                key = (m, y)
                if key in res_data:
                    m_gross = res_data[key]['gross']
                    m_costs = res_data[key]['costs'] + prop_costs_data.get(key, Decimal(0))
                    total_net += (m_gross - m_costs)
                elif key in history_data:
                    total_net += (history_data[key]['gross'] - history_data[key]['costs'])
                elif key in prop_costs_data:
                    total_net -= prop_costs_data[key]
                
                m += 1
                if m > 12: m = 1; y += 1
                
            return total_net

        net_this_year = get_period_net_robust(ytd_start_this_year, ytd_end_this_year, prop)
        net_last_year = get_period_net_robust(ytd_start_last_year, ytd_end_last_year, prop)
        
        growth = 0
        if net_last_year != 0:
            growth = ((net_this_year - net_last_year) / abs(net_last_year)) * 100
        elif net_this_year != 0:
            growth = 100
            
        properties_data.append({
            'obj': prop,
            'res_count': prop_res.count(),
            'occupancy': min(100, round(occupancy_rate, 1)),
            'vacancy_loss': max(0, vacancy_loss),
            'gross': prop_gross,
            'costs': total_prop_costs,
            'net': prop_net,
            'ytd_growth': round(growth, 1),
            'has_last_year': net_last_year != 0
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
        start_date__gte=first_day_last_month,
        is_cancelled=False
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
    
    return render(request, 'mobile/reservation_detail.html', {
        'reservation': reservation,
        'property': reservation.property,
        'total_paid': total_paid,
        'remaining': remaining,
        'title': _("Detalhes da Reserva")
    })
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
