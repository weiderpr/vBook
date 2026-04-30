import calendar
from datetime import timedelta, date
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, JsonResponse
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Sum, Q

from .models import Property, PropertyCost, FinancialHistory, Service, ServiceProvider
from .utils import get_property_stats
from .forms import PropertyForm, PropertyCostForm, PropertyInstructionsForm, PropertyAuthorizationForm, ServiceProviderForm
from reservations.models import Reservation, ReservationCost

class PropertyInstructionsUpdateView(LoginRequiredMixin, UpdateView):
    model = Property
    form_class = PropertyInstructionsForm
    template_name = 'properties/property_instructions_form.html'
    context_object_name = 'property'

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_item'] = 'instructions'
        return context

    def get_success_url(self):
        messages.success(self.request, _("Instruções de reserva atualizadas com sucesso!"))
        return reverse_lazy('properties:dashboard', kwargs={'pk': self.object.pk})

class PropertyAuthorizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Property
    form_class = PropertyAuthorizationForm
    template_name = 'properties/property_authorization_form.html'
    context_object_name = 'property'

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_item'] = 'authorization'
        context['editor_version'] = 'v3' # Force cache refresh
        return context

    def get_success_url(self):
        messages.success(self.request, _("Modelo de autorização atualizado com sucesso!"))
        return reverse_lazy('properties:authorization', kwargs={'pk': self.object.pk})

class PropertyDashboardView(LoginRequiredMixin, DetailView):
    model = Property
    template_name = 'properties/property_dashboard.html'
    context_object_name = 'property'

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Financial Stats Logic
        today = timezone.localtime(timezone.now()).date()
        month_reservations = self.object.reservations.filter(
            end_date__month=today.month, 
            end_date__year=today.year,
            is_cancelled=False
        )
        
        # Portuguese month names mapping
        meses = [
            _('Janeiro'), _('Fevereiro'), _('Março'), _('Abril'), 
            _('Maio'), _('Junho'), _('Julho'), _('Agosto'), 
            _('Setembro'), _('Outubro'), _('Novembro'), _('Dezembro')
        ]
        
        context['month_name'] = meses[today.month - 1]
        context['month_count'] = month_reservations.count()
        context['month_revenue'] = month_reservations.aggregate(Sum('total_value'))['total_value__sum'] or 0
        
        # Idle Days Logic (Nights without guests)
        unused_weekday, total_days = calendar.monthrange(today.year, today.month)
        month_start = date(today.year, today.month, 1)
        month_end = date(today.year, today.month, total_days)
        
        # Get reservations that overlap with this month
        all_res = self.object.reservations.filter(
            start_date__lte=month_end,
            end_date__gt=month_start,
            is_cancelled=False
        ).values('start_date', 'end_date')
        
        reserved_nights = set()
        for res in all_res:
            s = max(res['start_date'], month_start)
            e = min(res['end_date'], month_end + timedelta(days=1))
            curr = s
            while curr < e:
                if curr.month == today.month:
                    reserved_nights.add(curr)
                curr += timedelta(days=1)
        
        context['idle_days'] = total_days - len(reserved_nights)
        
        return context


class PropertyListView(LoginRequiredMixin, ListView):
    model = Property
    template_name = 'properties/property_list.html'
    context_object_name = 'properties'

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        properties_with_stats = []
        for prop in context['properties']:
            stats = get_property_stats(prop)
            properties_with_stats.append({
                'obj': prop,
                'stats': stats
            })
        context['properties_data'] = properties_with_stats
        return context

class PropertyCreateView(LoginRequiredMixin, CreateView):
    model = Property
    form_class = PropertyForm
    template_name = 'properties/property_form.html'
    success_url = reverse_lazy('properties:list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, _("Propriedade cadastrada com sucesso!"))
        return super().form_valid(form)

class PropertyUpdateView(LoginRequiredMixin, UpdateView):
    model = Property
    form_class = PropertyForm
    template_name = 'properties/property_form.html'
    context_object_name = 'property'

    def get_success_url(self):
        return reverse_lazy('properties:dashboard', kwargs={'pk': self.object.pk})

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Propriedade atualizada com sucesso!"))
        return super().form_valid(form)

class PropertyDeleteView(LoginRequiredMixin, DeleteView):
    model = Property
    template_name = 'properties/property_confirm_delete.html'
    success_url = reverse_lazy('properties:list')
    context_object_name = 'property'

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Propriedade removida com sucesso!"))
        return super().delete(request, *args, **kwargs)

class PropertySettingsView(LoginRequiredMixin, DetailView):
    model = Property
    template_name = 'properties/property_settings.html'
    context_object_name = 'property'

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_item'] = 'settings'
        
        costs = self.object.costs.all()
        context['costs_booking'] = costs.filter(frequency='per_booking')
        
        # Merge Property Costs and Finished Maintenances for the payments list
        from maintenance.models import Maintenance
        maintenances = Maintenance.objects.filter(property=self.object, status='finished').order_by('-execution_end_date')[:20]
        
        # Prepare a unified list for display
        unified_payments = []
        for pc in costs.exclude(frequency='per_booking').order_by('-payment_date', '-id')[:20]:
            unified_payments.append({
                'pk': pc.pk,
                'date': pc.payment_date,
                'name': pc.name,
                'amount': pc.amount,
                'type': 'cost',
                'description': pc.description,
                'amount_type': pc.amount_type,
                'recipient': pc.recipient,
                'frequency': pc.frequency,
                'month': pc.month,
                'year': pc.year,
                'provider_id': pc.provider_id,
                'provider_name': pc.provider.name if pc.provider else '',
                'provider_photo': pc.provider.photo.url if pc.provider and pc.provider.photo else ''
            })
        for m in maintenances:
            m_date = m.execution_end_date
            if not m_date:
                m_date = m.updated_at.date() if hasattr(m.updated_at, 'date') else m.updated_at
            
            unified_payments.append({
                'pk': m.pk,
                'date': m_date,
                'name': f"{_('Manutenção')}: {m.title}",
                'amount': m.execution_value or Decimal(0),
                'type': 'maintenance',
                'description': f"{_('Prestador')}: {m.provider.name if m.provider else _('N/A')}",
                'm_id': m.id,
                'p_id': m.property.id
            })
        
        # Sort unified list by date descending
        unified_payments.sort(key=lambda x: (x['date'] or date.min), reverse=True)
        context['costs_payments'] = unified_payments[:20]
        
        context['cost_form'] = PropertyCostForm()
        
        # Financial Structure Logic: OPTIMIZED with Bulk Fetch
        acquisition_date = self.object.acquisition_date
        today = timezone.localtime(timezone.now()).date()
        
        # 1. Fetch all reservations and their costs in bulk (EXCLUDING CANCELLED)
        reservations = self.object.reservations.filter(is_cancelled=False)
        res_data = {} # Key: (month, year), Value: {'gross': D, 'costs': D}
        
        for res in reservations:
            # We use end_date (Checkout) for month/year alignment
            key = (res.end_date.month, res.end_date.year)
            if key not in res_data:
                res_data[key] = {'gross': Decimal(0), 'costs': Decimal(0)}
            res_data[key]['gross'] += res.total_value
            
        # Bulk fetch reservation costs
        all_res_costs = ReservationCost.objects.filter(reservation__in=reservations)
        for rc in all_res_costs:
            key = (rc.reservation.end_date.month, rc.reservation.end_date.year)
            res_data[key]['costs'] += rc.value
            
        # 2. Fetch all other property costs in bulk
        prop_costs_data = {} # Key: (month, year), Value: sum
        other_costs = self.object.costs.exclude(frequency='per_booking')
        for pc in other_costs:
            m, y = None, None
            if pc.payment_date:
                m, y = pc.payment_date.month, pc.payment_date.year
            elif pc.month and pc.year:
                m, y = pc.month, pc.year
                
            if m and y:
                key = (m, y)
                prop_costs_data[key] = prop_costs_data.get(key, Decimal(0)) + pc.amount
        
        # 2.5 Fetch all finished maintenances for financial structure
        maint_data = {} # Key: (month, year), Value: sum
        finished_maints = Maintenance.objects.filter(property=self.object, status='finished')
        for m in finished_maints:
            dt = m.execution_end_date or m.updated_at
            if dt:
                key = (dt.month, dt.year)
                maint_data[key] = maint_data.get(key, Decimal(0)) + (m.execution_value or Decimal(0))
                
        # 3. Fetch all manual financial history in bulk
        history_data = {} # Key: (month, year), Value: {'gross': D, 'costs': D}
        histories = self.object.financial_histories.all()
        for h in histories:
            key = (h.month, h.year)
            history_data[key] = {'gross': h.gross_value, 'costs': h.costs}
            
        financial_structure = []
        
        # Iterate from acquisition to today
        curr_year = acquisition_date.year
        curr_month = acquisition_date.month
        
        while curr_year < today.year or (curr_year == today.year and curr_month <= today.month):
            key = (curr_month, curr_year)
            has_reservations = key in res_data
            has_prop_costs = key in prop_costs_data
            
            is_locked = has_reservations
            
            gross = Decimal(0)
            costs_sum = Decimal(0)
            
            if is_locked:
                gross = res_data[key]['gross']
                costs_sum = res_data[key]['costs']
                if has_prop_costs:
                    costs_sum += prop_costs_data[key]
                if key in maint_data:
                    costs_sum += maint_data[key]
            else:
                history = history_data.get(key)
                if history:
                    gross = history['gross']
                    costs_sum = history['costs']
                else:
                    if has_prop_costs:
                        costs_sum += prop_costs_data[key]
                    if key in maint_data:
                        costs_sum += maint_data[key]
            
            net = gross - costs_sum
            margin = (net / gross * 100) if gross > 0 else Decimal(0)
            
            financial_structure.append({
                'year': curr_year,
                'month': curr_month,
                'month_name': self._get_month_name(curr_month),
                'gross': gross,
                'costs': costs_sum,
                'net': net,
                'margin': margin,
                'is_locked': is_locked
            })
            
            # Next month
            if curr_month == 12:
                curr_month = 1
                curr_year += 1
            else:
                curr_month += 1
        
        context['financial_structure'] = reversed(financial_structure)
        
        # 5. Build yearly_structure
        yearly_aggr = {}
        # Use the non-reversed list for aggregation
        for item in financial_structure:
            y = item['year']
            if y not in yearly_aggr:
                yearly_aggr[y] = {'gross': Decimal(0), 'costs': Decimal(0), 'net': Decimal(0)}
            yearly_aggr[y]['gross'] += item['gross']
            yearly_aggr[y]['costs'] += item['costs']
            yearly_aggr[y]['net'] += item['net']
            
        yearly_structure = []
        for y, data in yearly_aggr.items():
            margin = (data['net'] / data['gross'] * 100) if data['gross'] > 0 else Decimal(0)
            yearly_structure.append({
                'year': y,
                'gross': data['gross'],
                'costs': data['costs'],
                'net': data['net'],
                'margin': margin
            })
            
        context['yearly_structure'] = sorted(yearly_structure, key=lambda x: x['year'], reverse=True)
        
        # 6. Grand totals for yearly structure
        total_gross = Decimal(0)
        total_costs = Decimal(0)
        total_net = Decimal(0)
        for item in yearly_structure:
            total_gross += item['gross']
            total_costs += item['costs']
            total_net += item['net']
        
        total_margin = (total_net / total_gross * 100) if total_gross > 0 else Decimal(0)
        
        context['yearly_totals'] = {
            'gross': total_gross,
            'costs': total_costs,
            'net': total_net,
            'margin': total_margin
        }
        
        return context

    def _get_month_name(self, month_index):
        meses = [
            _('Janeiro'), _('Fevereiro'), _('Março'), _('Abril'), 
            _('Maio'), _('Junho'), _('Julho'), _('Agosto'), 
            _('Setembro'), _('Outubro'), _('Novembro'), _('Dezembro')
        ]
        return meses[month_index - 1]



class PropertyCostCreateView(LoginRequiredMixin, CreateView):
    model = PropertyCost
    form_class = PropertyCostForm

    def form_valid(self, form):
        property_id = self.kwargs.get('pk')
        try:
            prop = Property.objects.get(pk=property_id, user=self.request.user)
            form.instance.property = prop
            messages.success(self.request, _("Custo adicionado com sucesso!"))
            return super().form_valid(form)
        except Property.DoesNotExist:
            messages.error(self.request, _("Propriedade não encontrada."))
            return redirect('properties:list')

    def form_invalid(self, form):
        property_id = self.kwargs.get('pk')
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{form.fields[field].label}: {error}")
        return redirect('properties:settings', pk=property_id)

    def get_success_url(self):
        return reverse_lazy('properties:settings', kwargs={'pk': self.kwargs.get('pk')})


class PropertyCostDeleteView(LoginRequiredMixin, DeleteView):
    model = PropertyCost

    def get_queryset(self):
        return PropertyCost.objects.filter(property__user=self.request.user)

    def get_success_url(self):
        return reverse_lazy('properties:settings', kwargs={'pk': self.object.property.pk})

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Custo removido com sucesso!"))
        return super().delete(request, *args, **kwargs)


class PropertyCostUpdateView(LoginRequiredMixin, UpdateView):
    model = PropertyCost
    form_class = PropertyCostForm

    def get_queryset(self):
        return PropertyCost.objects.filter(property__user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Custo atualizado com sucesso!"))
        return super().form_valid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{form.fields[field].label}: {error}")
        return redirect('properties:settings', pk=self.get_object().property.pk)

    def get_success_url(self):
        return reverse_lazy('properties:settings', kwargs={'pk': self.object.property.pk})


class PropertyCostListAPIView(LoginRequiredMixin, View):
    def get(self, request, pk):
        prop = get_object_or_404(Property, pk=pk, user=request.user)
        try:
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 20))
        except (ValueError, TypeError):
            page = 1
            limit = 20
            
        offset = (page - 1) * limit
        
        all_payments = prop.costs.exclude(frequency='per_booking').order_by('-payment_date', '-id')
        costs = all_payments[offset:offset+limit]
        total_count = all_payments.count()
        
        data = []
        for cost in costs:
            data.append({
                'id': cost.pk,
                'name': cost.name,
                'description': cost.description or '',
                'amount': float(cost.amount),
                'amount_type': cost.amount_type,
                'recipient': cost.recipient,
                'frequency': cost.frequency,
                'payment_date': cost.payment_date.strftime('%Y-%m-%d') if cost.payment_date else None,
                'payment_date_display': cost.payment_date.strftime('%d/%m/%Y') if cost.payment_date else '',
                'month': cost.month,
                'year': cost.year,
                'period_display': cost.get_period_display(),
                'recipient_display': cost.get_recipient_display(),
                'provider_id': cost.provider_id,
                'provider_name': cost.provider.name if cost.provider else '',
                'provider_photo': cost.provider.photo.url if cost.provider and cost.provider.photo else None,
            })
            
        return JsonResponse({
            'results': data,
            'has_more': total_count > offset + limit
        })


class PropertyFinancialHistorySaveView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        property_id = self.kwargs.get('pk')
        prop = get_object_or_404(Property, pk=property_id, user=request.user)
            
        months = request.POST.getlist('history_month[]')
        years = request.POST.getlist('history_year[]')
        gross_values = request.POST.getlist('history_gross[]')
        costs_values = request.POST.getlist('history_costs[]')
        
        for i in range(len(months)):
            try:
                # Clean year/month from any potential localization dots
                m_str = months[i].replace('.', '').replace(',', '')
                y_str = years[i].replace('.', '').replace(',', '')
                m = int(m_str)
                y = int(y_str)
                
                # Security: Check if locked in real-time (has non-cancelled reservations)
                # We use end_date (checkout) to match the accounting logic used in the UI and reports
                has_res = prop.reservations.filter(end_date__year=y, end_date__month=m, is_cancelled=False).exists()
                
                if not has_res:
                    gross_clean = self._clean_currency(gross_values[i])
                    costs_clean = self._clean_currency(costs_values[i])
                    
                    FinancialHistory.objects.update_or_create(
                        property=prop,
                        month=m,
                        year=y,
                        defaults={
                            'gross_value': gross_clean,
                            'costs': costs_clean,
                            'net_value': gross_clean - costs_clean
                        }
                    )
            except (ValueError, IndexError):
                continue
                
        messages.success(request, _("Histórico financeiro atualizado com sucesso!"))
        return redirect('properties:settings', pk=prop.pk)

    def _clean_currency(self, value):
        if not value: return Decimal(0)
        
        # Remove currency symbol and spaces
        clean = str(value).replace('R$', '').replace(' ', '')
        
        # In PT-BR (1.234,56):
        # We assume the last comma or dot is the decimal separator if there's only one.
        # If there are both, the comma is decimal.
        if ',' in clean:
            clean = clean.replace('.', '').replace(',', '.')
        # If there's a dot but no comma, it's ambiguous, but in our system (VMasker) 
        # a dot without a comma is likely a thousand separator (e.g. 1.000)
        # However, we'll try to be safe.
        elif '.' in clean:
            # Check if it looks like a thousand separator (3 digits after dot)
            parts = clean.split('.')
            if len(parts[-1]) == 3:
                clean = clean.replace('.', '')
            
        try:
            return Decimal(clean)
        except:
            return Decimal(0)


class ServiceProviderListView(LoginRequiredMixin, ListView):
    model = ServiceProvider
    template_name = 'properties/service_provider_list.html'
    context_object_name = 'providers'

    def get_queryset(self):
        queryset = ServiceProvider.objects.filter(user=self.request.user)
        name_query = self.request.GET.get("name")
        if name_query:
            queryset = queryset.filter(name__icontains=name_query)
        service_id = self.request.GET.get("service")
        if service_id:
            queryset = queryset.filter(services__id=service_id).distinct()
        # Sort by financial balance: Most negative (highest debt) first
        providers_list = sorted(list(queryset), key=lambda p: p.financial_balance)
        return providers_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_item"] = "providers"
        # Services are now global
        context["services"] = Service.objects.all()
        context["current_filters"] = {
            "name": self.request.GET.get("name", ""),
            "service": self.request.GET.get("service", "")
        }
        return context

class ServiceProviderSearchView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '')
        providers = ServiceProvider.objects.filter(
            user=request.user,
            name__icontains=q
        )[:10]
        
        results = []
        for p in providers:
            results.append({
                'id': p.id,
                'name': p.name,
                'photo_url': p.photo.url if p.photo else None
            })
        return JsonResponse(results, safe=False)

class ServiceProviderCreateView(LoginRequiredMixin, CreateView):
    model = ServiceProvider
    form_class = ServiceProviderForm
    template_name = 'properties/service_provider_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_item"] = "providers"
        return context

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, _("Prestador cadastrado com sucesso!"))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('properties:provider_list')

class ServiceProviderUpdateView(LoginRequiredMixin, UpdateView):
    model = ServiceProvider
    form_class = ServiceProviderForm
    template_name = 'properties/service_provider_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_queryset(self):
        return ServiceProvider.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_item"] = "providers"
        return context

    def form_valid(self, form):
        messages.success(self.request, _("Prestador atualizado com sucesso!"))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('properties:provider_list')

class ServiceProviderDeleteView(LoginRequiredMixin, DeleteView):
    model = ServiceProvider
    template_name = 'properties/serviceprovider_confirm_delete.html'

    def get_queryset(self):
        return ServiceProvider.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_item"] = "providers"
        return context

    def get_success_url(self):
        return reverse_lazy('properties:provider_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Prestador removido com sucesso!"))
        return super().delete(request, *args, **kwargs)

class ServiceProviderFinancialMovementsView(LoginRequiredMixin, View):
    def get(self, request, pk):
        provider = get_object_or_404(ServiceProvider, pk=pk, user=request.user)
        
        from maintenance.models import Maintenance
        from reservations.models import ReservationCost
        
        movements = []
        
        # 1. Debits: Reservation Costs
        res_costs = ReservationCost.objects.filter(
            provider=provider, 
            is_completed=True
        ).select_related('reservation', 'reservation__property')
        
        for rc in res_costs:
            movements.append({
                'type': 'debit',
                'category': _('Reserva'),
                'description': f"{rc.description} - {rc.reservation.property.name} ({rc.reservation.client_name})",
                'date': rc.completed_at.strftime('%Y-%m-%d') if rc.completed_at else rc.created_at.strftime('%Y-%m-%d'),
                'created_at': rc.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'value': float(rc.value)
            })
            
        # 2. Debits: Finished Maintenances
        maint_finished = Maintenance.objects.filter(
            provider=provider, 
            status='finished'
        ).select_related('property')
        
        for m in maint_finished:
            movements.append({
                'type': 'debit',
                'category': _('Manutenção'),
                'description': f"{m.title} - {m.property.name}",
                'date': m.execution_end_date.strftime('%Y-%m-%d') if m.execution_end_date else m.updated_at.strftime('%Y-%m-%d'),
                'created_at': m.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'value': float(m.execution_value) if m.execution_value else 0
            })
            
        # 3. Credits: Payments made
        from .models import ProviderPayment
        payments = provider.payments.all()
        for p in payments:
            movements.append({
                'type': 'credit',
                'category': _('Pagamento'),
                'description': p.observations or _("Liquidação de Saldo"),
                'date': p.date.strftime('%Y-%m-%d'),
                'created_at': p.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'value': float(p.value)
            })
            
        # 4. Debits: Fixed Property Costs
        prop_costs = provider.property_costs.exclude(frequency='per_booking').select_related('property')
        for pc in prop_costs:
            movements.append({
                'type': 'debit',
                'category': _('Custo Fixo'),
                'description': f"{pc.name} - {pc.property.name}",
                'date': pc.payment_date.strftime('%Y-%m-%d') if pc.payment_date else pc.created_at.strftime('%Y-%m-%d'),
                'created_at': pc.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'value': float(pc.amount)
            })
            
        # Sort by date descending, and credits first on same day, then by created_at
        movements.sort(key=lambda x: (x['date'], x['type'] == 'credit', x['created_at']), reverse=True)
        
        # Pagination (20 per page)
        try:
            page = int(request.GET.get('page', 1))
        except (ValueError, TypeError):
            page = 1
            
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_movements = movements[start:end]
        has_more = len(movements) > end
        
        return JsonResponse({
            'provider_name': provider.name,
            'balance': float(provider.financial_balance),
            'movements': paginated_movements,
            'has_more': has_more,
            'page': page
        })

class ServiceProviderAddPaymentView(LoginRequiredMixin, View):
    def post(self, request, pk):
        provider = get_object_or_404(ServiceProvider, pk=pk, user=request.user)
        from .models import ProviderPayment
        
        try:
            val_str = request.POST.get('value', '0').replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
            value = Decimal(val_str)
            date_str = request.POST.get('date')
            observations = request.POST.get('observations', '')
            
            if value <= 0:
                return JsonResponse({'status': 'error', 'message': _("O valor deve ser maior que zero.")}, status=400)
                
            payment = ProviderPayment.objects.create(
                provider=provider,
                user=request.user,
                date=date_str or timezone.now().date(),
                value=value,
                observations=observations
            )
            
            return JsonResponse({
                'status': 'success', 
                'balance': float(provider.financial_balance),
                'message': _("Pagamento registrado com sucesso!")
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


class ServiceProviderPublicView(View):
    def get(self, request, token):
        provider = get_object_or_404(ServiceProvider, access_token=token)
        # Only show services that are NOT completed and NOT cancelled
        costs = provider.reservation_costs.filter(
            is_completed=False, 
            reservation__is_cancelled=False
        ).select_related('reservation', 'reservation__property').order_by('reservation__property__name', '-reservation__end_date')
        
        # Calculate the first day of the previous month to limit history
        now = timezone.now()
        first_day_current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        first_day_previous = (first_day_current - timedelta(days=1)).replace(day=1)

        # Fetch completed costs for the history section, limited to current and previous month, excluding cancelled
        completed_costs = provider.reservation_costs.filter(
            is_completed=True,
            reservation__is_cancelled=False,
            completed_at__gte=first_day_previous
        ).select_related('reservation', 'reservation__property').order_by('reservation__property__id', '-completed_at')
        
        # Fetch next service for each property (Home view), excluding cancelled
        active_costs_for_home = provider.reservation_costs.filter(
            is_completed=False,
            reservation__is_cancelled=False
        ).select_related('reservation', 'reservation__property').order_by('reservation__start_date')
        next_services = []
        seen_properties = set()
        for cost in active_costs_for_home:
            if cost.reservation.property_id not in seen_properties:
                next_services.append(cost)
                seen_properties.add(cost.reservation.property_id)

        return render(request, "properties/service_provider_public.html", {
            "provider": provider,
            "costs": costs,
            "completed_costs": completed_costs,
            "next_services": next_services
        })

    def post(self, request, token):
        provider = get_object_or_404(ServiceProvider, access_token=token)
        name = request.POST.get("name")
        phone = request.POST.get("phone")
        cpf = request.POST.get("cpf")
        photo = request.FILES.get("photo")
        theme = request.POST.get("theme")
        
        if name: provider.name = name
        if phone: provider.phone = phone
        if cpf: provider.cpf = cpf
        if photo: provider.photo = photo
        if theme: provider.theme = theme
        
        provider.save()
        messages.success(request, _("Perfil atualizado com sucesso!"))
        return redirect("properties:provider_public", token=token)

class ServiceProviderCompleteServiceView(View):
    def post(self, request, token, cost_id):
        provider = get_object_or_404(ServiceProvider, access_token=token)
        cost = get_object_or_404(ReservationCost, pk=cost_id, provider=provider)
        
        cost.is_completed = True
        cost.completed_at = timezone.now()
        cost.save()
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
            
        return redirect("properties:provider_public", token=token)

class ServiceProviderCancelCompletionView(View):
    def post(self, request, token, cost_id):
        provider = get_object_or_404(ServiceProvider, access_token=token)
        cost = get_object_or_404(ReservationCost, pk=cost_id, provider=provider)
        
        cost.is_completed = False
        cost.completed_at = None
        cost.save()
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
            
        return redirect("properties:provider_public", token=token)


class PropertyReportsView(LoginRequiredMixin, DetailView):
    model = Property
    template_name = 'properties/property_reports.html'
    context_object_name = 'property'

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_item'] = 'reports'
        
        # 1. Handle Year Selection
        today = timezone.localtime(timezone.now()).date()
        selected_year = self.request.GET.get('year')
        try:
            if selected_year:
                selected_year = str(selected_year).replace('.', '').replace(',', '')
            selected_year = int(selected_year)
        except (TypeError, ValueError):
            selected_year = today.year
            
        context['selected_year'] = selected_year
        
        # Available years for selector (from acquisition to today)
        acquisition_date = self.object.acquisition_date or (timezone.now().date() - timedelta(days=365))
        context['years_range'] = range(acquisition_date.year, today.year + 1)
        
        # 2. Build months list for the SELECTED YEAR
        months_list = []
        for m in range(1, 13):
            months_list.append({
                'month': m,
                'year': selected_year,
                'name': self._get_month_name(m),
                'key': (m, selected_year)
            })
        
        # 3. Data containers
        costs_by_name = {} # { "Cleaning": { 'values': {(m,y): val}, 'total': T } }
        monthly_revenue = {} # { (m,y): val }
        monthly_costs_total = {} # { (m,y): sum }
        
        # 4. Fetch Revenue and Reservation Costs
        reservations = self.object.reservations.filter(is_cancelled=False).prefetch_related('costs')
        for res in reservations:
            # Use end_date as accounting reference
            key = (res.end_date.month, res.end_date.year)
            monthly_revenue[key] = monthly_revenue.get(key, Decimal(0)) + res.total_value
            
            for rc in res.costs.all():
                name = rc.description
                if name not in costs_by_name:
                    costs_by_name[name] = {'values': {}, 'total': Decimal(0)}
                
                costs_by_name[name]['values'][key] = costs_by_name[name]['values'].get(key, Decimal(0)) + rc.value
                costs_by_name[name]['total'] += rc.value
                monthly_costs_total[key] = monthly_costs_total.get(key, Decimal(0)) + rc.value
                
        # 5. Fetch Monthly Property Costs
        prop_costs = self.object.costs.filter(frequency='monthly')
        for pc in prop_costs:
            if pc.month and pc.year:
                key = (pc.month, pc.year)
                name = pc.name
                if name not in costs_by_name:
                    costs_by_name[name] = {'values': {}, 'total': Decimal(0)}
                
                costs_by_name[name]['values'][key] = costs_by_name[name]['values'].get(key, Decimal(0)) + pc.amount
                costs_by_name[name]['total'] += pc.amount
                monthly_costs_total[key] = monthly_costs_total.get(key, Decimal(0)) + pc.amount

        # 5.5 Fetch Finished Maintenances for Reports
        from maintenance.models import Maintenance
        maintenances_rep = Maintenance.objects.filter(property=self.object, status='finished')
        maint_category_name = _("Manutenções")
        for m in maintenances_rep:
            dt = m.execution_end_date or m.updated_at
            if dt:
                # Ensure we handle both date and datetime
                key = (dt.month, dt.year)
                val = m.execution_value or Decimal(0)
                if maint_category_name not in costs_by_name:
                    costs_by_name[maint_category_name] = {'values': {}, 'total': Decimal(0)}
                
                costs_by_name[maint_category_name]['values'][key] = costs_by_name[maint_category_name]['values'].get(key, Decimal(0)) + val
                costs_by_name[maint_category_name]['total'] += val
                monthly_costs_total[key] = monthly_costs_total.get(key, Decimal(0)) + val

        # 6. Fetch Manual Financial History (Optional entries for months without full data)
        histories = self.object.financial_histories.filter(year=selected_year)
        for h in histories:
            key = (h.month, h.year)
            
            # Add to revenue if manual revenue exists
            if h.gross_value > 0:
                monthly_revenue[key] = monthly_revenue.get(key, Decimal(0)) + h.gross_value
            
            # Add to costs if manual costs exist
            if h.costs > 0:
                name = _("Ajustes Manuais")
                if name not in costs_by_name:
                    costs_by_name[name] = {'values': {}, 'total': Decimal(0)}
                
                costs_by_name[name]['values'][key] = costs_by_name[name]['values'].get(key, Decimal(0)) + h.costs
                costs_by_name[name]['total'] += h.costs
                monthly_costs_total[key] = monthly_costs_total.get(key, Decimal(0)) + h.costs

        # 7. Calculate Totals and ROI per month
        summary_rows = {
            'revenue': {'values': {}, 'total': Decimal(0)},
            'costs': {'values': {}, 'total': Decimal(0)},
            'balance': {'values': {}, 'total': Decimal(0)},
            'roi': {'values': {}, 'total': Decimal(0)}
        }
        
        grand_total_revenue = Decimal(0)
        grand_total_costs = Decimal(0)
        
        for m in months_list:
            key = m['key']
            rev = monthly_revenue.get(key, Decimal(0))
            cost = monthly_costs_total.get(key, Decimal(0))
            balance = rev - cost
            roi = (balance / rev * 100) if rev > 0 else Decimal(0)
            
            summary_rows['revenue']['values'][key] = rev
            summary_rows['revenue']['total'] += rev
            
            summary_rows['costs']['values'][key] = cost
            summary_rows['costs']['total'] += cost
            
            summary_rows['balance']['values'][key] = balance
            summary_rows['balance']['total'] += balance
            
            summary_rows['roi']['values'][key] = roi
            
            grand_total_revenue += rev
            grand_total_costs += cost

        # Global ROI (Net Balance / Total Revenue)
        grand_total_roi = (summary_rows['balance']['total'] / grand_total_revenue * 100) if grand_total_revenue > 0 else Decimal(0)
        summary_rows['roi']['total'] = grand_total_roi
        
        context['months'] = months_list
        context['costs_by_name'] = costs_by_name
        context['sorted_cost_names'] = sorted(costs_by_name.keys())
        context['summary_rows'] = summary_rows
        
        return context

    def _get_month_name(self, month_index):
        meses = [
            _('Jan'), _('Fev'), _('Mar'), _('Abr'), 
            _('Mai'), _('Jun'), _('Jul'), _('Ago'), 
            _('Set'), _('Out'), _('Nov'), _('Dez')
        ]
        return meses[month_index - 1]
