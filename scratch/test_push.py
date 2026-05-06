import json
import os
import logging
from pywebpush import webpush, WebPushException

# Configure logging to see what's happening
logging.basicConfig(level=logging.DEBUG)

private_key_path = '/root/verticebook/private_key.pem'
admin_email = 'admin@verticebook.tech'

sub_info = {
    "endpoint": "https://web.push.apple.com/QLZGadbaOt5WVjpnMNa0fAscU8JgKEsu2tc-J2zQvxRiU26irZRcKKRrZ1zkTy_zaOF2wl5pUZuXfZapAHE0scEatWZ5AOCow3K7sFA3ToHHeT5-M1I9iQHClU00C1i2p2MXx6cBJcB2QQNBvfHIHeXGLcJZ08UVym4j2Ob22zw",
    "keys": {
        "p256dh": "BNTf+LknsPnx/1t+jzNg8BEEZXKQLZlWMZ7CeMuCuo3R0/eK6gulM4W/DftGN+sWk7wk7+LKYS6ynEFKM/EiGX8=",
        "auth": "+QsO8IGDxOLWQcGtVq3lhw=="
    }
}

payload = {
    "title": "Teste Manual",
    "body": "Se você ler isso, o push funcionou!",
    "icon": "/book/static/images/hero.png"
}

print("Iniciando envio...")
try:
    response = webpush(
        subscription_info=sub_info,
        data=json.dumps(payload),
        vapid_private_key=private_key_path,
        vapid_claims={
            "sub": f"mailto:{admin_email}"
        }
    )
    print(f"Sucesso! Status: {response.status_code}")
    print(f"Resposta: {response.text}")
except WebPushException as ex:
    print(f"Erro WebPush: {ex}")
    if ex.response:
        print(f"Status: {ex.response.status_code}")
        print(f"Corpo: {ex.response.text}")
except Exception as e:
    print(f"Erro inesperado: {e}")
