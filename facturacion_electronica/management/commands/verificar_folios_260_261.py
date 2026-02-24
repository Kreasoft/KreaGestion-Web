from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from empresas.models import Empresa

class Command(BaseCommand):
    help = 'Verifica estado de folios 260 y 261'

    def handle(self, *args, **options):
        empresa = Empresa.objects.filter(activa=True).first()
        if not empresa:
            self.stdout.write(self.style.ERROR("No hay empresa activa"))
            return

        self.stdout.write("=" * 60)
        self.stdout.write("DIAGNÓSTICO FOLIOS 260 y 261 - BD LOCAL")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Empresa: {empresa.nombre}")
        self.stdout.write(f"RUT: {empresa.rut}")
        self.stdout.write(f"DTEBox URL: {empresa.dtebox_url or 'No configurada'}")
        self.stdout.write(f"Ambiente: {empresa.dtebox_ambiente or 'No configurado'}")
        self.stdout.write("")

        folios = ['260', '261']
        for folio in folios:
            self.stdout.write(f"--- FOLIO {folio} ---")
            
            dtes = DocumentoTributarioElectronico.objects.filter(
                tipo_dte='39',
                folio=folio,
                empresa=empresa
            ).order_by('-fecha_creacion')
            
            if dtes.exists():
                dte = dtes.first()
                self.stdout.write(f"✓ Encontrado en BD local:")
                self.stdout.write(f"  - ID: {dte.id}")
                self.stdout.write(f"  - Estado: {dte.estado}")
                self.stdout.write(f"  - Track ID: {dte.track_id or 'N/A'}")
                self.stdout.write(f"  - Fecha: {dte.fecha_creacion}")
                self.stdout.write(f"  - Venta ID: {dte.venta_id or 'N/A'}")
                
                if dte.error_envio:
                    self.stdout.write(self.style.ERROR(f"  - Error: {dte.error_envio[:100]}"))
            else:
                self.stdout.write(self.style.WARNING(f"✗ No existe DTE con folio {folio}"))
            
            self.stdout.write("")

        self.stdout.write("=" * 60)
        self.stdout.write("PARA VERIFICAR EN GDEXPRESS:")
        self.stdout.write("1. Accede a http://200.6.118.43")
        self.stdout.write("2. Busca en Documentos Emitidos los folios 260 y 261")
        self.stdout.write("3. Si NO están en GDExpress, el DTE local tiene estado incorrecto")
        self.stdout.write("=" * 60)
