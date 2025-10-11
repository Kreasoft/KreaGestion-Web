from django.core.management.base import BaseCommand
from ventas.models import Venta

class Command(BaseCommand):
    help = 'Ver el último ticket generado'

    def handle(self, *args, **options):
        # Buscar el último ticket
        ultimo_ticket = Venta.objects.filter(tipo_documento='vale').order_by('-fecha_creacion').first()
        
        if ultimo_ticket:
            self.stdout.write(f"\n=== ÚLTIMO TICKET GENERADO ===")
            self.stdout.write(f"Número: {ultimo_ticket.numero_venta}")
            self.stdout.write(f"Fecha: {ultimo_ticket.fecha_creacion}")
            self.stdout.write(f"Cliente: {ultimo_ticket.cliente.nombre if ultimo_ticket.cliente else 'N/A'}")
            self.stdout.write(f"\n--- VALORES ---")
            self.stdout.write(f"Subtotal: ${ultimo_ticket.subtotal}")
            self.stdout.write(f"Neto: ${ultimo_ticket.neto}")
            self.stdout.write(f"IVA: ${ultimo_ticket.iva}")
            self.stdout.write(f"Impuesto Específico: ${ultimo_ticket.impuesto_especifico}")
            self.stdout.write(f"Total: ${ultimo_ticket.total}")
            
            # Mostrar detalles
            self.stdout.write(f"\n--- DETALLES ---")
            for detalle in ultimo_ticket.ventadetalle_set.all():
                self.stdout.write(f"- {detalle.articulo.nombre}: {detalle.cantidad} x ${detalle.precio_unitario} = ${detalle.precio_total}")
        else:
            self.stdout.write(self.style.ERROR('No se encontraron tickets'))
