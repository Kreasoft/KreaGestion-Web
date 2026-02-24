import os
import django
import sys

sys.path.append(r'c:\PROJECTOS-WEB\GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from empresas.models import Empresa
from facturacion_electronica.dte_service import DTEService

def enviar_guia_por_folio(folio):
    empresa = Empresa.objects.first()
    dte = DocumentoTributarioElectronico.objects.filter(empresa=empresa, tipo_dte='52', folio=folio).first()
    if not dte:
        print(f"✗ No se encontró guía folio {folio}")
        return
    print("=" * 80)
    print(f"ENVIANDO GUÍA FOLIO {folio} (DTE ID: {dte.id})")
    print("=" * 80)
    service = DTEService(empresa)
    try:
        resultado = service.enviar_dte_al_sii(dte)
        print("\nRESULTADO:")
        print(f"  success: {resultado.get('success')}")
        print(f"  track_id: {resultado.get('track_id')}")
        print(f"  error: {resultado.get('error')}")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    folio = int(sys.argv[1]) if len(sys.argv) > 1 else 98
    enviar_guia_por_folio(folio)
