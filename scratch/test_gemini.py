import google.generativeai as genai
import os
from django.conf import settings
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

def trigger_reservation_wizard(property_id: int = None):
    return {"status": "trigger_wizard", "property_id": property_id}

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="Se o usuário quiser criar reserva, chame trigger_reservation_wizard IMEDIATAMENTE. Responda apenas em JSON: {\"message\": \"...\", \"can_answer\": true}.",
    tools=[trigger_reservation_wizard]
)

response = model.generate_content("me ajude a criar uma reserva")
print("Response content:")
print(response.candidates[0].content)
