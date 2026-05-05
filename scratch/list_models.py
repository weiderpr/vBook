import google.generativeai as genai
import os
from django.conf import settings

# This script needs the Django environment
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

genai.configure(api_key=settings.GEMINI_API_KEY)

print("Listing models:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
