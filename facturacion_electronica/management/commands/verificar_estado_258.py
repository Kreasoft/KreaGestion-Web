from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico

class Command(BaseCommand):
    help = 'Verifica estado del DTE 258'

    def handle(self, *args, **options):
        dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=258).first()
        
        if not dte:
            self.stdout.write(self.style.ERROR('No se encontro boleta 258'))
            return
        
        self.stdout.write(f'Boleta folio {dte.folio}:')
        self.stdout.write(f'  Estado SII: {dte.estado_sii}')
        self.stdout.write(f'  Track ID: {dte.track_id or "(sin track id)"}')
        self.stdout.write(f'  Tiene timbre: {"SI" if dte.timbre_electronico else "NO"}')
        self.stdout.write(f'  Fecha envio: {dte.fecha_envio_sii or "(no enviada)"}')
        
        if dte.track_id or dte.timbre_electronico:
            self.stdout.write(self.style.SUCCESS('\n✅ La boleta YA ESTA ENVIADA a GDExpress'))
            self.stdout.write('   No es necesario reenviarla.')
        else:
            self.stdout.write(self.style.WARNING('\n⚠️ La boleta NO tiene timbre registrado'))
            self.stdout.write('   Puede intentar enviarla nuevamente.')
