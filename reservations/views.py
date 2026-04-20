from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _

from properties.models import Property, PropertyCost
from .models import Reservation, ReservationCost
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

    def form_valid(self, form):
        form.instance.property = self.get_property()
        response = super().form_valid(form)
        
        # Save reservation costs
        self.save_reservation_costs(self.object)
        
        messages.success(self.request, _("Reserva cadastrada com sucesso!"))
        return response

    def save_reservation_costs(self, reservation):
        descriptions = self.request.POST.getlist('cost_description[]')
        values = self.request.POST.getlist('cost_value[]')
        property_cost_ids = self.request.POST.getlist('cost_property_id[]')
        
        # Clear existing costs if any (for updates)
        reservation.costs.all().delete()
        
        from decimal import Decimal
        for i in range(len(descriptions)):
            if descriptions[i]:
                try:
                    # Clean currency formatting
                    val_str = values[i].replace('R$', '').replace('.', '').replace(',', '.').strip()
                    val = Decimal(val_str)
                    
                    prop_cost = None
                    if i < len(property_cost_ids) and property_cost_ids[i]:
                        prop_cost = PropertyCost.objects.filter(pk=property_cost_ids[i]).first()
                    
                    ReservationCost.objects.create(
                        reservation=reservation,
                        description=descriptions[i],
                        value=val,
                        property_cost=prop_cost
                    )
                except (ValueError, IndexError, ArithmeticError):
                    continue

    def get_success_url(self):
        return reverse('reservations:list', kwargs={'property_pk': self.kwargs.get('property_pk')})

class ReservationUpdateView(LoginRequiredMixin, PropertyContextMixin, UpdateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'reservations/reservation_form.html'

    def get_queryset(self):
        return Reservation.objects.filter(property__user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reservation_costs'] = self.object.costs.all()
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Save reservation costs (using same logic as CreateView)
        create_view = ReservationCreateView()
        create_view.request = self.request
        create_view.save_reservation_costs(self.object)
        
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
