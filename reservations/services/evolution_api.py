import requests
import logging
import base64
from django.conf import settings

logger = logging.getLogger(__name__)

class EvolutionService:
    """
    Serviço de integração com a Evolution API para envio de mensagens via WhatsApp.
    Implementação 100% gratuita e isolada.
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'EVOLUTION_API_URL', 'http://localhost:8010').rstrip('/')
        self.api_key = getattr(settings, 'AUTHENTICATION_API_KEY', 'vbook_secret_key_2026')
        self.headers = {
            'apikey': self.api_key,
            'Content-Type': 'application/json'
        }
        self.instance_name = 'vbook'

    def _ensure_instance_exists(self):
        """
        Verifica se a instância existe, se não, cria uma.
        """
        try:
            # Check if instance exists
            response = requests.get(
                f"{self.base_url}/instance/fetchInstances",
                headers=self.headers
            )
            
            if response.status_code == 200:
                instances = response.json()
                if any(inst.get('name') == self.instance_name or inst.get('instanceName') == self.instance_name for inst in instances):
                    return True

            # Create instance if not found
            data = {
                "instanceName": self.instance_name,
                "integration": "WHATSAPP-BAILEYS"
            }
            create_resp = requests.post(
                f"{self.base_url}/instance/create",
                headers=self.headers,
                json=data
            )
            return create_resp.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Erro ao verificar/criar instância na Evolution API: {e}")
            return False

    def enviar_link_checkin(self, reservation_id):
        """
        Envia o link de check-in para o hóspede.
        """
        from reservations.models import Reservation
        
        try:
            reserva = Reservation.objects.get(id=reservation_id)
            if not reserva.client_phone:
                return False, "Hóspede sem telefone cadastrado."

            # Garantir instância
            self._ensure_instance_exists()

            # Formatar número (remover caracteres não numéricos)
            phone = ''.join(filter(str.isdigit, reserva.client_phone))
            if not phone.startswith('55') and len(phone) <= 11:
                phone = f"55{phone}"

            checkin_url = reserva.get_checkin_url()
            
            # Determine greeting based on current hour
            import datetime
            now = datetime.datetime.now()
            hour = now.hour
            
            if 5 <= hour < 12:
                greeting = "Bom dia"
            elif 12 <= hour < 18:
                greeting = "Boa tarde"
            else:
                greeting = "Boa noite"

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

            logger.info(f"Enviando WhatsApp para {phone} via {self.base_url}")
            
            response = requests.post(
                f"{self.base_url}/message/sendText/{self.instance_name}",
                headers=self.headers,
                json=payload
            )

            if response.status_code in [200, 201]:
                logger.info(f"Mensagem de check-in enviada para {phone} (Reserva {reservation_id})")
                return True, "Mensagem enviada com sucesso."
            else:
                try:
                    resp_data = response.json()
                    error_msg = resp_data.get('message', 'Erro desconhecido')
                except:
                    error_msg = response.text or 'Erro desconhecido'
                
                logger.error(f"Erro Evolution API ({response.status_code}): {error_msg}")
                return False, f"Erro na API ({response.status_code}): {error_msg}"

        except Reservation.DoesNotExist:
            return False, "Reserva não encontrada."
        except Exception as e:
            logger.error(f"Erro inesperado no serviço de WhatsApp: {e}")
            return False, f"Erro: {str(e)}"

    def enviar_documento(self, number, file_bytes, file_name, caption=""):
        """
        Envia um documento (PDF) via WhatsApp.
        """
        try:
            # Garantir instância
            self._ensure_instance_exists()

            # Formatar número
            phone = ''.join(filter(str.isdigit, number))
            if not phone.startswith('55') and len(phone) <= 11:
                phone = f"55{phone}"

            # Encode to base64
            b64_data = base64.b64encode(file_bytes).decode('utf-8')
            media_content = b64_data

            payload = {
                "number": phone,
                "mediatype": "document",
                "mimetype": "application/pdf",
                "caption": caption,
                "media": media_content,
                "fileName": file_name,
                "delay": 1200
            }

            logger.info(f"Enviando documento para {phone} via {self.base_url}")
            
            response = requests.post(
                f"{self.base_url}/message/sendMedia/{self.instance_name}",
                headers=self.headers,
                json=payload
            )

            if response.status_code in [200, 201]:
                logger.info(f"Documento enviado com sucesso para {phone}")
                return True, "Documento enviado."
            else:
                try:
                    resp_data = response.json()
                    error_msg = resp_data.get('message', 'Erro desconhecido')
                except:
                    error_msg = response.text or 'Erro desconhecido'
                
                logger.error(f"Erro Evolution API Media ({response.status_code}): {error_msg}")
                return False, f"Erro na API ({response.status_code}): {error_msg}"

        except Exception as e:
            logger.error(f"Erro inesperado ao enviar documento: {e}")
            return False, f"Erro: {str(e)}"
