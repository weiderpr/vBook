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
    from .models import PropertyCost, FinancialHistory
    from maintenance.models import Maintenance

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
    
    # 2.5 Debits: Finished Maintenances in this month
    # Using a Q object to check both execution_end_date and updated_at
    prop_maint_costs = Maintenance.objects.filter(
        property=prop,
        status='finished'
    ).filter(
        Q(execution_end_date__month=month, execution_end_date__year=year) |
        Q(execution_end_date__isnull=True, updated_at__month=month, updated_at__year=year)
    ).aggregate(total=Sum('execution_value'))['total'] or 0
    
    total_prop_costs = prop_res_costs + prop_fixed_costs + prop_maint_costs
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

def get_yearly_stats(user):
    """
    Aggregates financial data (gross and costs) for ALL available years.
    Returns a list of all years with data and the stats for each property.
    """
    from django.utils import timezone
    from properties.models import Property, PropertyCost, FinancialHistory
    from django.db.models import Sum, Q
    from decimal import Decimal
    from maintenance.models import Maintenance
    
    properties = Property.objects.filter(user=user)
    
    # 1. Find all years with any data
    years_set = set()
    
    # Years from reservations
    res_years = Reservation.objects.filter(property__user=user).dates('end_date', 'year')
    for d in res_years: years_set.add(d.year)
    
    # Years from property costs
    cost_years = PropertyCost.objects.filter(property__user=user, year__isnull=False).values_list('year', flat=True)
    for y in cost_years: years_set.add(y)
    
    cost_p_years = PropertyCost.objects.filter(property__user=user, payment_date__isnull=False).dates('payment_date', 'year')
    for d in cost_p_years: years_set.add(d.year)
    
    # Years from history
    hist_years = FinancialHistory.objects.filter(property__user=user).values_list('year', flat=True)
    for y in hist_years: years_set.add(y)
    
    # If no data, at least show current year
    if not years_set:
        years_set.add(timezone.localtime(timezone.now()).year)
        
    years = sorted(list(years_set), reverse=True)
    
    data = {
        'all_years': years,
        'properties': []
    }
    
    for prop in properties:
        prop_data = {
            'name': prop.name,
            'color': prop.color or '#3b82f6',
            'data_by_year': {}
        }
        for year in years:
            # Gross from reservations ending in this year
            res_gross = Reservation.objects.filter(
                property=prop,
                end_date__year=year,
                is_cancelled=False
            ).aggregate(total=Sum('total_value'))['total'] or Decimal(0)
            
            # Costs from reservations ending in this year
            res_costs = ReservationCost.objects.filter(
                reservation__property=prop,
                reservation__end_date__year=year,
                reservation__is_cancelled=False
            ).aggregate(total=Sum('value'))['total'] or Decimal(0)
            
            # Fixed costs for this year
            fixed_costs = PropertyCost.objects.filter(
                Q(property=prop) &
                (
                    Q(payment_date__year=year) |
                    (Q(year=year) & Q(payment_date__isnull=True))
                )
            ).exclude(frequency='per_booking').aggregate(total=Sum('amount'))['total'] or Decimal(0)
            
            hist_sum = FinancialHistory.objects.filter(property=prop, year=year).aggregate(
                g=Sum('gross_value'), c=Sum('costs')
            )
            
            m_gross = hist_sum['g'] or Decimal(0)
            m_costs = hist_sum['c'] or Decimal(0)

            # Maintenance costs for this year
            maint_costs = Maintenance.objects.filter(
                property=prop,
                status='finished'
            ).filter(
                Q(execution_end_date__year=year) |
                Q(execution_end_date__isnull=True, updated_at__year=year)
            ).aggregate(total=Sum('execution_value'))['total'] or Decimal(0)
            
            # Combine everything
            gross = res_gross + m_gross
            total_costs = res_costs + fixed_costs + m_costs + maint_costs
            
            prop_data['data_by_year'][year] = {
                'gross': float(gross),
                'costs': float(total_costs),
                'net': float(gross - total_costs)
            }
            
        data['properties'].append(prop_data)
        
    return data

def get_operational_stats(user):
    """
    Returns counts for check-ins/outs today per property and global overdue maintenance.
    """
    from django.utils import timezone
    from reservations.models import Reservation
    from maintenance.models import Maintenance
    from properties.models import Property
    from django.db.models import Count, Q
    
    today = timezone.localtime(timezone.now()).date()
    properties = Property.objects.filter(user=user)
    
    property_movements = []
    for prop in properties:
        ins = Reservation.objects.filter(property=prop, start_date=today, is_cancelled=False).count()
        outs = Reservation.objects.filter(property=prop, end_date=today, is_cancelled=False).count()
        
        if ins > 0 or outs > 0:
            property_movements.append({
                'name': prop.name,
                'checkins': ins,
                'checkouts': outs
            })
    
    overdue_maintenance = Maintenance.objects.filter(
        property__user=user,
        status__in=['open', 'budgeting', 'in_progress'],
        end_date__lt=today,
        is_archived=False
    ).count()
    
    return {
        'property_movements': property_movements,
        'overdue_maintenance': overdue_maintenance,
        'total_movements': sum(m['checkins'] + m['checkouts'] for m in property_movements)
    }
