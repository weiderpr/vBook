from django.views.generic import TemplateView, DetailView
from django.views import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator

class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
            
        if getattr(user, 'is_admin', False):
            return True
            
        if user.user_type == 'staff':
            # Staff must have an assigned condominium
            return user.condo is not None
            
        return False

@method_decorator(ensure_csrf_cookie, name='dispatch')
class DashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'mobilecondominio/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.utils import timezone
        today = timezone.now().date()
        
        # Filter by condo
        condo = self.request.user.condo
        
        context['checkins_today'] = Reservation.objects.filter(
            property__condo=condo,
            start_date=today,
            is_cancelled=False
        ).count()
        
        context['checkouts_today'] = Reservation.objects.filter(
            property__condo=condo,
            end_date=today,
            is_cancelled=False
        ).count()
        
        context['active_item'] = 'dashboard'
        return context

class QRScannerView(StaffRequiredMixin, TemplateView):
    template_name = 'mobilecondominio/qr_scanner.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_item'] = 'scan'
        return context

from reservations.models import Reservation, GateRelease

class ActiveGuestsListView(StaffRequiredMixin, TemplateView):
    template_name = 'mobilecondominio/active_guests.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.utils import timezone
        import datetime
        
        today = timezone.now().date()
        
        # Base queryset: checked in, gate release done, not cancelled, and not checked out
        queryset = Reservation.objects.filter(
            checkin_completed=True,
            gate_releases__release_type='entry',
            checkout_completed=False,
            is_cancelled=False
        ).select_related('property', 'property__condo', 'client').prefetch_related('gate_releases', 'gate_releases__user', 'costs__provider')
        
        # Apply condominium filter for staff
        if self.request.user.user_type == 'staff' and not getattr(self.request.user, 'is_admin', False):
            queryset = queryset.filter(property__condo=self.request.user.condo)
            
        # Add property-level checkout time logic for each reservation
        guests = []
        for res in queryset.order_by('end_date'):
            res.display_checkout_time = res.checkout_time or res.property.default_checkout_time or datetime.time(11, 0)
            # Pre-filter costs that have a provider associated
            res.provider_costs = [c for c in res.costs.all() if c.provider]
            guests.append(res)
            
        context['guests'] = guests
        context['active_item'] = 'dashboard'
        return context

class CheckoutView(StaffRequiredMixin, View):
    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Validation for staff users
        if request.user.user_type == 'staff' and not getattr(request.user, 'is_admin', False):
            if reservation.property.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error', 
                    'message': _("Erro: Esta reserva não pertence ao seu condomínio.")
                }, status=403)
        
        reservation.checkout_completed = True
        reservation.save(update_fields=['checkout_completed'])
        
        # Create GateRelease entry for exit
        GateRelease.objects.get_or_create(
            reservation=reservation,
            release_type='exit',
            defaults={'user': request.user}
        )
        
        from django.contrib import messages
        messages.success(request, _("Check-out realizado com sucesso para %s!") % reservation.client_name)
        
        return JsonResponse({'status': 'success', 'redirect_url': reverse('mobilecondominio:active_guests')})

class QRCheckInDetailView(StaffRequiredMixin, View):
    def get(self, request, token):
        reservation = get_object_or_404(Reservation, checkin_token=token)
        
        # Validation: Reservation must belong to the staff's condominium
        if request.user.user_type == 'staff' and not getattr(request.user, 'is_admin', False):
            if reservation.property.condo != request.user.condo:
                from django.contrib import messages
                other_condo = reservation.property.condo
                if other_condo:
                    msg = _("Acesso negado: Esta reserva pertence ao condomínio '%s'.") % other_condo.name
                else:
                    msg = _("Acesso negado: Esta reserva não pertence ao seu condomínio.")
                messages.error(request, msg)
                return redirect('mobilecondominio:dashboard')
        
        # Redirect to the detail view
        return redirect('mobilecondominio:reservation_detail', pk=reservation.pk)

class ReservationDetailView(StaffRequiredMixin, DetailView):
    model = Reservation
    template_name = 'mobilecondominio/reservation_detail.html'
    context_object_name = 'reservation'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.user_type == 'staff' and not getattr(self.request.user, 'is_admin', False):
            # Staff can only see reservations for their assigned condominium
            return qs.filter(property__condo=self.request.user.condo)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_item'] = 'dashboard'
        context['client'] = self.object.client
        context['complement'] = getattr(self.object.client, 'complement', None) if self.object.client else None
        context['companions'] = self.object.companions.all()
        context['is_released'] = GateRelease.objects.filter(reservation=self.object, release_type='entry').exists()
        return context

class GateReleaseView(StaffRequiredMixin, View):
    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Validation for staff users
        if request.user.user_type == 'staff' and not getattr(request.user, 'is_admin', False):
            if reservation.property.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error', 
                    'message': _("Erro: Esta reserva não pertence ao seu condomínio.")
                }, status=403)
        
        # Create GateRelease entry for entry
        GateRelease.objects.get_or_create(
            reservation=reservation,
            release_type='entry',
            defaults={'user': request.user}
        )
        
        from django.contrib import messages
        messages.success(request, _("Acesso liberado com sucesso para %s!") % reservation.client_name)
        
        return JsonResponse({'status': 'success', 'redirect_url': reverse('mobilecondominio:dashboard')})

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
import json

class ProfileView(StaffRequiredMixin, TemplateView):
    template_name = 'mobilecondominio/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_item'] = 'profile'
        context['password_form'] = PasswordChangeForm(self.request.user)
        return context

class ChangePasswordView(StaffRequiredMixin, View):
    def post(self, request):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            return JsonResponse({'status': 'success', 'message': _("Senha alterada com sucesso!")})
        else:
            # Simple error message from the first error found
            error_msg = _("Erro ao alterar senha.")
            if form.errors:
                first_error = list(form.errors.values())[0][0]
                error_msg = first_error
            return JsonResponse({'status': 'error', 'message': error_msg}, status=400)

class UpdateThemeView(StaffRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            theme = data.get('theme')
            if theme in ['light', 'dark']:
                request.user.mobile_theme_preference = theme
                request.user.save()
                return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        return JsonResponse({'status': 'error', 'message': _("Tema inválido")}, status=400)

class DailyReservationsListView(StaffRequiredMixin, TemplateView):
    template_name = 'mobilecondominio/daily_reservations.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.utils import timezone
        today = timezone.now().date()
        
        type = self.request.GET.get('type', 'checkin')
        condo = self.request.user.condo
        
        if type == 'checkout':
            queryset = Reservation.objects.filter(
                property__condo=condo,
                end_date=today,
                is_cancelled=False
            )
            context['title'] = _("Check-outs Hoje")
        else:
            queryset = Reservation.objects.filter(
                property__condo=condo,
                start_date=today,
                is_cancelled=False
            )
            context['title'] = _("Check-ins Hoje")
            
        context['reservations'] = queryset.select_related('property', 'client').order_by('property__address_complement')
        context['type'] = type
        context['active_item'] = 'dashboard'
        return context
