from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico

class Command(BaseCommand):
    help = 'Corrige montos del DTE 258'

    def handle(self, *args, **options):
        dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=258).first()
        
        if not dte:
            self.stdout.write(self.style.ERROR('No se encontro boleta 258'))
            return
        
        self.stdout.write(f'Boleta folio {dte.folio} - ANTES:')
        self.stdout.write(f'  Neto: {dte.monto_neto}')
        self.stdout.write(f'  IVA: {dte.monto_iva}')
        self.stdout.write(f'  Total: {dte.monto_total}')
        
        # Corregir con valores correctos de la venta
        venta = None
        if hasattr(dte, 'venta') and dte.venta:
            venta = dte.venta
        elif dte.orden_despacho.exists():
            venta = dte.orden_despacho.first()
        
        if venta:
            dte.monto_neto = int(venta.neto)
            dte.monto_iva = int(venta.iva)
            dte.monto_total = int(venta.total)
            dte.save()
            
            self.stdout.write(f'\nDESPUES:')
            self.stdout.write(f'  Neto: {dte.monto_neto}')
            self.stdout.write(f'  IVA: {dte.monto_iva}')
            self.stdout.write(f'  Total: {dte.monto_total}')
            self.stdout.write(self.style.SUCCESS('\nMontos corregidos exitosamente'))
            
            # Ahora regenerar XML
            self.stdout.write('\nRegenerando XML...')
            from facturacion_electronica.dte_generator import DTEXMLGenerator
            generator = DTEXMLGenerator(dte.empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
            xml_nuevo = generator.generar_xml_desde_dte()
            dte.xml_firmado = xml_nuevo
            dte.save()
            self.stdout.write(self.style.SUCCESS('XML regenerado'))
        else:
            self.stdout.write(self.style.ERROR('No se encontro venta asociada'))
