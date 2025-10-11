from django.core.management.base import BaseCommand
from ventas.models import Venta
from decimal import Decimal

class Command(BaseCommand):
    help = 'Corregir valores del ticket #000092'

    def handle(self, *args, **options):
        try:
            # Buscar el ticket
            ticket = Venta.objects.get(numero_venta='000092', tipo_documento='vale')
            
            self.stdout.write(f"\n=== TICKET #000092 - VALORES ACTUALES ===")
            self.stdout.write(f"Subtotal: {ticket.subtotal}")
            self.stdout.write(f"Neto: {ticket.neto}")
            self.stdout.write(f"IVA: {ticket.iva}")
            self.stdout.write(f"Impuesto Específico: {ticket.impuesto_especifico}")
            self.stdout.write(f"Total: {ticket.total}")
            
            # Corregir valores
            # Para Coca Cola 350ml: Precio final $1.644
            # Neto: $1.200, IVA: $228, Imp. Esp: $216
            ticket.subtotal = Decimal('1644.00')
            ticket.neto = Decimal('1200.00')
            ticket.iva = Decimal('228.00')
            ticket.impuesto_especifico = Decimal('216.00')
            ticket.total = Decimal('1644.00')
            ticket.save()
            
            self.stdout.write(f"\n=== TICKET #000092 - VALORES CORREGIDOS ===")
            self.stdout.write(f"Subtotal: {ticket.subtotal}")
            self.stdout.write(f"Neto: {ticket.neto}")
            self.stdout.write(f"IVA: {ticket.iva}")
            self.stdout.write(f"Impuesto Específico: {ticket.impuesto_especifico}")
            self.stdout.write(f"Total: {ticket.total}")
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Ticket #000092 corregido exitosamente'))
            
        except Venta.DoesNotExist:
            self.stdout.write(self.style.ERROR('✗ Ticket #000092 no encontrado'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))
