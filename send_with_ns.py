
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

def send_file_with_ns():
    xml_path = r"C:\Users\Usuario\Downloads\nuevo40.xml"
    empresa = Empresa.objects.get(id=1)
    
    with open(xml_path, 'rb') as f:
        xml_bytes = f.read()
    
    xml_str = xml_bytes.decode('ISO-8859-1')
    
    # Inyectar namespace
    if 'xmlns="http://www.sii.cl/SiiDte"' not in xml_str:
        xml_str = xml_str.replace('<DTE version="1.0">', '<DTE version="1.0" xmlns="http://www.sii.cl/SiiDte">')
    
    # Minificar (DTEBox lo prefiere)
    xml_str = re.sub(r'>\s+<', '><', xml_str.strip())
    
    xml_b64 = base64.b64encode(xml_str.encode('ISO-8859-1')).decode('ascii')
    
    payload = {
        "Environment": "T",
        "Content": xml_b64,
        "ResolutionNumber": 80,
        "ResolutionDate": "2014-08-22",
        "PDF417Columns": 0,
        "PDF417Level": 0,
        "PDF417Type": 0,
        "TED": ""
    }
    
    # Probamos con SendBoletaDocument para ver el error de esquema
    url = "http://200.6.118.43/api/Core.svc/core/SendBoletaDocument"
    headers = {
        'AuthKey': empresa.dtebox_auth_key,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    print(f"Enviando con NS a SendBoletaDocument...")
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"STATUS: {response.status}")
            data = json.loads(response.read().decode('utf-8'))
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"ERROR: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))

if __name__ == "__main__":
    send_file_with_ns()
