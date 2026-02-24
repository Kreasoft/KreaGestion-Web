
import os
import sys
import django
import base64
import json
import urllib.request
import re

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa

def send_v3():
    xml_path = r"C:\Users\Usuario\Downloads\nuevo40.xml"
    empresa = Empresa.objects.get(id=1)
    
    with open(xml_path, 'rb') as f:
        xml_bytes = f.read()
    
    xml_b64 = base64.b64encode(xml_bytes).decode('ascii')
    
    # 2. Probamos el endpoint con el flag de Boleta (/1/)
    # http://200.6.118.43/api/Core.svc/core/SendDocumentAsXML/{env}/{isBoleta}/{xmlB64}
    
    # IMPORTANTE: El XML B64 debe estar URL-Encoded si va en la URL
    from urllib.parse import quote
    xml_b64_quoted = quote(xml_b64)
    
    url = f"http://200.6.118.43/api/Core.svc/core/SendDocumentAsXML/T/1/{xml_b64_quoted}"
    
    headers = {
        'AuthKey': empresa.dtebox_auth_key,
        'Accept': 'application/json'
    }
    
    print(f"Enviando via GET-style (Boleta flag 1) a: {url[:100]}...")
    try:
        req = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"STATUS: {response.status}")
            data = json.loads(response.read().decode('utf-8'))
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"ERROR: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))

if __name__ == "__main__":
    send_v3()
