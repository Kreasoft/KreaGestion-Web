import os
import sys
import django

# Configurar Django
sys.path.insert(0, r'c:\PROJECTOS-WEB\GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico

# Obtener últimas 5 guías
guias = DocumentoTributarioElectronico.objects.filter(tipo_dte='52').order_by('-id')[:10]

print(f"Total guías encontradas: {guias.count()}\n")

for g in guias:
    print(f"Folio: {g.folio}")
    print(f"  Estado SII: {g.estado_sii}")
    print(f"  Track ID: {g.track_id or 'Sin track ID'}")
    print(f"  Fecha emisión: {g.fecha_emision}")
    print("-" * 50)
