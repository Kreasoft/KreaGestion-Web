from django.core.management.base import BaseCommand
from tesoreria.models import MovimientoCuentaCorrienteCliente
from decimal import Decimal

class Command(BaseCommand):
    help = 'Corrige los montos de movimientos de cuenta corriente que están divididos por 1000'

    def handle(self, *args, **options):
        self.stdout.write('Buscando movimientos con montos incorrectos...\n')
        
        movimientos = MovimientoCuentaCorrienteCliente.objects.filter(
            tipo_movimiento='debe',
            venta__isnull=False
        ).select_related('venta')
        
        corregidos = 0
        
        for mov in movimientos:
            # Si el monto del movimiento es diferente al total de la venta
            if mov.monto != mov.venta.total:
                self.stdout.write(f'\nMovimiento ID {mov.pk}:')
                self.stdout.write(f'  Venta: {mov.venta.numero_venta}')
                self.stdout.write(f'  Monto actual: {mov.monto}')
                self.stdout.write(f'  Monto correcto (venta.total): {mov.venta.total}')
                
                # Corregir el monto
                diferencia = mov.venta.total - mov.monto
                mov.monto = mov.venta.total
                mov.saldo_nuevo = mov.saldo_anterior + mov.monto
                mov.save()
                
                # Actualizar la cuenta corriente
                cuenta = mov.cuenta_corriente
                cuenta.saldo_total += diferencia
                cuenta.saldo_pendiente += diferencia
                cuenta.save()
                
                self.stdout.write(self.style.SUCCESS(f'  ✓ Corregido'))
                corregidos += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Total corregidos: {corregidos}'))
