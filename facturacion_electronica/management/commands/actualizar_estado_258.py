from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from django.utils import timezone

class Command(BaseCommand):
    help = 'Actualiza estado de boleta 258 con datos reales de GDExpress'

    def handle(self, *args, **options):
        dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=258).first()
        
        if not dte:
            self.stdout.write(self.style.ERROR('No se encontro boleta 258'))
            return
        
        self.stdout.write('Actualizando boleta 258 con datos de GDExpress...')
        
        # Datos reales del historial
        dte.estado_sii = 'Aceptado'
        dte.track_id = '27301631'
        dte.fecha_envio_sii = timezone.now()
        dte.glosa_sii = 'Documento autorizado por el SII'
        dte.respuesta_sii = 'TrackID 27301631 - Dte Aceptado'
        dte.save()
        
        self.stdout.write(self.style.SUCCESS('✅ Boleta 258 actualizada correctamente'))
        self.stdout.write(f'   Estado: {dte.estado_sii}')
        self.stdout.write(f'   Track ID: {dte.track_id}')
        self.stdout.write(f'   Folio: {dte.folio}')
        self.stdout.write('')
        self.stdout.write('La boleta ya está aprobada por el SII.')
        self.stdout.write('No es necesario volver a enviarla.')
