import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
import django
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico

# Resetear folios 260 y 261 para permitir nuevo intento de envío
dtes = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio__in=[260, 261])

for dte in dtes:
    dte.estado_sii = 'generado'
    dte.error_envio = ''
    dte.track_id = ''
    dte.save()
    print(f"Folio {dte.folio} reseteado")

print("\nFolios 260 y 261 listos para reenvío.")
print("Ahora puedes procesar las ventas nuevamente desde el sistema.")
