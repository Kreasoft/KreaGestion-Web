from django.core.management.base import BaseCommand
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.models import DocumentoTributarioElectronico

class Command(BaseCommand):
    help = 'Regenera XML de boleta 258 con formato correcto'

    def handle(self, *args, **options):
        dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=258).first()
        
        if not dte:
            self.stdout.write(self.style.ERROR('No se encontro boleta 258'))
            return
        
        self.stdout.write(f'Regenerando XML para boleta folio {dte.folio}...')
        
        try:
            # DTEXMLGenerator(empresa, documento, tipo_dte, folio, caf)
            generator = DTEXMLGenerator(dte.empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
            xml_nuevo = generator.generar_xml_desde_dte()
            
            # Mostrar primeros 800 caracteres
            self.stdout.write('XML generado (primeros 800 chars):')
            self.stdout.write(xml_nuevo[:800])
            
            # Guardar
            dte.xml_firmado = xml_nuevo
            dte.save()
            
            self.stdout.write(self.style.SUCCESS('\nXML regenerado y guardado exitosamente'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
