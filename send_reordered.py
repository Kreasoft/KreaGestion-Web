
import os
import sys
import django
import base64
import json
import urllib.request
import re
import xml.etree.ElementTree as ET

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa

def send_reordered():
    xml_path = r"C:\Users\Usuario\Downloads\nuevo40.xml"
    empresa = Empresa.objects.get(id=1)
    
    # Parseamos para reordenar
    tree = ET.parse(xml_path)
    root = tree.getroot()
    doc = root.find('Documento')
    enc = doc.find('Encabezado')
    
    # Reordenar Encabezado: IdDoc, Emisor, Receptor, Totales
    # Y movemos FechaResol/NroResol a IdDoc si queremos probar, 
    # o los dejamos al final de Encabezado.
    
    iddoc = enc.find('IdDoc')
    emisor = enc.find('Emisor')
    receptor = enc.find('Receptor')
    totales = enc.find('Totales')
    
    # Nuevo encabezado
    new_enc = ET.Element('Encabezado')
    if iddoc is not None: new_enc.append(iddoc)
    if emisor is not None: new_enc.append(emisor)
    if receptor is not None: new_enc.append(receptor)
    if totales is not None: new_enc.append(totales)
    
    # Reemplazar
    doc.remove(enc)
    doc.insert(0, new_enc)
    
    # Agregar NS
    root.set('xmlns', 'http://www.sii.cl/SiiDte')
    
    xml_str = ET.tostring(root, encoding='ISO-8859-1').decode('ISO-8859-1')
    xml_str = re.sub(r'>\s+<', '><', xml_str.strip())
    
    xml_b64 = base64.b64encode(xml_str.encode('ISO-8859-1')).decode('ascii')
    
    payload = {
        "Environment": "T",
        "Content": xml_b64,
        "ResolutionNumber": 80,
        "ResolutionDate": "2014-08-22",
        "PDF417Columns": 0, "PDF417Level": 0, "PDF417Type": 0, "TED": ""
    }
    
    url = "http://200.6.118.43/api/Core.svc/core/SendBoletaDocument"
    print("Enviando version REORDENADA a SendBoletaDocument...")
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'AuthKey': empresa.dtebox_auth_key, 'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=30) as response:
            print(json.dumps(json.loads(response.read().decode('utf-8')), indent=2))
    except Exception as e:
        if hasattr(e, 'read'): print(e.read().decode('utf-8'))
        else: print(f"ERROR: {e}")

if __name__ == "__main__":
    send_reordered()
