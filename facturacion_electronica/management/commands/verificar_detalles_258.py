from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico

class Command(BaseCommand):
    help = 'Verifica detalles del DTE 258'

    def handle(self, *args, **options):
        dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=258).first()
        
        if not dte:
            self.stdout.write(self.style.ERROR('No se encontro boleta 258'))
            return
        
        # Obtener venta asociada
        venta = None
        if hasattr(dte, 'venta') and dte.venta:
            venta = dte.venta
        elif dte.orden_despacho.exists():
            venta = dte.orden_despacho.first()
        
        if not venta:
            self.stdout.write(self.style.ERROR('No se encontro venta asociada'))
            return
        
        self.stdout.write(f'Boleta folio {dte.folio} - Detalles de venta:')
        self.stdout.write(f'Total DTE: {dte.monto_total}')
        
        total_items = 0
        for item in venta.ventadetalle_set.all():
            subtotal = float(item.cantidad) * float(item.precio_unitario)
            total_items += subtotal
            self.stdout.write(f'  - {item.articulo.nombre}: {item.cantidad} x ${item.precio_unitario} = ${subtotal}')
        
        self.stdout.write(f'\nTotal items: ${total_items}')
        self.stdout.write(f'Total DTE: ${dte.monto_total}')
        
        if abs(total_items - float(dte.monto_total)) > 1:
            self.stdout.write(self.style.WARNING(f'⚠️ DIFERENCIA: ${total_items - float(dte.monto_total)}'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Totales coinciden'))
