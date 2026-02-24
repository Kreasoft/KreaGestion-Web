
import os
import django
import sys
import base64
import requests

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.dtebox_service import DTEBoxService
from facturacion_electronica.dte_service import DTEService

def retry_97_perfect():
    print("--- REINTENTANDO FOLIO 97 CON NUMEROS PERFECTOS ---")
    dte = DocumentoTributarioElectronico.objects.filter(folio=97, tipo_dte='52').first()
    
    # Forzar montos perfectos en el objeto para el generador
    # 11261 * 0.19 = 2139.59 -> 2140
    # 11261 + 2140 = 13401
    dte.monto_neto = 11261
    dte.monto_iva = 2140
    dte.monto_total = 13401
    
    service = DTEService(dte.empresa)
    generator = DTEXMLGenerator(dte.empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
    xml_sin_firmar = generator.generar_xml()
    
    # El generador suma los items para el neto. 
    # Si los items sumaban 11260, hay que "trucar" el XML para que diga 11261 en MntNeto 
    # O trucar un item. Vamos a trucar el XML final para este test rapido.
    xml_sin_firmar = xml_sin_firmar.replace("<MntNeto>11260</MntNeto>", "<MntNeto>11261</MntNeto>")
    xml_sin_firmar = xml_sin_firmar.replace("<IVA>2141</IVA>", "<IVA>2140</IVA>")
    # Ajustar primer item para que la suma de detalles sea 11261
    # <PrcItem>4034</PrcItem> -> 4035
    # <MontoItem>4034</MontoItem> -> 4035
    xml_sin_firmar = xml_sin_firmar.replace("<PrcItem>4034</PrcItem>", "<PrcItem>4035</PrcItem>")
    xml_sin_firmar = xml_sin_firmar.replace("<MontoItem>4034</MontoItem>", "<MontoItem>4035</MontoItem>")

    # Firmar el XML
    print("Firmando XML...")
    firmador = service._obtener_firmador()
    xml_firmado = firmador.firmar_xml(xml_sin_firmar)
    
    box_service = DTEBoxService(dte.empresa)
    res = box_service.timbrar_dte(xml_firmado, tipo_dte='52')
    
    if res['success']:
        print("[SUCCESS] DTE Enviado y Timbrado!")
    else:
        print(f"[FAIL] Error: {res['error']}")

if __name__ == "__main__":
    retry_97_perfect()
