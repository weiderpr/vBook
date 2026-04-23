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

def generate_reservation_authorization_pdf(reservation):
    """
    Gera os bytes do PDF de autorização para uma reserva específica usando o modelo HTML.
    """
    prop = reservation.property
    owner = prop.user
    client = reservation.client
    complement = getattr(client, 'complement', None) if client else None
    companions = reservation.companions.all()

    # 1. Obter o modelo HTML (Fallback para um padrão se vazio)
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

    # Processamento Dinâmico de Acompanhantes (Clonagem de Blocos)
    # Encontra o bloco pai mais próximo (tr, li, p, div) que contém {{acompanhante_nome}} ou {{acompanhante_rg}}
    # e duplica o bloco inteiro para cada acompanhante.
    pattern_comp = re.compile(r'<(tr|li|p|div)[^>]*>(?:(?!</?\1>).)*?\{\{acompanhante_(?:nome|rg)\}\}.*?</\1>', re.IGNORECASE | re.DOTALL)
    
    def replacer_companions(match):
        original_block = match.group(0)
        result = ""
        for i, comp in enumerate(companions, 1):
            block = original_block.replace('{{acompanhante_nome}}', comp.name or '')
            block = block.replace('{{acompanhante_rg}}', comp.rg or '')
            # Opcional: Se o usuário quiser listar com números, podemos substituir um {{acompanhante_index}} no futuro.
            result += block
        
        # Se não houver acompanhantes, podemos remover o bloco ou colocar um aviso.
        if not companions:
            # Mantém a tag original para não quebrar tabelas, mas diz "Nenhum acompanhante"
            tag_name = match.group(1).lower()
            if tag_name == 'tr':
                result = f'<tr><td colspan="100%" style="text-align: center; color: #666;">(Nenhum acompanhante cadastrado)</td></tr>'
            else:
                result = f'<{tag_name} style="color: #666;">(Nenhum acompanhante cadastrado)</{tag_name}>'
                
        return result

    html_content = re.sub(pattern_comp, replacer_companions, html_content)

    # Assinatura em HTML
    signature_html = ""
    if prop.signature:
        try:
            # fpdf2 handles local paths in img src
            signature_html = f'<img src="{prop.signature.path}" width="120">'
        except Exception as e:
            logger.error(f"Erro ao obter path da assinatura: {e}")
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

    # 3. Substituir as variáveis simples restantes no HTML
    for key, value in data.items():
        # Regex para lidar com {{variavel}} ou {{ variavel }}
        pattern = re.compile(r'\{\{\s*' + key + r'\s*\}\}')
        html_content = pattern.sub(value, html_content)

    # 4. Gerar o PDF usando o motor HTML do fpdf2
    pdf = FPDF()
    pdf.set_margins(12, 12, 12) # Left, Top, Right em milímetros
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=12) # Bottom margin em milímetros
    
    # Adicionar fontes padrão se necessário
    pdf.set_font("helvetica", size=11)
    
    try:
        # Limpeza extra para compatibilidade com fpdf2
        html_compat = html_content
        html_compat = re.sub(r'style="text-align:\s*center;?"', 'align="center"', html_compat)
        html_compat = re.sub(r'style="text-align:\s*right;?"', 'align="right"', html_compat)
        html_compat = re.sub(r'style="text-align:\s*left;?"', 'align="left"', html_compat)
        html_compat = re.sub(r'style="text-align:\s*justify;?"', 'align="justify"', html_compat)
        
        # Lógica de Rodapé Fixo
        # Procura por um bloco com a classe document-footer
        footer_match = re.search(r'<div[^>]*class="document-footer"[^>]*>(.*?)</div>', html_compat, re.DOTALL | re.IGNORECASE)
        
        if footer_match:
            footer_html = footer_match.group(0)
            # Remove o rodapé do conteúdo principal para não duplicar
            main_html = html_compat.replace(footer_html, "")
            
            # Renderiza o conteúdo principal
            pdf.write_html(main_html)
            
            # Posiciona o rodapé na base da página (última página)
            # Aprox 40mm do fundo para caber assinatura e borda
            pdf.set_y(-45) 
            pdf.write_html(footer_html)
        else:
            # Renderização normal sem rodapé separado
            pdf.write_html(html_compat)

    except Exception as e:
        logger.error(f"Erro ao renderizar HTML no PDF: {e}")
        # Fallback caso o HTML esteja muito quebrado
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "Erro ao processar o modelo de autorização.", ln=True, align="C")
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(0, 5, f"Por favor, verifique a formatação do modelo. Erro: {str(e)}")

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
