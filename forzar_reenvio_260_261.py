import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')

import django
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dtebox_service import DTEBoxService
from empresas.models import Empresa

print("FORZAR REENVÍO FOLIOS 260 Y 261")
print("=" * 50)

empresa = Empresa.objects.filter(activa=True).first()
if not empresa:
    print("❌ No hay empresa activa")
    exit(1)

folios = ['260', '261']

for folio in folios:
    print(f"\n--- FOLIO {folio} ---")
    
    try:
        dte = DocumentoTributarioElectronico.objects.get(
            tipo_dte='39',
            folio=folio,
            empresa=empresa
        )
        
        # Resetear estado para permitir reenvío
        dte.estado_sii = 'generado'
        dte.track_id = ''
        dte.error_envio = ''
        dte.fecha_envio_sii = None
        dte.save()
        
        print(f"✓ DTE {dte.id} reseteado a estado 'generado'")
        print(f"  - Track ID limpiado")
        print(f"  - Error envío limpiado")
        
        # Intentar enviar a GDExpress
        print(f"  - Intentando envío a GDExpress...")
        
        service = DTEBoxService(empresa)
        resultado = service.timbrar_dte(dte.xml_firmado, tipo_dte='39')
        
        if resultado.get('success'):
            dte.timbre_electronico = resultado.get('ted', '')
            dte.track_id = resultado.get('track_id', '')
            dte.estado_sii = 'enviado'
            dte.save()
            print(f"  ✅ ENVIADO EXITOSAMENTE")
            print(f"     Track ID: {dte.track_id}")
        else:
            error = resultado.get('error', 'Error desconocido')
            dte.error_envio = error
            dte.save()
            print(f"  ❌ ERROR: {error[:100]}")
            
            # Si es error de "ya enviado", mostrar advertencia especial
            if 'ya fue enviado' in error.lower():
                print(f"  ⚠️  GDExpress dice que ya existe pero no aparece en su sistema")
                print(f"     Solución: Contactar soporte de GDExpress directamente")
            
    except DocumentoTributarioElectronico.DoesNotExist:
        print(f"❌ No existe DTE con folio {folio}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 50)
print("PROCESO COMPLETADO")
print("=" * 50)
