from datetime import timedelta, date, datetime, time
import calendar
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _

from properties.models import Property, PropertyCost
from .models import Reservation, ReservationCost, ReservationPayment
from .forms import ReservationForm

class PropertyContextMixin:
    """Provides the property object to the context and ensures ownership."""
    property_object = None

    def get_property(self):
        if not self.property_object:
            self.property_object = get_object_or_404(
                Property, 
                pk=self.kwargs.get('property_pk'), 
                user=self.request.user
            )
        return self.property_object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        property_obj = self.get_property()
        context['property'] = property_obj
        # Add property-level default costs for per-booking frequency
        context['property_costs'] = PropertyCost.objects.filter(
            property=property_obj, 
            frequency='per_booking'
        )
        return context

class ReservationListView(LoginRequiredMixin, PropertyContextMixin, ListView):
    model = Reservation
    template_name = 'reservations/reservation_list_v2.html'
    context_object_name = 'reservations'

    def get_queryset(self):
        return Reservation.objects.filter(property=self.get_property())

class ReservationCreateView(LoginRequiredMixin, PropertyContextMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'reservations/reservation_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['property_obj'] = self.get_property()
        return kwargs

    def form_valid(self, form):
        form.instance.property = self.get_property()
        response = super().form_valid(form)
        
        # Save reservation costs and payments
        self.save_reservation_costs(self.object)
        self.save_reservation_payments(self.object)
        
        messages.success(self.request, _("Reserva cadastrada com sucesso!"))
        return response

    def save_reservation_costs(self, reservation):
        descriptions = self.request.POST.getlist('cost_description[]')
        values = self.request.POST.getlist('cost_value[]')
        property_cost_ids = self.request.POST.getlist('cost_property_id[]')
        provider_ids = self.request.POST.getlist('cost_provider_id[]')
        
        # Clear existing costs if any (for updates)
        reservation.costs.all().delete()
        
        from decimal import Decimal
        from properties.models import ServiceProvider
        for i in range(len(descriptions)):
            if descriptions[i]:
                try:
                    # Clean currency formatting
                    val_str = values[i].replace('R$', '').replace('.', '').replace(',', '.').strip()
                    val = Decimal(val_str)
                    
                    prop_cost = None
                    if i < len(property_cost_ids) and property_cost_ids[i]:
                        prop_cost = PropertyCost.objects.filter(pk=property_cost_ids[i]).first()
                    
                    provider = None
                    if i < len(provider_ids) and provider_ids[i]:
                        provider = ServiceProvider.objects.filter(pk=provider_ids[i]).first()
                    elif prop_cost:
                        provider = prop_cost.provider
                    
                    ReservationCost.objects.create(
                        reservation=reservation,
                        description=descriptions[i],
                        value=val,
                        property_cost=prop_cost,
                        provider=provider
                    )
                except (ValueError, IndexError, ArithmeticError):
                    continue

    def save_reservation_payments(self, reservation):
        descriptions = self.request.POST.getlist('payment_description[]')
        values = self.request.POST.getlist('payment_value[]')
        dates = self.request.POST.getlist('payment_date[]')
        
        reservation.payments.all().delete()
        
        from decimal import Decimal
        for i in range(len(descriptions)):
            if descriptions[i]:
                try:
                    val_str = values[i].replace('R$', '').replace('.', '').replace(',', '.').strip()
                    val = Decimal(val_str)
                    
                    date_val = dates[i] if i < len(dates) and dates[i] else None
                    if not date_val:
                        from django.utils import timezone
                        date_val = timezone.now().date()
                    
                    ReservationPayment.objects.create(
                        reservation=reservation,
                        description=descriptions[i],
                        value=val,
                        payment_date=date_val
                    )
                except (ValueError, IndexError, ArithmeticError):
                    continue

    def get_success_url(self):
        return reverse('reservations:list', kwargs={'property_pk': self.kwargs.get('property_pk')})

class ReservationUpdateView(LoginRequiredMixin, PropertyContextMixin, UpdateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'reservations/reservation_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['property_obj'] = self.get_property()
        return kwargs

    def get_queryset(self):
        return Reservation.objects.filter(property__user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reservation_costs'] = self.object.costs.all()
        context['reservation_payments'] = self.object.payments.all()
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Save reservation costs and payments (using same logic as CreateView)
        create_view = ReservationCreateView()
        create_view.request = self.request
        create_view.save_reservation_costs(self.object)
        create_view.save_reservation_payments(self.object)
        
        messages.success(self.request, _("Reserva atualizada com sucesso!"))
        return response

    def get_success_url(self):
        return reverse('reservations:list', kwargs={'property_pk': self.kwargs.get('property_pk')})

class ReservationDeleteView(LoginRequiredMixin, PropertyContextMixin, DeleteView):
    model = Reservation
    template_name = 'reservations/reservation_confirm_delete.html'

    def get_queryset(self):
        return Reservation.objects.filter(property__user=self.request.user)

    def get_success_url(self):
        messages.success(self.request, _("Reserva removida com sucesso!"))
        return reverse('reservations:list', kwargs={'property_pk': self.kwargs.get('property_pk')})

from django.views import View

class ReservationToggleCancelView(LoginRequiredMixin, View):
    def post(self, request, property_pk, pk):
        reservation = get_object_or_404(Reservation, pk=pk, property__pk=property_pk, property__user=request.user)
        reservation.is_cancelled = not reservation.is_cancelled
        reservation.save()
        
        status = _("cancelada") if reservation.is_cancelled else _("restaurada")
        messages.success(request, _(f"Reserva {status} com sucesso!"))
        
        return redirect('reservations:list', property_pk=property_pk)

@login_required
def search_clients(request, property_pk):
    q = request.GET.get('q', '')
    if len(q) < 2:
        return JsonResponse([], safe=False)
    
    # We search for unique client names in existing reservations
    # Filtering by the user's properties to ensure privacy
    clients = Reservation.objects.filter(
        property__user=request.user,
        client_name__icontains=q
    ).values_list('client_name', flat=True).distinct()[:10]
    
    return JsonResponse(list(clients), safe=False)

@login_required
def send_whatsapp_reservation(request, property_pk, pk):
    """
    View para gatilhar o envio de boas-vindas e link de check-in via WhatsApp.
    """
    from .services.evolution_api import EvolutionService
    
    reservation = get_object_or_404(Reservation, pk=pk, property__pk=property_pk, property__user=request.user)
    
    # Usa a instância do proprietário da propriedade
    service = EvolutionService(user=reservation.property.user)
    success, message = service.enviar_link_checkin(reservation.id)
    
    if success:
        reservation.welcome_message_sent = True
        reservation.save(update_fields=['welcome_message_sent'])
        messages.success(request, message)
    else:
        messages.error(request, message)
    
    return redirect('reservations:list', property_pk=property_pk)


class ReservationCalendarView(LoginRequiredMixin, PropertyContextMixin, ListView):
    model = Reservation
    template_name = 'reservations/reservation_calendar.html'
    context_object_name = 'reservations'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        property_obj = self.get_property()
        
        # 1. Get Month/Year from GET
        today = date.today()
        month = int(self.request.GET.get('month', today.month))
        year = int(self.request.GET.get('year', today.year))
        
        # Ensure month is within 1-12
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
            
        context['current_month'] = month
        context['current_year'] = year
        context['month_name'] = self._get_month_name(month)
        
        # 2. Navigation logic
        prev_month = month - 1
        prev_year = year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1
            
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
            
        context['prev_month'] = prev_month
        context['prev_year'] = prev_year
        context['next_month'] = next_month
        context['next_year'] = next_year
        
        # 3. Calendar Grid Generation
        cal = calendar.Calendar(firstweekday=6) # Sunday start
        month_days = cal.monthdatescalendar(year, month)
        
        # 4. Fetch Reservations for this month (plus some padding)
        start_of_grid = month_days[0][0]
        end_of_grid = month_days[-1][-1]
        
        reservations = Reservation.objects.filter(
            property=property_obj,
            is_cancelled=False,
            start_date__lte=end_of_grid,
            end_date__gte=start_of_grid
        ).order_by('start_date')
        
        # 4.5. Fetch Payments for this month
        payments_qs = property_obj.costs.filter(
            payment_date__range=(start_of_grid, end_of_grid)
        ).select_related('provider')
        
        # Organize payments by date
        payment_days = {} # date -> list of payments
        for p in payments_qs:
            if p.payment_date not in payment_days:
                payment_days[p.payment_date] = []
            payment_days[p.payment_date].append({
                'name': p.name,
                'amount': p.amount,
                'description': p.description
            })
        
        # 5. Prepare Grid Data
        grid = []
        for week in month_days:
            week_data = []
            for day in week:
                day_reservations = []
                for res in reservations:
                    if res.start_date <= day <= res.end_date:
                        is_start = res.start_date == day
                        is_end = res.end_date == day
                        
                        # Calculate percentages for the bar
                        start_pct = 0
                        end_pct = 100
                        
                        if is_start:
                            t = res.checkin_time or property_obj.default_checkin_time or time(14, 0)
                            start_pct = (t.hour * 60 + t.minute) / 14.4 # (h*60+m) / 1440 * 100
                        
                        if is_end:
                            t = res.checkout_time or property_obj.default_checkout_time or time(11, 0)
                            end_pct = (t.hour * 60 + t.minute) / 14.4
                            
                        day_reservations.append({
                            'id': res.id,
                            'client_name': res.client_name,
                            'is_start': is_start,
                            'is_end': is_end,
                            'start_pct': start_pct,
                            'end_pct': end_pct,
                            'width_pct': max(end_pct - start_pct, 5), # Minimum 5% width
                            'color': self._get_color_for_reservation(res.id)
                        })
                
                week_data.append({
                    'date': day,
                    'is_current_month': day.month == month,
                    'is_today': day == today,
                    'payments': payment_days.get(day, []),
                    'has_payment': day in payment_days,
                    'reservations': day_reservations
                })
            grid.append(week_data)
            
        context['calendar_grid'] = grid
        context['day_names'] = [_('Dom'), _('Seg'), _('Ter'), _('Qua'), _('Qui'), _('Sex'), _('Sáb')]
        
        return context

    def _get_month_name(self, month_index):
        meses = [
            _('Janeiro'), _('Fevereiro'), _('Março'), _('Abril'), 
            _('Maio'), _('Junho'), _('Julho'), _('Agosto'), 
            _('Setembro'), _('Outubro'), _('Novembro'), _('Dezembro')
        ]
        return meses[month_index - 1]

    def _get_color_for_reservation(self, res_id):
        # Professional blue for a sober look
        return '#3b82f6'
