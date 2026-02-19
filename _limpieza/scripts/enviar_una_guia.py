import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionCloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.background_sender import get_background_sender

# Obtener la última guía
guia = DocumentoTributarioElectronico.objects.filter(tipo_dte='52').order_by('-id').first()

if not guia:
    print("No hay guías para enviar")
else:
    print(f"Guía encontrada: Folio {guia.folio}")
    print(f"Estado actual: {guia.estado_sii}")
    
    # Intentar enviar
    sender = get_background_sender()
    empresa_id = guia.empresa.id
    
    print(f"Enviando guía {guia.folio} al SII...")
    resultado = sender.enviar_dte(guia.id, empresa_id)
    
    if resultado:
        print(f"✓ Guía enviada exitosamente")
    else:
        print(f"✗ Error al enviar guía")
    
    # Refrescar y mostrar estado
    guia.refresh_from_db()
    print(f"Estado final: {guia.estado_sii}")
    if guia.track_id:
        print(f"Track ID: {guia.track_id}")
