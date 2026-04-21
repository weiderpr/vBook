import logging
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    Service class for sending WhatsApp messages via Twilio API.
    Senior Developer implementation: Transparent, server-side, with robust logging and error handling.
    """
    
    def __init__(self):
        try:
            self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            self.from_number = f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}"
        except Exception as e:
            logger.error(f"Failed to initialize Twilio Client: {str(e)}")
            self.client = None

    def send_checkin_link(self, reservation):
        """
        Sends a check-in link to the guest's WhatsApp number.
        """
        if not self.client:
            return False, "Twilio configuration error."

        to_number = f"whatsapp:{reservation.get_whatsapp_formatted_phone()}"
        checkin_url = reservation.get_checkin_url()
        
        message_body = (
            f"Olá {reservation.client_name}! 🌊\n\n"
            f"Estamos ansiosos pela sua chegada na propriedade '{reservation.property.name}'.\n"
            f"Para agilizar seu check-in, por favor complete seus dados no link abaixo:\n\n"
            f"{checkin_url}\n\n"
            f"Obrigado, VerticeBook."
        )

        try:
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            logger.info(f"WhatsApp sent successfully to {to_number}. SID: {message.sid}")
            return True, message.sid
        except TwilioRestException as e:
            logger.error(f"Twilio error sending message to {to_number}: {e.msg}")
            return False, str(e.msg)
        except Exception as e:
            logger.exception(f"Unexpected error sending WhatsApp to {to_number}")
            return False, "Erro inesperado ao enviar mensagem."
