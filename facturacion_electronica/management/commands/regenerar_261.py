from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_service import DTEService
from empresas.models import Empresa

class Command(BaseCommand):
    help = 'Regenerar XML folio 261'

    def handle(self, *args, **options):
        empresa = Empresa.objects.filter(activa=True).first()
        dte = DocumentoTributarioElectronico.objects.get(tipo_dte='39', folio=261, empresa=empresa)
        
        self.stdout.write(f"Regenerando folio 261 (DTE {dte.id})...")
        
        service = DTEService(empresa)
        service.procesar_dte_existente(dte)
        
        dte.refresh_from_db()
        xml = dte.xml_firmado[:3000]
        
        if 'RznSocEmisor' in xml and 'TasaIVA' not in xml:
            self.stdout.write(self.style.SUCCESS("✅ XML correcto - RznSocEmisor presente, sin TasaIVA"))
        else:
            self.stdout.write(self.style.ERROR("❌ XML aún tiene errores de esquema"))
