import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
import django
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dtebox_service import DTEBoxService
from empresas.models import Empresa

empresa = Empresa.objects.filter(activa=True).first()
service = DTEBoxService(empresa)

print("ENVIANDO A GDEXPRESS")
print("="*50)

for folio in [260, 261]:
    print(f"\nFolio {folio}:")
    try:
        dte = DocumentoTributarioElectronico.objects.get(tipo_dte='39', folio=folio)
        
        if not dte.xml_firmado:
            print("  ERROR: Sin XML firmado")
            continue
            
        resultado = service.timbrar_dte(dte.xml_firmado, '39')
        
        if resultado.get('success'):
            dte.timbre_electronico = resultado.get('ted', '')
            dte.track_id = resultado.get('track_id', '')
            dte.estado_sii = 'enviado'
            dte.error_envio = ''
            dte.save()
            print(f"  ✅ ENVIADO - Track: {dte.track_id}")
        else:
            error = resultado.get('error', 'Desconocido')
            dte.error_envio = error
            dte.save()
            print(f"  ❌ ERROR: {error[:100]}")
            
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "="*50)
print("Proceso completado")
