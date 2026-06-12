from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from reservations.models import Reservation, GateRelease, Companion
from properties.models import Property, PortariaCustomProperty, ServiceProvider, Service
from .models import PortariaCheckinManual, PortariaCheckinManualGuest, ServiceProviderAccessLog, PortariaCheckinVisitor
import datetime
import json
import logging

logger = logging.getLogger(__name__)


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if getattr(user, 'is_admin', False):
            return True
        if user.user_type == 'staff':
            # O porteiro precisa de um condomínio associado
            return user.condo is not None
        return False

class DashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'admcondominio/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localtime(timezone.now()).date()
        
        # Filtro de condomínio baseado no usuário logado
        condo = self.request.user.condo
        context['condo'] = condo
        
        # 1. Check-ins para hoje
        checkins_today = list(Reservation.objects.filter(
            property__condo=condo,
            start_date=today,
            is_cancelled=False
        ).select_related('property', 'property__portaria_custom', 'client').prefetch_related('gate_releases__user'))
        
        current_time = timezone.now()
        today_date = timezone.localtime(current_time).date()
        for res in checkins_today:
            can_undo = False
            if res.checkin_completed and not res.checkout_completed and not res.is_cancelled:
                entry_rel = res.entry_release
                if entry_rel and entry_rel.user == self.request.user:
                    entry_date = timezone.localtime(entry_rel.released_at).date()
                    if entry_date == today_date:
                        can_undo = True
            res.can_undo_checkin = can_undo
            res.is_manual = False
            
        manual_checkins_today = PortariaCheckinManual.objects.filter(
            property__condo=condo,
            checkin_date=today
        ).select_related('property', 'property__portaria_custom')
        for mc in manual_checkins_today:
            mc.client_name = mc.responsible_name
            mc.client_phone = ""
            mc.is_manual = True
            mc.can_undo_checkin = mc.checkin_completed and not mc.checkout_completed and timezone.localtime(mc.created_at).date() == today_date
            mc.checkin_time = None
            mc.start_date = mc.checkin_date
            mc.end_date = mc.checkout_date

        all_checkins_today = checkins_today + list(manual_checkins_today)
        all_checkins_today.sort(key=lambda x: (
            x.checkin_time or datetime.time(14, 0) if hasattr(x, 'checkin_time') and x.checkin_time else datetime.time(14, 0),
            x.property.display_complement or ""
        ))
        context['checkins_today'] = all_checkins_today
        
        # 2. Check-outs para hoje
        checkouts_today = list(Reservation.objects.filter(
            Q(end_date=today) | Q(checkout_completed=True, gate_releases__release_type='exit', gate_releases__released_at__date=today),
            property__condo=condo,
            is_cancelled=False
        ).distinct().select_related('property', 'property__portaria_custom', 'client'))
        for r in checkouts_today:
            r.is_manual = False

        manual_checkouts_today = PortariaCheckinManual.objects.filter(
            Q(checkout_date=today) | Q(checkout_completed=True, updated_at__date=today),
            property__condo=condo
        ).select_related('property', 'property__portaria_custom')
        for mc in manual_checkouts_today:
            mc.client_name = mc.responsible_name
            mc.client_phone = ""
            mc.is_manual = True
            mc.checkout_time = None
            mc.start_date = mc.checkin_date
            mc.end_date = mc.checkout_date
            
        all_checkouts_today = checkouts_today + list(manual_checkouts_today)
        all_checkouts_today.sort(key=lambda x: (
            x.checkout_time or datetime.time(11, 0) if hasattr(x, 'checkout_time') and x.checkout_time else datetime.time(11, 0),
            x.property.display_complement or ""
        ))
        context['checkouts_today'] = all_checkouts_today
        
        # 3. Apartamentos ocupados hoje (estadia ativa, check-in feito e check-out pendente)
        occupied_apartments = list(Reservation.objects.filter(
            property__condo=condo,
            start_date__lte=today,
            end_date__gte=today,
            checkin_completed=True,
            checkout_completed=False,
            is_cancelled=False
        ).select_related('property', 'property__portaria_custom', 'client').prefetch_related('client__complement'))
        for r in occupied_apartments:
            r.is_manual = False

        manual_occupied = PortariaCheckinManual.objects.filter(
            property__condo=condo,
            checkin_date__lte=today,
            checkout_date__gte=today,
            checkin_completed=True,
            checkout_completed=False
        ).select_related('property', 'property__portaria_custom')
        for mc in manual_occupied:
            mc.client_name = mc.responsible_name
            mc.client_phone = ""
            mc.is_manual = True
            mc.start_date = mc.checkin_date
            mc.end_date = mc.checkout_date

        all_occupied = occupied_apartments + list(manual_occupied)
        all_occupied.sort(key=lambda x: x.property.display_complement or "")
        context['occupied_apartments'] = all_occupied
        
        # Contadores rápidos
        count_checkins_pending = sum(1 for r in all_checkins_today if not r.checkin_completed)
        count_checkouts_pending = sum(1 for r in all_checkouts_today if not r.checkout_completed)
        count_occupied = len(all_occupied)
        
        context['count_checkins_pending'] = count_checkins_pending
        context['count_checkouts_pending'] = count_checkouts_pending
        context['count_occupied'] = count_occupied
        
        # 4. Prestadores de Serviço ativos no condomínio hoje (checkout_time é nulo)
        active_providers = ServiceProviderAccessLog.objects.filter(
            condo=condo,
            checkout_time__isnull=True
        ).select_related('provider').prefetch_related('properties')
        
        context['active_providers'] = active_providers
        context['count_active_providers'] = active_providers.count()
        
        # Logs de liberação recentes (últimos 10)
        context['recent_releases'] = GateRelease.objects.filter(
            reservation__property__condo=condo
        ).select_related('reservation', 'reservation__property', 'user').order_by('-released_at')[:10]
        
        return context


class GateReleaseEntryView(StaffRequiredMixin, View):
    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Garantir controle de acesso por condomínio
        if not getattr(request.user, 'is_admin', False):
            if reservation.property.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Erro: Esta reserva não pertence ao seu condomínio.")
                }, status=403)
        
        if reservation.is_cancelled:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: Esta reserva está cancelada.")
            }, status=400)
            
        # Marca check-in como concluído ao liberar a portaria
        reservation.checkin_completed = True
        reservation.save(update_fields=['checkin_completed'])
        
        # Cria ou obtém o registro de liberação de entrada
        release, created = GateRelease.objects.get_or_create(
            reservation=reservation,
            release_type='entry',
            defaults={'user': request.user}
        )
        
        release_time = timezone.localtime(release.released_at).strftime('%H:%M')
        
        # Retorna os dados necessários para o frontend atualizar a UI dinamicamente
        comp = getattr(reservation.client, 'complement', None) if reservation.client else None
        return JsonResponse({
            'status': 'success',
            'message': _("Acesso de entrada liberado com sucesso para %s!") % reservation.client_name,
            'release_time': release_time,
            'reservation': {
                'id': reservation.pk,
                'client_name': reservation.client_name,
                'client_phone': reservation.client_phone,
                'property_complement': reservation.property.display_complement or "",
                'car_model': comp.car_model if comp else "",
                'car_plate': comp.car_plate if comp else "",
                'start_date': reservation.start_date.strftime('%d/%m/%Y'),
                'end_date': reservation.end_date.strftime('%d/%m/%Y'),
            }
        })

class GateReleaseUndoView(StaffRequiredMixin, View):
    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Garantir controle de acesso por condomínio
        if not getattr(request.user, 'is_admin', False):
            if reservation.property.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Erro: Esta reserva não pertence ao seu condomínio.")
                }, status=403)
        
        if reservation.is_cancelled:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: Esta reserva está cancelada.")
            }, status=400)
            
        if not reservation.checkin_completed:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: Esta reserva não possui check-in concluído.")
            }, status=400)
            
        if reservation.checkout_completed:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: Não é possível desfazer o check-in pois o check-out já foi realizado.")
            }, status=400)
            
        entry_release = reservation.entry_release
        if not entry_release:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: Registro de liberação de entrada não encontrado.")
            }, status=400)
            
        # Verificar se é o mesmo usuário
        if entry_release.user != request.user:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: Apenas o mesmo usuário que realizou o check-in pode desfazê-lo.")
            }, status=403)
            
        # Verificar se ainda está no mesmo dia
        today = timezone.localtime(timezone.now()).date()
        release_date = timezone.localtime(entry_release.released_at).date()
        if release_date != today:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: O check-in só pode ser desfeito no mesmo dia em que foi realizado.")
            }, status=400)
            
        # Registrar ação em log para futura auditoria
        logger.info(
            "AUDITORIA: Usuário %s (ID: %s) desfez o check-in da reserva %s (Hóspede: %s, Condomínio: %s, Unidade: %s). O registro de liberação de entrada criado em %s foi excluído.",
            request.user.username,
            request.user.pk,
            reservation.pk,
            reservation.client_name,
            reservation.property.condo.name,
            reservation.property.display_complement or reservation.property.name,
            timezone.localtime(entry_release.released_at).strftime('%d/%m/%Y %H:%M:%S')
        )
        
        # Desfazer as ações
        entry_release.delete()
        reservation.checkin_completed = False
        reservation.save(update_fields=['checkin_completed'])
        
        return JsonResponse({
            'status': 'success',
            'message': _("Check-in desfeito com sucesso!")
        })

class GateReleaseExitView(StaffRequiredMixin, View):
    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Garantir controle de acesso por condomínio
        if not getattr(request.user, 'is_admin', False):
            if reservation.property.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Erro: Esta reserva não pertence ao seu condomínio.")
                }, status=403)
        
        if reservation.is_cancelled:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: Esta reserva está cancelada.")
            }, status=400)
            
        # Marca check-out como concluído
        reservation.checkout_completed = True
        reservation.save(update_fields=['checkout_completed'])
        
        # Cria ou obtém o registro de liberação de saída
        release, created = GateRelease.objects.get_or_create(
            reservation=reservation,
            release_type='exit',
            defaults={'user': request.user}
        )
        
        release_time = timezone.localtime(release.released_at).strftime('%H:%M')
        
        return JsonResponse({
            'status': 'success',
            'message': _("Check-out realizado com sucesso para %s!") % reservation.client_name,
            'release_time': release_time,
            'reservation_id': reservation.pk
        })

class ReservationDetailsJsonView(StaffRequiredMixin, View):
    def get(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Garantir controle de acesso por condomínio
        if not getattr(request.user, 'is_admin', False):
            if reservation.property.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Erro: Esta reserva não pertence ao seu condomínio.")
                }, status=403)
        
        comp = getattr(reservation.client, 'complement', None) if reservation.client else None
        companions = list(reservation.companions.values('id', 'name', 'rg'))
        visitors = list(reservation.visitors.values('id', 'name', 'document'))
        
        # Obter os logs de portaria ordenados por data de liberação
        releases = []
        for r in reservation.gate_releases.all().order_by('released_at'):
            releases.append({
                'type': r.get_release_type_display(),
                'type_raw': r.release_type,
                'time': timezone.localtime(r.released_at).strftime('%d/%m/%Y %H:%M'),
                'user': r.user.full_name if r.user else _("Sistema")
            })
            
        data = {
            'id': reservation.pk,
            'client_name': reservation.client_name,
            'client_phone': reservation.client_phone,
            'property_name': reservation.property.display_name,
            'property_complement': reservation.property.display_complement or "",
            'start_date': reservation.start_date.strftime('%d/%m/%Y'),
            'end_date': reservation.end_date.strftime('%d/%m/%Y'),
            'checkin_completed': reservation.checkin_completed,
            'checkout_completed': reservation.checkout_completed,
            'car_model': comp.car_model if comp else "",
            'car_plate': comp.car_plate if comp else "",
            'cpf': comp.cpf if comp else "",
            'rg': comp.rg if comp else "",
            'companions': companions,
            'visitors': [{'id': v['id'], 'name': v['name'], 'rg': v['document']} for v in visitors],
            'releases': releases,
            'is_cancelled': reservation.is_cancelled
        }
        
        return JsonResponse({'status': 'success', 'data': data})


class PropertyCustomizationView(StaffRequiredMixin, View):
    def post(self, request, pk):
        property_obj = get_object_or_404(Property, pk=pk)
        
        # Access control
        if not getattr(request.user, 'is_admin', False):
            if property_obj.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Erro: Esta propriedade não pertence ao seu condomínio.")
                }, status=403)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': _("Dados inválidos.")
            }, status=400)
            
        nome_portaria = data.get('nome_portaria', '').strip()
        bloco = data.get('bloco', '').strip()
        nome_proprietario = data.get('nome_proprietario', '').strip()
        telefone_proprietario = data.get('telefone_proprietario', '').strip()
        
        custom_obj, created = PortariaCustomProperty.objects.get_or_create(property=property_obj)
        custom_obj.nome_portaria = nome_portaria if nome_portaria else None
        custom_obj.bloco = bloco if bloco else None
        custom_obj.nome_proprietario = nome_proprietario if nome_proprietario else None
        custom_obj.telefone_proprietario = telefone_proprietario if telefone_proprietario else None
        custom_obj.save()
        
        return JsonResponse({
            'status': 'success',
            'message': _("Configurações da portaria salvas com sucesso!")
        })


class PropertyManualCreateView(StaffRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': _("Dados inválidos.")
            }, status=400)
            
        name = data.get('name', '').strip()
        bloco = data.get('bloco', '').strip()
        nome_proprietario = data.get('nome_proprietario', '').strip()
        telefone_proprietario = data.get('telefone_proprietario', '').strip()
        address_complement = data.get('address_complement', '').strip()
        
        if not name:
            return JsonResponse({
                'status': 'error',
                'message': _("O nome da propriedade/unidade é obrigatório.")
            }, status=400)
            
        condo = request.user.condo
        if not condo:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: Você não está associado a nenhum condomínio.")
            }, status=403)
            
        # Create Property with optional fields set to None/Empty and condo address details
        property_obj = Property.objects.create(
            user=None,
            name=name,
            condo=condo,
            description=f"Cadastro manual da portaria para {name}.",
            address_street=condo.address_street,
            address_number=condo.address_number,
            address_neighborhood=condo.address_neighborhood,
            address_city=condo.address_city,
            address_state=condo.address_state,
            address_complement=address_complement if address_complement else None,
            acquisition_value=None,
            acquisition_date=None
        )
        
        # Create corresponding custom property organization config
        PortariaCustomProperty.objects.create(
            property=property_obj,
            nome_portaria=name,
            bloco=bloco if bloco else None,
            nome_proprietario=nome_proprietario if nome_proprietario else None,
            telefone_proprietario=telefone_proprietario if telefone_proprietario else None
        )
        
        return JsonResponse({
            'status': 'success',
            'message': _("Unidade cadastrada com sucesso!")
        })


class PropertiesListView(StaffRequiredMixin, TemplateView):
    template_name = 'admcondominio/properties.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        condo = self.request.user.condo
        context['condo'] = condo
        
        today = timezone.localtime(timezone.now()).date()
        
        # Obter IDs de propriedades ocupadas por reserva ativa hoje
        occupied_property_ids = set(Reservation.objects.filter(
            property__condo=condo,
            start_date__lte=today,
            end_date__gte=today,
            checkin_completed=True,
            checkout_completed=False,
            is_cancelled=False
        ).values_list('property_id', flat=True))
        
        # Obter IDs de propriedades ocupadas por check-in manual ativo hoje
        manual_occupied_property_ids = set(PortariaCheckinManual.objects.filter(
            property__condo=condo,
            checkin_date__lte=today,
            checkout_date__gte=today,
            checkin_completed=True,
            checkout_completed=False
        ).values_list('property_id', flat=True))
        
        all_occupied_ids = occupied_property_ids.union(manual_occupied_property_ids)
        
        properties = list(Property.objects.filter(condo=condo).select_related('user', 'portaria_custom').order_by('address_complement', 'name'))
        for prop in properties:
            prop.is_occupied = prop.id in all_occupied_ids
            
        context['properties'] = properties
        return context


class PropertyManualCheckinView(StaffRequiredMixin, View):
    def post(self, request, pk):
        property_obj = get_object_or_404(Property, pk=pk)
        
        if not getattr(request.user, 'is_admin', False):
            if property_obj.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Erro: Esta propriedade não pertence ao seu condomínio.")
                }, status=403)
                
        if property_obj.user is not None:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: Esta propriedade possui proprietário cadastrado e não aceita check-in manual.")
            }, status=400)
            
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': _("Dados inválidos.")
            }, status=400)
            
        checkin_date_str = data.get('checkin_date', '').strip()
        checkout_date_str = data.get('checkout_date', '').strip()
        responsible_name = data.get('responsible_name', '').strip()
        responsible_cpf = data.get('responsible_cpf', '').strip()
        responsible_rg = data.get('responsible_rg', '').strip()
        car_model = data.get('car_model', '').strip()
        car_plate = data.get('car_plate', '').strip()
        guests_list = data.get('guests', [])
        
        if not (checkin_date_str and checkout_date_str and responsible_name and responsible_cpf and responsible_rg):
            return JsonResponse({
                'status': 'error',
                'message': _("Todos os campos obrigatórios (*) devem ser preenchidos.")
            }, status=400)
            
        try:
            checkin_date = datetime.datetime.strptime(checkin_date_str, '%Y-%m-%d').date()
            checkout_date = datetime.datetime.strptime(checkout_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'status': 'error',
                'message': _("Formato de data inválido.")
            }, status=400)
            
        if checkout_date < checkin_date:
            return JsonResponse({
                'status': 'error',
                'message': _("A data de checkout não pode ser menor que a data de checkin.")
            }, status=400)
            
        checkin_obj = PortariaCheckinManual.objects.create(
            property=property_obj,
            checkin_date=checkin_date,
            checkout_date=checkout_date,
            responsible_name=responsible_name,
            responsible_cpf=responsible_cpf,
            responsible_rg=responsible_rg,
            car_model=car_model if car_model else None,
            car_plate=car_plate if car_plate else None,
            checkin_completed=True,
            checkout_completed=False
        )
        
        for guest_data in guests_list:
            g_name = guest_data.get('name', '').strip()
            g_doc = guest_data.get('document', '').strip()
            if g_name and g_doc:
                PortariaCheckinManualGuest.objects.create(
                    checkin_manual=checkin_obj,
                    name=g_name,
                    document=g_doc
                )
                
        return JsonResponse({
            'status': 'success',
            'message': _("Check-in manual registrado com sucesso!")
        })


class ManualCheckinDetailsJsonView(StaffRequiredMixin, View):
    def get(self, request, pk):
        checkin_obj = get_object_or_404(PortariaCheckinManual, pk=pk)
        
        if not getattr(request.user, 'is_admin', False):
            if checkin_obj.property.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Erro: Esta propriedade não pertence ao seu condomínio.")
                }, status=403)
                
        guests = list(checkin_obj.guests.values('id', 'name', 'document'))
        visitors = list(checkin_obj.visitors.values('id', 'name', 'document'))
        
        data = {
            'id': checkin_obj.pk,
            'client_name': checkin_obj.responsible_name,
            'client_phone': "",
            'property_name': checkin_obj.property.display_name,
            'property_complement': checkin_obj.property.display_complement or "",
            'start_date': checkin_obj.checkin_date.strftime('%d/%m/%Y'),
            'end_date': checkin_obj.checkout_date.strftime('%d/%m/%Y'),
            'checkin_completed': checkin_obj.checkin_completed,
            'checkout_completed': checkin_obj.checkout_completed,
            'car_model': checkin_obj.car_model or "",
            'car_plate': checkin_obj.car_plate or "",
            'cpf': checkin_obj.responsible_cpf,
            'rg': checkin_obj.responsible_rg,
            'companions': [{'id': g['id'], 'name': g['name'], 'rg': g['document']} for g in guests],
            'visitors': [{'id': v['id'], 'name': v['name'], 'rg': v['document']} for v in visitors],
            'releases': [],
            'is_cancelled': False,
            'is_manual': True
        }
        
        return JsonResponse({'status': 'success', 'data': data})


class AddVisitorsView(StaffRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': _("Dados inválidos.")
            }, status=400)
            
        obj_id = data.get('id')
        is_manual = data.get('is_manual', False)
        visitors = data.get('visitors', [])
        
        if not obj_id or not isinstance(visitors, list) or not visitors:
            return JsonResponse({
                'status': 'error',
                'message': _("ID do check-in e lista de visitantes são obrigatórios.")
            }, status=400)
            
        # Access control and object retrieval
        if is_manual:
            checkin_obj = get_object_or_404(PortariaCheckinManual, pk=obj_id)
            if not getattr(request.user, 'is_admin', False):
                if checkin_obj.property.condo != request.user.condo:
                    return JsonResponse({
                        'status': 'error',
                        'message': _("Erro: Este check-in não pertence ao seu condomínio.")
                    }, status=403)
        else:
            reservation = get_object_or_404(Reservation, pk=obj_id)
            if not getattr(request.user, 'is_admin', False):
                if reservation.property.condo != request.user.condo:
                    return JsonResponse({
                        'status': 'error',
                        'message': _("Erro: Esta reserva não pertence ao seu condomínio.")
                    }, status=403)
                    
        # Validate visitors input
        valid_visitors = []
        for v in visitors:
            name = v.get('name', '').strip()
            doc = v.get('document', '').strip()
            if not name or not doc:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Nome e CPF/RG de todos os visitantes são obrigatórios.")
                }, status=400)
            if len(name) > 255:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Nome do visitante não pode exceder 255 caracteres.")
                }, status=400)
            
            doc_limit = 50
            if len(doc) > doc_limit:
                return JsonResponse({
                    'status': 'error',
                    'message': _("O documento do visitante não pode exceder %d caracteres.") % doc_limit
                }, status=400)
            
            valid_visitors.append((name, doc))
            
        # Save visitors
        created_count = 0
        if is_manual:
            for name, doc in valid_visitors:
                PortariaCheckinVisitor.objects.create(
                    checkin_manual=checkin_obj,
                    name=name,
                    document=doc
                )
                created_count += 1
        else:
            for name, doc in valid_visitors:
                PortariaCheckinVisitor.objects.create(
                    reservation=reservation,
                    name=name,
                    document=doc
                )
                created_count += 1
                
        return JsonResponse({
            'status': 'success',
            'message': _("%d visitante(s) adicionado(s) com sucesso!") % created_count
        })


class AddCompanionsView(StaffRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': _("Dados inválidos.")
            }, status=400)
            
        obj_id = data.get('id')
        is_manual = data.get('is_manual', False)
        companions = data.get('companions', [])
        
        if not obj_id or not isinstance(companions, list) or not companions:
            return JsonResponse({
                'status': 'error',
                'message': _("ID do check-in e lista de acompanhantes são obrigatórios.")
            }, status=400)
            
        # Access control and object retrieval
        if is_manual:
            checkin_obj = get_object_or_404(PortariaCheckinManual, pk=obj_id)
            if not getattr(request.user, 'is_admin', False):
                if checkin_obj.property.condo != request.user.condo:
                    return JsonResponse({
                        'status': 'error',
                        'message': _("Erro: Este check-in não pertence ao seu condomínio.")
                    }, status=403)
        else:
            reservation = get_object_or_404(Reservation, pk=obj_id)
            if not getattr(request.user, 'is_admin', False):
                if reservation.property.condo != request.user.condo:
                    return JsonResponse({
                        'status': 'error',
                        'message': _("Erro: Esta reserva não pertence ao seu condomínio.")
                    }, status=403)
                    
        # Validate companions input
        valid_companions = []
        for c in companions:
            name = c.get('name', '').strip()
            doc = c.get('document', '').strip()
            if not name or not doc:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Nome e CPF/RG de todos os acompanhantes são obrigatórios.")
                }, status=400)
            if len(name) > 255:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Nome do acompanhante não pode exceder 255 caracteres.")
                }, status=400)
            
            doc_limit = 50 if is_manual else 20
            if len(doc) > doc_limit:
                return JsonResponse({
                    'status': 'error',
                    'message': _("O documento do acompanhante não pode exceder %d caracteres.") % doc_limit
                }, status=400)
            
            valid_companions.append((name, doc))
            
        # Save companions
        created_count = 0
        if is_manual:
            for name, doc in valid_companions:
                PortariaCheckinManualGuest.objects.create(
                    checkin_manual=checkin_obj,
                    name=name,
                    document=doc
                )
                created_count += 1
        else:
            for name, doc in valid_companions:
                Companion.objects.create(
                    reservation=reservation,
                    name=name,
                    rg=doc
                )
                created_count += 1
                
        return JsonResponse({
            'status': 'success',
            'message': _("%d acompanhante(s) adicionado(s) com sucesso!") % created_count
        })


class DeleteCompanionView(StaffRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': _("Dados inválidos.")}, status=400)
            
        comp_id = data.get('id')
        is_manual = data.get('is_manual', False)
        
        if not comp_id:
            return JsonResponse({'status': 'error', 'message': _("ID do acompanhante é obrigatório.")}, status=400)
            
        if is_manual:
            guest = get_object_or_404(PortariaCheckinManualGuest, pk=comp_id)
            if not getattr(request.user, 'is_admin', False):
                if guest.checkin_manual.property.condo != request.user.condo:
                    return JsonResponse({'status': 'error', 'message': _("Acesso negado.")}, status=403)
            guest.delete()
        else:
            companion = get_object_or_404(Companion, pk=comp_id)
            if not getattr(request.user, 'is_admin', False):
                if companion.reservation.property.condo != request.user.condo:
                    return JsonResponse({'status': 'error', 'message': _("Acesso negado.")}, status=403)
            companion.delete()
            
        return JsonResponse({'status': 'success', 'message': _("Acompanhante removido com sucesso!")})


class DeleteVisitorView(StaffRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': _("Dados inválidos.")}, status=400)
            
        visitor_id = data.get('id')
        
        if not visitor_id:
            return JsonResponse({'status': 'error', 'message': _("ID do visitante é obrigatório.")}, status=400)
            
        visitor = get_object_or_404(PortariaCheckinVisitor, pk=visitor_id)
        
        # Access control
        if visitor.reservation:
            condo = visitor.reservation.property.condo
        elif visitor.checkin_manual:
            condo = visitor.checkin_manual.property.condo
        else:
            return JsonResponse({'status': 'error', 'message': _("Visitante sem associação válida.")}, status=400)
            
        if not getattr(request.user, 'is_admin', False):
            if condo != request.user.condo:
                return JsonResponse({'status': 'error', 'message': _("Acesso negado.")}, status=403)
                
        visitor.delete()
        return JsonResponse({'status': 'success', 'message': _("Visitante removido com sucesso!")})


class ManualCheckinExitView(StaffRequiredMixin, View):
    def post(self, request, pk):
        checkin_obj = get_object_or_404(PortariaCheckinManual, pk=pk)
        
        if not getattr(request.user, 'is_admin', False):
            if checkin_obj.property.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Erro: Esta propriedade não pertence ao seu condomínio.")
                }, status=403)
                
        checkin_obj.checkout_completed = True
        checkin_obj.save(update_fields=['checkout_completed'])
        
        return JsonResponse({
            'status': 'success',
            'message': _("Check-out manual realizado com sucesso para %s!") % checkin_obj.responsible_name,
            'reservation_id': checkin_obj.pk
        })


class ManualCheckinUndoView(StaffRequiredMixin, View):
    def post(self, request, pk):
        checkin_obj = get_object_or_404(PortariaCheckinManual, pk=pk)
        
        if not getattr(request.user, 'is_admin', False):
            if checkin_obj.property.condo != request.user.condo:
                return JsonResponse({
                    'status': 'error',
                    'message': _("Erro: Esta propriedade não pertence ao seu condomínio.")
                }, status=403)
                
        if checkin_obj.checkout_completed:
            return JsonResponse({
                'status': 'error',
                'message': _("Erro: Não é possível desfazer o check-in pois o check-out já foi realizado.")
            }, status=400)
            
        logger.info(
            "AUDITORIA: Usuário %s (ID: %s) desfez o check-in MANUAL %s (Responsável: %s, Condomínio: %s, Unidade: %s). O registro de check-in manual foi excluído.",
            request.user.username,
            request.user.pk,
            checkin_obj.pk,
            checkin_obj.responsible_name,
            checkin_obj.property.condo.name,
            checkin_obj.property.display_complement or checkin_obj.property.name
        )
        
        checkin_obj.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': _("Check-in manual desfeito com sucesso!")
        })


class HistoryListView(StaffRequiredMixin, TemplateView):
    template_name = 'admcondominio/history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        condo = self.request.user.condo
        context['condo'] = condo

        # Query release actions (registered properties)
        releases = GateRelease.objects.filter(
            reservation__property__condo=condo
        ).select_related('reservation', 'reservation__property', 'user')

        # Query manual checkins
        manuals = PortariaCheckinManual.objects.filter(
            property__condo=condo
        ).select_related('property')

        # Query provider access logs
        provider_logs = ServiceProviderAccessLog.objects.filter(
            condo=condo
        ).select_related('operator_entry', 'operator_exit').prefetch_related('properties')

        # Combine actions
        actions = []
        for r in releases:
            actions.append({
                'timestamp': r.released_at,
                'action_type': 'checkin' if r.release_type == 'entry' else 'checkout',
                'is_manual': False,
                'guest_name': r.reservation.client_name,
                'property_name': r.reservation.property.display_name,
                'property_complement': r.reservation.property.display_complement,
                'operator': r.user.full_name if r.user else _("Sistema"),
                'details': {
                    'phone': r.reservation.client_phone,
                    'start_date': r.reservation.start_date,
                    'end_date': r.reservation.end_date,
                }
            })

        for m in manuals:
            # Check-in Manual is created with checkin_completed=True
            actions.append({
                'timestamp': m.created_at,
                'action_type': 'checkin',
                'is_manual': True,
                'guest_name': m.responsible_name,
                'property_name': m.property.display_name,
                'property_complement': m.property.display_complement,
                'operator': _("Portaria (Manual)"),
                'details': {
                    'phone': "",
                    'start_date': m.checkin_date,
                    'end_date': m.checkout_date,
                    'cpf': m.responsible_cpf,
                    'rg': m.responsible_rg,
                }
            })

            # Check-out Manual is completed when checkout_completed is True
            if m.checkout_completed:
                actions.append({
                    'timestamp': m.updated_at,
                    'action_type': 'checkout',
                    'is_manual': True,
                    'guest_name': m.responsible_name,
                    'property_name': m.property.display_name,
                    'property_complement': m.property.display_complement,
                    'operator': _("Portaria (Manual)"),
                    'details': {
                        'phone': "",
                        'start_date': m.checkin_date,
                        'end_date': m.checkout_date,
                        'cpf': m.responsible_cpf,
                        'rg': m.responsible_rg,
                    }
                })

        for pl in provider_logs:
            # Check-in Event
            props_list = list(pl.properties.all())
            prop_names = ", ".join([p.display_name for p in props_list]) if props_list else _("Área Comum")
            prop_complements = ", ".join([p.display_complement for p in props_list if p.display_complement]) if props_list else ""
            
            actions.append({
                'timestamp': pl.checkin_time,
                'action_type': 'checkin',
                'is_manual': False,
                'is_provider': True,
                'guest_name': pl.provider_name,
                'property_name': prop_names,
                'property_complement': prop_complements,
                'operator': pl.operator_entry.full_name if pl.operator_entry else _("Portaria"),
                'details': {
                    'phone': pl.provider_phone or "",
                    'cpf': pl.provider_cpf or "",
                    'reason': pl.reason,
                    'car_model': pl.car_model or "",
                    'car_plate': pl.car_plate or "",
                }
            })
            
            # Check-out Event (if completed)
            if pl.checkout_time:
                actions.append({
                    'timestamp': pl.checkout_time,
                    'action_type': 'checkout',
                    'is_manual': False,
                    'is_provider': True,
                    'guest_name': pl.provider_name,
                    'property_name': prop_names,
                    'property_complement': prop_complements,
                    'operator': pl.operator_exit.full_name if pl.operator_exit else _("Portaria"),
                    'details': {
                        'phone': pl.provider_phone or "",
                        'cpf': pl.provider_cpf or "",
                        'reason': pl.reason,
                        'car_model': pl.car_model or "",
                        'car_plate': pl.car_plate or "",
                    }
                })

        # Sort actions by timestamp DESC (most recent first)
        actions.sort(key=lambda x: x['timestamp'], reverse=True)

        # Apply search filter if query exists
        q = self.request.GET.get('q', '').strip().lower()
        if q:
            filtered_actions = []
            for act in actions:
                search_text = (
                    f"{act['guest_name']} "
                    f"{act['property_name'] or ''} "
                    f"{act['property_complement'] or ''} "
                    f"{act['operator'] or ''}"
                ).lower()
                if q in search_text:
                    filtered_actions.append(act)
            actions = filtered_actions

        # Pagination
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        paginator = Paginator(actions, 25)  # 25 actions per page
        page = self.request.GET.get('page')
        try:
            paginated_actions = paginator.page(page)
        except PageNotAnInteger:
            paginated_actions = paginator.page(1)
        except EmptyPage:
            paginated_actions = paginator.page(paginator.num_pages)

        context['actions'] = paginated_actions
        context['search_query'] = q
        return context


class PortariaDriveView(StaffRequiredMixin, TemplateView):
    template_name = 'admcondominio/drive.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        condo = self.request.user.condo
        context['condo'] = condo
        context['active_item'] = 'portaria_drive'
        
        if condo:
            workspace_name = f"Portaria {condo.name}"
            workspace_key = f"vertice_book_portaria_{condo.id}"
            
            import requests
            from django.conf import settings
            
            api_key = getattr(settings, 'VERTICE_DRIVE_API_KEY', 'app_Hr4aCzy0Az2GJJl8xIuNfn35HqkV9CpF')
            url = "https://drive.verticesistemas.tech/api/embed/token"
            headers = {
                "X-API-Key": api_key
            }
            data = {
                "workspace_key": workspace_key,
                "workspace_name": workspace_name
            }
            
            embed_url = None
            error_msg = None
            try:
                response = requests.post(url, headers=headers, data=data, timeout=10)
                if response.status_code == 200:
                    resp_json = response.json()
                    embed_url = resp_json.get('url')
                else:
                    error_msg = f"Erro da API do Vértice Drive: Código {response.status_code}"
            except Exception as e:
                error_msg = f"Não foi possível conectar ao Vértice Drive: {str(e)}"
        else:
            embed_url = None
            error_msg = "Nenhum condomínio associado a este usuário."
            
        context['embed_url'] = embed_url
        context['error_msg'] = error_msg
        return context


class ProvidersListView(StaffRequiredMixin, TemplateView):
    template_name = 'admcondominio/providers.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        condo = self.request.user.condo
        context['condo'] = condo
        context['active_item'] = 'providers'

        # Get all properties for this condo
        properties = Property.objects.filter(condo=condo).order_by('address_complement', 'name')
        context['properties'] = properties

        # Get all services for categorizing
        context['services'] = Service.objects.all()

        # Get system users with properties in this condo
        owner_ids = Property.objects.filter(condo=condo, user__isnull=False).values_list('user_id', flat=True).distinct()
        
        # Query active providers from owners & manual registrations
        owner_providers = ServiceProvider.objects.filter(user_id__in=owner_ids, is_active=True).prefetch_related('services')
        manual_providers = ServiceProvider.objects.filter(condo=condo, is_active=True).prefetch_related('services')
        
        all_providers = list(owner_providers) + list(manual_providers)

        # Unify by CPF or Phone
        grouped = {}
        for p in all_providers:
            key = None
            if p.cpf:
                key = ('cpf', p.cpf.strip().replace('.', '').replace('-', '').replace('/', ''))
            elif p.phone:
                key = ('phone', p.phone.strip())
                
            if not key:
                continue

            if key not in grouped:
                origins = []
                properties_served = []
                
                if p.condo == condo:
                    origins.append(_("Portaria (Avulso)"))
                if p.user_id:
                    user_props = Property.objects.filter(condo=condo, user_id=p.user_id)
                    for prop in user_props:
                        properties_served.append(prop)
                        origins.append(f"{_('Proprietário')}: {prop.display_name} ({prop.display_complement or prop.name})")

                grouped[key] = {
                    'id': p.id,
                    'name': p.name,
                    'cpf': p.cpf,
                    'phone': p.phone,
                    'photo': p.photo.url if p.photo else None,
                    'services': list(p.services.all()),
                    'properties_served': properties_served,
                    'origins': list(set(origins)),
                    'is_inside': False,
                    'active_log_id': None,
                    'raw_provider': p
                }
            else:
                gp = grouped[key]
                if p.condo == condo:
                    if _("Portaria (Avulso)") not in gp['origins']:
                        gp['origins'].append(_("Portaria (Avulso)"))
                if p.user_id:
                    user_props = Property.objects.filter(condo=condo, user_id=p.user_id)
                    for prop in user_props:
                        if prop not in gp['properties_served']:
                            gp['properties_served'].append(prop)
                        origin_str = f"{_('Proprietário')}: {prop.display_name} ({prop.display_complement or prop.name})"
                        if origin_str not in gp['origins']:
                            gp['origins'].append(origin_str)
                # Merge services
                for s in p.services.all():
                    if s not in gp['services']:
                        gp['services'].append(s)
                # Keep photo if new one is present
                if not gp['photo'] and p.photo:
                    gp['photo'] = p.photo.url

        # Check who is inside currently
        active_logs = ServiceProviderAccessLog.objects.filter(condo=condo, checkout_time__isnull=True)
        active_by_key = {}
        for log in active_logs:
            log_key = None
            if log.provider_cpf:
                log_key = ('cpf', log.provider_cpf.strip().replace('.', '').replace('-', '').replace('/', ''))
            elif log.provider_phone:
                log_key = ('phone', log.provider_phone.strip())
            if log_key:
                active_by_key[log_key] = log

        for key, gp in grouped.items():
            if key in active_by_key:
                gp['is_inside'] = True
                gp['active_log_id'] = active_by_key[key].id

        # Sort grouped by name
        sorted_providers = sorted(grouped.values(), key=lambda x: x['name'].lower())
        context['providers'] = sorted_providers
        context['active_providers'] = [p for p in sorted_providers if p['is_inside']]
        
        return context


class ProviderCreateView(StaffRequiredMixin, View):
    def post(self, request):
        name = request.POST.get('name', '').strip()
        cpf = request.POST.get('cpf', '').strip()
        phone = request.POST.get('phone', '').strip()
        services_ids = request.POST.getlist('services')
        photo = request.FILES.get('photo')

        if not name or not cpf:
            return JsonResponse({'status': 'error', 'message': _("Nome e CPF são obrigatórios.")}, status=400)

        condo = request.user.condo
        cpf_clean = cpf.replace('.', '').replace('-', '').replace('/', '')

        # Check if already exists manually for this condo
        if ServiceProvider.objects.filter(condo=condo, cpf=cpf).exists():
            return JsonResponse({'status': 'error', 'message': _("Já existe um prestador cadastrado com este CPF na portaria.")}, status=400)

        # Create
        provider = ServiceProvider.objects.create(
            name=name,
            cpf=cpf,
            phone=phone,
            condo=condo,
            user=None
        )
        if photo:
            provider.photo = photo
            provider.save()

        if services_ids:
            provider.services.set(Service.objects.filter(id__in=services_ids))

        return JsonResponse({
            'status': 'success',
            'message': _("Prestador cadastrado com sucesso!"),
            'provider': {
                'id': provider.id,
                'name': provider.name,
                'cpf': provider.cpf,
                'phone': provider.phone,
                'photo_url': provider.photo.url if provider.photo else None
            }
        })


class ProviderCheckinView(StaffRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            # Fallback to standard POST (for multipart/form-data checks)
            data = request.POST

        provider_id = data.get('provider_id')
        reason = data.get('reason', '').strip()
        property_ids = data.get('properties', [])
        car_model = data.get('car_model', '').strip()
        car_plate = data.get('car_plate', '').strip()

        if not provider_id or not reason:
            return JsonResponse({'status': 'error', 'message': _("Prestador e Motivo do acesso são obrigatórios.")}, status=400)

        condo = request.user.condo
        provider = get_object_or_404(ServiceProvider, pk=provider_id)

        # Check if already inside (by CPF or Phone)
        q_filter = Q(condo=condo, checkout_time__isnull=True)
        if provider.cpf:
            q_filter &= Q(provider_cpf=provider.cpf)
        else:
            q_filter &= Q(provider_phone=provider.phone)

        if ServiceProviderAccessLog.objects.filter(q_filter).exists():
            return JsonResponse({'status': 'error', 'message': _("Este prestador já possui um acesso de entrada ativo no condomínio.")}, status=400)

        # Save Entry Log
        log = ServiceProviderAccessLog.objects.create(
            condo=condo,
            provider=provider,
            provider_name=provider.name,
            provider_cpf=provider.cpf,
            provider_phone=provider.phone,
            checkin_time=timezone.now(),
            reason=reason,
            car_model=car_model or None,
            car_plate=car_plate or None,
            operator_entry=request.user
        )

        if property_ids:
            log.properties.set(Property.objects.filter(id__in=property_ids, condo=condo))

        return JsonResponse({
            'status': 'success',
            'message': _("Entrada do prestador %s registrada com sucesso!") % provider.name
        })


class ProviderCheckoutView(StaffRequiredMixin, View):
    def post(self, request, pk):
        condo = request.user.condo
        log = get_object_or_404(ServiceProviderAccessLog, pk=pk, condo=condo)

        if log.checkout_time:
            return JsonResponse({'status': 'error', 'message': _("Este acesso já possui saída registrada.")}, status=400)

        log.checkout_time = timezone.now()
        log.operator_exit = request.user
        log.save()

        return JsonResponse({
            'status': 'success',
            'message': _("Saída do prestador %s registrada com sucesso!") % log.provider_name
        })


class ProviderSearchAPIView(StaffRequiredMixin, View):
    def get(self, request):
        q = request.GET.get('q', '').strip().lower()
        condo = request.user.condo

        # Get system users with properties in this condo
        owner_ids = Property.objects.filter(condo=condo, user__isnull=False).values_list('user_id', flat=True).distinct()
        
        # Query active providers from owners & manual registrations
        owner_providers = ServiceProvider.objects.filter(
            Q(name__icontains=q) | Q(cpf__icontains=q),
            user_id__in=owner_ids,
            is_active=True
        ).prefetch_related('services')
        
        manual_providers = ServiceProvider.objects.filter(
            Q(name__icontains=q) | Q(cpf__icontains=q),
            condo=condo,
            is_active=True
        ).prefetch_related('services')

        all_providers = list(owner_providers) + list(manual_providers)

        # Unify by CPF or Phone
        grouped = {}
        for p in all_providers:
            key = None
            if p.cpf:
                key = ('cpf', p.cpf.strip().replace('.', '').replace('-', '').replace('/', ''))
            elif p.phone:
                key = ('phone', p.phone.strip())
            if not key:
                continue

            if key not in grouped:
                origins = []
                properties_served = []
                if p.condo == condo:
                    origins.append(_("Portaria (Avulso)"))
                if p.user_id:
                    user_props = Property.objects.filter(condo=condo, user_id=p.user_id)
                    for prop in user_props:
                        properties_served.append(prop.id)
                        origins.append(f"{prop.display_name} ({prop.display_complement or prop.name})")

                grouped[key] = {
                    'id': p.id,
                    'name': p.name,
                    'cpf': p.cpf,
                    'phone': p.phone,
                    'photo': p.photo.url if p.photo else None,
                    'services': [s.name for s in p.services.all()],
                    'properties_served': properties_served,
                    'origins': list(set(origins)),
                    'is_inside': False,
                    'active_log_id': None
                }
            else:
                gp = grouped[key]
                if p.condo == condo:
                    if _("Portaria (Avulso)") not in gp['origins']:
                        gp['origins'].append(_("Portaria (Avulso)"))
                if p.user_id:
                    user_props = Property.objects.filter(condo=condo, user_id=p.user_id)
                    for prop in user_props:
                        if prop.id not in gp['properties_served']:
                            gp['properties_served'].append(prop.id)
                        origin_str = f"{prop.display_name} ({prop.display_complement or prop.name})"
                        if origin_str not in gp['origins']:
                            gp['origins'].append(origin_str)
                # Keep photo if new one is present
                if not gp['photo'] and p.photo:
                    gp['photo'] = p.photo.url

        # Tag who is currently inside
        active_logs = ServiceProviderAccessLog.objects.filter(condo=condo, checkout_time__isnull=True)
        active_by_key = {}
        for log in active_logs:
            log_key = None
            if log.provider_cpf:
                log_key = ('cpf', log.provider_cpf.strip().replace('.', '').replace('-', '').replace('/', ''))
            elif log.provider_phone:
                log_key = ('phone', log.provider_phone.strip())
            if log_key:
                active_by_key[log_key] = log

        for key, gp in grouped.items():
            if key in active_by_key:
                gp['is_inside'] = True
                gp['active_log_id'] = active_by_key[key].id

        return JsonResponse(list(grouped.values()), safe=False)


class ProviderAccessDetailsJsonView(StaffRequiredMixin, View):
    def get(self, request, pk):
        condo = request.user.condo
        log = get_object_or_404(ServiceProviderAccessLog, pk=pk, condo=condo)
        
        properties = list(log.properties.values('name', 'address_complement'))
        
        data = {
            'id': log.pk,
            'provider_name': log.provider_name,
            'provider_cpf': log.provider_cpf or "",
            'provider_phone': log.provider_phone or "",
            'checkin_time': timezone.localtime(log.checkin_time).strftime('%d/%m/%Y %H:%M'),
            'checkout_time': timezone.localtime(log.checkout_time).strftime('%d/%m/%Y %H:%M') if log.checkout_time else "",
            'reason': log.reason,
            'car_model': log.car_model or "",
            'car_plate': log.car_plate or "",
            'operator_entry': log.operator_entry.full_name if log.operator_entry else _("Sistema"),
            'operator_exit': log.operator_exit.full_name if log.operator_exit else "",
            'properties': properties
        }
        
        return JsonResponse({'status': 'success', 'data': data})



