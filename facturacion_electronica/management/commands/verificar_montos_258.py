from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico

class Command(BaseCommand):
    help = 'Verifica montos del DTE 258'

    def handle(self, *args, **options):
        dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=258).first()
        
        if not dte:
            self.stdout.write(self.style.ERROR('No se encontro boleta 258'))
            return
        
        self.stdout.write(f'Boleta folio {dte.folio}:')
        self.stdout.write(f'  Monto Neto: {dte.monto_neto}')
        self.stdout.write(f'  Monto IVA: {dte.monto_iva}')
        self.stdout.write(f'  Monto Total: {dte.monto_total}')
        
        # Verificar si la suma es correcta
        suma = int(dte.monto_neto or 0) + int(dte.monto_iva or 0)
        total = int(dte.monto_total or 0)
        
        self.stdout.write(f'  Neto + IVA = {suma}')
        self.stdout.write(f'  Total declarado = {total}')
        
        if suma != total:
            self.stdout.write(self.style.WARNING(f'  ⚠️ DIFERENCIA: {total - suma}'))
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ Montos consistentes'))
        
        # Verificar items de la venta asociada
        venta = None
        if hasattr(dte, 'venta') and dte.venta:
            venta = dte.venta
        elif dte.orden_despacho.exists():
            venta = dte.orden_despacho.first()
        
        if venta:
            self.stdout.write(f'\nVenta asociada:')
            self.stdout.write(f'  Neto: {venta.neto}')
            self.stdout.write(f'  IVA: {venta.iva}')
            self.stdout.write(f'  Total: {venta.total}')
