import json
import os
import google.generativeai as genai
from groq import Groq
from openai import OpenAI
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from pathlib import Path
from datetime import datetime
import logging
import traceback

# Configuração de Log local
debug_log_path = Path(settings.BASE_DIR) / 'chatbot_debug.log'
def log_debug(msg):
    with open(debug_log_path, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")

# --- Ferramentas (Tools) ---
def create_reservation_tool(property_id: int, client_name: str, client_phone: str, start_date: str, end_date: str, total_value: float, guests_count: int = 1):
    """Cria uma nova reserva no VerticeBook."""
    from reservations.models import Reservation, Client
    from properties.models import Property
    try:
        prop = Property.objects.get(id=int(property_id))
        client, _ = Client.objects.get_or_create(name=client_name, defaults={'phone': client_phone})
        sd = datetime.strptime(start_date, '%Y-%m-%d').date()
        ed = datetime.strptime(end_date, '%Y-%m-%d').date()
        res = Reservation.objects.create(
            property=prop, client=client, client_name=client_name, client_phone=client_phone,
            start_date=sd, end_date=ed, total_value=float(total_value), guests_count=int(guests_count)
        )
        return {"status": "success", "message": f"Reserva #{res.id} criada!", "reservation_id": res.id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def trigger_reservation_wizard(property_id: int = None):
    """Aciona o assistente do sistema para coletar dados e criar uma reserva de forma guiada."""
    return {"status": "trigger_wizard", "property_id": property_id}

AVAILABLE_TOOLS = {
    "create_reservation_tool": create_reservation_tool,
    "trigger_reservation_wizard": trigger_reservation_wizard
}

# --- Provedores de IA ---

class AIProvider:
    def chat(self, message, history, system_instruction):
        # Retorna (texto_da_resposta, se_executou_tool)
        raise NotImplementedError

class GeminiProvider(AIProvider):
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model_name = "gemini-2.0-flash"

    def chat(self, message, history, system_instruction):
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction,
            tools=[create_reservation_tool, trigger_reservation_wizard]
        )
        chat = model.start_chat(history=history)
        response = chat.send_message(message)
        
        # Lógica de Function Calling para Gemini
        parts = response.candidates[0].content.parts
        function_call = next((part.function_call for part in parts if part.function_call), None)
        
        was_tool_called = False
        if function_call:
            was_tool_called = True
            log_debug(f"Gemini solicitou tool: {function_call.name}")
            tool_func = AVAILABLE_TOOLS.get(function_call.name)
            if tool_func:
                result = tool_func(**{k: v for k, v in function_call.args.items()})
                
                # Check for Wizard Trigger
                if result.get('status') == 'trigger_wizard':
                    return json.dumps({
                        "message": "Perfeito! Vou te ajudar com isso agora mesmo. Iniciando assistente de reserva...",
                        "mode": "wizard",
                        "property_id": result.get('property_id'),
                        "can_answer": True
                    }), True

                try:
                    # Forma correta e mais compatível de enviar a resposta da tool
                    response = chat.send_message(
                        parts=[{
                            'function_response': {
                                'name': function_call.name,
                                'response': result
                            }
                        }]
                    )
                except Exception as e:
                    log_debug(f"Falha na resposta final do Gemini após tool: {str(e)}")
                    # Se a ação no banco foi um sucesso, garantimos a resposta ao usuário mesmo com erro na IA
                    if result.get('status') == 'success':
                        return json.dumps({
                            "message": f"<b>Ok! {result.get('message')}</b><br>A reserva foi registrada com sucesso no sistema. (Houve um problema técnico ao gerar a mensagem final de confirmação, mas a ação foi concluída).",
                            "can_answer": True
                        }), True
                    raise e
        
        return response.text, was_tool_called

class GroqProvider(AIProvider):
    def __init__(self, api_key):
        # max_retries=0 impede que o sistema fique "pensando" (lento) quando a cota acaba
        self.client = Groq(api_key=api_key, max_retries=0)
        self.model_name = "llama-3.1-8b-instant"

    def chat(self, message, history, system_instruction):
        # Converte histórico do formato Gemini para OpenAI/Groq, economizando tokens
        messages = [{"role": "system", "content": system_instruction}]
        for h in history:
            role = "assistant" if h['role'] == "model" else "user"
            content = h['parts'][0]
            # Trunca respostas muito longas do assistente para economizar tokens
            if role == "assistant" and len(content) > 150:
                content = content[:150] + "... (truncated)"
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        # Groq Tool definition
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "trigger_reservation_wizard",
                    "description": "Aciona o assistente do sistema para criar uma reserva de forma guiada",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {"type": "integer"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_reservation_tool",
                    "description": "Cria uma nova reserva no VerticeBook",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {"type": "integer"},
                            "client_name": {"type": "string"},
                            "client_phone": {"type": "string"},
                            "start_date": {"type": "string", "description": "Formato YYYY-MM-DD"},
                            "end_date": {"type": "string", "description": "Formato YYYY-MM-DD"},
                            "total_value": {"type": "number"},
                            "guests_count": {"type": "integer"}
                        },
                        "required": ["property_id", "client_name", "client_phone", "start_date", "end_date", "total_value"]
                    }
                }
            }
        ]

        # Captura explícita de erros HTTP (429, 503, etc.) para garantir fallback ao próximo provider
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                timeout=15.0
            )
        except Exception as groq_err:
            log_debug(f"GroqProvider erro na chamada inicial: {str(groq_err)}")
            raise  # Re-lança para o loop de fallback capturar e ir para OpenRouter

        response_message = response.choices[0].message

        if response_message.tool_calls:
            log_debug(f"Groq solicitou tool: {response_message.tool_calls[0].function.name}")
            for tool_call in response_message.tool_calls:
                tool_func = AVAILABLE_TOOLS.get(tool_call.function.name)
                if tool_func:
                    args = json.loads(tool_call.function.arguments)
                    result = tool_func(**args)

                    # Check for Wizard Trigger
                    if result.get('status') == 'trigger_wizard':
                        return json.dumps({
                            "message": "Com certeza! Iniciando o assistente de reserva para você...",
                            "mode": "wizard",
                            "property_id": result.get('property_id'),
                            "can_answer": True
                        }), True

                    messages.append(response_message)
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_call.function.name,
                        "content": json.dumps(result)
                    })

                    try:
                        # Segunda chamada para resposta final
                        final_response = self.client.chat.completions.create(
                            model=self.model_name,
                            messages=messages,
                            timeout=15.0
                        )
                        return final_response.choices[0].message.content, True
                    except Exception as e:
                        log_debug(f"Falha na resposta final do Groq após tool: {str(e)}")
                        if result.get('status') == 'success':
                            return json.dumps({
                                "message": f"<b>Ok! {result.get('message')}</b><br>A reserva foi criada.",
                                "can_answer": True
                            }), True
                        raise e

        return response_message.content, False


class OpenRouterProvider(AIProvider):
    def __init__(self, api_key):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        # Lista de modelos free/baratos para fallback interno
        self.models = [
            "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.1-8b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
            "openrouter/auto"
        ]

    def chat(self, message, history, system_instruction):
        messages = [{"role": "system", "content": system_instruction}]
        for h in history:
            role = "assistant" if h['role'] == "model" else "user"
            content = h['parts'][0]
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        last_error = None
        for model in self.models:
            try:
                log_debug(f"OpenRouter: tentando modelo {model}")
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    extra_headers={
                        "HTTP-Referer": "https://verticebook.com.br",
                        "X-Title": "VerticeBook Help Desk",
                    },
                    timeout=20.0
                )
                return response.choices[0].message.content, False
            except Exception as e:
                last_error = str(e)
                log_debug(f"OpenRouter: falha no modelo {model}: {last_error}")
                continue
        
        raise Exception(f"Todos os modelos do OpenRouter falharam. Último erro: {last_error}")

# --- View Principal ---

@csrf_exempt
def chat_query_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '')
        property_id = data.get('property_id', '')
        current_url = data.get('current_url', 'Página inicial')
        history = data.get('history', [])
        
        # --- Detecção Rápida de Intenção (sem IA) ---
        # Exige VERBOS DE AÇÃO junto com palavras de reserva para evitar acionar o wizard
        # em perguntas informativas como "o que é uma reserva?"
        RESERVATION_ACTION_PATTERNS = [
            'fazer uma reserva', 'fazer reserva', 'criar reserva', 'nova reserva',
            'registrar reserva', 'cadastrar reserva', 'agendar', 'agendamento',
            'quero reservar', 'preciso reservar', 'cadastrar hóspede', 'registrar hóspede',
            'me ajude a reservar', 'fazer um check-in', 'fazer checkin',
            'adicionar reserva', 'incluir reserva', 'abrir reserva', 'criar uma reserva',
            'ajuda com reserva', 'marcar reserva', 'marcar agendamento'
        ]
        msg_lower = user_message.strip().lower()
        
        # Filtro de segurança: se falar em "manutenção", não é reserva
        is_maintenance = 'manutenção' in msg_lower or 'manutencao' in msg_lower
        
        log_debug(f"Avaliando detecção rápida para: '{msg_lower}'")
        
        if not is_maintenance and any(pattern in msg_lower for pattern in RESERVATION_ACTION_PATTERNS):
            prop_id_for_wizard = property_id if str(property_id).isdigit() else None
            log_debug(f"Detecção por palavras-chave: intenção de reserva detectada. property_id={prop_id_for_wizard}")
            return JsonResponse({
                "message": "Com certeza! Iniciando o assistente de reserva para você...",
                "mode": "wizard",
                "property_id": prop_id_for_wizard,
                "can_answer": True
            })
        # --- Fim da Detecção Rápida ---

        # Carregar contexto - OTIMIZADO EXTREMO: Apenas o Guia de Ajuda
        base_dir = settings.BASE_DIR
        files_to_read = [
            base_dir / 'HELP_GUIDE.md',
            # Removido STANDARDS e models para evitar Rate Limit diário (TPD)
        ]
        
        context = ""
        for file_path in files_to_read:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    context += f"--- {file_path.name} ---\n{f.read()}\n\n"
        
        # Propriedades do usuário
        user_props_str = ""
        if request.user.is_authenticated:
            from properties.models import Property
            user_properties = list(Property.objects.filter(user=request.user).values('id', 'name'))
            user_props_str = "Propriedades: " + ", ".join([f"{p['name']} (ID:{p['id']})" for p in user_properties])

        system_instruction = (
            "Você é o assistente do VerticeBook. REGRAS:\n"
            "1. Responda APENAS em JSON: {\"message\": \"...\", \"can_answer\": true}.\n"
            "2. Estilo: Use <b> e <br> para formatar a 'message'. Seja direto.\n"
            "3. RESERVA/AGENDAMENTO: Se o usuário quiser criar uma reserva, registrar hóspede ou agendar, chame IMEDIATAMENTE 'trigger_reservation_wizard' e pare. Resposta: 'Iniciando assistente...'.\n"
            "4. Não tente coletar dados sozinho nem desenhar formulários.\n"
            f"CONTEXTO:\n{context}\n"
            f"{user_props_str}\n"
            f"Página: {current_url}\n"
            "Data: " + datetime.now().strftime('%Y-%m-%d')
        )

        providers = []
        
        # Tentar Gemini primeiro
        gemini_key = getattr(settings, 'GEMINI_API_KEY', None)
        if gemini_key and "AIza" in str(gemini_key): # Basic check for Gemini key
            providers.append(GeminiProvider(gemini_key))
            log_debug("GeminiProvider adicionado.")
            
        # Tentar Groq depois
        groq_key = getattr(settings, 'GROQ_API_KEY', None)
        if groq_key and "gsk_" in str(groq_key): # Basic check for Groq key
            providers.append(GroqProvider(groq_key))
            log_debug("GroqProvider adicionado.")

        # Tentar OpenRouter como última instância (Resiliência Total)
        or_key = getattr(settings, 'OPENROUTER_API_KEY', None)
        if or_key and "sk-or-" in str(or_key):
            providers.append(OpenRouterProvider(or_key))
            log_debug("OpenRouterProvider adicionado.")

        if not providers:
            log_debug("ALERTA: Nenhum provedor configurado!")
            return JsonResponse({'message': 'Erro: Nenhum provedor de IA disponível ou configurado no servidor.'})
        
        text_response = None
        for provider in providers:
            try:
                log_debug(f"Tentando provedor: {provider.__class__.__name__}")
                text_response, tool_executed = provider.chat(user_message, history[-20:], system_instruction)
                if text_response:
                    break # Sucesso!
            except Exception as e:
                log_debug(f"Falha no provedor {provider.__class__.__name__}: {str(e)}")
                # Se uma tool foi executada (mesmo que tenha falhado depois), NÃO tentamos outro provedor
                # para evitar duplicidade de ações no banco de dados.
                if 'tool_executed' in locals() and tool_executed:
                    log_debug("Interrompendo fallback pois uma tool já foi executada.")
                    break
                continue # Próximo...

        if not text_response:
            msg = 'Estamos com alta demanda nas APIs de IA. Por favor, tente novamente em alguns segundos.'
            from .models import ChatInteraction
            ChatInteraction.objects.create(
                user=request.user if request.user.is_authenticated else None,
                question=user_message,
                answer=msg,
                current_url=current_url,
                status='error'
            )
            return JsonResponse({'message': msg})

        # Processar resposta JSON com mais robustez
        try:
            import re
            # Tentar extrair o JSON (procurando a primeira e última chave)
            json_match = re.search(r'(\{.*\})', text_response, re.DOTALL)
            if json_match:
                clean_json = json_match.group(1)
                try:
                    response_data = json.loads(clean_json)
                except:
                    # Se falhar o parse mas houver texto útil, tentamos limpar
                    # Se a IA misturou JSON com texto livre, pegamos o texto livre como mensagem
                    if '"message":' in clean_json:
                        # Tenta extrair apenas o valor da chave message via regex simples
                        msg_extract = re.search(r'"message":\s*"(.*?)"', clean_json, re.DOTALL)
                        if msg_extract:
                            response_data = {"message": msg_extract.group(1), "can_answer": True}
                        else:
                            response_data = {"message": text_response, "can_answer": True}
                    else:
                        response_data = {"message": text_response, "can_answer": True}
            else:
                response_data = {"message": text_response, "can_answer": True}
        except:
            response_data = {"message": text_response, "can_answer": True}
            
        # Limpeza final: se a mensagem contiver JSON interno, preservamos TODOS os campos
        # IMPORTANTE: isso garante que mode/property_id do wizard não sejam descartados
        if isinstance(response_data.get('message'), str) and response_data['message'].strip().startswith('{'):
            try:
                second_attempt = json.loads(response_data['message'])
                if isinstance(second_attempt, dict) and 'message' in second_attempt:
                    response_data.update(second_attempt)  # merge completo, preserva mode/property_id
            except:
                pass

        
        # Registrar no Banco de Dados
        from .models import ChatInteraction
        status = 'answered'
        if not response_data.get('can_answer', True):
            status = 'unresolved'
            
        ChatInteraction.objects.create(
            user=request.user if request.user.is_authenticated else None,
            question=user_message,
            answer=response_data.get('message', ''),
            current_url=current_url,
            status=status
        )
        
        return JsonResponse(response_data)

    except Exception as e:
        log_debug(f"Erro Fatal: {str(e)}\n{traceback.format_exc()}")
        msg = 'Desculpe, serviço temporariamente indisponível.'
        try:
            from .models import ChatInteraction
            ChatInteraction.objects.create(
                user=request.user if request.user.is_authenticated else None,
                question=user_message if 'user_message' in locals() else 'N/A',
                answer=str(e),
                current_url=current_url if 'current_url' in locals() else 'N/A',
                status='error'
            )
        except:
            pass
        return JsonResponse({'message': msg})

@csrf_exempt
def chat_wizard_step_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        message = data.get('message', '')
        raw_property_id = data.get('property_id')
        is_init = data.get('init', False)
        
        # Converte property_id para int ou None com segurança
        property_id = None
        if raw_property_id and str(raw_property_id).isdigit():
            property_id = int(raw_property_id)

        from .wizard_logic import ReservationWizard
        wizard = ReservationWizard(request.session)
        
        if is_init:
            # First question
            reply = wizard.get_next_question(property_id)
            is_done = False
            mode = 'wizard'
        else:
            # Process answer
            reply, is_done, mode = wizard.process_answer(message, request.user)
            
        if is_done:
            # Clear wizard state
            if 'wizard_data' in request.session: del request.session['wizard_data']
            if 'wizard_step' in request.session: del request.session['wizard_step']
        else:
            wizard.save_state(request.session)
            
        return JsonResponse({
            'message': reply,
            'is_done': is_done,
            'mode': mode
        })
    except Exception as e:
        log_debug(f"Erro no Wizard: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'message': 'Houve um problema no assistente. Voltando ao chat normal.', 'is_done': True, 'mode': 'normal'})

def help_center_view(request):
    return render(request, 'ajuda/help_center.html')

@csrf_exempt
def save_help_preference(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
        
    try:
        data = json.loads(request.body)
        help_id = data.get('help_id')
        show_again = data.get('show_again', True)
        
        if not help_id:
            return JsonResponse({'error': 'Missing help_id'}, status=400)
            
        from .models import HelpPreference
        pref, created = HelpPreference.objects.update_or_create(
            user=request.user,
            help_id=help_id,
            defaults={'show_again': show_again}
        )
        
        return JsonResponse({'status': 'success', 'created': created})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
