from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from accounts.models import CustomUser
from properties.models import Service
from .models import Condo
from .forms import ServiceCategoryForm, CondoForm
from accounts.forms import UserAdminForm, UserRegistrationForm

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
