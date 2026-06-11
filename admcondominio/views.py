from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from reservations.models import Reservation, GateRelease
from properties.models import Property, PortariaCustomProperty
from .models import PortariaCheckinManual, PortariaCheckinManualGuest
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
            property__condo=condo,
            end_date=today,
            is_cancelled=False
        ).select_related('property', 'property__portaria_custom', 'client'))
        for r in checkouts_today:
            r.is_manual = False

        manual_checkouts_today = PortariaCheckinManual.objects.filter(
            property__condo=condo,
            checkout_date=today
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
        companions = list(reservation.companions.values('name', 'rg'))
        
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
        context['properties'] = Property.objects.filter(condo=condo).select_related('user', 'portaria_custom').order_by('address_complement', 'name')
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
                
        guests = list(checkin_obj.guests.values('name', 'document'))
        
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
            'companions': [{'name': g['name'], 'rg': g['document']} for g in guests],
            'releases': [],
            'is_cancelled': False,
            'is_manual': True
        }
        
        return JsonResponse({'status': 'success', 'data': data})


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

