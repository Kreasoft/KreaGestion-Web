from django.core.management.base import BaseCommand
from facturacion_electronica.dtebox_service import DTEBoxService
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.models import DocumentoTributarioElectronico
from core.models import Empresa

class Command(BaseCommand):
    help = 'Reenvia la boleta folio 258 con XML corregido'

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('REENVIO DE BOLETA FOLIO 258')
        self.stdout.write('=' * 80)

        dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=258).first()

        if not dte:
            self.stdout.write(self.style.ERROR('No se encontro la boleta folio 258'))
            boletas = DocumentoTributarioElectronico.objects.filter(tipo_dte='39').order_by('-folio')[:5]
            self.stdout.write('\nBoletas disponibles:')
            for b in boletas:
                self.stdout.write(f'  - Folio {b.folio}, Estado: {b.estado_sii}')
            return

        self.stdout.write(f'\nBoleta encontrada:')
        self.stdout.write(f'  Folio: {dte.folio}')
        self.stdout.write(f'  Estado SII: {dte.estado_sii}')
        self.stdout.write(f'  Empresa: {dte.empresa.nombre}')

        empresa = dte.empresa

        if not empresa.dtebox_habilitado:
            self.stdout.write(self.style.ERROR(f'DTEBox no esta habilitado para {empresa.nombre}'))
            return

        self.stdout.write(f'\nDTEBox configurado:')
        self.stdout.write(f'  URL: {empresa.dtebox_url}')
        self.stdout.write(f'  Ambiente: {empresa.dtebox_ambiente}')

        self.stdout.write(f'\nRegenerando XML con formato correcto...')

        try:
            generator = DTEXMLGenerator(dte, empresa)
            xml_nuevo = generator.generar_xml_desde_dte()

            self.stdout.write(f'XML regenerado exitosamente')
            self.stdout.write(f'Longitud: {len(xml_nuevo)} caracteres')
            self.stdout.write(f'\nPrimeros 800 caracteres:')
            self.stdout.write('-' * 80)
            self.stdout.write(xml_nuevo[:800])
            self.stdout.write('-' * 80)

            dte.xml_firmado = xml_nuevo
            dte.save()
            self.stdout.write(self.style.SUCCESS('XML guardado en el DTE'))

            self.stdout.write(f'\nEnviando a DTEBox...')

            service = DTEBoxService(empresa)
            resultado = service.timbrar_dte(dte.xml_firmado, '39')

            self.stdout.write(f'\nResultado del envio:')
            self.stdout.write(f'  Success: {resultado.get(\"success\")}')
            self.stdout.write(f'  Estado: {resultado.get(\"estado\")}')
            self.stdout.write(f'  Error: {resultado.get(\"error\")}')
            self.stdout.write(f'  Track ID: {resultado.get(\"track_id\")}')

            if resultado.get('success'):
                self.stdout.write(self.style.SUCCESS('\nBOLETA FOLIO 258 ENVIADA EXITOSAMENTE!'))
                dte.estado_sii = 'enviado'
                dte.track_id = resultado.get('track_id')
                if resultado.get('ted'):
                    dte.timbre_electronico = resultado.get('ted')
                dte.save()
                self.stdout.write(self.style.SUCCESS('DTE actualizado en la base de datos'))
            else:
                self.stdout.write(self.style.ERROR(f'\nERROR EN ENVIO: {resultado.get(\"error\")}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nEXCEPCION: {type(e).__name__}: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
