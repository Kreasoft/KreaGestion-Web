from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dtebox_service import DTEBoxService
from empresas.models import Empresa

class Command(BaseCommand):
    help = 'Enviar folios 260 y 261 a GDExpress'

    def handle(self, *args, **options):
        empresa = Empresa.objects.filter(activa=True).first()
        if not empresa:
            self.stdout.write(self.style.ERROR('No hay empresa activa'))
            return

        service = DTEBoxService(empresa)

        for folio in [260, 261]:
            self.stdout.write(f'\nFolio {folio}:')
            try:
                dte = DocumentoTributarioElectronico.objects.get(
                    tipo_dte='39', folio=folio, empresa=empresa
                )

                if not dte.xml_firmado:
                    self.stdout.write(self.style.ERROR('  Sin XML firmado'))
                    continue

                resultado = service.timbrar_dte(dte.xml_firmado, '39')

                if resultado.get('success'):
                    dte.timbre_electronico = resultado.get('ted', '')
                    dte.track_id = resultado.get('track_id', '')
                    dte.estado_sii = 'enviado'
                    dte.error_envio = ''
                    dte.save()
                    self.stdout.write(self.style.SUCCESS(f'  ENVIADO - Track: {dte.track_id}'))
                else:
                    error = resultado.get('error', 'Desconocido')
                    dte.error_envio = error
                    dte.save()
                    self.stdout.write(self.style.ERROR(f'  ERROR: {error[:100]}'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))
