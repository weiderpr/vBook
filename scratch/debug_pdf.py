import os
import django
import sys

# Setup Django
sys.path.append('/root/verticebook')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from reservations.models import Reservation
from reservations.views_checkin import generate_reservation_authorization_pdf

try:
    res = Reservation.objects.get(pk=20)
    print(f"Gerando PDF para reserva {res.pk} - {res.client_name}")
    pdf_bytes = generate_reservation_authorization_pdf(res)
    
    with open('scratch/debug_res_20.pdf', 'wb') as f:
        f.write(pdf_bytes)
    print("PDF gerado com sucesso em scratch/debug_res_20.pdf")
except Exception as e:
    print(f"ERRO ao gerar PDF: {e}")
    if "Character" in str(e):
        # Tentar extrair o índice e o caractere do erro
        try:
            import re as re_mod
            match = re_mod.search(r'Character "(.*?)" at index (\d+)', str(e))
            if match:
                char = match.group(1)
                idx = int(match.group(2))
                print(f"Caractere problemático: '{char}' (Unicode: {ord(char)}) no índice {idx}")
        except:
            pass
    import traceback
    traceback.print_exc()
