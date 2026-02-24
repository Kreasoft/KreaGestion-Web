import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
import django
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dtebox_service import DTEBoxService
from empresas.models import Empresa

print("ENVIANDO FOLIO 261 A GDEXPRESS")
print("="*60)

empresa = Empresa.objects.filter(activa=True).first()
dte = DocumentoTributarioElectronico.objects.get(tipo_dte='39', folio=261, empresa=empresa)

print(f"DTE ID: {dte.id}")
print(f"Folio: {dte.folio}")
print(f"XML firmado: {len(dte.xml_firmado) if dte.xml_firmado else 0} chars")
print()

# Enviar a GDExpress
service = DTEBoxService(empresa)
resultado = service.timbrar_dte(dte.xml_firmado, '39')

print("RESULTADO:")
print("-"*60)

if resultado.get('success'):
    dte.timbre_electronico = resultado.get('ted', '')
    dte.track_id = resultado.get('track_id', 'DTEBOX-261')
    dte.estado_sii = 'enviado'
    dte.error_envio = ''
    dte.save()
    print(f"✅ ENVIADO EXITOSAMENTE")
    print(f"   Track ID: {dte.track_id}")
    print(f"   TED recibido: {'Sí' if dte.timbre_electronico else 'No'}")
else:
    error = resultado.get('error', 'Error desconocido')
    dte.error_envio = error
    dte.save()
    print(f"❌ ERROR: {error}")

print("="*60)
