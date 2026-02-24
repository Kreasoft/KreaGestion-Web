
import os
import sys
import django
import re
import base64
import json
import urllib.request
from decimal import Decimal

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa

def send_fixed_user_xml():
    empresa = Empresa.objects.get(id=1)
    
    # Tomamos el contenido de nuevo40.xml pero lo "corregimos" para que el validador lo acepte
    # 1. IdDoc al principio
    # 2. Quitar FechaResol/NroResol del XML
    # 3. Quitar Transporte (No es valido en DTE 39)
    # 4. Corregir nombres de campos (RznSocEmisor, GiroEmisor)
    # 5. Agregar xmlns
    
    xml = f"""<DTE version="1.0" xmlns="http://www.sii.cl/SiiDte">
<Documento ID="F99282T39">
<Encabezado>
<IdDoc>
<TipoDTE>39</TipoDTE>
<Folio>99282</Folio>
<FchEmis>2026-02-21</FchEmis>
<IndServicio>3</IndServicio>
</IdDoc>
<Emisor>
<RUTEmisor>77117239-3</RUTEmisor>
<RznSocEmisor>Sociedad Informatica Kreasoft SpA</RznSocEmisor>
<GiroEmisor>Desarrollo de Software</GiroEmisor>
<DirOrigen>Victor Plaza Mayorga 887</DirOrigen>
<CmnaOrigen>El Bosque</CmnaOrigen>
<CiudadOrigen>Santiago</CiudadOrigen>
</Emisor>
<Receptor>
<RUTRecep>66666666-6</RUTRecep>
<RznSocRecep>Particular</RznSocRecep>
</Receptor>
<Totales>
<MntNeto>12345</MntNeto>
<IVA>2345</IVA>
<MntTotal>14690</MntTotal>
</Totales>
</Encabezado>
<Detalle>
<NroLinDet>1</NroLinDet>
<NmbItem>Nombre del detalle</NmbItem>
<QtyItem>10</QtyItem>
<PrcItem>1469</PrcItem>
<MontoItem>14690</MontoItem>
</Detalle>
</Documento>
</DTE>"""

    xml = re.sub(r'>\s+<', '><', xml.strip())
    xml_b64 = base64.b64encode(xml.encode('ISO-8859-1')).decode('ascii')
    
    payload = {
        "Environment": "T",
        "Content": xml_b64,
        "ResolutionNumber": 80,
        "ResolutionDate": "2014-08-22",
        "PDF417Columns": 0, "PDF417Level": 0, "PDF417Type": 0, "TED": ""
    }
    
    url = "http://200.6.118.43/api/Core.svc/core/SendBoletaDocument"
    headers = {'AuthKey': empresa.dtebox_auth_key, 'Content-Type': 'application/json', 'Accept': 'application/json'}
    
    print("Enviando version CORREGIDA del XML del usuario...")
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"ERROR: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))

if __name__ == "__main__":
    send_fixed_user_xml()
