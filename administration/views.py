from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, View
from datetime import datetime
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from accounts.models import CustomUser
from properties.models import Service
from .models import Condo
from .forms import ServiceCategoryForm, CondoForm
from accounts.forms import UserAdminForm, UserRegistrationForm
from subscriptions.models import Subscription
from django.http import JsonResponse

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and getattr(self.request.user, 'is_admin', False)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        messages.error(self.request, _("Acesso restrito a administradores."))
        return redirect('dashboard')

class AdminDashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'administration/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Painel Administrativo")
        # Estatísticas básicas
        context['total_users'] = CustomUser.objects.count()
        context['total_categories'] = Service.objects.count()
        return context

# CRUD Usuários
class UserListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = CustomUser
    template_name = 'administration/users/user_list.html'
    context_object_name = 'users_list'
    ordering = ['-date_joined']
    paginate_by = 20

class UserCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = CustomUser
    form_class = UserRegistrationForm
    template_name = 'administration/users/user_form.html'
    success_url = reverse_lazy('administration:user_list')

    def form_valid(self, form):
        messages.success(self.request, _("Usuário criado com sucesso!"))
        return super().form_valid(form)

class UserUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = CustomUser
    form_class = UserAdminForm
    template_name = 'administration/users/user_form.html'
    success_url = reverse_lazy('administration:user_list')

    def form_valid(self, form):
        messages.success(self.request, _("Usuário atualizado com sucesso!"))
        return super().form_valid(form)

class UserDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = CustomUser
    template_name = 'administration/users/user_confirm_delete.html'
    success_url = reverse_lazy('administration:user_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Usuário excluído com sucesso!"))
        return super().delete(request, *args, **kwargs)

class UserPlanDetailAjaxView(LoginRequiredMixin, AdminRequiredMixin, View):
    def get(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        try:
            subscription = Subscription.objects.get(user=user)
            payments = [
                {
                    'date': p.created_at.strftime('%d/%m/%Y %H:%M'),
                    'amount': f"R$ {p.amount}",
                    'status': p.status,
                    'id': p.mp_payment_id[:15]
                } for p in subscription.payments.all()
            ]
            data = {
                'plan_description': subscription.plan.description,
                'status_display': subscription.get_status_display(),
                'status': subscription.status,
                'start_date': subscription.start_date.strftime('%d/%m/%Y') if subscription.start_date else '-',
                'end_date': subscription.end_date.strftime('%d/%m/%Y') if subscription.end_date else '-',
                'end_date_raw': subscription.end_date.strftime('%Y-%m-%d') if subscription.end_date else '',
                'base_value': f"R$ {subscription.plan.base_value}",
                'update_url': f"/book/administrador/usuarios/{user.pk}/alterar-vencimento/",
                'periodicity': subscription.plan.get_periodicity_display(),
                'payments': payments
            }
        except Subscription.DoesNotExist:
            data = {'error': _("Este usuário ainda não possui um plano assinado.")}
        return JsonResponse(data)

class UserPlanRemoveView(LoginRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        Subscription.objects.filter(user=user).delete()
        messages.success(request, _("Plano removido com sucesso do usuário %s.") % user.full_name)
        return redirect('administration:user_list')

class UserPlanUpdateDateView(LoginRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        subscription = get_object_or_404(Subscription, user=user)
        new_date_str = request.POST.get('new_date')
        if new_date_str:
            try:
                # Usar datetime.strptime e depois tornar aware se necessário, 
                # mas o Django costuma lidar bem com datetime ingênuo se USE_TZ=True 
                # e o modelo espera datetime.
                from django.utils import timezone
                naive_date = datetime.strptime(new_date_str, '%Y-%m-%d')
                aware_date = timezone.make_aware(naive_date)
                subscription.end_date = aware_date
                
                # Sincroniza o status com base na nova data
                if aware_date > timezone.now():
                    subscription.status = 'active'
                else:
                    subscription.status = 'expired'
                
                subscription.save()
                messages.success(request, _("Vencimento do plano de %s alterado com sucesso para %s.") % (user.full_name, new_date_str))
            except ValueError:
                messages.error(request, _("Data inválida."))
        return redirect('administration:user_list')

# CRUD Categorias de Serviço
class ServiceCategoryListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Service
    template_name = 'administration/services/service_list.html'
    context_object_name = 'services'
    ordering = ['name']
    paginate_by = 20

class ServiceCategoryCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Service
    form_class = ServiceCategoryForm
    template_name = 'administration/services/service_form.html'
    success_url = reverse_lazy('administration:service_category_list')

    def form_valid(self, form):
        messages.success(self.request, _("Categoria de serviço criada com sucesso!"))
        return super().form_valid(form)

class ServiceCategoryUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Service
    form_class = ServiceCategoryForm
    template_name = 'administration/services/service_form.html'
    success_url = reverse_lazy('administration:service_category_list')

    def form_valid(self, form):
        messages.success(self.request, _("Categoria de serviço atualizada com sucesso!"))
        return super().form_valid(form)

class ServiceCategoryDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Service
    template_name = 'administration/services/service_confirm_delete.html'
    success_url = reverse_lazy('administration:service_category_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Categoria de serviço excluída com sucesso!"))
        return super().delete(request, *args, **kwargs)

# CRUD Condomínios
class CondoListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Condo
    template_name = 'administration/condos/condo_list.html'
    context_object_name = 'condos'
    ordering = ['name']
    paginate_by = 20

class CondoCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Condo
    form_class = CondoForm
    template_name = 'administration/condos/condo_form.html'
    success_url = reverse_lazy('administration:condo_list')

    def form_valid(self, form):
        messages.success(self.request, _("Condomínio criado com sucesso!"))
        return super().form_valid(form)

class CondoUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Condo
    form_class = CondoForm
    template_name = 'administration/condos/condo_form.html'
    success_url = reverse_lazy('administration:condo_list')

    def form_valid(self, form):
        messages.success(self.request, _("Condomínio atualizado com sucesso!"))
        return super().form_valid(form)

class CondoDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Condo
    template_name = 'administration/condos/condo_confirm_delete.html'
    success_url = reverse_lazy('administration:condo_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Condomínio excluído com sucesso!"))
        return super().delete(request, *args, **kwargs)

from django.http import JsonResponse

class CondoDetailAjaxView(LoginRequiredMixin, View):
    def get(self, request, pk):
        condo = get_object_or_404(Condo, pk=pk)
        data = {
            'name': condo.name,
            'address_street': condo.address_street,
            'address_number': condo.address_number,
            'address_neighborhood': condo.address_neighborhood,
            'address_city': condo.address_city,
            'address_state': condo.address_state,
            'authorization_template': condo.authorization_template,
        }
        return JsonResponse(data)

from .models import Plan
from .forms import PlanForm

class PlanListView(AdminRequiredMixin, ListView):
    model = Plan
    template_name = 'administration/plans/plan_list.html'
    context_object_name = 'plans'

class PlanCreateView(AdminRequiredMixin, CreateView):
    model = Plan
    form_class = PlanForm
    template_name = 'administration/plans/plan_form.html'
    success_url = reverse_lazy('administration:plan_list')
    
    def form_valid(self, form):
        messages.success(self.request, _("Plano criado com sucesso!"))
        return super().form_valid(form)

class PlanUpdateView(AdminRequiredMixin, UpdateView):
    model = Plan
    form_class = PlanForm
    template_name = 'administration/plans/plan_form.html'
    success_url = reverse_lazy('administration:plan_list')
    
    def form_valid(self, form):
        messages.success(self.request, _("Plano atualizado com sucesso!"))
        return super().form_valid(form)

class PlanDeleteView(AdminRequiredMixin, DeleteView):
    model = Plan
    template_name = 'administration/plans/plan_confirm_delete.html'
    success_url = reverse_lazy('administration:plan_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Plano excluído com sucesso!"))
        return super().delete(request, *args, **kwargs)

from .models import SystemSetting
from .forms import SystemSettingForm

class SystemSettingUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = SystemSetting
    form_class = SystemSettingForm
    template_name = 'administration/settings/settings_form.html'
    success_url = reverse_lazy('administration:settings')

    def get_object(self, queryset=None):
        return SystemSetting.get_settings()

    def form_valid(self, form):
        messages.success(self.request, _("Configurações atualizadas com sucesso!"))
        return super().form_valid(form)
