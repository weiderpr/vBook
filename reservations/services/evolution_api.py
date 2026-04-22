import requests
import logging
import base64
from django.conf import settings

logger = logging.getLogger(__name__)

class EvolutionService:
    """
    Serviço de integração com a Evolution API para envio de mensagens via WhatsApp.
    Suporta múltiplas instâncias (uma por usuário).
    """
    
    def __init__(self, user=None, instance_name=None):
        self.base_url = getattr(settings, 'EVOLUTION_API_URL', 'http://localhost:8010').rstrip('/')
        self.global_api_key = getattr(settings, 'AUTHENTICATION_API_KEY', 'vbook_secret_key_2026')
        self.headers = {
            'apikey': self.global_api_key,
            'Content-Type': 'application/json'
        }
        
        if user:
            self.instance_name = user.whatsapp_instance_name or f"vbook_{user.id}"
            self.instance_key = user.whatsapp_instance_key
        else:
            self.instance_name = instance_name or 'vbook'
            self.instance_key = None

    def _apply_minimal_settings(self, name):
        """Aplica configurações mínimas para a instância (não guardar histórico, ignorar grupos, etc)."""
        settings_payload = {
            "rejectCall": True,
            "msgCall": "",
            "groupsIgnore": True,
            "alwaysOnline": False,
            "readMessages": False,
            "readStatus": False,
            "syncFullHistory": False
        }
        try:
            requests.post(
                f"{self.base_url}/settings/set/{name}",
                headers=self.headers,
                json=settings_payload,
                timeout=5
            )
        except Exception as e:
            logger.error(f"Erro ao aplicar configurações mínimas na instância {name}: {e}")

    def create_instance(self, instance_name=None):
        """Cria uma nova instância na Evolution API ou retorna a existente."""
        name = instance_name or self.instance_name
        data = {
            "instanceName": name,
            "integration": "WHATSAPP-BAILEYS"
        }
        try:
            response = requests.post(
                f"{self.base_url}/instance/create",
                headers=self.headers,
                json=data
            )
            if response.status_code in [200, 201]:
                self._apply_minimal_settings(name)
                return response.json()
            
            # Se já existir ou erro de permissão (normalmente ocorre se já existir na v2)
            if response.status_code in [403, 409, 400]:
                logger.info(f"Instância {name} já pode existir ({response.status_code}). Tentando recuperar...")
                # Busca as instâncias existentes
                fetch_response = requests.get(
                    f"{self.base_url}/instance/fetchInstances",
                    headers=self.headers
                )
                if fetch_response.status_code == 200:
                    instances = fetch_response.json()
                    for inst in instances:
                        if inst.get('name') == name or inst.get('instanceName') == name:
                            self._apply_minimal_settings(name)
                            # Formata para que o código chamador encontre o 'hash' (token)
                            return {
                                'instance': inst,
                                'hash': inst.get('token')
                            }
            
            logger.error(f"Erro Evolution API Create ({response.status_code}): {response.text}")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar/recuperar instância na Evolution API: {e}")
            return None

    def get_connection_status(self):
        """Verifica o status da conexão da instância usando múltiplos métodos para maior precisão."""
        try:
            # 1. Tenta o endpoint rápido de estado
            response = requests.get(
                f"{self.base_url}/instance/connectionState/{self.instance_name}",
                headers=self.headers
            )
            status = None
            if response.status_code == 200:
                data = response.json()
                status = data.get('instance', {}).get('state')
            elif response.status_code == 404:
                return 'not_found'
            
            # 2. Se o status for ambíguo (ex: 'connecting' ou erro), consulta a lista geral (como o Manager faz)
            if status != 'open':
                fetch_response = requests.get(
                    f"{self.base_url}/instance/fetchInstances",
                    headers=self.headers
                )
                if fetch_response.status_code == 200:
                    instances = fetch_response.json()
                    for inst in instances:
                        if inst.get('name') == self.instance_name or inst.get('instanceName') == self.instance_name:
                            # Se na lista geral estiver 'open', confiamos nisso (alinha com o Manager)
                            api_status = inst.get('connectionStatus') or inst.get('status')
                            if api_status == 'open':
                                return 'open'
                            return api_status or status
                elif fetch_response.status_code == 404:
                    return 'not_found'
            
            return status or 'disconnected'
        except Exception as e:
            logger.error(f"Erro ao verificar status da instância {self.instance_name}: {e}")
            return 'disconnected'

    def get_qrcode(self):
        """Obtém o QR Code para conexão."""
        try:
            response = requests.get(
                f"{self.base_url}/instance/connect/{self.instance_name}",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar QR Code para {self.instance_name}: {e}")
            return None

    def logout_instance(self):
        """Desconecta o WhatsApp da instância."""
        try:
            response = requests.delete(
                f"{self.base_url}/instance/logout/{self.instance_name}",
                headers=self.headers
            )
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Erro ao fazer logout da instância {self.instance_name}: {e}")
            return False

    def delete_instance(self):
        """Remove a instância da Evolution API."""
        try:
            response = requests.delete(
                f"{self.base_url}/instance/delete/{self.instance_name}",
                headers=self.headers
            )
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Erro ao deletar instância {self.instance_name}: {e}")
            return False

    def _ensure_instance_exists(self):
        """Verifica se a instância existe, se não, tenta criar."""
        try:
            response = requests.get(
                f"{self.base_url}/instance/fetchInstances",
                headers=self.headers
            )
            if response.status_code == 200:
                instances = response.json()
                if any(inst.get('name') == self.instance_name or inst.get('instanceName') == self.instance_name for inst in instances):
                    return True

            return self.create_instance() is not None
        except Exception as e:
            logger.error(f"Erro ao assegurar instância {self.instance_name}: {e}")
            return False

    def enviar_link_checkin(self, reservation_id):
        """Envia o link de check-in para o hóspede."""
        from reservations.models import Reservation
        try:
            reserva = Reservation.objects.get(id=reservation_id)
            if not reserva.client_phone:
                return False, "Hóspede sem telefone cadastrado."

            # Garantir que a instância do proprietário existe
            self._ensure_instance_exists()

            phone = ''.join(filter(str.isdigit, reserva.client_phone))
            if not phone.startswith('55') and len(phone) <= 11:
                phone = f"55{phone}"

            checkin_url = reserva.get_checkin_url()
            
            import datetime
            hour = datetime.datetime.now().hour
            if 5 <= hour < 12: greeting = "Bom dia"
            elif 12 <= hour < 18: greeting = "Boa tarde"
            else: greeting = "Boa noite"

            message = (
                f"Olá, *{reserva.client_name}*, {greeting}. Obrigado pela sua reserva. "
                f"Abaixo seguem alguns dados para conferência:\n\n"
                f"*{reserva.property.name}*\n"
                f"*{reserva.start_date.strftime('%d/%m/%Y')}* até *{reserva.end_date.strftime('%d/%m/%Y')}*.\n\n"
                "Por favor, preencha os dados no link abaixo para a sua autorização no condomínio.\n\n"
                f"{checkin_url}"
            )

            payload = {
                "number": phone,
                "text": message,
                "delay": 1200,
                "linkPreview": True
            }

            response = requests.post(
                f"{self.base_url}/message/sendText/{self.instance_name}",
                headers=self.headers,
                json=payload
            )

            if response.status_code in [200, 201]:
                return True, "Mensagem enviada com sucesso."
            
            error_data = {}
            try:
                error_data = response.json()
            except: pass
            
            msg = error_data.get('response', {}).get('message') or error_data.get('message') or f"Erro na API ({response.status_code})"
            return False, msg

        except Exception as e:
            logger.error(f"Erro no envio de check-in: {e}")
            return False, f"Erro: {str(e)}"

    def enviar_documento(self, number, file_bytes, file_name, caption=""):
        """Envia um documento (PDF) via WhatsApp."""
        try:
            self._ensure_instance_exists()

            phone = ''.join(filter(str.isdigit, number))
            if not phone.startswith('55') and len(phone) <= 11:
                phone = f"55{phone}"

            b64_data = base64.b64encode(file_bytes).decode('utf-8')
            payload = {
                "number": phone,
                "mediatype": "document",
                "mimetype": "application/pdf",
                "caption": caption,
                "media": b64_data,
                "fileName": file_name,
                "delay": 1200
            }

            response = requests.post(
                f"{self.base_url}/message/sendMedia/{self.instance_name}",
                headers=self.headers,
                json=payload
            )

            if response.status_code in [200, 201]:
                return True, "Documento enviado."
            
            error_data = {}
            try:
                error_data = response.json()
            except: pass
            msg = error_data.get('response', {}).get('message') or error_data.get('message') or f"Erro API: {response.status_code}"
            return False, msg
        except Exception as e:
            logger.error(f"Erro ao enviar documento: {e}")
            return False, str(e)
