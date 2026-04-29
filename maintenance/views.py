from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from properties.models import Property, ServiceProvider
from .models import Maintenance, Budget, MaintenancePhoto, ProviderEvaluation
from .forms import BudgetForm, MaintenanceForm
from django.db.models import Count, Avg
import decimal

class PropertyMaintenanceMixin:
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
        context['property'] = self.get_property()
        context['active_item'] = 'maintenance'
        return context

class MaintenanceListView(LoginRequiredMixin, PropertyMaintenanceMixin, ListView):
    model = Maintenance
    template_name = 'maintenance/maintenance_list.html'
    context_object_name = 'maintenances'

    def get_queryset(self):
        qs = Maintenance.objects.filter(property=self.get_property())
        show_archived = self.request.GET.get('show_archived') == 'true'
        if not show_archived:
            qs = qs.filter(is_archived=False)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_archived'] = self.request.GET.get('show_archived') == 'true'
        return context

class MaintenanceCreateView(LoginRequiredMixin, PropertyMaintenanceMixin, CreateView):
    model = Maintenance
    form_class = MaintenanceForm
    template_name = 'maintenance/maintenance_form.html'

    def form_valid(self, form):
        form.instance.property = self.get_property()
        messages.success(self.request, _("Manutenção cadastrada com sucesso!"))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('maintenance:list', kwargs={'property_pk': self.kwargs.get('property_pk')})

class MaintenanceUpdateView(LoginRequiredMixin, PropertyMaintenanceMixin, UpdateView):
    model = Maintenance
    form_class = MaintenanceForm
    template_name = 'maintenance/maintenance_form.html'

    def get_queryset(self):
        return Maintenance.objects.filter(property__user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Manutenção atualizada com sucesso!"))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('maintenance:list', kwargs={'property_pk': self.kwargs.get('property_pk')})

class MaintenanceDeleteView(LoginRequiredMixin, PropertyMaintenanceMixin, DeleteView):
    model = Maintenance
    template_name = 'maintenance/maintenance_confirm_delete.html'

    def get_queryset(self):
        return Maintenance.objects.filter(property__user=self.request.user)

    def get_success_url(self):
        messages.success(self.request, _("Manutenção removida com sucesso!"))
        return reverse('maintenance:list', kwargs={'property_pk': self.kwargs.get('property_pk')})

class MaintenanceArchiveView(LoginRequiredMixin, PropertyMaintenanceMixin, View):
    def post(self, request, property_pk, pk):
        maintenance = get_object_or_404(Maintenance, pk=pk, property__user=request.user)
        maintenance.is_archived = not maintenance.is_archived
        maintenance.save()
        status_msg = _("arquivada") if maintenance.is_archived else _("desarquivada")
        messages.success(request, f"Manutenção {status_msg} com sucesso!")
        return redirect('maintenance:list', property_pk=property_pk)

class MaintenanceWizardView(LoginRequiredMixin, PropertyMaintenanceMixin, DetailView):
    model = Maintenance
    context_object_name = 'maintenance'

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['maintenance/includes/maintenance_wizard_partial.html']
        return ['maintenance/maintenance_wizard.html']

    def get_queryset(self):
        return Maintenance.objects.filter(property__user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        maintenance = self.get_object()
        
        # Determine wizard step (1 to 4)
        # 1: Photos (status open)
        # 2: Budgets (status open)
        # 3: Execution (status in_progress)
        # 4: Conclusion (status finished)
        
        step = self.request.GET.get('step') or self.request.POST.get('step')
        if not step:
            if maintenance.status == 'open':
                step = 1
            elif maintenance.status == 'budgeting':
                step = 2
            elif maintenance.status == 'in_progress':
                step = 3
            elif maintenance.status == 'finished':
                step = 4
            else:
                step = 1
        
        
        # Check for read_only mode
        is_read_only = self.request.GET.get('read_only') == 'true' or self.request.POST.get('read_only') == 'true'
        context['is_read_only'] = is_read_only
        
        context['wizard_step'] = int(step)
        context['budgets'] = maintenance.budgets.all()
        context['budget_form'] = BudgetForm()
        context['photos'] = maintenance.photos.all()
        context['evaluation'] = getattr(maintenance, 'evaluation', None)
        
        # Step 2: Possible Providers
        if int(step) == 2:
            maintenance_services = maintenance.services.all()
            if maintenance_services.exists():
                # Base queryset for providers matching categories
                base_providers = ServiceProvider.objects.filter(
                    services__in=maintenance_services,
                    is_active=True
                ).annotate(avg_rating=Avg('evaluations__rating')).distinct().order_by('-avg_rating')
                
                context['my_providers'] = base_providers.filter(user=self.request.user)
                context['other_providers'] = base_providers.exclude(user=self.request.user)
            else:
                context['my_providers'] = []
                context['other_providers'] = []

        return context

    def post(self, request, *args, **kwargs):
        maintenance = self.get_object()
        action = request.POST.get('action')
        is_read_only = request.POST.get('read_only') == 'true'

        if is_read_only and action in ['advance', 'regress', 'save_execution', 'submit_evaluation']:
            return JsonResponse({'status': 'error', 'message': _("Modo somente leitura ativo.")}, status=403)

        if action == 'advance':
            current_step = int(request.POST.get('step', 1))
            
            if current_step == 1:
                # Moving from Photos to Budgets
                maintenance.status = 'budgeting'
                maintenance.save()
                return JsonResponse({'status': 'success', 'new_status': 'budgeting', 'new_step': 2})
                
            elif current_step == 2:
                # Moving from Budgets to Execution
                maintenance.status = 'in_progress'
                maintenance.save()
                return JsonResponse({'status': 'success', 'new_status': 'in_progress', 'new_step': 3})
                
            elif current_step == 3:
                # Finalizing
                provider_name = request.POST.get('provider_name')
                provider_phone = request.POST.get('provider_phone')
                execution_start_date = request.POST.get('execution_start_date')
                execution_end_date = request.POST.get('execution_end_date')
                execution_value = request.POST.get('execution_value')

                if all([provider_name, provider_phone, execution_start_date, execution_end_date, execution_value]):
                    maintenance.provider_name = provider_name
                    maintenance.provider_phone = provider_phone
                    maintenance.execution_start_date = execution_start_date
                    maintenance.execution_end_date = execution_end_date
                    
                    val = execution_value.replace('.', '').replace(',', '.')
                    maintenance.execution_value = decimal.Decimal(val)
                    
                    provider, created = ServiceProvider.objects.get_or_create(
                        user=request.user,
                        name=provider_name,
                        defaults={'phone': provider_phone}
                    )
                    maintenance.provider = provider
                    
                    maintenance.status = 'finished'
                    maintenance.save()
                    return JsonResponse({'status': 'success', 'new_status': 'finished', 'new_step': 4})
                else:
                    return JsonResponse({
                        'status': 'error', 
                        'message': _("Por favor, preencha todos os campos de execução para finalizar.")
                    }, status=400)
        
        elif action == 'regress':
            current_step = int(request.POST.get('step', 1))
            
            if current_step == 2:
                # Back to Photos
                maintenance.status = 'open'
                maintenance.save()
                return JsonResponse({'status': 'success', 'new_status': 'open', 'new_step': 1})
            elif current_step == 3:
                # Back to Budgets
                maintenance.status = 'budgeting'
                maintenance.save()
                return JsonResponse({'status': 'success', 'new_status': 'budgeting', 'new_step': 2})
            elif current_step == 4:
                # Back to Execution
                maintenance.status = 'in_progress'
                maintenance.save()
                return JsonResponse({'status': 'success', 'new_status': 'in_progress', 'new_step': 3})
            
            return JsonResponse({'status': 'success', 'new_step': current_step})
        
        elif action == 'save_execution':
            maintenance.provider_name = request.POST.get('provider_name')
            maintenance.provider_phone = request.POST.get('provider_phone')
            maintenance.execution_start_date = request.POST.get('execution_start_date')
            maintenance.execution_end_date = request.POST.get('execution_end_date')
            
            value = request.POST.get('execution_value')
            if value:
                value = value.replace('.', '').replace(',', '.')
                maintenance.execution_value = decimal.Decimal(value)
            
            maintenance.save()
            return JsonResponse({'status': 'success', 'message': _("Dados de execução salvos!")})

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'new_status': maintenance.status})
            
        return redirect('maintenance:wizard', property_pk=maintenance.property.pk, pk=maintenance.pk)

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

class MaintenanceListViewOld(LoginRequiredMixin, View):
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

class MaintenanceCreateViewOld(LoginRequiredMixin, View):
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
        
        # Limit 3 photos
        if maintenance.photos.count() >= 3:
            return JsonResponse({
                'status': 'error', 
                'message': _("Limite de 3 fotos atingido.")
            }, status=400)
        
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

class ProviderAutocompleteView(LoginRequiredMixin, View):
    def get(self, request):
        query = request.GET.get('q', '')
        if query:
            # Search in ServiceProvider registration (global)
            providers = ServiceProvider.objects.filter(
                name__icontains=query
            ).values('name', 'phone').distinct()[:10]
            
            # Convert to list of dicts for JS to handle name/phone
            return JsonResponse(list(providers), safe=False)
        return JsonResponse([], safe=False)

class SubmitEvaluationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            maintenance = get_object_or_404(Maintenance, pk=kwargs['maintenance_pk'])
            rating = request.POST.get('rating')
            comment = request.POST.get('comment')

            # If provider is not linked yet, try to link it now
            if not maintenance.provider and maintenance.provider_name:
                provider, created = ServiceProvider.objects.get_or_create(
                    user=request.user,
                    name=maintenance.provider_name,
                    defaults={'phone': maintenance.provider_phone}
                )
                maintenance.provider = provider
                maintenance.save()

            if not maintenance.provider:
                return JsonResponse({'status': 'error', 'message': _('Prestador não encontrado para esta manutenção.')}, status=400)

            if not rating:
                return JsonResponse({'status': 'error', 'message': _('Nota não fornecida.')}, status=400)

            evaluation, created = ProviderEvaluation.objects.update_or_create(
                maintenance=maintenance,
                defaults={
                    'provider': maintenance.provider,
                    'rating': int(rating),
                    'comment': comment,
                    'user': request.user
                }
            )

            return JsonResponse({
                'status': 'success', 
                'message': _('Avaliação enviada com sucesso!') if created else _('Avaliação atualizada!')
            })
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
