import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from libreria_dte_gdexpress.dte_gdexpress.gdexpress.cliente import ClienteGDExpress

# Obtener empresa activa
empresa = Empresa.objects.filter(activa=True).first()
if not empresa:
    print("❌ No hay empresa activa")
    exit(1)

print(f"✓ Empresa: {empresa.nombre}")
print(f"✓ RUT: {empresa.rut}")
print(f"✓ DTEBox URL: {empresa.dtebox_url}")
print(f"✓ Ambiente: {empresa.dtebox_ambiente}")
print()

# Crear cliente DTEBox
cliente = ClienteGDExpress(
    api_key=empresa.dtebox_auth_key,
    ambiente=empresa.dtebox_ambiente or 'CERTIFICACION',
    url_servicio=empresa.dtebox_url
)

# Buscar documentos de los últimos 90 días
print("Buscando documentos recibidos (últimos 90 días)...")
try:
    documentos = cliente.obtener_documentos_recibidos(
        rut_receptor=empresa.rut,
        dias=90
    )
    
    print(f"\n✓ Documentos encontrados: {len(documentos)}")
    
    if documentos:
        print("\nPrimeros 5 documentos:")
        for i, doc in enumerate(documentos[:5], 1):
            print(f"{i}. Tipo: {doc.get('TipoDTE', 'N/A')}, Folio: {doc.get('Folio', 'N/A')}, Fecha: {doc.get('FchEmis', 'N/A')}, Emisor: {doc.get('RznSoc', 'N/A')}")
    else:
        print("\n⚠ No se encontraron documentos en los últimos 90 días")
        print("Verifica en tu aplicación VB6 si hay documentos recibidos en ese período")
        
except Exception as e:
    print(f"\n❌ Error al consultar DTEBox: {e}")
    import traceback
    traceback.print_exc()
