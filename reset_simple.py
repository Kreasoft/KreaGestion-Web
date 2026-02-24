import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
import django
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico

for folio in [260, 261]:
    dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=folio).first()
    if dte:
        dte.estado_sii = 'generado'
        dte.error_envio = ''
        dte.track_id = ''
        dte.save()
        print(f"Folio {folio} reseteado a 'generado'")
    else:
        print(f"Folio {folio} no encontrado")

print("\nAhora puedes reenviar desde el sistema web")
