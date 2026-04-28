from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone
import calendar

def get_property_stats(prop, month=None, year=None):
    """
    Calculates occupancy, gross, costs, net, vacancy loss, and growth for a property.
    """
    now = timezone.localtime(timezone.now())
    if month is None: month = now.month
    if year is None: year = now.year
    
    today = now.date()
    
    days_in_month = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)
    
    # Imports inside to avoid circular dependencies if called from models
    from reservations.models import Reservation, ReservationCost
    from .models import PropertyCost, FinancialHistory

    # Reservations for the month (accounting reference: end_date)
    prop_res = Reservation.objects.filter(
        property=prop,
        end_date__month=month,
        end_date__year=year,
        is_cancelled=False
    )
    
    # Occupancy Calculation (overlap logic)
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
    
    # Financial Stats
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
        potential_gross = float(prop_gross) / (occupancy_rate / 100)
        vacancy_loss = potential_gross - float(prop_gross)
    else:
        vacancy_loss = 0
        
    # YTD Performance
    ytd_start_this_year = date(year, 1, 1)
    ytd_end_this_year = today
    
    ytd_start_last_year = date(year - 1, 1, 1)
    ytd_end_last_year = date(year - 1, today.month, today.day)
    
    def get_period_net_robust(start, end, p):
        total_net = Decimal(0)
        
        # Pre-fetch data
        reservations = Reservation.objects.filter(
            property=p, end_date__range=[start, end], is_cancelled=False
        )
        res_data = {}
        for res in reservations:
            key = (res.end_date.month, res.end_date.year)
            if key not in res_data: res_data[key] = {'gross': Decimal(0), 'costs': Decimal(0)}
            res_data[key]['gross'] += res.total_value
        
        res_costs = ReservationCost.objects.filter(reservation__in=reservations)
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
        prop_costs_data = {}
        for pc in prop_costs:
            m, y = (pc.payment_date.month, pc.payment_date.year) if pc.payment_date else (pc.month, pc.year)
            if m and y:
                prop_costs_data[(m, y)] = prop_costs_data.get((m, y), Decimal(0)) + pc.amount
                
        histories = FinancialHistory.objects.filter(property=p, year__range=[start.year, end.year])
        history_data = {(h.month, h.year): {'gross': h.gross_value, 'costs': h.costs} for h in histories}
        
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

    # Current Status (Occupied/Free)
    is_currently_occupied = Reservation.objects.filter(
        property=prop,
        is_cancelled=False,
        start_date__lte=today,
        end_date__gte=today
    ).exists()

    return {
        'occupancy': min(100, round(occupancy_rate, 1)),
        'vacancy_loss': max(0, vacancy_loss),
        'gross': prop_gross,
        'costs': total_prop_costs,
        'net': prop_net,
        'ytd_growth': round(growth, 1),
        'has_last_year': net_last_year != 0,
        'res_count': prop_res.count(),
        'is_currently_occupied': is_currently_occupied
    }
