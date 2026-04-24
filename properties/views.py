from datetime import timedelta
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
from .forms import PropertyForm, PropertyCostForm, PropertyInstructionsForm, PropertyAuthorizationForm, ServiceForm, ServiceProviderForm
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
        today = timezone.now().date()
        month_reservations = self.object.reservations.filter(
            end_date__month=today.month, 
            end_date__year=today.year
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
            # We use end_date (Checkout) for month/year alignment as requested
            key = (res.end_date.month, res.end_date.year)
            if key not in res_data:
                res_data[key] = {'gross': Decimal(0), 'costs': Decimal(0)}
            res_data[key]['gross'] += res.total_value
            
        # Bulk fetch reservation costs
        all_res_costs = ReservationCost.objects.filter(reservation__in=reservations)
        for rc in all_res_costs:
            key = (rc.reservation.end_date.month, rc.reservation.end_date.year)
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
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_item"] = "providers"
        context["service_form"] = ServiceForm()
        context["services"] = Service.objects.filter(user=self.request.user)
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

class ServiceCreateView(LoginRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        service = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'id': service.id, 'name': service.name})
        messages.success(self.request, _("Serviço cadastrado com sucesso!"))
        return redirect(self.request.META.get('HTTP_REFERER', '/'))

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

class ServiceUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk, user=request.user)
        name = request.POST.get('name')
        if name:
            service.name = name
            service.save()
            return JsonResponse({'status': 'success', 'name': service.name})
        return JsonResponse({'status': 'error', 'message': 'Nome inválido'}, status=400)

class ServiceDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk, user=request.user)
        service.delete()
        return JsonResponse({'status': 'success'})
