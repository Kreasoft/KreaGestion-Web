"""
Script para probar envío directo con el XML de ejemplo que funciona
"""
import base64
import xml.etree.ElementTree as ET
import urllib.request
from empresas.models import Empresa

# Obtener configuración de empresa
empresa = Empresa.objects.first()

print("=" * 80)
print("PRUEBA DE ENVÍO CON XML DE EJEMPLO")
print("=" * 80)

# Leer XML de ejemplo que funciona
with open(r'facturacion_electronica\XML_PARA_ENVIAR_Corregido (1).xml', 'rb') as f:
    xml_ejemplo = f.read()

print(f"\n1. XML de ejemplo cargado: {len(xml_ejemplo)} bytes")

# Codificar en base64
xml_b64 = base64.b64encode(xml_ejemplo).decode('ascii')
print(f"2. XML codificado en base64: {len(xml_b64)} caracteres")

# Construir request (EXACTAMENTE como libreria_dte_gdexpress)
req_root = ET.Element("SendDocumentAsXMLRequest")
req_root.set("xmlns", "http://gdexpress.cl/api")

ET.SubElement(req_root, "Environment").text = empresa.dtebox_ambiente or 'T'
ET.SubElement(req_root, "Content").text = xml_b64
ET.SubElement(req_root, "ResolutionNumber").text = str(int(empresa.resolucion_numero))
ET.SubElement(req_root, "ResolutionDate").text = empresa.resolucion_fecha.strftime('%Y-%m-%d')
ET.SubElement(req_root, "PDF417Columns").text = "5"
ET.SubElement(req_root, "PDF417Level").text = "2"
ET.SubElement(req_root, "PDF417Type").text = "1"
ET.SubElement(req_root, "TED").text = ""

# Serializar
xml_request = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(req_root, encoding='utf-8', method='xml')

print(f"3. Request construido: {len(xml_request)} bytes")
print(f"\n4. Request (primeros 500 chars):")
print(xml_request[:500].decode('utf-8'))

# Enviar
url = f"{empresa.dtebox_url}/api/Core.svc/core/SendDocumentAsXML"
headers = {
    'AuthKey': empresa.dtebox_auth_key,
    'Content-Type': 'application/xml',
    'Accept': 'application/xml'
}

print(f"\n5. Enviando a: {url}")
print(f"   AuthKey: {empresa.dtebox_auth_key[:10]}...")

try:
    req = urllib.request.Request(url, data=xml_request, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=60) as response:
        response_data = response.read().decode('utf-8')
        print(f"\n✅ ÉXITO - Status: {response.status}")
        print(f"\nRespuesta:")
        print(response_data[:500])
        
except urllib.error.HTTPError as e:
    error_msg = e.read().decode('utf-8') if e.fp else str(e)
    print(f"\n❌ ERROR HTTP {e.code}")
    print(f"Respuesta de error:")
    print(error_msg[:500])
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")

print("\n" + "=" * 80)
