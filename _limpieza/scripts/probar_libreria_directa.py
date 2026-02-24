"""
Probar envío usando directamente la librería dte_gdexpress
"""
import os
import django
import sys

sys.path.append(r'c:\PROJECTOS-WEB\GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from empresas.models import Empresa
from libreria_dte_gdexpress.dte_gdexpress.gdexpress.cliente import ClienteGDExpress

# Obtener DTE y empresa
# Tomar último DTE pendiente o con error, priorizando guías 52
try:
    dte = DocumentoTributarioElectronico.objects.filter(estado_sii__in=['generado','error_envio']).order_by('-id').first()
except Exception:
    dte = DocumentoTributarioElectronico.objects.order_by('-id').first()
empresa = Empresa.objects.first()

print("=" * 80)
print("PRUEBA CON LIBRERÍA DTE_GDEXPRESS DIRECTA")
print("=" * 80)

# Crear cliente
cliente = ClienteGDExpress(
    api_key=empresa.dtebox_auth_key,
    ambiente='CERTIFICACION',
    url_servicio=empresa.dtebox_url
)

print(f"\nDTE: Tipo {dte.tipo_dte}, Folio {dte.folio}")
print(f"XML length: {len(dte.xml_firmado)} caracteres")
print(f"Empresa: {empresa.nombre}")
print(f"URL: {empresa.dtebox_url}")
print(f"Ambiente: {empresa.dtebox_ambiente}")

# Enviar
print("\nEnviando...")
resultado = cliente.enviar_dte(
    xml_firmado=dte.xml_firmado,
    resolucion_numero=empresa.resolucion_numero,
    resolucion_fecha=empresa.resolucion_fecha.strftime('%Y-%m-%d')
)

print("\n" + "=" * 80)
print("RESULTADO:")
print("=" * 80)
print(f"Success: {resultado.get('success')}")
if resultado.get('success'):
    print(f"✅ ÉXITO!")
    print(f"Track ID: {resultado.get('track_id')}")
    print(f"Estado: {resultado.get('estado')}")
    print(f"Glosa: {resultado.get('glosa')}")
else:
    print(f"❌ ERROR:")
    print(f"Error: {resultado.get('error')}")
    print(f"Detalle: {resultado.get('detalle', '')}")

print("=" * 80)
