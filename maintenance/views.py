from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, View
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from properties.models import Property
from .models import Maintenance, Budget, MaintenancePhoto
from .forms import BudgetForm
from django.db.models import Count

class MaintenanceDashboardView(LoginRequiredMixin, DetailView):
    model = Property
    template_name = 'maintenance/maintenance_dashboard.html'
    context_object_name = 'property'

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_item'] = 'maintenance'
        
        # Count maintenances by status
        status_counts = self.object.maintenances.values('status').annotate(count=Count('id'))
        counts_dict = {s[0]: 0 for s in Maintenance.STATUS_CHOICES}
        for sc in status_counts:
            counts_dict[sc['status']] = sc['count']
        
        context['status_counts'] = counts_dict
        context['status_choices'] = Maintenance.STATUS_CHOICES
        
        # Initially load 'open' maintenances
        context['initial_status'] = 'open'
        context['maintenances'] = self.object.maintenances.filter(status='open')
        
        return context

class MaintenanceListView(LoginRequiredMixin, View):
    """AJAX view to return the list of maintenances for a specific status."""
    def get(self, request, property_pk):
        property_obj = get_object_or_404(Property, pk=property_pk, user=request.user)
        status = request.GET.get('status', 'open')
        
        maintenances = property_obj.maintenances.filter(status=status).order_by('-start_date')
        
        html = render_to_string('maintenance/includes/maintenance_list_items.html', {
            'maintenances': maintenances,
            'property': property_obj
        })
        
        return JsonResponse({'html': html, 'count': maintenances.count()})

class MaintenanceDetailView(LoginRequiredMixin, View):
    """AJAX view to return the details of a specific maintenance."""
    def get(self, request, pk):
        maintenance = get_object_or_404(Maintenance, pk=pk, property__user=request.user)
        
        html = render_to_string('maintenance/includes/maintenance_detail_content.html', {
            'maintenance': maintenance
        })
        
        return JsonResponse({'html': html, 'title': maintenance.title})

class MaintenanceCreateView(LoginRequiredMixin, View):
    def post(self, request, property_pk):
        property_obj = get_object_or_404(Property, pk=property_pk, user=request.user)
        
        title = request.POST.get('title')
        description = request.POST.get('description')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        status = request.POST.get('status', 'open')
        
        maintenance = Maintenance.objects.create(
            property=property_obj,
            title=title,
            description=description,
            start_date=start_date,
            end_date=end_date,
            status=status
        )

        # Get all counts
        status_counts = property_obj.maintenances.values('status').annotate(count=Count('id'))
        counts_dict = {s[0]: 0 for s in Maintenance.STATUS_CHOICES}
        for sc in status_counts:
            counts_dict[sc['status']] = sc['count']
        
        return JsonResponse({
            'status': 'success',
            'id': maintenance.id,
            'counts': counts_dict,
            'message': _("Manutenção criada com sucesso!")
        })

class MaintenanceUpdateStatusView(LoginRequiredMixin, View):
    def post(self, request, pk):
        maintenance = get_object_or_404(Maintenance, pk=pk, property__user=request.user)
        new_status = request.POST.get('status')
        
        if new_status in dict(Maintenance.STATUS_CHOICES):
            maintenance.status = new_status
            maintenance.save()

            # Get all counts for the property
            property_obj = maintenance.property
            status_counts = property_obj.maintenances.values('status').annotate(count=Count('id'))
            counts_dict = {s[0]: 0 for s in Maintenance.STATUS_CHOICES}
            for sc in status_counts:
                counts_dict[sc['status']] = sc['count']

            return JsonResponse({
                'status': 'success',
                'counts': counts_dict
            })
        
        return JsonResponse({'status': 'error', 'message': _("Status inválido")}, status=400)

class MaintenanceBudgetCreateView(LoginRequiredMixin, View):
    def post(self, request, maintenance_pk):
        maintenance = get_object_or_404(Maintenance, pk=maintenance_pk, property__user=request.user)
        budget_id = request.POST.get('budget_id')
        
        if budget_id:
            budget = get_object_or_404(Budget, pk=budget_id, maintenance=maintenance)
            form = BudgetForm(request.POST, instance=budget)
        else:
            form = BudgetForm(request.POST)
        
        if form.is_valid():
            budget = form.save(commit=False)
            budget.maintenance = maintenance
            budget.save()
            
            budgets = maintenance.budgets.all()
            html = render_to_string('maintenance/includes/budget_list.html', {
                'budgets': budgets,
                'maintenance': maintenance
            })
            
            return JsonResponse({
                'status': 'success',
                'html': html,
                'message': _("Orçamento salvo com sucesso!")
            })
            
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

class MaintenanceBudgetDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        budget = get_object_or_404(Budget, pk=pk, maintenance__property__user=request.user)
        maintenance = budget.maintenance
        budget.delete()
        
        budgets = maintenance.budgets.all()
        html = render_to_string('maintenance/includes/budget_list.html', {
            'budgets': budgets,
            'maintenance': maintenance
        })
        
        return JsonResponse({
            'status': 'success',
            'html': html,
            'message': _("Orçamento excluído com sucesso!")
        })

class MaintenanceBudgetDetailView(LoginRequiredMixin, View):
    """Returns budget data for editing."""
    def get(self, request, pk):
        budget = get_object_or_404(Budget, pk=pk, maintenance__property__user=request.user)
        return JsonResponse({
            'id': budget.id,
            'provider_name': budget.provider_name,
            'phone': budget.phone,
            'value': budget.value,
            'start_date': budget.start_date.isoformat(),
            'end_date': budget.end_date.isoformat(),
            'observations': budget.observations or ''
        })

class MaintenancePhotoUploadView(LoginRequiredMixin, View):
    def post(self, request, maintenance_pk):
        maintenance = get_object_or_404(Maintenance, pk=maintenance_pk, property__user=request.user)
        
        # If already has 3 photos, remove the oldest one
        if maintenance.photos.count() >= 3:
            oldest_photo = maintenance.photos.order_by('created_at').first()
            if oldest_photo:
                oldest_photo.delete()
        
        image = request.FILES.get('image')
        if image:
            photo = MaintenancePhoto.objects.create(maintenance=maintenance, image=image)
            
            # Re-render hidden data for immediate sync
            photos_html = ""
            for p in maintenance.photos.all():
                photos_html += f'<img src="{p.image.url}" data-id="{p.id}">'

            return JsonResponse({
                'status': 'success',
                'message': _("Foto enviada com sucesso!"),
                'photos_html': photos_html,
                'photo_count': maintenance.photos.count()
            })
            
        return JsonResponse({'status': 'error', 'message': _("Nenhuma imagem enviada.")}, status=400)

class MaintenancePhotoDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        photo = get_object_or_404(MaintenancePhoto, pk=pk, maintenance__property__user=request.user)
        maintenance = photo.maintenance
        photo.delete()
        
        # Re-render hidden data for immediate sync
        photos_html = ""
        for p in maintenance.photos.all():
            photos_html += f'<img src="{p.image.url}" data-id="{p.id}">'
            
        return JsonResponse({
            'status': 'success',
            'message': _("Foto excluída com sucesso!"),
            'photos_html': photos_html,
            'photo_count': maintenance.photos.count()
        })
