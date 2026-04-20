from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Sum, Q

from .models import Property, PropertyCost, FinancialHistory
from .forms import PropertyForm, PropertyCostForm
from reservations.models import Reservation, ReservationCost

class PropertyDashboardView(LoginRequiredMixin, DetailView):
    model = Property
    template_name = 'properties/property_dashboard.html'
    context_object_name = 'property'

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Financial Stats Logic
        today = timezone.now().date()
        month_reservations = self.object.reservations.filter(
            start_date__month=today.month, 
            start_date__year=today.year
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
        
        return context


class PropertyListView(LoginRequiredMixin, ListView):
    model = Property
    template_name = 'properties/property_list.html'
    context_object_name = 'properties'

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

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
        context['costs_monthly'] = costs.filter(frequency='monthly')
        context['costs_yearly'] = costs.filter(frequency='yearly')
        
        context['cost_form'] = PropertyCostForm()
        
        # Financial Structure Logic: OPTIMIZED with Bulk Fetch
        acquisition_date = self.object.acquisition_date
        today = timezone.now().date()
        
        # 1. Fetch all reservations and their costs in bulk
        reservations = self.object.reservations.all()
        res_data = {} # Key: (month, year), Value: {'gross': D, 'costs': D}
        
        for res in reservations:
            # We use start_date for month/year alignment
            key = (res.start_date.month, res.start_date.year)
            if key not in res_data:
                res_data[key] = {'gross': Decimal(0), 'costs': Decimal(0)}
            res_data[key]['gross'] += res.total_value
            
        # Bulk fetch reservation costs
        all_res_costs = ReservationCost.objects.filter(reservation__in=reservations)
        for rc in all_res_costs:
            key = (rc.reservation.start_date.month, rc.reservation.start_date.year)
            res_data[key]['costs'] += rc.value
            
        # 2. Fetch all monthly property costs in bulk
        prop_costs_data = {} # Key: (month, year), Value: sum
        monthly_costs = self.object.costs.filter(frequency='monthly')
        for pc in monthly_costs:
            if pc.month and pc.year:
                key = (pc.month, pc.year)
                prop_costs_data[key] = prop_costs_data.get(key, Decimal(0)) + pc.amount
                
        # 3. Fetch all manual financial history in bulk
        history_data = {} # Key: (month, year), Value: {'gross': D, 'costs': D}
        histories = self.object.financial_histories.all()
        for h in histories:
            key = (h.month, h.year)
            history_data[key] = {'gross': h.gross_value, 'costs': h.costs}
            
        financial_structure = []
        
        # Iterate from acquisition to today using dictionaries (O(1) lookups)
        curr_year = acquisition_date.year
        curr_month = acquisition_date.month
        
        while curr_year < today.year or (curr_year == today.year and curr_month <= today.month):
            key = (curr_month, curr_year)
            has_reservations = key in res_data
            has_prop_costs = key in prop_costs_data
            
            # Only lock if there are REAL reservations. 
            # Monthly property costs shouldn't lock the row, so users can still inform gross revenue.
            is_locked = has_reservations
            
            gross = Decimal(0)
            costs_sum = Decimal(0)
            
            if is_locked:
                gross = res_data[key]['gross']
                costs_sum = res_data[key]['costs']
                
                # Add monthly costs to system costs if they exist
                if has_prop_costs:
                    costs_sum += prop_costs_data[key]
            else:
                # Manual entry mode
                history = history_data.get(key)
                if history:
                    gross = history['gross']
                    costs_sum = history['costs']
                elif has_prop_costs:
                    # Optional: pre-populate costs from property costs if no history exists yet
                    costs_sum = prop_costs_data[key]
            
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
            return self.form_invalid(form)

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

    def get_success_url(self):
        return reverse_lazy('properties:settings', kwargs={'pk': self.object.property.pk})


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
                
                # Security: Check if locked in real-time (has reservations)
                has_res = prop.reservations.filter(start_date__year=y, start_date__month=m).exists()
                
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
        clean = value.replace('R$', '').replace(' ', '')
        
        # In PT-BR (1.234,56):
        # 1. Remove all dots (thousands separator)
        # 2. Replace the comma with a dot (decimal separator)
        clean = clean.replace('.', '').replace(',', '.')
            
        try:
            return Decimal(clean)
        except:
            return Decimal(0)

