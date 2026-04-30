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

AVAILABLE_TOOLS = {
    "create_reservation_tool": create_reservation_tool
}

# --- Provedores de IA ---

class AIProvider:
    def chat(self, message, history, system_instruction):
        raise NotImplementedError

class GeminiProvider(AIProvider):
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model_name = "gemini-3-flash-preview"

    def chat(self, message, history, system_instruction):
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction,
            tools=[create_reservation_tool]
        )
        chat = model.start_chat(history=history)
        response = chat.send_message(message)
        
        # Lógica de Function Calling para Gemini
        parts = response.candidates[0].content.parts
        function_call = next((part.function_call for part in parts if part.function_call), None)
        
        if function_call:
            log_debug(f"Gemini solicitou tool: {function_call.name}")
            tool_func = AVAILABLE_TOOLS.get(function_call.name)
            if tool_func:
                result = tool_func(**{k: v for k, v in function_call.args.items()})
                response = chat.send_message(
                    genai.types.Content(parts=[genai.types.Part.from_function_response(name=function_call.name, response=result)])
                )
        
        return response.text

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
            # Mantém as mensagens do usuário intactas pois contêm os dados reais
            if role == "assistant" and len(content) > 150:
                content = content[:150] + "... (truncated)"
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        # Groq Tool definition
        tools = [
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

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        
        if response_message.tool_calls:
            log_debug(f"Groq solicitou tool: {response_message.tool_calls[0].function.name}")
            for tool_call in response_message.tool_calls:
                tool_func = AVAILABLE_TOOLS.get(tool_call.function.name)
                if tool_func:
                    args = json.loads(tool_call.function.arguments)
                    result = tool_func(**args)
                    
                    messages.append(response_message)
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_call.function.name,
                        "content": json.dumps(result)
                    })
                    
                    # Segunda chamada para resposta final
                    final_response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages
                    )
                    return final_response.choices[0].message.content

        return response_message.content

class OpenRouterProvider(AIProvider):
    def __init__(self, api_key):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.model_name = "openrouter/auto"

    def chat(self, message, history, system_instruction):
        messages = [{"role": "system", "content": system_instruction}]
        for h in history:
            role = "assistant" if h['role'] == "model" else "user"
            content = h['parts'][0]
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            extra_headers={
                "HTTP-Referer": "https://verticebook.com.br",
                "X-Title": "VerticeBook Help Desk",
            }
        )
        return response.choices[0].message.content

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
            "Você é o assistente virtual do VerticeBook. Use o Guia de Ajuda para responder dúvidas.\n\n"
            f"CONTEXTO DO SISTEMA:\n{context}\n\n"
            f"{user_props_str}\n"
            f"ID da Propriedade Atual: {property_id if property_id else 'Nenhuma'}\n"
            f"PÁGINA ONDE O USUÁRIO ESTÁ AGORA: {current_url}\n\n"
            "REGRAS DE OURO (NÃO DESVIE):\n"
            "1. Responda APENAS em JSON: {\"message\": \"sua resposta aqui\", \"can_answer\": true}.\n"
            "2. ESTILO VISUAL: Use HTML rico. Use <b> para termos importantes, <br> para quebras de linha e <ul>/<li> para listas e passos.\n"
            "3. TOM DE VOZ: Seja profissional, prestativo e direto. Evite textos em bloco único; prefira listas escaneáveis.\n"
            "4. Se o usuário quiser criar reserva, explique o passo a passo de forma elegante e pergunte se ele quer sua ajuda.\n"
            "5. Se ele aceitar ajuda, você deve coletar EXATAMENTE estes 6 campos e NADA MAIS:\n"
            "   - client_name (Nome completo)\n"
            "   - client_phone (Telefone)\n"
            "   - start_date (Data inicial YYYY-MM-DD)\n"
            "   - end_date (Data final YYYY-MM-DD)\n"
            "   - total_value (Valor total em reais)\n"
            "   - guests_count (Quantidade de hóspedes)\n"
            "6. NUNCA peça por 'inquilino', 'descrição de moradia' ou 'prestadores' durante este fluxo.\n"
            "7. Peça um campo por vez. Se o usuário já informou alguns no histórico, NÃO peça de novo.\n"
            "8. Quando tiver os 6 campos, chame obrigatoriamente 'create_reservation_tool'.\n"
            "9. LINKS: Ao sugerir links do Guia de Ajuda, SUBSTITUA SEMPRE o termo '[ID]' pelo ID Real da propriedade atual informado acima.\n"
            "10. PRIVACIDADE TÉCNICA CRÍTICA: NUNCA mencione termos como 'Regras de Ouro', 'Contexto do Sistema', 'System Instruction', 'ID da Propriedade', 'Tool', 'JSON' ou qualquer variável técnica na sua resposta final para o usuário. Se você não souber a resposta ou não puder ajudar, defina \"can_answer\": false e peça desculpas de forma amigável, sugerindo que o administrador será notificado.\n"
            "11. CONTEXTO DE TELA (CRÍTICO): Se o usuário perguntar 'me explique essa tela' ou similar, você DEVE olhar o campo 'PÁGINA ONDE O USUÁRIO ESTÁ AGORA'. \n"
            "   - Se a URL for '/dashboard/', use EXCLUSIVAMENTE a seção '4. Dashboard de Gestão Centralizada' do Guia de Ajuda para explicar os 3 componentes (Desempenho Anual, Distribuição de Receita e Status Operacional).\n"
            "   - Se a URL contiver '/painel/', use a seção '6. Análise Financeira' (Dashboard da Propriedade).\n"
            "   - Seja detalhado e aponte o que cada gráfico/card naquela tela específica faz.\n"
            "12. Se você não encontrar a informação no Guia de Ajuda, responda que não tem essa informação no momento e que registrou a dúvida para nossa equipe. Defina \"can_answer\": false.\n"
            "Data Atual: " + datetime.now().strftime('%Y-%m-%d')
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
                text_response = provider.chat(user_message, history[-20:], system_instruction)
                if text_response:
                    break # Sucesso!
            except Exception as e:
                log_debug(f"Falha no provedor {provider.__class__.__name__}: {str(e)}")
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
            # Procura por algo que comece com { e termine com }
            json_match = re.search(r'({.*})', text_response, re.DOTALL)
            if json_match:
                clean_text = json_match.group(1)
            else:
                clean_text = text_response.strip()
                
            response_data = json.loads(clean_text)
        except:
            response_data = {"message": text_response, "can_answer": True}
        
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
