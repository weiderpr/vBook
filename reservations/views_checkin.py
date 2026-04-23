from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from .models import Reservation, ClientComplement, Companion
from .forms_checkin import ClientComplementForm, get_companion_formset
from .services.evolution_api import EvolutionService
import logging
import io
import re
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

        # Pre-resolve client by phone if not linked yet, scoped to the current owner
        client = reservation.client
        if not client:
            from .models import Client
            owner = reservation.property.user
            client = Client.objects.filter(
                phone=reservation.client_phone, 
                reservations__property__user=owner
            ).distinct().first()
            
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
        owner = reservation.property.user
        
        # Ensure client is resolved before form initialization
        client = reservation.client
        new_name = request.POST.get('client_name')
        
        if not client:
            from .models import Client
            # Try to find existing client FOR THIS OWNER first
            client = Client.objects.filter(
                phone=reservation.client_phone,
                reservations__property__user=owner
            ).distinct().first()
            
            if not client:
                # Create a new client record
                client = Client.objects.create(
                    phone=reservation.client_phone, 
                    name=new_name or reservation.client_name
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

class GuestAuthorizationPDFView(View):
    """
    View pública para o hóspede baixar seu PDF usando o token da reserva.
    """
    def get(self, request, token):
        reservation = get_object_or_404(Reservation, checkin_token=token)
        
        if not reservation.checkin_completed:
            return HttpResponseForbidden("O check-in ainda não foi concluído.")

        output_bytes = generate_reservation_authorization_pdf(reservation)
        
        response = HttpResponse(output_bytes, content_type='application/pdf')
        filename = f"autorizacao_{reservation.client_name}.pdf".replace(' ', '_')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response

class GuestPropertyInstructionsView(View):
    """
    View pública para o hóspede visualizar as instruções da reserva.
    """
    def get(self, request, token):
        reservation = get_object_or_404(Reservation, checkin_token=token)
        return render(request, 'reservations/property_instructions_guest.html', {
            'reservation': reservation,
            'property': reservation.property
        })

from django.contrib.auth.mixins import LoginRequiredMixin

def generate_reservation_authorization_html(reservation, for_pdf=False):
    """
    Gera o HTML final da autorização com todas as variáveis substituídas.
    """
    prop = reservation.property
    owner = prop.user
    client = reservation.client
    complement = getattr(client, 'complement', None) if client else None
    companions = reservation.companions.all()

    # 1. Obter o modelo HTML
    html_content = prop.authorization_template
    if not html_content:
        html_content = "<h2>AUTORIZAÇÃO DE LOCAÇÃO</h2><p>Modelo não configurado.</p>"

    # 2. Preparar os dados para substituição
    owner_name = getattr(owner, 'full_name', '') or owner.get_full_name() or owner.username
    client_name = client.name if client else reservation.client_name
    rg = complement.rg if complement else "---"
    cpf = complement.cpf if complement else "---"
    
    client_addr = "---"
    if complement:
        client_addr = f"{complement.street}, {complement.number}"
        if complement.complement: client_addr += f" - {complement.complement}"
        client_addr += f", {complement.neighborhood}, {complement.city}/{complement.state}"

    days = (reservation.end_date - reservation.start_date).days
    checkin_str = reservation.start_date.strftime("%d/%m/%Y")
    checkout_str = reservation.end_date.strftime("%d/%m/%Y")
    
    veic = complement.car_model if complement else "---"
    placa = complement.car_plate if complement else "---"

    # Processamento Dinâmico de Acompanhantes
    pattern_comp = re.compile(r'<(tr|li|p|div)[^>]*>(?:(?!</?\1>)[\s\S])*?\{\{\s*acompanhante_(?:nome|rg)\s*\}\}[\s\S]*?<\/\1>', re.IGNORECASE)
    
    def replacer_companions(match):
        original_block = match.group(0)
        result = ""
        for i, comp in enumerate(companions, 1):
            block = re.sub(r'\{\{\s*acompanhante_nome\s*\}\}', comp.name or '', original_block)
            block = re.sub(r'\{\{\s*acompanhante_rg\s*\}\}', comp.rg or '', block)
            result += block
        
        if not companions:
            tag_name = match.group(1).lower()
            if tag_name == 'tr':
                result = f'<tr><td colspan="100%" style="text-align: center; color: #666;">(Nenhum acompanhante cadastrado)</td></tr>'
            else:
                result = f'<{tag_name} style="color: #666;">(Nenhum acompanhante cadastrado)</{tag_name}>'
        return result

    html_content = re.sub(pattern_comp, replacer_companions, html_content)
    
    if for_pdf:
        # Limpeza apenas para o motor do PDF (WeasyPrint)
        html_content = re.sub(r'position:\s*absolute;?', '', html_content, flags=re.IGNORECASE)

    # Assinatura em HTML
    signature_html = ""
    if prop.signature:
        try:
            signature_html = f'<img src="{prop.signature.url}" class="signature-img" style="width: 120px !important; height: auto; display: inline-block; margin: 0 auto;">'
        except Exception as e:
            logger.error(f"Erro ao obter URL da assinatura: {e}")
            signature_html = '<span>(Erro ao carregar assinatura)</span>'
    else:
        signature_html = '<span>(Assinatura não cadastrada)</span>'

    data = {
        'proprietario_nome': owner_name,
        'propriedade_nome': prop.name,
        'hospede_nome': client_name,
        'hospede_rg': rg,
        'hospede_cpf': cpf,
        'hospede_endereco': client_addr,
        'hospede_telefone': client.phone if client else reservation.client_phone,
        'total_dias': str(days),
        'data_entrada': checkin_str,
        'data_saida': checkout_str,
        'veiculo_nome': veic,
        'veiculo_placa': placa,
        'assinatura_proprietario': signature_html
    }

    # 3. Substituir as variáveis
    for key, value in data.items():
        pattern = re.compile(r'\{\{\s*' + key + r'\s*\}\}')
        html_content = pattern.sub(str(value), html_content)
    
    return html_content

def generate_reservation_authorization_pdf(reservation):
    """
    Gera os bytes do PDF de autorização para uma reserva específica usando o modelo HTML.
    """
    html_content = generate_reservation_authorization_html(reservation, for_pdf=True)

    # 4. Gerar o PDF usando WeasyPrint
    try:
        from weasyprint import HTML, CSS
        from django.conf import settings
        
        base_css = CSS(string="""
            * { 
                margin: 0; 
                padding: 0; 
                box-sizing: border-box; 
            }
            @page {
                size: A4;
                margin: 8mm 12mm;
                @bottom-right {
                    content: counter(page);
                    font-size: 8pt;
                    color: #999;
                }
            }
            body {
                font-family: Arial, Helvetica, sans-serif;
                font-size: 11pt;
                line-height: 1.2;
                color: #000;
                display: flex;
                flex-direction: column;
                min-height: 281mm; /* Altura exata da página A4 menos as margens */
            }
            /* Garantir margem zero em parágrafos para bater com o reset global do dashboard */
            p { margin: 0; }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            /* Regra para mostrar bordas apenas se a tabela tiver atributo border="1" ou estilo de borda */
            table[border="1"], table.with-border {
                border: 1px solid #000;
            }
            table[border="1"] td, table[border="1"] th,
            table.with-border td, table.with-border th {
                border: 1px solid #000;
            }
            th, td {
                padding: 8px;
                vertical-align: top;
            }
            .document-footer {
                margin-top: auto !important;
                padding-top: 5mm;
                /* Removendo bordas e margens extras para ser identico ao modal de preview */
            }
            img {
                max-width: 120px;
                height: auto;
                display: inline-block;
            }
        """)

        # Gerar PDF
        pdf_bytes = HTML(string=html_content, base_url=settings.BASE_DIR).write_pdf(stylesheets=[base_css])
        return pdf_bytes

    except Exception as e:
        logger.error(f"Erro ao renderizar com WeasyPrint: {e}")
        # Fallback minimalista se WeasyPrint falhar (raro)
        from django.template.loader import render_to_string
        return b"Erro ao gerar PDF de alta fidelidade."

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

@method_decorator(xframe_options_sameorigin, name='dispatch')
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
    Recebe um PDF (via POST) ou gera um e envia via WhatsApp.
    """
    def post(self, request, property_pk, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        # Check ownership
        if reservation.property.user != request.user:
            return JsonResponse({'status': 'error', 'message': "Sem permissão"}, status=403)

        pdf_bytes = None
        
        # Tenta pegar o PDF enviado pelo frontend (Blob/Base64)
        if 'pdf_base64' in request.POST:
            try:
                import base64
                pdf_data = request.POST.get('pdf_base64')
                if ',' in pdf_data:
                    pdf_data = pdf_data.split(',')[1]
                pdf_bytes = base64.b64decode(pdf_data)
                logger.info(f"Recebido PDF via base64 para reserva {pk}")
            except Exception as e:
                logger.error(f"Erro ao decodificar PDF base64: {e}")
        
        # Se não recebeu, gera no servidor (fallback ou legibilidade)
        if not pdf_bytes:
            try:
                pdf_bytes = generate_reservation_authorization_pdf(reservation)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f"Erro ao gerar PDF: {str(e)}"}, status=500)

        # 2. Inicializar Serviço com a instância do proprietário
        service = EvolutionService(user=reservation.property.user)
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

class ReservationAuthorizationHTMLView(LoginRequiredMixin, View):
    """
    Retorna o HTML processado da autorização para preview fiel no frontend.
    """
    def get(self, request, property_pk, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        if reservation.property.user != request.user:
            return HttpResponseForbidden("Sem permissão")
            
        html_content = generate_reservation_authorization_html(reservation)
        return HttpResponse(html_content)

class ReservationAuthorizationPDFView(LoginRequiredMixin, View):
    """
    Gera o PDF da autorização para o administrador baixar.
    """
    def get(self, request, property_pk, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        if reservation.property.user != request.user:
            return HttpResponseForbidden("Sem permissão")
            
        pdf_bytes = generate_reservation_authorization_pdf(reservation)
        filename = f"Autorizacao_{reservation.start_date.strftime('%d_%m_%Y')}.pdf"
        
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

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
