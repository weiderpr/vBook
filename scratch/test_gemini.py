import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv('/root/verticebook/.env')
api_key = os.getenv('GEMINI_API_KEY')
print(f"API Key found: {api_key[:10]}...")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

try:
    response = model.generate_content("Oi, teste")
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
