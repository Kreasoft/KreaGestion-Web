import os
import sys
import django

sys.path.append(r'c:\PROJECTOS-WEB\GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico as DTE

def main(folio):
    dte = DTE.objects.filter(folio=folio).order_by('-id').first()
    if not dte:
        print("NOT_FOUND")
        return
    print(f"ID={dte.id} TIP0={dte.tipo_dte} ESTADO={dte.estado_sii}")

if __name__ == "__main__":
    folio = int(sys.argv[1]) if len(sys.argv) > 1 else 78
    main(folio)
