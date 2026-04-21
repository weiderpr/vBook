from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from .models import Reservation, ClientComplement, Companion
from .forms_checkin import ClientComplementForm, get_companion_formset
from .services.evolution_api import EvolutionService
import logging
import io
from django.http import HttpResponse, HttpResponseForbidden
from fpdf import FPDF
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

class GuestCheckInView(View):
    """
    View premium para o hóspede completar seus dados.
    """
    def get(self, request, token):
        reservation = get_object_or_404(Reservation, checkin_token=token)
        
        if reservation.checkin_completed:
            return render(request, 'reservations/checkin_success.html', {'reservation': reservation})

        # Pre-resolve client by phone if not linked yet
        client = reservation.client
        if not client:
            from .models import Client
            client = Client.objects.filter(phone=reservation.client_phone).first()
            if client:
                reservation.client = client
                reservation.save(update_fields=['client'])

        complement = getattr(client, 'complement', None) if client else None
        form = ClientComplementForm(instance=complement)
        
        # Dynamic formset
        extra_companions = max(0, reservation.guests_count - 1)
        CompanionFormSet = get_companion_formset(extra=extra_companions)
        formset = CompanionFormSet(instance=reservation, queryset=Companion.objects.none())
        
        context = {
            'reservation': reservation,
            'property': reservation.property,
            'form': form,
            'formset': formset,
            'extra_companions': extra_companions,
        }
        return render(request, 'reservations/checkin_form.html', context)

    def post(self, request, token):
        reservation = get_object_or_404(Reservation, checkin_token=token)
        
        # Ensure client is resolved before form initialization
        client = reservation.client
        new_name = request.POST.get('client_name')
        
        if not client:
            from .models import Client
            client, _ = Client.objects.get_or_create(
                phone=reservation.client_phone, 
                defaults={'name': new_name or reservation.client_name}
            )
            reservation.client = client
            reservation.save(update_fields=['client'])
        
        # Update client name if changed
        if new_name and client.name != new_name:
            client.name = new_name
            client.save(update_fields=['name'])

        complement = getattr(client, 'complement', None)

        extra_companions = max(0, reservation.guests_count - 1)
        CompanionFormSet = get_companion_formset(extra=extra_companions)
        
        form = ClientComplementForm(request.POST, instance=complement)
        formset = CompanionFormSet(request.POST, instance=reservation)

        if form.is_valid() and formset.is_valid():
            comp = form.save(commit=False)
            comp.client = client
            comp.save()
            
            # Clear existing companions to prevent duplicates on multi-submission
            reservation.companions.all().delete()
            formset.save()

            reservation.checkin_completed = True
            reservation.save(update_fields=['checkin_completed'])

            return render(request, 'reservations/checkin_success.html', {'reservation': reservation})
        
        context = {
            'reservation': reservation,
            'property': reservation.property,
            'form': form,
            'formset': formset,
        }
        return render(request, 'reservations/checkin_form.html', context)

from django.contrib.auth.mixins import LoginRequiredMixin

def generate_reservation_authorization_pdf(reservation):
    """
    Gera os bytes do PDF de autorização para uma reserva específica.
    """
    prop = reservation.property
    owner = prop.user
    client = reservation.client
    complement = getattr(client, 'complement', None) if client else None
    companions = reservation.companions.all()

    # Lógica de geração do PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Cores (Preto e Branco como o modelo)
    pdf.set_text_color(0, 0, 0)
    
    # Header
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 7, "AUTORIZAÇÃO DE LOCAÇÃO", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 5, f"CONDOMÍNIO {prop.name.upper()}", ln=True, align="C")
    
    # Endereço da Propriedade
    pdf.set_font("Helvetica", "B", 10)
    address_line1 = f"{prop.address_street.upper()}, Nº{prop.address_number}"
    if prop.address_city:
        address_line1 += f" - {prop.address_city.upper()}/{prop.address_state.upper()}"
    pdf.cell(0, 4, address_line1, ln=True, align="C")
    
    if prop.address_complement:
        pdf.cell(0, 4, prop.address_complement.upper(), ln=True, align="C")
    
    pdf.ln(4)
    
    # Texto Principal
    pdf.set_font("Helvetica", "", 11)
    owner_name = getattr(owner, 'full_name', '') or owner.get_full_name() or owner.username
    client_name = client.name if client else reservation.client_name
    rg = complement.rg if complement else "---"
    cpf = complement.cpf if complement else "---"
    
    # Endereço do Cliente
    client_addr = "---"
    if complement:
        client_addr = f"{complement.street}, {complement.number}"
        if complement.complement: client_addr += f" - {complement.complement}"
        client_addr += f", {complement.neighborhood}, {complement.city}/{complement.state}"

    days = (reservation.end_date - reservation.start_date).days
    
    main_text = (
        f"Eu, {owner_name}, proprietário do {prop.name}, autorizo o Sr.(a) {client_name}, "
        f"portador do RG {rg} e CPF {cpf}, residente no endereço: {client_addr} e as pessoas "
        f"abaixo relacionadas a permanecerem em meu apartamento pelo período de {days} dias. "
        f"Fone: {client.phone if client else reservation.client_phone}"
    )
    pdf.multi_cell(0, 6, main_text)
    pdf.ln(2)
    
    # Datas e Veículo em uma linha
    pdf.set_font("Helvetica", "B", 9)
    checkin_str = reservation.start_date.strftime("%d/%m/%Y")
    checkout_str = reservation.end_date.strftime("%d/%m/%Y")
    veic = complement.car_model if complement else "---"
    placa = complement.car_plate if complement else "---"
    
    info_line = f"Início: {checkin_str} (14h) | Término: {checkout_str} (11h) | Veículo: {veic} | Placa: {placa}"
    pdf.cell(0, 6, info_line, ln=True)
    pdf.ln(1)
    
    # Tabela de Acompanhantes
    pdf.set_font("Helvetica", "BU", 10)
    pdf.cell(0, 6, "Relação das demais pessoas:", ln=True)
    pdf.set_font("Helvetica", "B", 10)
    
    # Colunas
    pdf.cell(10, 8, "#", border=1, align="C")
    pdf.cell(120, 8, "NOME", border=1, align="C")
    pdf.cell(50, 8, "RG", border=1, align="C")
    pdf.ln()
    
    pdf.set_font("Helvetica", "", 10)
    for i, comp in enumerate(companions, 1):
        pdf.cell(10, 8, str(i), border=1, align="C")
        pdf.cell(120, 8, comp.name[:60], border=1) # Limit name length
        pdf.cell(50, 8, comp.rg, border=1, align="C")
        pdf.ln()
        
    # Fill empty lines if few companions
    for i in range(len(companions) + 1, 8):
        pdf.cell(10, 8, str(i), border=1, align="C")
        pdf.cell(120, 8, "", border=1)
        pdf.cell(50, 8, "", border=1)
        pdf.ln()
        
    pdf.ln(4)
    
    # REGRAS DO CONDOMÍNIO
    pdf.set_font("Helvetica", "BU", 10)
    pdf.cell(0, 8, "Dentre as principais regras e normas do condomínio destacamos:", ln=True, align="C")
    pdf.ln(2)
    
    rules = [
        ("OBRIGATORIEDADE DO USO DE PULSEIRA DE IDENTIFICAÇÃO", "é obrigatório o uso da pulseira de identificação, que será colocada no locatário pelo porteiro no momento do check-in. O locatário deverá permanecer com a pulseira por todo período em que estiver hospedado no condomínio. Em caso de perda ou extravio da pulseira será cobrada uma taxa no valor de R$ 3,00 para reposição da mesma."),
        ("OBRIGATORIEDADE DO USO DE CRACHÁ VEICULAR", "cada veículo receberá no momento do check-in um crachá veicular modelo gancho. O crachá deve ser colocado de forma visível no para-brisa do veículo e somente veículos com crachá terão liberação para entrada ao condomínio. O locatário deverá devolver o crachá na portaria no momento do check-out e em caso de perda ou extravio o proprietário do apto deverá arcar com os custos para emissão da 2ª via do crachá veicular."),
        ("BARULHO", "Proibido perturbar o sossego dos moradores a qualquer hora, quer na área comum quer no interior da própria unidade especialmente no horário de silêncio no período das 22:00 as 08:00 horas da manhã."),
        ("LIXO", "Proibido lançar detritos, varreduras, ou qualquer objeto pelas janelas. O lixo deverá ser acondicionado em sacos plásticos e colocado na lixeira do prédio tomando cuidado para que não ocorram respingos."),
        ("ÁGUA", "Não desperdiçar água. Proibido o uso de água para lavagem de carros, barcos ou motocicletas na área comum do prédio."),
        ("VARAIS DE ROUPA", "Não colocar varais de roupas, estender, bater ou secar tapetes ou roupas nas janelas, nas sacadas, bem como nos corredores e nas áreas comuns;"),
        ("PISCINA", "Não levar para o recinto da piscina frascos, copos, garrafas em vidro, porcelana ou material similar que possam quebrar, demais recipientes plásticos poderão ser utilizados desde que fora da água. O usuário que deixar detritos na piscina de qualquer espécie ou origem será convocado para removê-los."),
        ("QUANTIDADE DE PESSOAS POR APTO", "Fica estabelecido um limite de 08 pessoas, incluindo crianças mesmo que de colo."),
        ("NO APARTAMENTO", "Não molhar a área seca dos banheiros, não dependurar roupas e/ou toalhas molhadas nas portas, não sujar as paredes, não subir nas cadeiras, não apoiar peso nas mesas e/ou racks, retirar constantemente o lixo do apartamento (lixeira ao lado da portaria social), não pular nas camas e sofá.")
    ]
    
    pdf.set_font("Helvetica", "", 7)
    for title, text in rules:
        pdf.set_font("Helvetica", "B", 7)
        pdf.write(4, f"{title}: ")
        pdf.set_font("Helvetica", "", 7)
        pdf.write(4, f"{text}\n")
        pdf.ln(2)
        
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, "O condômino deverá ser comunicado de qualquer quebra do regulamento e se houver despesa deverá arcar com os custos.")
    
    # Assinaturas
    pdf.ln(20)
    curr_y = pdf.get_y()
    
    if prop.signature:
        try:
            pdf.image(prop.signature.path, x=35, y=curr_y-18, w=40)
        except Exception as e:
             logger.error(f"Erro ao carregar assinatura: {e}")

    pdf.line(20, curr_y, 90, curr_y)
    pdf.line(120, curr_y, 190, curr_y)
    pdf.ln(2)
    pdf.set_x(20)
    pdf.cell(70, 5, "Proprietário", align="C")
    pdf.set_x(120)
    pdf.cell(70, 5, "Locatário", align="C")
    
    return bytes(pdf.output())

class ReservationGuestDetailView(LoginRequiredMixin, View):
    """
    Retorna um fragmento HTML com os dados do hóspede para o modal.
    """
    def get(self, request, property_pk, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Check ownership
        if reservation.property.user != request.user:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Você não tem permissão para ver estes dados.")

        client = reservation.client
        complement = getattr(client, 'complement', None) if client else None
        companions = reservation.companions.all()
        
        context = {
            'reservation': reservation,
            'client': client,
            'complement': complement,
            'companions': companions,
        }
        return render(request, 'reservations/includes/guest_detail_modal_content.html', context)

class ReservationAuthorizationPDFView(LoginRequiredMixin, View):
    """
    Gera um PDF da autorização de locação baseado na imagem modelo.
    """
    def get(self, request, property_pk, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Verificar permissão (pertence ao usuário logado)
        if reservation.property.user != request.user:
            return HttpResponseForbidden("Você não tem permissão para gerar este documento.")

        if not reservation.checkin_completed:
            messages.warning(request, "A autorização só pode ser gerada após o check-in ser concluído pelo hóspede.")
        # Gerar bytes usando a nova função helper
        output_bytes = generate_reservation_authorization_pdf(reservation)
        
        # Identificar resposta
        response = HttpResponse(output_bytes, content_type='application/pdf')
        filename = f"autorizacao_{reservation.property.name}_{reservation.start_date}.pdf".replace(' ', '_')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Content-Length'] = len(output_bytes)
        response['X-Frame-Options'] = 'SAMEORIGIN'
        
        return response

class ReservationSendAuthorizationWhatsAppView(LoginRequiredMixin, View):
    """
    Gera o PDF e envia via WhatsApp para o hóspede e para o condomínio.
    """
    def post(self, request, property_pk, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Check ownership
        if reservation.property.user != request.user:
            return JsonResponse({'status': 'error', 'message': "Sem permissão"}, status=403)

        # 1. Gerar PDF
        try:
            pdf_bytes = generate_reservation_authorization_pdf(reservation)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f"Erro ao gerar PDF: {str(e)}"}, status=500)

        # 2. Inicializar Serviço
        service = EvolutionService()
        filename = f"Autorizacao_{reservation.start_date.strftime('%d_%m_%Y')}.pdf"
        
        results = []
        any_success = False
        
        # 3. Enviar para o Hóspede
        guest_phone = reservation.client_phone
        if guest_phone:
            caption = f"Olá {reservation.client_name}, segue sua autorização de locação para a propriedade {reservation.property.name}."
            ok, msg = service.enviar_documento(guest_phone, pdf_bytes, filename, caption)
            results.append({'to': 'Hóspede', 'ok': ok, 'msg': msg})
            if ok: any_success = True
        
        # 4. Enviar para o Condomínio
        condo_phone = reservation.property.condo_phone
        if condo_phone:
            caption = f"Segue autorização de locação para {reservation.client_name} - {reservation.property.name}."
            ok, msg = service.enviar_documento(condo_phone, pdf_bytes, filename, caption)
            results.append({'to': 'Condomínio', 'ok': ok, 'msg': msg})
            if ok: any_success = True
        else:
            results.append({'to': 'Condomínio', 'ok': False, 'msg': 'Telefone do condomínio não cadastrado.'})

        # 5. Atualizar Status na Reserva se houver pelo menos um sucesso
        if any_success:
            reservation.authorization_sent = True
            reservation.authorization_sent_at = timezone.now()
            reservation.save(update_fields=['authorization_sent', 'authorization_sent_at'])

        return JsonResponse({
            'status': 'success' if any_success else 'error',
            'message': str(_("Mensagem enviada com sucesso!")) if any_success else str(_("Erro ao enviar mensagem via WhatsApp. Verifique a conexão.")),
            'details': results
        })
class ReservationCheckInResetView(LoginRequiredMixin, View):
    """
    Exclui os dados de check-in (acompanhantes, vínculo com cliente) e 
    permite que a reserva seja preenchida novamente.
    """
    def post(self, request, property_pk, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Check ownership
        if reservation.property.user != request.user:
            return HttpResponseForbidden("Sem permissão")

        # 1. Delete companions
        reservation.companions.all().delete()

        # 2. Delete complement if exists
        client = reservation.client
        if client and hasattr(client, 'complement'):
            client.complement.delete()

        # 3. Reset fields
        reservation.checkin_completed = False
        reservation.client = None
        reservation.authorization_sent = False
        reservation.authorization_sent_at = None
        
        reservation.save()

        messages.success(request, _("Dados de check-in excluídos com sucesso. O hóspede já pode preencher novamente."))
        return redirect('reservations:list', property_pk=property_pk)
